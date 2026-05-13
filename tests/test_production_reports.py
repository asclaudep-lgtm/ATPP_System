"""Tests for B7-B10 production reports."""
from datetime import datetime, timedelta

from database.models import (
    IssueKind, IssueSeverity, IssueStatus, Operation, Product,
    ProductionIssue, RouteStep, RouteStepStatus, TechProcess, TPStatus,
    TPType, User, Workshop, WorkOrder, WorkOrderItem, WorkOrderStatus,
)
from modules import production, production_reports


def _admin(s):
    return s.query(User).filter_by(username='admin').first()


def _make_tp_with_ops(s, n_ops=3):
    admin = _admin(s)
    p = Product(designation='REP-1', name='R'); s.add(p); s.flush()
    tp = TechProcess(number='TP-REP-1', version='1', author_id=admin.id,
                     product_id=p.id, status=TPStatus.APPROVED,
                     tp_type=TPType.SINGLE)
    s.add(tp); s.flush()
    for i in range(1, n_ops + 1):
        s.add(Operation(tech_process_id=tp.id, number=f'{i*5:03d}',
                         name=f'Op {i}', sort_order=i))
    s.flush()
    return tp.id


def test_throughput_counts_completed_steps(db_manager):
    db_manager.create_user('master_r', 'StrongPass1!', role='master',
                            must_change_password=False)
    db_manager.create_user('worker_r', 'StrongPass1!', role='worker',
                            must_change_password=False)
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = s.query(User).filter_by(username='master_r').first()
        worker = s.query(User).filter_by(username='worker_r').first()
        tp_id = _make_tp_with_ops(s)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=10)
        wh = s.query(Workshop).filter_by(code='WH').first()
        op_ws = s.query(Workshop).filter_by(code='TURN1').first()
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id,
            initial_workshop_id=wh.id,
            split_into=[10])
        item_id = items[0].id

        production.start_operation(
            s, user={'id': worker.id, 'role': 'worker'},
            item_id=item_id, workshop_id=wh.id)
        production.finish_operation(
            s, user={'id': worker.id, 'role': 'worker'},
            item_id=item_id, qty_good=10, qty_scrap=0,
            next_workshop_id=op_ws.id)

    with db_manager.get_session() as s:
        worker = s.query(User).filter_by(username='worker_r').first()
        rows = production_reports.throughput(
            s,
            date_from=datetime.now() - timedelta(hours=1),
            date_to=datetime.now() + timedelta(hours=1))
        # должна быть запись по worker_r на участке WH
        assert any(r['worker_id'] == worker.id and r['finished_steps'] >= 1
                    for r in rows)


def test_lead_time_returns_avg_minutes(db_manager):
    db_manager.create_user('master_lt', 'StrongPass1!', role='master',
                            must_change_password=False)
    db_manager.create_user('worker_lt', 'StrongPass1!', role='worker',
                            must_change_password=False)
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = s.query(User).filter_by(username='master_lt').first()
        worker = s.query(User).filter_by(username='worker_lt').first()
        tp_id = _make_tp_with_ops(s)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5)
        wh = s.query(Workshop).filter_by(code='WH').first()
        op_ws = s.query(Workshop).filter_by(code='TURN1').first()
        items = production.register_work_order(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id, initial_workshop_id=wh.id, split_into=[5])
        item_id = items[0].id
        production.start_operation(
            s, user={'id': worker.id, 'role': 'worker'},
            item_id=item_id, workshop_id=wh.id)
        production.finish_operation(
            s, user={'id': worker.id, 'role': 'worker'},
            item_id=item_id, qty_good=5, qty_scrap=0,
            next_workshop_id=op_ws.id)

    with db_manager.get_session() as s:
        rows = production_reports.lead_time(
            s,
            date_from=datetime.now() - timedelta(hours=1),
            date_to=datetime.now() + timedelta(hours=1))
        assert rows
        for r in rows:
            assert 'avg_minutes' in r
            assert r['avg_minutes'] >= 0


def test_issues_summary_counts_by_kind(db_manager):
    db_manager.create_user('master_is', 'StrongPass1!', role='master',
                            must_change_password=False)
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = s.query(User).filter_by(username='master_is').first()
        tp_id = _make_tp_with_ops(s)
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5)
        for kind in (IssueKind.NO_MATERIAL, IssueKind.NO_TOOL,
                      IssueKind.NO_TOOL):
            production.open_issue(
                s, user={'id': master.id, 'role': 'master'},
                work_order_id=wo.id, kind=kind,
                severity=IssueSeverity.MEDIUM,
                title=f'{kind.value}',
                blocks_production=False,
            )

    with db_manager.get_session() as s:
        rows = production_reports.issues_summary(
            s,
            date_from=datetime.now() - timedelta(hours=1),
            date_to=datetime.now() + timedelta(hours=1))
        kinds = {r['kind']: r['count'] for r in rows}
        assert kinds.get(IssueKind.NO_TOOL.value) == 2
        assert kinds.get(IssueKind.NO_MATERIAL.value) == 1


def test_shift_journal_lists_events(db_manager):
    """B9: события за смену видны в журнале."""
    db_manager.create_user('master_sj', 'StrongPass1!', role='master',
                            must_change_password=False)
    with db_manager.get_session() as s:
        admin = _admin(s)
        tp_id = _make_tp_with_ops(s)
        production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp_id, qty_total=5)
    with db_manager.get_session() as s:
        # смена за сегодня — должна найтись хотя бы 1 запись (RELEASED).
        from datetime import date
        rows = production_reports.shift_journal(
            s, day=date.today(),
            shift_start_hour=0, shift_hours=24)
        assert any(r['event_type'] == 'RELEASED' for r in rows)
