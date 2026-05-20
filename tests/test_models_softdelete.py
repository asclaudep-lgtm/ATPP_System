"""Тесты soft delete для ТП и операций."""
from datetime import datetime
from database.models import (
    User, Product, TechProcess, Operation, TPStatus, TPType,
)


def test_softdelete_columns_exist(db_manager):
    with db_manager.get_session() as s:
        u = s.query(User).filter_by(username='admin').first()
        p = Product(designation='SD-1', name='SD test')
        s.add(p); s.flush()
        tp = TechProcess(number='TP-SD', version='1', author_id=u.id,
                         product_id=p.id, status=TPStatus.DRAFT,
                         tp_type=TPType.SINGLE)
        s.add(tp); s.flush()
        op = Operation(tech_process_id=tp.id, number='005', name='Test',
                       sort_order=1)
        s.add(op); s.flush()

        # Проставить флаги
        tp.is_deleted = True
        tp.deleted_at = datetime.now()
        op.is_deleted = True
        op.deleted_at = datetime.now()

    with db_manager.get_session() as s:
        active_tp = (s.query(TechProcess)
                     .filter((not TechProcess.is_deleted) |
                             (TechProcess.is_deleted.is_(None))).count())
        deleted_tp = s.query(TechProcess).filter_by(is_deleted=True).count()
        assert active_tp == 0
        assert deleted_tp == 1
