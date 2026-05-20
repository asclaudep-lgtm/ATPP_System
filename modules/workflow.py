"""
Workflow утверждения ТП с ролевыми подписями и блокировкой на редактирование.

Сценарий:
1. Технолог создаёт ТП (статус Черновик).
2. Отправляет «На согласование» — система требует подписи ролей.
3. Гл. технолог / нормоконтроль / ОТК ставят подписи.
4. Когда собраны все обязательные роли — статус автоматически
   переключается в «Утверждён» и ТП блокируется для редактирования.
5. Изменить утверждённый ТП можно только через «Снять с утверждения»
   (с обязательным комментарием — пишется в audit log).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from database.models import (
    LOCKED_STATUSES,
    ApprovalSignature,
    SignerRole,
    TechProcess,
    TPStatus,
    User,
)

from . import audit

# Какие роли обязательны для перехода в «Утверждён».
# Можно настраивать (через settings, в будущем — отдельная админка).
DEFAULT_REQUIRED_ROLES: Set[str] = {
    SignerRole.NORMER.value,
    SignerRole.CHIEF_TECH.value,
    SignerRole.APPROVER.value,
}


def is_locked(tp: TechProcess) -> bool:
    """ТП заблокирован для редактирования (Утверждён или В архиве)."""
    return tp.status in LOCKED_STATUSES


def get_signatures(session, tp_id: int) -> List[ApprovalSignature]:
    return (session.query(ApprovalSignature)
            .filter(ApprovalSignature.tech_process_id == tp_id)
            .order_by(ApprovalSignature.signed_at)
            .all())


def signed_roles(session, tp_id: int) -> Set[str]:
    return {s.role for s in get_signatures(session, tp_id)}


def required_roles_satisfied(session, tp_id: int,
                             required: Optional[Set[str]] = None) -> bool:
    req = required or DEFAULT_REQUIRED_ROLES
    return req.issubset(signed_roles(session, tp_id))


def add_signature(session, tp_id: int, role: str,
                  user_id: Optional[int] = None,
                  comment: Optional[str] = None) -> ApprovalSignature:
    """Добавляет подпись. Если уже есть подпись с этой ролью — заменяет."""
    existing = (session.query(ApprovalSignature)
                .filter(ApprovalSignature.tech_process_id == tp_id,
                        ApprovalSignature.role == role)
                .first())
    if existing is not None:
        existing.user_id = user_id
        existing.signed_at = datetime.now()
        existing.comment = comment
        sig = existing
    else:
        sig = ApprovalSignature(
            tech_process_id=tp_id,
            role=role,
            user_id=user_id,
            signed_at=datetime.now(),
            comment=comment,
        )
        session.add(sig)
    session.flush()
    audit.log_change_session(session, entity_type='TechProcess',
                             entity_id=tp_id, user_id=user_id,
                             action='sign',
                             description=f'Подпись «{role}»' +
                                         (f': {comment}' if comment else ''))
    return sig


def remove_signature(session, tp_id: int, role: str,
                     user_id: Optional[int] = None) -> bool:
    n = (session.query(ApprovalSignature)
         .filter(ApprovalSignature.tech_process_id == tp_id,
                 ApprovalSignature.role == role)
         .delete())
    if n:
        audit.log_change_session(session, entity_type='TechProcess',
                                 entity_id=tp_id, user_id=user_id,
                                 action='unsign',
                                 description=f'Снята подпись «{role}»')
    return bool(n)


def try_auto_approve(session, tp_id: int,
                     user_id: Optional[int] = None) -> bool:
    """Если все обязательные подписи собраны — переключаем статус
    в «Утверждён» и фиксируем approved_at / approved_by.
    Возвращает True, если статус изменился.
    """
    tp = session.get(TechProcess, tp_id)
    if tp is None:
        return False
    if tp.status == TPStatus.APPROVED:
        return False
    if not required_roles_satisfied(session, tp_id):
        return False
    tp.status = TPStatus.APPROVED
    tp.approved_at = datetime.now()
    if user_id is not None:
        u = session.get(User, user_id)
        if u is not None:
            tp.approved_by = u.full_name or u.username
    audit.log_change_session(session, entity_type='TechProcess',
                             entity_id=tp_id, user_id=user_id,
                             action='approve',
                             description='ТП утверждён (все обязательные подписи получены)')
    return True


def unlock_for_edit(session, tp_id: int, user_id: int,
                    reason: str) -> bool:
    """Снимает утверждение и возвращает в Черновик с обязательным
    комментарием. Подписи сохраняются (видны в истории), но обнуляются
    флаги approved_at / approved_by.
    """
    tp = session.get(TechProcess, tp_id)
    if tp is None:
        return False
    if tp.status not in LOCKED_STATUSES:
        return False
    tp.status = TPStatus.DRAFT
    tp.approved_at = None
    tp.approved_by = None
    audit.log_change_session(session, entity_type='TechProcess',
                             entity_id=tp_id, user_id=user_id,
                             action='unlock',
                             description=f'Снято с утверждения: {reason}')
    return True
