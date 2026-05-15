"""Тесты модуля «Производство» (release / register / move / issue)."""
import pytest

from database.models import (
    IssueKind, IssueSeverity, IssueStatus,
    Operation, Product, RouteStepStatus,
    TechProcess, TPStatus, TPType, User, Workshop,
    WorkOrder, WorkOrderItem, WorkOrderItemStatus, WorkOrderStatus,
)


# ──────────────── helpers ────────────────

def _admin(s):
    return s.query(User).filter_by(username='admin').first()


def _master(s, db):
    """Создаёт тестового мастера (роль master)."""
    m = User(
        username='master1',
        password_hash=db._hash_password('m'),
        full_name='Иван Мастер',
        role='master', is_active=True,
    )
    s.add(m); s.flush()
    return m


def _make_tp_with_ops(s, n_ops=3, qty_total=10):
    """Создаёт ТП с n_ops операциями. Возвращает tp_id."""
    admin = _admin(s)
    p = Product(designation='PROD-1', name='Тест-деталь')
    s.add(p); s.flush()
    tp = TechProcess(number='TP-PROD-1', version='1', author_id=admin.id,
                     product_id=p.id, status=TPStatus.APPROVED,
                     tp_type=TPType.SINGLE)
    s.add(tp); s.flush()
    for i in range(1, n_ops + 1):
        s.add(Operation(tech_process_id=tp.id,
                        number=f'{i*5:03d}', name=f'Операция {i}',
                        sort_order=i))
    s.flush()
    return tp.id


# ──────────────── tests ────────────────


def test_release_to_production_creates_wo(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        tp_id = _make_tp_with_ops(s)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id,
            qty_total=10, customer_order='ORD-1',
        )
        assert wo.status == WorkOrderStatus.RELEASED
        assert wo.number.startswith('WO-')
        assert wo.qty_total == 10


def test_release_requires_role(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        tp_id = _make_tp_with_ops(s)
        with pytest.raises(production.ProductionError):
            production.release_to_production(
                s, user={'id': 999, 'role': 'user'},
                tech_process_id=tp_id, qty_total=5,
            )


def test_register_creates_items_and_steps(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=3, qty_total=10)
        ws = s.query(Workshop).filter_by(code='WH').first()

        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=10,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
            split_into=[6, 4],
        )
        assert len(items) == 2
        assert sum(i.qty for i in items) == 10
        assert all(i.barcode.startswith('ATPP-WI-') for i in items)
        # шаги маршрута созданы для каждой операции
        for item in items:
            assert len(item.route_steps) == 3
            assert all(rs.status == RouteStepStatus.PENDING
                       for rs in item.route_steps)
        s.flush()
        assert wo.status == WorkOrderStatus.REGISTERED


def test_register_validates_split(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, qty_total=10)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=10,
        )
        with pytest.raises(production.ProductionError):
            production.register_work_order(
                s, user={'id': master.id, 'role': 'master'},
                work_order_id=wo.id, initial_workshop_id=ws.id,
                split_into=[5, 4],  # сумма 9, не 10
            )


def test_full_happy_path_three_operations(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=3, qty_total=5)
        ws = s.query(Workshop).filter_by(code='WH').first()
        ws_turn = s.query(Workshop).filter_by(code='TURN1').first()
        ws_qc = s.query(Workshop).filter_by(code='QC').first()

        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]

        # Op 1
        production.start_operation(
            s, user={'id': master.id, 'role': 'master'},
            item_id=item.id, workshop_id=ws.id,
        )
        production.finish_operation(
            s, user={'id': master.id, 'role': 'master'},
            item_id=item.id, qty_good=5,
            next_workshop_id=ws_turn.id,
        )
        s.flush()
        assert item.current_workshop_id == ws_turn.id

        # Op 2
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id, workshop_id=ws_turn.id)
        production.finish_operation(s, user={'id': master.id, 'role': 'master'},
                                    item_id=item.id, qty_good=5,
                                    next_workshop_id=ws_qc.id)

        # Op 3 (последняя)
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id, workshop_id=ws_qc.id)
        production.finish_operation(s, user={'id': master.id, 'role': 'master'},
                                    item_id=item.id, qty_good=5)

        s.flush()
        assert item.status == WorkOrderItemStatus.DONE
        assert wo.status == WorkOrderStatus.DONE
        assert wo.qty_done == 5
        assert wo.qty_scrap == 0


def test_scrap_quantity_recorded(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=1, qty_total=10)
        ws = s.query(Workshop).filter_by(code='WH').first()

        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=10,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id)
        production.finish_operation(s, user={'id': master.id, 'role': 'master'},
                                    item_id=item.id, qty_good=8, qty_scrap=2)
        s.flush()
        assert wo.qty_done == 8
        assert wo.qty_scrap == 2
        assert wo.status == WorkOrderStatus.DONE


def test_finish_rejects_overcount(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=1, qty_total=5)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id)
        with pytest.raises(production.ProductionError):
            production.finish_operation(
                s, user={'id': master.id, 'role': 'master'},
                item_id=item.id, qty_good=5, qty_scrap=3)


def test_open_blocking_issue_freezes_wo(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=4)
        ws = s.query(Workshop).filter_by(code='WH').first()

        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=4,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id)

        issue = production.open_issue(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, work_order_item_id=item.id,
            kind=IssueKind.NO_MATERIAL, severity=IssueSeverity.BLOCKER,
            title='Нет заготовки', description='Кончился прокат',
            workshop_id=ws.id, blocks_production=True,
        )
        assert issue.status == IssueStatus.OPEN
        s.flush()
        assert wo.status == WorkOrderStatus.ON_HOLD


def test_resolve_issue_resumes_wo(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=4)
        ws = s.query(Workshop).filter_by(code='WH').first()

        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=4,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]
        production.start_operation(s, user={'id': master.id, 'role': 'master'},
                                   item_id=item.id)
        issue = production.open_issue(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, kind=IssueKind.NO_TOOL,
            severity=IssueSeverity.BLOCKER, title='Нет фрезы',
            blocks_production=True,
        )
        s.flush()
        assert wo.status == WorkOrderStatus.ON_HOLD

        production.resolve_issue(
            s, user={'id': admin.id, 'role': 'admin'},
            issue_id=issue.id, resolution='Привезли инструмент',
        )
        s.flush()
        assert wo.status == WorkOrderStatus.IN_PROGRESS
        assert issue.status == IssueStatus.RESOLVED


def test_barcode_parse_roundtrip():
    from modules import production
    bc = production.generate_barcode(item_id=42)
    assert bc.startswith('ATPP-WI-42-')
    assert production.parse_barcode(bc) == 42
    assert production.parse_barcode('1234567890') is None
    assert production.parse_barcode('  ATPP-WI-7-AAAA  ') == 7


def test_optimistic_lock_on_concurrent_update(db_manager):
    """Параллельное изменение partии вызывает StaleDataError."""
    from sqlalchemy.orm.exc import StaleDataError
    from modules import production
    # Сначала готовим данные в одной сессии
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=4)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=4,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item_id = items[0].id

    # Две параллельные сессии открывают одну и ту же партию.
    # scoped_session() возвращает одну сессию на поток, потому здесь
    # используем session_factory напрямую.
    factory = db_manager.Session.session_factory
    s1 = factory()
    s2 = factory()
    try:
        item1 = s1.get(WorkOrderItem, item_id)
        item2 = s2.get(WorkOrderItem, item_id)
        item1.status = WorkOrderItemStatus.IN_PROGRESS
        s1.commit()
        item2.status = WorkOrderItemStatus.MOVED
        with pytest.raises(StaleDataError):
            s2.commit()
    finally:
        s1.close(); s2.close()


def test_wip_by_workshop_summary(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=4)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=4,
        )
        production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
            split_into=[2, 2],
        )
        wip = production.wip_by_workshop(s)
        wh_row = next(row for row in wip if row['workshop_code'] == 'WH')
        assert wh_row['items_count'] == 2
        assert wh_row['qty_total'] == 4


# ──────────────────────────────────────────────────────────────────────────
# Возврат партии на доработку (REWORK) — фича A2 (v6)
# ──────────────────────────────────────────────────────────────────────────

def _setup_three_op_partial(db_manager, finished_count=2):
    """Готовит партию, у которой выполнено ``finished_count`` из 3 операций.

    Возвращает (wo_id, item_id, master_user_dict).
    """
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=3, qty_total=5)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        item = items[0]
        master_user = {'id': master.id, 'role': 'master'}
        for _ in range(finished_count):
            production.start_operation(s, user=master_user, item_id=item.id)
            production.finish_operation(s, user=master_user,
                                        item_id=item.id, qty_good=5)
        s.flush()
        return wo.id, item.id, master_user


def test_rework_returns_partition_to_previous_step(db_manager):
    from modules import production
    wo_id, item_id, master = _setup_three_op_partial(db_manager,
                                                     finished_count=2)
    with db_manager.get_session() as s:
        item = s.get(WorkOrderItem, item_id)
        # До rework: на 3-й операции, шаги 1,2 = DONE, шаг 3 = PENDING
        steps_before = sorted(item.route_steps, key=lambda x: x.seq)
        assert steps_before[0].status == RouteStepStatus.DONE
        assert steps_before[1].status == RouteStepStatus.DONE
        assert steps_before[2].status == RouteStepStatus.PENDING

        production.rework_partition(
            s, user=master, item_id=item_id,
            reason='Брак по геометрии — нужно повторно фрезеровать',
        )
        s.flush()
        steps_after = sorted(item.route_steps, key=lambda x: x.seq)
        # Шаг 2 теперь REWORK (на него вернули)
        assert steps_after[1].status == RouteStepStatus.REWORK
        # Шаг 3 сброшен в PENDING
        assert steps_after[2].status == RouteStepStatus.PENDING
        assert item.current_operation_id == steps_after[1].operation_id
        assert item.status == WorkOrderItemStatus.WAITING


def test_rework_requires_reason(db_manager):
    from modules import production
    wo_id, item_id, master = _setup_three_op_partial(db_manager,
                                                     finished_count=1)
    with db_manager.get_session() as s:
        with pytest.raises(production.ProductionError):
            production.rework_partition(
                s, user=master, item_id=item_id, reason='   ',
            )


def test_rework_requires_role(db_manager):
    from modules import production
    wo_id, item_id, _ = _setup_three_op_partial(db_manager, finished_count=1)
    with db_manager.get_session() as s:
        with pytest.raises(production.ProductionError):
            production.rework_partition(
                s, user={'id': 999, 'role': 'worker'},
                item_id=item_id, reason='пытаемся',
            )


def test_rework_blocks_when_no_done_step(db_manager):
    """На самой первой операции откатывать некуда → ProductionError."""
    from modules import production
    wo_id, item_id, master = _setup_three_op_partial(db_manager,
                                                     finished_count=0)
    with db_manager.get_session() as s:
        with pytest.raises(production.ProductionError):
            production.rework_partition(
                s, user=master, item_id=item_id,
                reason='пробуем откатить с нулевой',
            )


def test_rework_logs_event(db_manager):
    from modules import production
    from database.models import ProductionEvent
    wo_id, item_id, master = _setup_three_op_partial(db_manager,
                                                     finished_count=2)
    with db_manager.get_session() as s:
        production.rework_partition(
            s, user=master, item_id=item_id, reason='повтор операции 2',
        )
        s.flush()
        evt = (s.query(ProductionEvent)
               .filter(ProductionEvent.event_type == 'REWORK_INITIATED')
               .first())
        assert evt is not None
        assert evt.work_order_id == wo_id
        assert evt.work_order_item_id == item_id


# ──────────────────────────────────────────────────────────────────────────
# Отмена наряда — фича A3 (v6)
# ──────────────────────────────────────────────────────────────────────────

def test_cancel_work_order_marks_status_canceled(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=6)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=6,
        )
        production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
            split_into=[3, 3],
        )

        production.cancel_work_order(
            s, user={'id': admin.id, 'role': 'admin'},
            work_order_id=wo.id, reason='Заказ снят клиентом',
        )
        s.flush()
        assert wo.status == WorkOrderStatus.CANCELED
        # Все партии помечены SCRAP, шаги SKIPPED
        for it in wo.items:
            assert it.status == WorkOrderItemStatus.SCRAP
            for st in it.route_steps:
                assert st.status == RouteStepStatus.SKIPPED


def test_cancel_requires_reason_and_role(db_manager):
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=4)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=4,
        )
        # Без причины
        with pytest.raises(production.ProductionError):
            production.cancel_work_order(
                s, user={'id': admin.id, 'role': 'admin'},
                work_order_id=wo.id, reason='',
            )
        # Чужая роль
        with pytest.raises(production.ProductionError):
            production.cancel_work_order(
                s, user={'id': master.id, 'role': 'master'},
                work_order_id=wo.id, reason='пытаюсь отменить',
            )


def test_cancel_already_done_blocked(db_manager):
    """Завершённый наряд отменить нельзя."""
    from modules import production
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=1, qty_total=2)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=2,
        )
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
        )
        master_user = {'id': master.id, 'role': 'master'}
        production.start_operation(s, user=master_user, item_id=items[0].id)
        production.finish_operation(s, user=master_user, item_id=items[0].id,
                                    qty_good=2)
        s.flush()
        assert wo.status == WorkOrderStatus.DONE
        with pytest.raises(production.ProductionError):
            production.cancel_work_order(
                s, user={'id': admin.id, 'role': 'admin'},
                work_order_id=wo.id, reason='пробуем отменить готовый',
            )


# ──────────────────────────────────────────────────────────────────────────
# Печать ярлыков пачкой — фича A4 (v6)
# ──────────────────────────────────────────────────────────────────────────

def test_generate_labels_pdf_returns_pdf(db_manager):
    from modules import production, barcode_gen
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = _master(s, db_manager)
        tp_id = _make_tp_with_ops(s, n_ops=2, qty_total=12)
        ws = s.query(Workshop).filter_by(code='WH').first()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=12,
        )
        production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=ws.id,
            split_into=[1] * 12,
        )
        s.flush()
        pdf_bytes = barcode_gen.generate_labels_pdf(s, wo.id)
    assert pdf_bytes.startswith(b'%PDF'), 'Output should be a PDF'
    assert len(pdf_bytes) > 1000  # минимум разумного PDF


def test_generate_labels_pdf_empty_wo_errors(db_manager):
    from modules import production, barcode_gen
    with db_manager.get_session() as s:
        admin = _admin(s)
        tp_id = _make_tp_with_ops(s, n_ops=1, qty_total=1)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=1,
        )
        # Не регистрируем — у наряда нет партий
        s.flush()
        with pytest.raises(barcode_gen.BarcodeError):
            barcode_gen.generate_labels_pdf(s, wo.id)
