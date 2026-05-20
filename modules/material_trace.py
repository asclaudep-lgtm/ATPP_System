"""
v9-5: Трассируемость материала — партии, резервирование, списание.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from database.models import (
    MaterialBatch,
    MaterialIssue,
    MaterialReservation,
)

CERT_DIR = Path('data/material_certs')


def add_batch(
    session, *,
    material_id: int,
    lot_no: str,
    qty_received: float,
    supplier: str = '',
    unit: str = 'кг',
    received_date: Optional[date] = None,
    cert_src_path: Optional[str] = None,
    notes: str = '',
) -> MaterialBatch:
    """Создать запись о поступлении партии материала."""
    if received_date is None:
        received_date = date.today()
    cert_path = None
    if cert_src_path:
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        src = Path(cert_src_path)
        if not src.exists():
            raise FileNotFoundError(cert_src_path)
        dst = CERT_DIR / f'{uuid.uuid4().hex}{src.suffix.lower()}'
        shutil.copy2(src, dst)
        cert_path = str(dst.as_posix())

    batch = MaterialBatch(
        material_id=material_id,
        lot_no=lot_no,
        qty_received=float(qty_received),
        qty_reserved=0,
        qty_consumed=0,
        unit=unit,
        supplier=supplier or None,
        received_date=received_date,
        cert_path=cert_path,
        notes=notes or None,
    )
    session.add(batch)
    session.flush()
    return batch


def available_qty(batch: MaterialBatch) -> float:
    """Свободный (нерезервный, неcписанный) остаток партии."""
    return float((batch.qty_received or 0)
                 - (batch.qty_reserved or 0)
                 - (batch.qty_consumed or 0))


def reserve(session, *, batch_id: int, work_order_id: int,
            qty: float, reserved_by: Optional[int] = None,
            notes: str = '') -> MaterialReservation:
    batch: MaterialBatch = session.get(MaterialBatch, batch_id)
    if batch is None:
        raise ValueError(f'MaterialBatch #{batch_id} not found')
    free = available_qty(batch)
    if qty > free + 1e-6:
        raise ValueError(
            f'Недостаточно остатка партии: свободно {free:g} {batch.unit}, '
            f'нужно {qty:g}'
        )
    rec = MaterialReservation(
        batch_id=batch_id,
        work_order_id=work_order_id,
        qty=float(qty),
        reserved_by=reserved_by,
        notes=notes or None,
    )
    session.add(rec)
    batch.qty_reserved = (batch.qty_reserved or 0) + float(qty)
    session.flush()
    return rec


def release_reservation(session, *, reservation_id: int) -> None:
    """Снять (отменить) резерв — вернуть в свободный остаток."""
    rec: MaterialReservation = session.get(MaterialReservation, reservation_id)
    if rec is None:
        raise ValueError(f'MaterialReservation #{reservation_id} not found')
    if rec.released_at is not None:
        return
    rec.released_at = datetime.now()
    batch = rec.batch
    batch.qty_reserved = max(0.0, (batch.qty_reserved or 0) - float(rec.qty))
    session.flush()


def issue(session, *, batch_id: int, work_order_id: int,
          qty: float, issued_by: Optional[int] = None,
          notes: str = '') -> MaterialIssue:
    """Списать (отгрузить) материал из партии в производство."""
    batch: MaterialBatch = session.get(MaterialBatch, batch_id)
    if batch is None:
        raise ValueError(f'MaterialBatch #{batch_id} not found')
    available_total = float((batch.qty_received or 0)
                            - (batch.qty_consumed or 0))
    if qty > available_total + 1e-6:
        raise ValueError(
            f'Нельзя списать {qty:g} — остаток партии '
            f'{available_total:g} {batch.unit}'
        )
    rec = MaterialIssue(
        batch_id=batch_id,
        work_order_id=work_order_id,
        qty=float(qty),
        issued_by=issued_by,
        notes=notes or None,
    )
    session.add(rec)
    batch.qty_consumed = (batch.qty_consumed or 0) + float(qty)
    # Если был резерв под этот же WO — уменьшим его на ту же сумму.
    res = (session.query(MaterialReservation)
           .filter_by(batch_id=batch_id, work_order_id=work_order_id,
                      released_at=None)
           .first())
    if res is not None:
        decr = min(float(res.qty), float(qty))
        res.qty = float(res.qty) - decr
        batch.qty_reserved = max(0.0,
                                 (batch.qty_reserved or 0) - decr)
        if res.qty <= 1e-6:
            res.released_at = datetime.now()
    session.flush()
    return rec


def batches_for_material(session, material_id: int
                         ) -> List[MaterialBatch]:
    return (session.query(MaterialBatch)
            .filter(MaterialBatch.material_id == material_id)
            .order_by(MaterialBatch.received_date.desc())
            .all())


def trace_work_order(session, work_order_id: int) -> dict:
    """Что было зарезервировано / списано на этот наряд."""
    reservs = (session.query(MaterialReservation)
               .filter_by(work_order_id=work_order_id).all())
    issues = (session.query(MaterialIssue)
              .filter_by(work_order_id=work_order_id).all())
    return {'reservations': reservs, 'issues': issues}
