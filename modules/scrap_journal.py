"""
v9-9: Брак-журнал с фотофиксацией.

Лёгкий API над таблицами ``scrap_records`` / ``scrap_photos``.

Файлы фото хранятся в ``data/scrap/<scrap_id>/<uuid>.<ext>`` —
бэкап-модуль автоматически подбирает каталог ``data/``.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import func

from database.models import (
    Operation,
    ScrapDecision,
    ScrapPhoto,
    ScrapReason,
    ScrapRecord,
)

SCRAP_PHOTOS_DIR = Path('data/scrap')


def _ensure_dir(scrap_id: int) -> Path:
    p = SCRAP_PHOTOS_DIR / str(scrap_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_scrap(
    session,
    *,
    work_order_id: int,
    work_order_item_id: Optional[int] = None,
    operation_id: Optional[int] = None,
    route_step_id: Optional[int] = None,
    qty_scrap: int = 1,
    reason: ScrapReason = ScrapReason.OTHER,
    description: str = '',
    fault_operator_id: Optional[int] = None,
    reported_by: int = 0,
) -> ScrapRecord:
    """Создать запись о браке."""
    rec = ScrapRecord(
        work_order_id=work_order_id,
        work_order_item_id=work_order_item_id,
        operation_id=operation_id,
        route_step_id=route_step_id,
        qty_scrap=int(qty_scrap),
        reason=reason,
        description=description or None,
        fault_operator_id=fault_operator_id,
        reported_by=reported_by,
        reported_at=datetime.now(),
    )
    session.add(rec)
    session.flush()
    return rec


def attach_photo(
    session, *, scrap_id: int, src_path: str,
    caption: Optional[str] = None, uploaded_by: Optional[int] = None,
) -> ScrapPhoto:
    """Скопировать файл в data/scrap/<id>/, создать ScrapPhoto."""
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(src_path)
    dst_dir = _ensure_dir(scrap_id)
    new_name = f'{uuid.uuid4().hex}{src.suffix.lower()}'
    dst = dst_dir / new_name
    shutil.copy2(src, dst)

    ph = ScrapPhoto(
        scrap_id=scrap_id,
        file_path=str(dst.as_posix()),
        caption=caption or None,
        uploaded_by=uploaded_by,
    )
    session.add(ph)
    session.flush()
    return ph


def decide(
    session, *, scrap_id: int, decision: ScrapDecision,
    resolution: str = '', decided_by: int = 0,
) -> ScrapRecord:
    """Зафиксировать решение ОТК по записи о браке."""
    rec = session.get(ScrapRecord, scrap_id)
    if rec is None:
        raise ValueError(f'ScrapRecord #{scrap_id} not found')
    rec.decision = decision
    rec.resolution = resolution or None
    rec.decided_by = decided_by or None
    rec.decided_at = datetime.now()
    return rec


# ── Аналитика ─────────────────────────────────────────────────────

def scrap_by_reason(session, *, days: int = 30) -> List[Tuple[str, int, int]]:
    """Сводка «причина → (кол-во записей, всего брак-деталей)» за N дней."""
    since = datetime.now() - timedelta(days=days)
    rows = (session.query(ScrapRecord.reason,
                          func.count(ScrapRecord.id),
                          func.coalesce(func.sum(ScrapRecord.qty_scrap), 0))
            .filter(ScrapRecord.reported_at >= since)
            .group_by(ScrapRecord.reason)
            .all())
    return [(r[0].value if r[0] else '—', int(r[1]), int(r[2])) for r in rows]


def scrap_by_operation(session, *, days: int = 30, top: int = 5
                       ) -> List[Tuple[str, int]]:
    """Топ-N операций по количеству брак-деталей за период."""
    since = datetime.now() - timedelta(days=days)
    rows = (session.query(Operation.name,
                          func.coalesce(func.sum(ScrapRecord.qty_scrap), 0))
            .join(ScrapRecord, ScrapRecord.operation_id == Operation.id)
            .filter(ScrapRecord.reported_at >= since)
            .group_by(Operation.id, Operation.name)
            .order_by(func.coalesce(func.sum(ScrapRecord.qty_scrap), 0).desc())
            .limit(top)
            .all())
    return [(r[0] or '—', int(r[1])) for r in rows]


def total_scrap_qty(session, *, days: int = 30) -> int:
    since = datetime.now() - timedelta(days=days)
    val = (session.query(func.coalesce(func.sum(ScrapRecord.qty_scrap), 0))
           .filter(ScrapRecord.reported_at >= since)
           .scalar())
    return int(val or 0)
