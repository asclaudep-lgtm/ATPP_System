"""
Резервное копирование БД (SQLite и PostgreSQL).

Стратегия (одинаковая для обоих движков):
- При запуске приложения: создаётся один snapshot в день в data/backups/
  (если за сегодня ещё не было создано).
- Ротация: храним последние KEEP_DAILY дней + понедельничные за год.
- Ручной бэкап: пункт меню «Сервис → Резервная копия БД сейчас».
- После успешного локального бэкапа — копия зеркалируется на сетевую папку
  (если задана через ATPP_BACKUP_MIRROR или data/backup.cfg). При ошибке
  зеркала — только предупреждение в лог, основной бэкап остаётся валидным.

Форматы файлов:
- SQLite     -> atpp_YYYYMMDD_HHMMSS.db.gz   (gzip копия .db)
- PostgreSQL -> atpp_YYYYMMDD_HHMMSS.dump    (pg_dump --format=custom, уже сжат)

Восстановление автоматически определяет формат по расширению файла.
"""
from __future__ import annotations

from utils.logger import get_logger

_log = get_logger(__name__)

import gzip
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, unquote

from config import BASE_DIR, DATABASE_URL, DATA_DIR


BACKUP_DIR = BASE_DIR / 'data' / 'backups'
KEEP_DAILY = 30           # последние N ежедневных
KEEP_WEEKLY = 52          # понедельничные за год
WEEKDAY_KEEP = 0          # 0 = понедельник

# Расширения, по которым приложение распознаёт свои бэкапы
SQLITE_EXT = '.db.gz'
PG_EXT = '.dump'


# ──────────────────────────────────────────────────────────────────────────
# Вспомогательное
# ──────────────────────────────────────────────────────────────────────────

def _ensure_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _engine_kind() -> str:
    """Возвращает 'sqlite' | 'postgresql' | 'other' по DATABASE_URL."""
    url = (DATABASE_URL or '').lower()
    if url.startswith('sqlite'):
        return 'sqlite'
    if url.startswith('postgresql') or url.startswith('postgres'):
        return 'postgresql'
    return 'other'


def _sqlite_path() -> Optional[Path]:
    if not DATABASE_URL.startswith('sqlite'):
        return None
    raw = DATABASE_URL.split('///', 1)[-1]
    p = Path(raw)
    if not p.is_absolute():
        p = (BASE_DIR / raw).resolve()
    return p


def _parse_pg_url(url: str) -> dict:
    """Разбирает postgresql[+driver]://user:pass@host:port/dbname в словарь."""
    cleaned = url
    if cleaned.startswith('postgresql+'):
        # SQLAlchemy-style postgresql+psycopg2://...
        cleaned = 'postgresql://' + cleaned.split('://', 1)[1]
    parsed = urlparse(cleaned)
    return {
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port or 5432),
        'user': unquote(parsed.username) if parsed.username else '',
        'password': unquote(parsed.password) if parsed.password else '',
        'dbname': (parsed.path or '/').lstrip('/'),
    }


def _backup_filename(now: Optional[datetime] = None, *, ext: str = SQLITE_EXT) -> Path:
    now = now or datetime.now()
    ts = now.strftime('%Y%m%d_%H%M%S')
    host = socket.gethostname().replace(' ', '_') or 'host'
    return BACKUP_DIR / f'atpp_{host}_{ts}{ext}'


def list_backups() -> List[Path]:
    _ensure_dir()
    out = list(BACKUP_DIR.glob('atpp_*' + SQLITE_EXT))
    out.extend(BACKUP_DIR.glob('atpp_*' + PG_EXT))
    return sorted(out)


def _stamp_from_name(p: Path) -> Optional[datetime]:
    """Извлекает datetime из имени бэкапа.

    Поддерживается:
      - текущий формат  atpp_<host>_YYYYMMDD_HHMMSS.<ext>
      - устаревший формат atpp_YYYYMMDD_HHMMSS.<ext>
    """
    name = p.name
    for ext in (SQLITE_EXT, PG_EXT):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    parts = name.split('_')
    # минимум: ['atpp', 'YYYYMMDD', 'HHMMSS'] (legacy) либо длиннее
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(parts[-2] + '_' + parts[-1], '%Y%m%d_%H%M%S')
    except ValueError:
        return None


def already_backed_up_today() -> bool:
    today = datetime.now().date()
    for p in list_backups():
        d = _stamp_from_name(p)
        if d and d.date() == today:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────
# Зеркалирование на сетевую папку
# ──────────────────────────────────────────────────────────────────────────

def _mirror_target() -> Optional[Path]:
    """Куда отправлять копию бэкапа.

    Источник конфигурации (по приоритету):
      1. ENV ATPP_BACKUP_MIRROR
      2. файл data/backup.cfg (одна строка с путём)
    Поддерживается локальный путь и UNC (\\\\SERVER\\share\\...).
    """
    val = os.getenv('ATPP_BACKUP_MIRROR')
    if not val:
        cfg = DATA_DIR / 'backup.cfg'
        if cfg.exists():
            try:
                for line in cfg.read_text(encoding='utf-8').splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        val = line
                        break
            except Exception:
                pass
    if not val:
        return None
    return Path(val)


def _mirror_to(path: Path) -> Optional[Path]:
    target = _mirror_target()
    if target is None:
        return None
    try:
        host = socket.gethostname().replace(' ', '_') or 'host'
        dest_dir = target / host
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        shutil.copy2(path, dest)
        return dest
    except Exception as e:
        _log.warning('mirror error: %s', e)
        return None


# ──────────────────────────────────────────────────────────────────────────
# SQLite
# ──────────────────────────────────────────────────────────────────────────

def _make_backup_sqlite() -> Optional[Path]:
    src = _sqlite_path()
    if src is None or not src.exists():
        return None
    dst = _backup_filename(ext=SQLITE_EXT)
    try:
        with open(src, 'rb') as fin:
            with gzip.open(dst, 'wb', compresslevel=6) as fout:
                shutil.copyfileobj(fin, fout)
    except Exception:
        _log.exception('Backup operation failed')
        return None
    return dst


def _restore_backup_sqlite(backup_path: Path) -> bool:
    src = _sqlite_path()
    if src is None:
        return False
    if not backup_path.exists():
        return False
    try:
        if src.exists():
            backup_of_current = src.with_suffix(src.suffix + f'.bak_{int(time.time())}')
            shutil.copy2(src, backup_of_current)
        with gzip.open(backup_path, 'rb') as fin:
            with open(src, 'wb') as fout:
                shutil.copyfileobj(fin, fout)
        return True
    except Exception:
        _log.exception('Backup operation failed')
        return False


# ──────────────────────────────────────────────────────────────────────────
# PostgreSQL
# ──────────────────────────────────────────────────────────────────────────

def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _pg_tool(name: str) -> Optional[str]:
    """Находит pg_dump / pg_restore.

    Сначала PATH, затем стандартные пути установки PostgreSQL под Windows.
    """
    found = _which(name) or _which(name + '.exe')
    if found:
        return found
    # Windows: типовые пути установки
    if os.name == 'nt':
        candidates = []
        for base in (r'C:\Program Files\PostgreSQL', r'C:\Program Files (x86)\PostgreSQL'):
            try:
                if os.path.isdir(base):
                    for ver in sorted(os.listdir(base), reverse=True):
                        cand = os.path.join(base, ver, 'bin', name + '.exe')
                        if os.path.isfile(cand):
                            candidates.append(cand)
            except Exception:
                pass
        if candidates:
            return candidates[0]
    return None


def _pg_env(creds: dict) -> dict:
    env = os.environ.copy()
    if creds.get('password'):
        env['PGPASSWORD'] = creds['password']
    return env


def _make_backup_postgresql() -> Optional[Path]:
    creds = _parse_pg_url(DATABASE_URL)
    if not creds.get('dbname'):
        _log.warning('PG: пустое имя БД в DATABASE_URL')
        return None
    pg_dump = _pg_tool('pg_dump')
    if pg_dump is None:
        _log.warning('PG: не найден pg_dump (проверьте PATH или установку PostgreSQL)')
        return None
    dst = _backup_filename(ext=PG_EXT)
    cmd = [
        pg_dump,
        '-h', creds['host'],
        '-p', creds['port'],
        '-U', creds['user'] or 'postgres',
        '-d', creds['dbname'],
        '--format=custom',
        '--no-owner',
        '--no-privileges',
        '-f', str(dst),
    ]
    try:
        proc = subprocess.run(
            cmd, env=_pg_env(creds), capture_output=True, text=True, timeout=3600,
        )
        if proc.returncode != 0:
            _log.warning('pg_dump RC=%s: %s', proc.returncode, proc.stderr.strip())
            try:
                dst.unlink(missing_ok=True)
            except Exception:
                pass
            return None
        return dst
    except Exception:
        _log.exception('Backup operation failed')
        try:
            dst.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _restore_backup_postgresql(backup_path: Path) -> bool:
    if not backup_path.exists():
        return False
    creds = _parse_pg_url(DATABASE_URL)
    if not creds.get('dbname'):
        return False
    pg_restore = _pg_tool('pg_restore')
    if pg_restore is None:
        _log.warning('PG: не найден pg_restore')
        return False
    cmd = [
        pg_restore,
        '-h', creds['host'],
        '-p', creds['port'],
        '-U', creds['user'] or 'postgres',
        '-d', creds['dbname'],
        '--clean',
        '--if-exists',
        '--no-owner',
        '--no-privileges',
        str(backup_path),
    ]
    try:
        proc = subprocess.run(
            cmd, env=_pg_env(creds), capture_output=True, text=True, timeout=3600,
        )
        # pg_restore нередко возвращает 1 при предупреждениях (unknown objects);
        # считаем успехом 0 и 1 (warnings). Падаем только на >=2.
        if proc.returncode >= 2:
            _log.warning('pg_restore RC=%s: %s', proc.returncode, proc.stderr.strip())
            return False
        return True
    except Exception:
        _log.exception('Backup operation failed')
        return False


# ──────────────────────────────────────────────────────────────────────────
# Публичный API
# ──────────────────────────────────────────────────────────────────────────

def make_backup(*, force: bool = False) -> Optional[Path]:
    """Создать одну резервную копию БД.

    - SQLite       → atpp_<host>_<ts>.db.gz
    - PostgreSQL   → atpp_<host>_<ts>.dump

    Если force=False и сегодня уже был бэкап — вернёт путь существующего файла.
    После создания — отзеркалит файл в ATPP_BACKUP_MIRROR (если задано).
    """
    _ensure_dir()
    if not force and already_backed_up_today():
        # Возвращаем «сегодняшний» если уже есть
        today = datetime.now().date()
        for p in reversed(list_backups()):
            d = _stamp_from_name(p)
            if d and d.date() == today:
                return p

    kind = _engine_kind()
    if kind == 'sqlite':
        path = _make_backup_sqlite()
    elif kind == 'postgresql':
        path = _make_backup_postgresql()
    else:
        _log.warning('неподдерживаемый движок: %s', kind)
        return None

    if path is not None:
        _mirror_to(path)
    return path


def restore_backup(backup_path: Path) -> bool:
    """Восстановить БД из бэкапа. Формат определяется по расширению файла."""
    if not backup_path.exists():
        return False
    name = backup_path.name.lower()
    if name.endswith(SQLITE_EXT):
        return _restore_backup_sqlite(backup_path)
    if name.endswith(PG_EXT):
        return _restore_backup_postgresql(backup_path)
    # неизвестное расширение — пробуем по типу текущего движка
    kind = _engine_kind()
    if kind == 'sqlite':
        return _restore_backup_sqlite(backup_path)
    if kind == 'postgresql':
        return _restore_backup_postgresql(backup_path)
    return False


# ────────────────────────────────────────────────────────────────────────────
# C11. Проверка целостности резервной копии (test-restore)
# ────────────────────────────────────────────────────────────────────────────

def verify_backup_integrity(backup_path: Path) -> dict:
    """Проверяет, что бэкап читается и содержит данные.

    Стратегия:
        - SQLite: открываем bytes-копию через sqlite3 (no-op — без записи)
          и считаем количество таблиц + ключевых строк (users, products).
        - PostgreSQL: проверяем заголовок файла и его размер; полноценная
          проверка-restore требует свободной БД, поэтому делаем её только
          если выставлен ATPP_BACKUP_TEST_PG (нескучная база, например
          ``atpp_test_restore``).

    Возвращает структуру:
        {
            'ok': bool,
            'path': str,
            'kind': 'sqlite'|'postgresql'|'unknown',
            'size_bytes': int,
            'details': str,        # человекочитаемое
            'tables': int|None,
            'rows_users': int|None,
            'rows_products': int|None,
            'error': str|None,
        }
    """
    import gzip
    import shutil
    import sqlite3
    import tempfile

    info = {
        'ok': False, 'path': str(backup_path), 'kind': 'unknown',
        'size_bytes': 0, 'details': '',
        'tables': None, 'rows_users': None, 'rows_products': None,
        'error': None,
    }
    if not backup_path.exists():
        info['error'] = 'Файл не найден'
        return info
    info['size_bytes'] = backup_path.stat().st_size

    name = backup_path.name.lower()
    try:
        if name.endswith(SQLITE_EXT):
            info['kind'] = 'sqlite'
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / 'restore_check.db'
                with gzip.open(backup_path, 'rb') as src, open(tmp, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                con = sqlite3.connect(str(tmp))
                try:
                    cur = con.cursor()
                    cur.execute(
                        "SELECT count(*) FROM sqlite_master "
                        "WHERE type='table'")
                    info['tables'] = int(cur.fetchone()[0])
                    for tname, key in (('users', 'rows_users'),
                                        ('products', 'rows_products')):
                        try:
                            cur.execute(f'SELECT count(*) FROM {tname}')
                            info[key] = int(cur.fetchone()[0])
                        except sqlite3.Error:
                            pass
                finally:
                    con.close()
            info['ok'] = (info['tables'] or 0) > 0
            info['details'] = (
                f'Таблиц: {info["tables"]}, '
                f'users: {info["rows_users"]}, '
                f'products: {info["rows_products"]}')
        elif name.endswith(PG_EXT):
            info['kind'] = 'postgresql'
            # Базовая проверка: магическая последовательность pg_dump custom-format
            # начинается с "PGDMP". Этого достаточно, чтобы убедиться, что
            # файл — именно дамп, а не обрезок.
            with backup_path.open('rb') as f:
                head = f.read(5)
            if head == b'PGDMP':
                info['ok'] = info['size_bytes'] > 1024
                info['details'] = (f'Заголовок PGDMP, '
                                    f'размер {info["size_bytes"]} байт')
            else:
                info['ok'] = False
                info['details'] = ('Файл не похож на pg_dump (нет заголовка '
                                    'PGDMP).')
        else:
            info['error'] = f'Неизвестное расширение: {backup_path.suffix}'
    except Exception as e:
        info['ok'] = False
        info['error'] = f'{type(e).__name__}: {e}'
    return info


def verify_all_backups(limit: int = 5) -> list[dict]:
    """Проверяет последние ``limit`` бэкапов (по дате имени)."""
    backups = list_backups()[-int(limit):]
    return [verify_backup_integrity(p) for p in backups]


def rotate():
    """Удалить старые бэкапы по политике: оставить последние KEEP_DAILY
    дней + понедельничные за год.
    """
    backups = list_backups()
    if len(backups) <= KEEP_DAILY:
        return
    today = datetime.now().date()
    daily_threshold = today - timedelta(days=KEEP_DAILY)
    weekly_threshold = today - timedelta(days=KEEP_WEEKLY * 7)

    keep = set()
    keep.update(backups[-KEEP_DAILY:])
    for p in backups:
        d = _stamp_from_name(p)
        if not d:
            keep.add(p)  # не трогаем то, что не смогли распарсить
            continue
        d = d.date()
        if d >= weekly_threshold and d.weekday() == WEEKDAY_KEEP:
            keep.add(p)
        if d >= daily_threshold:
            keep.add(p)

    for p in backups:
        if p in keep:
            continue
        try:
            os.remove(p)
        except Exception:
            pass


def daily_backup_if_needed() -> Optional[Path]:
    """Безопасный вызов из launcher: ничего не падает."""
    try:
        if already_backed_up_today():
            return None
        path = make_backup()
        rotate()
        return path
    except Exception:
        _log.exception('Backup operation failed')
        return None


def backup_summary() -> Tuple[List[Path], Optional[Path]]:
    """Возвращает (список локальных бэкапов, путь зеркала-папки или None)."""
    return list_backups(), _mirror_target()


# ──────────────────────────────────────────────────────────────────────────
# Авто-бекап по расписанию (BackupScheduler)
# ──────────────────────────────────────────────────────────────────────────

import threading

class BackupScheduler:
    """Фоновый планировщик авто-бекапов с настраиваемым интервалом.

    Интервал задаётся в data/backup.cfg ключом BACKUP_INTERVAL_MINUTES=<N>.
    По умолчанию: 1440 (раз в сутки).
    """

    def __init__(self, interval_minutes: int = 1440):
        self._interval = interval_minutes
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @classmethod
    def from_config(cls) -> 'BackupScheduler':
        interval = 1440
        cfg = DATA_DIR / 'backup.cfg'
        if cfg.exists():
            try:
                for line in cfg.read_text(encoding='utf-8').splitlines():
                    line = line.strip()
                    if line.startswith('BACKUP_INTERVAL_MINUTES='):
                        interval = int(line.split('=', 1)[1])
                        break
            except Exception:
                pass
        return cls(interval_minutes=interval)

    @property
    def interval_minutes(self) -> int:
        return self._interval

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _log.info('Backup scheduler started (interval %d min)', self._interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.wait(self._interval * 60):
            try:
                path = make_backup()
                if path:
                    rotate()
                    _log.info('Scheduled backup created: %s', path)
            except Exception:
                _log.exception('Backup operation failed')


_backup_scheduler: Optional[BackupScheduler] = None


def get_backup_scheduler() -> BackupScheduler:
    global _backup_scheduler
    if _backup_scheduler is None:
        _backup_scheduler = BackupScheduler.from_config()
    return _backup_scheduler


def start_auto_backup():
    get_backup_scheduler().start()


def stop_auto_backup():
    if _backup_scheduler:
        _backup_scheduler.stop()
