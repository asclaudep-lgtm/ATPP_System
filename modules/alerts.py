"""Алёрт-канал (C12).

Простой механизм: критические события дублируются в ``data/alerts.json``
(циклический буфер последних N записей) и опционально POST-ятся на
HTTP-эндпойнт (``data/alerts.cfg`` → ``webhook=...``).

Для Telegram-бота URL имеет вид ``https://api.telegram.org/bot<TOKEN>/
sendMessage`` + ``chat_id``. Можно настроить любой webhook-получатель.

from utils.logger import get_logger

_log = get_logger(__name__)

ВАЖНО: модуль не падает, если интернета нет или вебхук не настроен —
просто пишет в ``alerts.json``. Это безопасно вызывать прямо в
бизнес-логике.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_MAX_ALERTS = 500


def _alerts_dir() -> Path:
    try:
        from config import DATA_DIR
        d = Path(DATA_DIR)
    except Exception:
        d = Path(__file__).resolve().parent.parent / 'data'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _alerts_log() -> Path:
    return _alerts_dir() / 'alerts.json'


def _alerts_cfg() -> Path:
    return _alerts_dir() / 'alerts.cfg'


def _read_cfg() -> dict[str, str]:
    """Читает простой ini-формат ``key=value``."""
    cfg = _alerts_cfg()
    if not cfg.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in cfg.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                out[k.strip().lower()] = v.strip()
    except Exception:
        _log.warning('cfg read failed: {e}')
    return out


def _append_log(record: dict[str, Any]) -> None:
    log = _alerts_log()
    data: list[dict] = []
    if log.exists():
        try:
            data = json.loads(log.read_text(encoding='utf-8'))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    data.append(record)
    if len(data) > _MAX_ALERTS:
        data = data[-_MAX_ALERTS:]
    try:
        log.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding='utf-8')
    except Exception:
        _log.warning('cannot write log: {e}')


def _post_webhook(url: str, payload: dict[str, Any]) -> None:
    """Простой POST. Использует urllib, без внешних зависимостей."""
    try:
        import urllib.request
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            url, data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            resp.read(64)
    except Exception:
        _log.warning('webhook failed ({url}): {e}')


def dispatch(
    *,
    kind: str,
    title: str,
    body: str = '',
    user_id: Optional[int] = None,
    related_issue_id: Optional[int] = None,
    related_work_order_id: Optional[int] = None,
) -> None:
    """Отправляет алёрт во все настроенные каналы. Никогда не бросает."""
    record = {
        'kind': kind,
        'title': title,
        'body': body,
        'user_id': user_id,
        'related_issue_id': related_issue_id,
        'related_work_order_id': related_work_order_id,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    _append_log(record)

    # ENV переопределяет конфиг
    cfg = _read_cfg()
    webhook = os.getenv('ATPP_ALERT_WEBHOOK', '') or cfg.get('webhook', '')
    if webhook:
        _post_webhook(webhook, record)


def list_alerts(limit: int = 100) -> list[dict[str, Any]]:
    """Последние N алёртов (хвост)."""
    log = _alerts_log()
    if not log.exists():
        return []
    try:
        data = json.loads(log.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            return []
        return data[-int(limit):]
    except Exception:
        return []
