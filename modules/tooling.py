"""
v9-4: Учёт оснастки — выдача/возврат, привязка к операциям.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from database.models import (
    OperationTooling,
    ToolingIssue,
    ToolingItem,
    ToolingStatus,
)


def issue_to_user(
    session,
    *,
    tooling_item_id: int,
    issued_to: int,
    issued_by: int,
    work_order_id: Optional[int] = None,
    operation_id: Optional[int] = None,
    notes: str = '',
) -> ToolingIssue:
    """Выдать оснастку в работу."""
    item: ToolingItem = session.get(ToolingItem, tooling_item_id)
    if item is None:
        raise ValueError(f'ToolingItem #{tooling_item_id} not found')
    if item.status != ToolingStatus.AVAILABLE:
        raise ValueError(
            f'Оснастка «{item.name}» сейчас «{item.status.value}», '
            f'выдать нельзя'
        )
    rec = ToolingIssue(
        tooling_item_id=tooling_item_id,
        issued_to=issued_to,
        issued_by=issued_by,
        work_order_id=work_order_id,
        operation_id=operation_id,
        notes=notes or None,
    )
    session.add(rec)
    item.status = ToolingStatus.ISSUED
    session.flush()
    return rec


def return_from_user(
    session,
    *,
    issue_id: int,
    wear_percent: Optional[int] = None,
    notes: str = '',
) -> ToolingIssue:
    """Принять оснастку обратно."""
    rec: ToolingIssue = session.get(ToolingIssue, issue_id)
    if rec is None:
        raise ValueError(f'ToolingIssue #{issue_id} not found')
    if rec.returned_at is not None:
        raise ValueError('Эта выдача уже закрыта')
    rec.returned_at = datetime.now()
    if wear_percent is not None:
        rec.return_wear_percent = int(wear_percent)
        item = rec.tooling
        if item is not None:
            item.wear_percent = max(int(item.wear_percent or 0),
                                    int(wear_percent))
    if notes:
        rec.notes = (rec.notes or '') + '\n' + notes
    item = rec.tooling
    if item is not None and item.status == ToolingStatus.ISSUED:
        item.status = ToolingStatus.AVAILABLE
    session.flush()
    return rec


def active_issues(session) -> List[ToolingIssue]:
    """Оснастка, которая сейчас на руках (returned_at IS NULL)."""
    return (session.query(ToolingIssue)
            .filter(ToolingIssue.returned_at.is_(None))
            .order_by(ToolingIssue.issued_at.desc())
            .all())


def attach_to_operation(session, *, operation_id: int,
                        tooling_item_id: int,
                        notes: str = '') -> OperationTooling:
    """Привязать оснастку к операции (если ещё не привязана)."""
    existing = (session.query(OperationTooling)
                .filter_by(operation_id=operation_id,
                           tooling_item_id=tooling_item_id)
                .first())
    if existing:
        return existing
    rec = OperationTooling(
        operation_id=operation_id,
        tooling_item_id=tooling_item_id,
        notes=notes or None,
    )
    session.add(rec)
    session.flush()
    return rec


def tooling_for_operation(session, operation_id: int
                          ) -> List[ToolingItem]:
    """Список оснастки, требуемой для операции."""
    return (session.query(ToolingItem)
            .join(OperationTooling,
                  OperationTooling.tooling_item_id == ToolingItem.id)
            .filter(OperationTooling.operation_id == operation_id)
            .all())
