"""Tests for A6 in-app notifications + auto-notify on issue assignment."""

from modules import notifications, production
from database.models import (
    IssueKind, IssueSeverity, Operation, Product, TechProcess, TPStatus,
    TPType, User,
)


def _admin(s):
    return s.query(User).filter_by(username='admin').first()


def _make_tp(s, *, db_manager):
    admin = _admin(s)
    p = Product(designation='NOTIF-1', name='Деталь')
    s.add(p); s.flush()
    tp = TechProcess(number='TP-NOTIF-1', version='1', author_id=admin.id,
                     product_id=p.id, status=TPStatus.APPROVED,
                     tp_type=TPType.SINGLE)
    s.add(tp); s.flush()
    for i in range(1, 4):
        s.add(Operation(tech_process_id=tp.id, number=f'{i*5:03d}',
                        name=f'Op {i}', sort_order=i))
    s.flush()
    return tp.id


def test_notify_user_creates_record(db_manager):
    db_manager.create_user('u1', 'StrongPass1!', must_change_password=False)
    with db_manager.get_session() as s:
        uid = s.query(User).filter_by(username='u1').first().id
        n = notifications.notify_user(
            s, user_id=uid, kind='TEST', title='Hello', body='body')
        assert n.id
        assert n.user_id == uid


def test_unread_count_and_mark_all_read(db_manager):
    db_manager.create_user('u2', 'StrongPass1!', must_change_password=False)
    with db_manager.get_session() as s:
        uid = s.query(User).filter_by(username='u2').first().id
        for i in range(3):
            notifications.notify_user(s, user_id=uid, kind='K', title=f't{i}')
        assert notifications.unread_count(s, uid) == 3
        n_marked = notifications.mark_all_read(s, uid)
        assert n_marked == 3
        assert notifications.unread_count(s, uid) == 0


def test_open_issue_with_assignee_creates_notification(db_manager):
    """A6: open_issue с assignee_id → создаётся ISSUE_ASSIGNED для назначенного."""
    db_manager.create_user('tech1', 'StrongPass1!', role='technologist',
                           must_change_password=False)
    db_manager.create_user('master1', 'StrongPass1!', role='master',
                           must_change_password=False)
    with db_manager.get_session() as s:
        tech = s.query(User).filter_by(username='tech1').first()
        master = s.query(User).filter_by(username='master1').first()
        tech_user = {'id': tech.id, 'role': 'technologist'}
        master_user = {'id': master.id, 'role': 'master'}
        tp_id = _make_tp(s, db_manager=db_manager)

        wo = production.release_to_production(
            s, user=tech_user, tech_process_id=tp_id, qty_total=10)
        wo_id = wo.id

        production.open_issue(
            s, user=master_user, work_order_id=wo_id,
            kind=IssueKind.NO_MATERIAL,
            severity=IssueSeverity.HIGH,
            title='Нет материала',
            description='Сталь 45 не пришла.',
            assignee_id=tech.id,
            blocks_production=True,
        )

    with db_manager.get_session() as s:
        tech = s.query(User).filter_by(username='tech1').first()
        notes = notifications.list_notifications(s, user_id=tech.id)
        assert any(n.kind == 'ISSUE_ASSIGNED' for n in notes)


def test_resolve_issue_notifies_opener(db_manager):
    """После resolve_issue открывшему уходит ISSUE_RESOLVED."""
    db_manager.create_user('tech2', 'StrongPass1!', role='technologist',
                           must_change_password=False)
    db_manager.create_user('master2', 'StrongPass1!', role='master',
                           must_change_password=False)
    with db_manager.get_session() as s:
        tech = s.query(User).filter_by(username='tech2').first()
        master = s.query(User).filter_by(username='master2').first()
        tech_user = {'id': tech.id, 'role': 'technologist'}
        master_user = {'id': master.id, 'role': 'master'}
        tp_id = _make_tp(s, db_manager=db_manager)

        wo = production.release_to_production(
            s, user=tech_user, tech_process_id=tp_id, qty_total=10)
        issue = production.open_issue(
            s, user=master_user, work_order_id=wo.id,
            kind=IssueKind.NO_TOOL,
            severity=IssueSeverity.MEDIUM,
            title='Нет инструмента',
            assignee_id=tech.id,
        )
        issue_id = issue.id

    with db_manager.get_session() as s:
        tech = s.query(User).filter_by(username='tech2').first()
        tech_user = {'id': tech.id, 'role': 'technologist'}
        production.resolve_issue(
            s, user=tech_user, issue_id=issue_id,
            resolution='Принесли резец.')

    with db_manager.get_session() as s:
        master = s.query(User).filter_by(username='master2').first()
        notes = notifications.list_notifications(s, user_id=master.id)
        assert any(n.kind == 'ISSUE_RESOLVED' for n in notes)
