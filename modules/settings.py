"""
Лёгкое хранилище пользовательских настроек.

Используем JSON-файл `data/settings.json` чтобы не плодить миграции БД для
мелочей вроде темы, размера шрифта, шага номеров операций и последних
заголовков МТП на деталь.

Все функции «fire-and-forget»: если что-то идёт не так, возвращаем дефолт и
продолжаем работать. Настройки — не критические данные.
"""
from __future__ import annotations

import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict

from config import DATA_DIR

_SETTINGS_PATH = DATA_DIR / "settings.json"
_LOCK = threading.Lock()

_DEFAULTS: Dict[str, Any] = {
    "theme": "light",          # light / dark
    "font_size": 9,            # базовый размер шрифта приложения, pt
    "language": "ru",          # ru / en
    "op_number_step": 5,       # шаг автоинкремента номеров операций
    "op_number_pad": 3,        # формат: 005 = pad 3, 010 = pad 3, 5 = pad 0
    "mtp_headers": {},         # dict[product_designation -> {project, kit, order}]
}


def _load() -> Dict[str, Any]:
    if not _SETTINGS_PATH.exists():
        return dict(_DEFAULTS)
    try:
        with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(_DEFAULTS)
        out = dict(_DEFAULTS)
        out.update(data)
        return out
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return dict(_DEFAULTS)


def _save(data: Dict[str, Any]) -> None:
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SETTINGS_PATH.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(_SETTINGS_PATH)
    except Exception:
        traceback.print_exc(file=sys.stderr)


def get(key: str, default: Any = None) -> Any:
    with _LOCK:
        data = _load()
        return data.get(key, default if default is not None else _DEFAULTS.get(key))


def set(key: str, value: Any) -> None:
    with _LOCK:
        data = _load()
        data[key] = value
        _save(data)


def all_settings() -> Dict[str, Any]:
    with _LOCK:
        return _load()


# ──────────────────────────────────────────────────────────────────────
# MTP header per product (item 12)
# ──────────────────────────────────────────────────────────────────────
def get_mtp_header(designation: str) -> Dict[str, str]:
    """Прочитать последний использованный заголовок МТП для детали."""
    if not designation:
        return {}
    headers = get('mtp_headers', {}) or {}
    val = headers.get(designation, {})
    if not isinstance(val, dict):
        return {}
    return {
        'project_name': str(val.get('project_name') or ''),
        'kit_number': str(val.get('kit_number') or ''),
        'order_number': str(val.get('order_number') or ''),
    }


def set_mtp_header(designation: str, *, project_name: str = '',
                   kit_number: str = '', order_number: str = '') -> None:
    if not designation:
        return
    with _LOCK:
        data = _load()
        headers = data.get('mtp_headers', {})
        if not isinstance(headers, dict):
            headers = {}
        headers[designation] = {
            'project_name': project_name or '',
            'kit_number': kit_number or '',
            'order_number': order_number or '',
        }
        data['mtp_headers'] = headers
        _save(data)


# ──────────────────────────────────────────────────────────────────────
# Op number formatting (item 13)
# ──────────────────────────────────────────────────────────────────────
def next_op_number(existing_numbers) -> str:
    """Вычислить следующий номер операции по настройкам шага и формата.

    Принимает iterable строковых номеров (как они хранятся в БД).
    """
    step = int(get('op_number_step', 5) or 5)
    pad = int(get('op_number_pad', 3) or 0)
    max_n = 0
    for raw in existing_numbers or []:
        try:
            n = int(str(raw).strip())
            if n > max_n:
                max_n = n
        except (TypeError, ValueError):
            continue
    nxt = max_n + step
    if pad > 0:
        return str(nxt).zfill(pad)
    return str(nxt)
