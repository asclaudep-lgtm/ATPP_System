"""Тесты PostgreSQL-ветки модуля резервного копирования (с моками)."""
import sys
import types
from pathlib import Path

import pytest


def _reload_backup_with_url(url: str, monkeypatch):
    """Перезагружает modules.backup с подменённым DATABASE_URL в config."""
    import config as _config
    monkeypatch.setattr(_config, 'DATABASE_URL', url)
    if 'modules.backup' in sys.modules:
        del sys.modules['modules.backup']
    import modules.backup as backup
    return backup


def test_engine_kind_detection(monkeypatch):
    backup = _reload_backup_with_url(
        'postgresql+psycopg2://u:p@host:5432/atpp', monkeypatch
    )
    assert backup._engine_kind() == 'postgresql'

    backup = _reload_backup_with_url('sqlite:///data/atpp.db', monkeypatch)
    assert backup._engine_kind() == 'sqlite'


def test_parse_pg_url_full():
    from modules.backup import _parse_pg_url
    creds = _parse_pg_url('postgresql+psycopg2://atpp:s%40cret@srv:5433/atpp')
    assert creds == {
        'host': 'srv',
        'port': '5433',
        'user': 'atpp',
        'password': 's@cret',
        'dbname': 'atpp',
    }


def test_parse_pg_url_defaults():
    from modules.backup import _parse_pg_url
    creds = _parse_pg_url('postgresql://atpp:pwd@host/atpp')
    assert creds['host'] == 'host'
    assert creds['port'] == '5432'
    assert creds['dbname'] == 'atpp'


def test_pg_make_backup_invokes_pg_dump(tmp_path, monkeypatch):
    """make_backup() для PostgreSQL зовёт pg_dump с верными аргументами."""
    backup = _reload_backup_with_url(
        'postgresql+psycopg2://atpp:pwd@srv:5432/atpp', monkeypatch
    )
    monkeypatch.setattr(backup, 'BACKUP_DIR', tmp_path / 'backups')
    monkeypatch.setattr(backup, '_pg_tool', lambda name: '/usr/bin/' + name)

    captured = {}

    def fake_run(cmd, env=None, capture_output=True, text=True, timeout=3600):
        captured['cmd'] = cmd
        captured['env'] = env
        # эмулируем создание файла, как сделал бы pg_dump
        out_idx = cmd.index('-f') + 1
        Path(cmd[out_idx]).write_bytes(b'PGDMP fake content')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(backup.subprocess, 'run', fake_run)

    path = backup.make_backup(force=True)
    assert path is not None
    assert path.exists()
    assert path.suffix == '.dump'

    cmd = captured['cmd']
    assert cmd[0].endswith('pg_dump')
    assert '-h' in cmd and 'srv' in cmd
    assert '-p' in cmd and '5432' in cmd
    assert '-U' in cmd and 'atpp' in cmd
    assert '-d' in cmd and 'atpp' in cmd
    assert '--format=custom' in cmd
    assert captured['env'].get('PGPASSWORD') == 'pwd'


def test_pg_make_backup_handles_failure(tmp_path, monkeypatch):
    """Если pg_dump упал — make_backup() вернёт None, файл не остаётся."""
    backup = _reload_backup_with_url(
        'postgresql+psycopg2://atpp:pwd@srv:5432/atpp', monkeypatch
    )
    monkeypatch.setattr(backup, 'BACKUP_DIR', tmp_path / 'backups')
    monkeypatch.setattr(backup, '_pg_tool', lambda name: '/usr/bin/' + name)

    def fake_run(cmd, env=None, capture_output=True, text=True, timeout=3600):
        return types.SimpleNamespace(returncode=1, stdout='', stderr='boom')

    monkeypatch.setattr(backup.subprocess, 'run', fake_run)

    path = backup.make_backup(force=True)
    assert path is None
    # ничего не создано
    if (tmp_path / 'backups').exists():
        leftovers = list((tmp_path / 'backups').glob('*.dump'))
        assert leftovers == []


def test_pg_restore_invokes_pg_restore(tmp_path, monkeypatch):
    backup = _reload_backup_with_url(
        'postgresql+psycopg2://atpp:pwd@srv:5432/atpp', monkeypatch
    )
    src = tmp_path / 'atpp_test_20260101_010101.dump'
    src.write_bytes(b'PGDMP')
    monkeypatch.setattr(backup, '_pg_tool', lambda name: '/usr/bin/' + name)

    captured = {}

    def fake_run(cmd, env=None, capture_output=True, text=True, timeout=3600):
        captured['cmd'] = cmd
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(backup.subprocess, 'run', fake_run)
    assert backup.restore_backup(src) is True
    assert captured['cmd'][0].endswith('pg_restore')
    assert '--clean' in captured['cmd']
    assert '--if-exists' in captured['cmd']
    assert str(src) in captured['cmd']


def test_mirror_copy(tmp_path, monkeypatch):
    """После make_backup() файл копируется в зеркальную папку (по hostname)."""
    backup = _reload_backup_with_url('sqlite:///' + str(tmp_path / 'atpp.db'),
                                     monkeypatch)
    # подкладываем источник для SQLite-бэкапа
    src_db = tmp_path / 'atpp.db'
    src_db.write_bytes(b'SQLite format 3\x00' + b'\x00' * 200)

    monkeypatch.setattr(backup, '_sqlite_path', lambda: src_db)
    monkeypatch.setattr(backup, 'BACKUP_DIR', tmp_path / 'local_backups')
    mirror_dir = tmp_path / 'mirror'
    monkeypatch.setenv('ATPP_BACKUP_MIRROR', str(mirror_dir))

    path = backup.make_backup(force=True)
    assert path is not None and path.exists()

    # должна появиться копия в mirror/<hostname>/<filename>
    found = list(mirror_dir.rglob(path.name))
    assert len(found) == 1, f'Зеркало не сработало: {list(mirror_dir.rglob("*"))}'


def test_mirror_unavailable_does_not_break(tmp_path, monkeypatch):
    """Если зеркало недоступно — основной бэкап всё равно успешен."""
    backup = _reload_backup_with_url('sqlite:///' + str(tmp_path / 'atpp.db'),
                                     monkeypatch)
    src_db = tmp_path / 'atpp.db'
    src_db.write_bytes(b'SQLite format 3\x00' + b'\x00' * 100)
    monkeypatch.setattr(backup, '_sqlite_path', lambda: src_db)
    monkeypatch.setattr(backup, 'BACKUP_DIR', tmp_path / 'local_backups')
    monkeypatch.setenv(
        'ATPP_BACKUP_MIRROR',
        str(tmp_path / 'definitely_not_writable' / 'no' / 'way'),
    )
    # имитируем недоступность через неперезаписываемое имя
    def _broken_copy(*a, **kw):
        raise OSError('mirror unreachable')
    monkeypatch.setattr(backup.shutil, 'copy2', _broken_copy)

    path = backup.make_backup(force=True)
    assert path is not None and path.exists()


def test_already_backed_up_today_with_pg_dump(tmp_path, monkeypatch):
    """already_backed_up_today() распознаёт как .db.gz, так и .dump."""
    backup = _reload_backup_with_url(
        'postgresql+psycopg2://atpp:pwd@srv/atpp', monkeypatch
    )
    monkeypatch.setattr(backup, 'BACKUP_DIR', tmp_path)
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    (tmp_path / f'atpp_pc1_{today}_120000.dump').write_bytes(b'x')
    assert backup.already_backed_up_today() is True
