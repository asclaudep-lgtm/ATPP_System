"""
v9-8: Извещения об изменениях (Engineering Change Notice).

Лёгкий API над таблицами ``ecns`` / ``ecn_approvals``.

Стандартный маршрут согласования (default):
   Гл. технолог → ОТК → Производство
Можно расширять / переопределять при создании.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Iterable

from database.models import (
    ECN, ECNApproval, ECNStatus, SignerRole,
    TechProcess, Product,
)


DEFAULT_ROUTE = [
    SignerRole.CHIEF_TECH.value,
    SignerRole.QC.value,
    SignerRole.APPROVER.value,
]


def next_ecn_number(session) -> str:
    """Генерация номера ECN вида ECN-2025-001."""
    year = datetime.now().year
    base = f'ECN-{year}-'
    used = (session.query(ECN.number)
            .filter(ECN.number.like(f'{base}%')).all())
    nums = []
    for (n,) in used:
        try:
            nums.append(int(str(n).rsplit('-', 1)[-1]))
        except Exception:
            pass
    nxt = (max(nums) if nums else 0) + 1
    return f'{base}{nxt:03d}'


def create_ecn(
    session, *,
    title: str,
    reason: str,
    proposed_change: str = '',
    product_id: Optional[int] = None,
    tech_process_id: Optional[int] = None,
    created_by: int,
    route_roles: Optional[Iterable[str]] = None,
) -> ECN:
    """Создать ECN в статусе DRAFT с подготовленным маршрутом согласования."""
    ecn = ECN(
        number=next_ecn_number(session),
        title=title,
        reason=reason,
        proposed_change=proposed_change or None,
        product_id=product_id,
        tech_process_id=tech_process_id,
        created_by=created_by,
        status=ECNStatus.DRAFT,
    )
    session.add(ecn)
    session.flush()

    for role in (route_roles or DEFAULT_ROUTE):
        appr = ECNApproval(
            ecn_id=ecn.id,
            role=role,
            decision='PENDING',
        )
        session.add(appr)
    session.flush()
    return ecn


def submit_for_review(session, *, ecn_id: int) -> ECN:
    """Перевести из DRAFT в UNDER_REVIEW."""
    ecn: ECN = session.get(ECN, ecn_id)
    if ecn is None:
        raise ValueError(f'ECN #{ecn_id} not found')
    if ecn.status != ECNStatus.DRAFT:
        raise ValueError(f'ECN в статусе {ecn.status.value}, нельзя отправить')
    ecn.status = ECNStatus.UNDER_REVIEW
    return ecn


def approve(session, *, ecn_id: int, role: str,
            user_id: int, comment: str = '') -> ECNApproval:
    """Подпись согласующего «согласовано»."""
    return _decide(session, ecn_id=ecn_id, role=role,
                   user_id=user_id, decision='APPROVED', comment=comment)


def reject(session, *, ecn_id: int, role: str,
           user_id: int, comment: str = '') -> ECNApproval:
    """Отклонить ECN от имени роли."""
    return _decide(session, ecn_id=ecn_id, role=role,
                   user_id=user_id, decision='REJECTED', comment=comment)


def _decide(session, *, ecn_id: int, role: str,
            user_id: int, decision: str, comment: str = '') -> ECNApproval:
    ecn: ECN = session.get(ECN, ecn_id)
    if ecn is None:
        raise ValueError(f'ECN #{ecn_id} not found')
    if ecn.status not in (ECNStatus.UNDER_REVIEW, ECNStatus.DRAFT):
        raise ValueError(
            f'ECN в статусе {ecn.status.value}, изменять решения нельзя')

    appr = (session.query(ECNApproval)
            .filter_by(ecn_id=ecn_id, role=role)
            .first())
    if appr is None:
        appr = ECNApproval(ecn_id=ecn_id, role=role)
        session.add(appr)
    appr.user_id = user_id
    appr.decision = decision
    appr.decided_at = datetime.now()
    appr.comment = comment or None
    session.flush()

    _recalculate_ecn_status(session, ecn)
    return appr


def _recalculate_ecn_status(session, ecn: ECN) -> None:
    """Если все «APPROVED» — APPROVED; если есть «REJECTED» — REJECTED."""
    approvals = list(ecn.approvals)
    if any(a.decision == 'REJECTED' for a in approvals):
        ecn.status = ECNStatus.REJECTED
        ecn.closed_at = datetime.now()
        return
    if approvals and all(a.decision == 'APPROVED' for a in approvals):
        ecn.status = ECNStatus.APPROVED
        ecn.closed_at = datetime.now()
        return


def mark_applied(session, *, ecn_id: int) -> ECN:
    ecn: ECN = session.get(ECN, ecn_id)
    if ecn is None:
        raise ValueError(f'ECN #{ecn_id} not found')
    if ecn.status != ECNStatus.APPROVED:
        raise ValueError(
            f'ECN {ecn.number} в статусе {ecn.status.value}, '
            'можно отметить применённым только из APPROVED')
    ecn.status = ECNStatus.APPLIED
    return ecn


def list_ecns(session, *, status: Optional[ECNStatus] = None
              ) -> List[ECN]:
    q = session.query(ECN)
    if status is not None:
        q = q.filter(ECN.status == status)
    return q.order_by(ECN.created_at.desc()).all()


# ——— v11: Гибкий маршрут согласования ———


def create_ecn_with_route(session, *,
                          title: str, reason: str,
                          product_id: Optional[int] = None,
                          tech_process_id: Optional[int] = None,
                          created_by: int,
                          route: Optional[List[str]] = None,
                          proposed_change: Optional[str] = None,
                          ) -> ECN:
    """Создать ECN с настраиваемым маршрутом согласования.

    route = список ролей SignerRole.value в порядке согласования.
    По умолчанию: ['Гл. технолог', 'ОТК', 'Утверждающий'].
    """
    from modules.ecn import next_ecn_number
    if route is None:
        route = [SignerRole.CHIEF_TECH.value,
                 SignerRole.QC.value,
                 SignerRole.APPROVER.value]

    number = next_ecn_number(session)
    ecn = ECN(
        number=number, title=title, reason=reason,
        product_id=product_id,
        tech_process_id=tech_process_id,
        proposed_change=proposed_change,
        status=ECNStatus.DRAFT,
        created_by=created_by,
    )
    session.add(ecn)
    session.flush()

    # Создать подписи под каждую роль в маршруте
    for role_value in route:
        approval = ECNApproval(
            ecn_id=ecn.id,
            role=role_value,
            decision='PENDING',
        )
        session.add(approval)
    session.flush()
    return ecn


def get_ecn_pending_actions(session, *, ecn_id: int) -> List[dict]:
    """Получить список ожидающих подписей для ECN."""
    approvals = session.query(ECNApproval).filter(
        ECNApproval.ecn_id == ecn_id,
        ECNApproval.decision == 'PENDING',
    ).all()
    return [{'role': a.role, 'id': a.id} for a in approvals]


def sign_ecn(session, *, ecn_id: int, approval_id: int,
             user_id: int, decision: str, comment: str = '') -> ECN:
    """Подписать ECN от имени конкретной роли."""
    approval = session.query(ECNApproval).get(approval_id)
    if approval is None or approval.ecn_id != ecn_id:
        raise ValueError('Подпись не найдена')
    approval.user_id = user_id
    approval.decision = decision
    approval.decided_at = datetime.now()
    approval.comment = comment or None

    if decision == 'REJECTED':
        ecn = session.query(ECN).get(ecn_id)
        ecn.status = ECNStatus.REJECTED
    elif decision == 'APPROVED':
        pending = get_ecn_pending_actions(session, ecn_id=ecn_id)
        if not pending:
            ecn = session.query(ECN).get(ecn_id)
            ecn.status = ECNStatus.APPROVED

    session.flush()
    return session.query(ECN).get(ecn_id)
