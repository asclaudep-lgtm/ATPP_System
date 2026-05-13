"""Тесты модуля workflow утверждения."""
from database.models import (
    User, Product, TechProcess, TPStatus, TPType,
)


def _make_tp(db) -> int:
    with db.get_session() as s:
        u = s.query(User).filter_by(username='admin').first()
        p = Product(designation='AAA', name='X')
        s.add(p); s.flush()
        tp = TechProcess(number='TP-WF', version='1', author_id=u.id,
                         product_id=p.id, status=TPStatus.DRAFT,
                         tp_type=TPType.SINGLE)
        s.add(tp); s.flush()
        return tp.id


def test_lock_after_full_signatures(db_manager):
    from modules import workflow
    tp_id = _make_tp(db_manager)
    with db_manager.get_session() as s:
        # Нет подписей → не утверждено, не заблокировано
        tp = s.query(TechProcess).get(tp_id)
        assert not workflow.is_locked(tp)
        # Добавляем все обязательные подписи
        for role in workflow.DEFAULT_REQUIRED_ROLES:
            workflow.add_signature(s, tp_id, role, user_id=1)
        ok = workflow.try_auto_approve(s, tp_id, user_id=1)
        assert ok is True
        s.refresh(tp)
        assert tp.status == TPStatus.APPROVED
        assert workflow.is_locked(tp)


def test_unlock_requires_reason(db_manager):
    from modules import workflow
    tp_id = _make_tp(db_manager)
    with db_manager.get_session() as s:
        tp = s.query(TechProcess).get(tp_id)
        tp.status = TPStatus.APPROVED
        ok = workflow.unlock_for_edit(s, tp_id, user_id=1, reason='Доработка')
        assert ok is True
        s.refresh(tp)
        assert tp.status == TPStatus.DRAFT
