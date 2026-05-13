"""
Тесты v9 «Средний горизонт».

10 фич:
1) Gantt-планировщик (scheduler.schedule_open_orders + detect_conflicts)
2) Загрузка оборудования (equipment_load)
3) Терминал ОТК (workflow через scrap_journal)
4) Учёт оснастки (tooling.issue/return + связи операций)
5) Учёт материала и трассируемость (material_trace: batch/reserve/issue)
6) Дашборд руководителя (manager_dashboard.kpi_snapshot + export_pdf)
7) Версионирование ТП — diff между снимками (tp_versioning)
8) ECN (ecn.create_ecn / approve / reject)
9) Брак-журнал с фото (scrap_journal.create + аналитика)
10) Метрологическая поверка (metrology.add_calibration + due alerts)
"""
from __future__ import annotations

import os
import json
import shutil
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
import pytest

from database.db_manager import DatabaseManager
from database.models import (
    User, Material, Equipment, Profession, Product, ProductGroup,
    TechProcess, TPStatus, TPType, Operation, Transition,
    WorkOrder, WorkOrderStatus, WorkOrderItem,
    RouteStep, RouteStepStatus, ScrapRecord, ScrapPhoto,
    ScrapReason, ScrapDecision, ToolingItem, ToolingStatus,
    ToolingIssue, MaterialBatch, MaterialReservation, MaterialIssue,
    ECN, ECNApproval, ECNStatus, SignerRole, Instrument, Calibration,
    InstrumentStatus, TPVersion,
)


@pytest.fixture
def db_manager(tmp_path):
    db_path = tmp_path / 'v9.db'
    dm = DatabaseManager(f'sqlite:///{db_path}')
    dm.init_database()
    yield dm
    dm.engine.dispose()


@pytest.fixture
def seed(db_manager):
    """Базовые сущности."""
    with db_manager.get_session() as s:
        u = User(username='qa', full_name='QA Inspector',
                 password_hash='x', role='qa')
        u2 = User(username='oper', full_name='Operator',
                  password_hash='x', role='operator')
        s.add_all([u, u2])
        s.flush()

        m = Material(name='Сталь 45', grade='Сталь 45')
        eq = Equipment(name='Токарный', model='16К20')
        eq2 = Equipment(name='Фрезерный', model='6Р12')
        prof = Profession(name='Токарь', typical_grade=3,
                          hourly_rates='{"3": 500}')
        grp = ProductGroup(name='Группа A')
        s.add_all([m, eq, eq2, prof, grp])
        s.flush()

        p = Product(designation='УЗГА.001', name='Корпус', group_id=grp.id)
        s.add(p)
        s.flush()

        tp = TechProcess(number='TP-001', product_id=p.id, version=1,
                         status=TPStatus.APPROVED, tp_type=TPType.SINGLE,
                         author_id=u.id)
        s.add(tp)
        s.flush()

        op1 = Operation(tech_process_id=tp.id, number='005',
                        name='Токарная', equipment_id=eq.id,
                        profession_id=prof.id, t_setup=10, t_piece=2,
                        sort_order=1)
        op2 = Operation(tech_process_id=tp.id, number='010',
                        name='Фрезерная', equipment_id=eq2.id,
                        profession_id=prof.id, t_setup=15, t_piece=3,
                        sort_order=2)
        s.add_all([op1, op2])
        s.flush()

        wo = WorkOrder(number='WO-001', tech_process_id=tp.id,
                       qty_total=10, qty_done=0, status=WorkOrderStatus.RELEASED,
                       due_date=date.today() + timedelta(days=5))
        s.add(wo)
        s.flush()
        item = WorkOrderItem(work_order_id=wo.id, qty=10,
                             barcode=f'BC-{wo.id}', serial=f'SN-{wo.id}-1')
        s.add(item)
        s.commit()

        return dict(user=u.id, oper=u2.id, material=m.id,
                    eq=eq.id, eq2=eq2.id, prof=prof.id, prod=p.id,
                    tp=tp.id, op1=op1.id, op2=op2.id,
                    wo=wo.id, item=item.id)


# ──────────────────────────────────────────────────────────────────
# 1) Gantt
# ──────────────────────────────────────────────────────────────────

def test_scheduler_creates_plan_for_open_orders(db_manager, seed):
    from modules.scheduler import schedule_open_orders, detect_conflicts
    with db_manager.get_session() as s:
        sched = schedule_open_orders(s, horizon_days=14)
    assert len(sched) == 2  # 2 операции, 1 наряд
    # Операции одного и того же наряда идут последовательно
    assert sched[0].finish <= sched[1].start
    conflicts = detect_conflicts(sched)
    assert conflicts == []


# ──────────────────────────────────────────────────────────────────
# 2) Equipment load
# ──────────────────────────────────────────────────────────────────

def test_equipment_load_fact_uses_route_steps(db_manager, seed):
    from modules.equipment_load import equipment_load
    # Создадим завершённый RouteStep на 60 минут
    with db_manager.get_session() as s:
        finished = datetime.now()
        started = finished - timedelta(minutes=60)
        rs = RouteStep(work_order_item_id=seed['item'],
                       operation_id=seed['op1'], seq=1,
                       status=RouteStepStatus.DONE,
                       started_at=started, finished_at=finished)
        s.add(rs)
        s.commit()
    with db_manager.get_session() as s:
        rows = equipment_load(s, days=30)
    busy = {r.equipment_id: r.busy_minutes for r in rows}
    assert busy.get(seed['eq']) == pytest.approx(60.0, abs=0.1)


def test_equipment_load_plan_uses_open_orders(db_manager, seed):
    from modules.equipment_load import planned_equipment_load
    with db_manager.get_session() as s:
        rows = planned_equipment_load(s, horizon_days=7)
    # Должно быть какое-то «занято» по нашим двум станкам
    by_eq = {r.equipment_id: r.busy_minutes for r in rows}
    assert by_eq[seed['eq']] > 0
    assert by_eq[seed['eq2']] > 0


# ──────────────────────────────────────────────────────────────────
# 3) QA terminal workflow (через scrap_journal)
# ──────────────────────────────────────────────────────────────────

def test_qa_workflow_accept_with_partial_scrap(db_manager, seed):
    from modules.scrap_journal import create_scrap, decide
    from database.models import ScrapDecision as SD
    with db_manager.get_session() as s:
        rec = create_scrap(s, work_order_id=seed['wo'], qty_scrap=2,
                           reason=ScrapReason.MATERIAL,
                           description='Раковина в металле',
                           reported_by=seed['user'])
        decide(s, scrap_id=rec.id, decision=SD.SCRAP,
               resolution='Не подлежит ремонту',
               decided_by=seed['user'])
        s.commit()
        rid = rec.id
    with db_manager.get_session() as s:
        rec = s.get(ScrapRecord, rid)
        assert rec.decision == SD.SCRAP
        assert rec.qty_scrap == 2


# ──────────────────────────────────────────────────────────────────
# 4) Tooling
# ──────────────────────────────────────────────────────────────────

def test_tooling_issue_and_return(db_manager, seed):
    from modules.tooling import issue_to_user, return_from_user
    with db_manager.get_session() as s:
        t = ToolingItem(inventory_no='T-001', name='Кондуктор-1',
                        status=ToolingStatus.AVAILABLE)
        s.add(t)
        s.commit()
        tid = t.id

    with db_manager.get_session() as s:
        rec = issue_to_user(s, tooling_item_id=tid,
                            issued_to=seed['oper'],
                            issued_by=seed['user'])
        s.commit()
        rid = rec.id
        # повторная выдача невозможна
        with pytest.raises(ValueError):
            issue_to_user(s, tooling_item_id=tid,
                          issued_to=seed['oper'],
                          issued_by=seed['user'])

    with db_manager.get_session() as s:
        t = s.get(ToolingItem, tid)
        assert t.status == ToolingStatus.ISSUED

    with db_manager.get_session() as s:
        return_from_user(s, issue_id=rid, wear_percent=15)
        s.commit()

    with db_manager.get_session() as s:
        t = s.get(ToolingItem, tid)
        assert t.status == ToolingStatus.AVAILABLE
        assert t.wear_percent == 15


# ──────────────────────────────────────────────────────────────────
# 5) Material traceability
# ──────────────────────────────────────────────────────────────────

def test_material_batch_reserve_issue(db_manager, seed):
    from modules.material_trace import (
        add_batch, reserve, issue, available_qty,
    )
    with db_manager.get_session() as s:
        b = add_batch(s, material_id=seed['material'],
                      lot_no='LOT-1', qty_received=100.0,
                      supplier='Поставщик', unit='кг')
        s.commit()
        bid = b.id

    with db_manager.get_session() as s:
        # Зарезервируем 30, спишем 10
        reserve(s, batch_id=bid, work_order_id=seed['wo'], qty=30,
                reserved_by=seed['user'])
        issue(s, batch_id=bid, work_order_id=seed['wo'], qty=10,
              issued_by=seed['user'])
        s.commit()

    with db_manager.get_session() as s:
        b = s.get(MaterialBatch, bid)
        assert b.qty_received == 100
        # Резерв уменьшился на сумму списания: 30 - 10 = 20
        assert b.qty_reserved == 20
        assert b.qty_consumed == 10
        # Свободно = 100 - 20 - 10 = 70
        assert available_qty(b) == 70

    # Превышение остатка должно бросать ValueError
    with db_manager.get_session() as s:
        with pytest.raises(ValueError):
            issue(s, batch_id=bid, work_order_id=seed['wo'], qty=200)


# ──────────────────────────────────────────────────────────────────
# 6) Manager dashboard / PDF
# ──────────────────────────────────────────────────────────────────

def test_kpi_snapshot_and_pdf(db_manager, seed, tmp_path):
    from modules.manager_dashboard import kpi_snapshot, export_pdf
    with db_manager.get_session() as s:
        snap = kpi_snapshot(s, days=30)
    assert snap.period_days == 30
    assert snap.wo_total >= 1
    pdf_path = tmp_path / 'kpi.pdf'
    export_pdf(snap, str(pdf_path))
    assert pdf_path.exists() and pdf_path.stat().st_size > 800


# ──────────────────────────────────────────────────────────────────
# 7) TP versioning diff
# ──────────────────────────────────────────────────────────────────

def test_tp_versioning_diff(db_manager, seed):
    from modules import audit
    from modules.tp_versioning import (
        list_versions, load_snapshot, diff_snapshots,
    )
    # Снимок v1
    v1 = audit.snapshot_tp(db_manager, tp_id=seed['tp'],
                           user_id=seed['user'], comment='before')
    assert v1 is not None

    # Изменим название одной операции и сделаем v2
    with db_manager.get_session() as s:
        op = s.get(Operation, seed['op1'])
        op.name = 'Токарная (обновлено)'
        op.t_piece = 5.5
        s.commit()
    v2 = audit.snapshot_tp(db_manager, tp_id=seed['tp'],
                           user_id=seed['user'], comment='after')
    assert v2 is not None

    with db_manager.get_session() as s:
        versions = list_versions(s, seed['tp'])
        assert len(versions) >= 2
        snap_a = load_snapshot(versions[-1])  # старший (v1)
        snap_b = load_snapshot(versions[0])   # младший (v2)
    diff = diff_snapshots(snap_a, snap_b)
    # Должны быть изменения в name и t_piece
    fields = {(d.get('op_number'), d.get('field'))
              for d in diff if d.get('kind') == 'op_field'}
    assert ('005', 'name') in fields
    assert ('005', 't_piece') in fields


# ──────────────────────────────────────────────────────────────────
# 8) ECN
# ──────────────────────────────────────────────────────────────────

def test_ecn_workflow_approve_all(db_manager, seed):
    from modules.ecn import create_ecn, submit_for_review, approve
    from database.models import ECNStatus as S
    with db_manager.get_session() as s:
        ecn = create_ecn(s,
                         title='Изменить ТП-001',
                         reason='Заменить операцию 010',
                         proposed_change='Перевести на станок ЧПУ',
                         product_id=seed['prod'],
                         tech_process_id=seed['tp'],
                         created_by=seed['user'])
        s.commit()
        eid = ecn.id
        # Создано 3 подписанта по умолчанию
        assert len(ecn.approvals) == 3

    with db_manager.get_session() as s:
        submit_for_review(s, ecn_id=eid)
        s.commit()
    with db_manager.get_session() as s:
        ecn = s.get(ECN, eid)
        assert ecn.status == S.UNDER_REVIEW

    # Все 3 — APPROVED, статус становится APPROVED
    with db_manager.get_session() as s:
        for role in (SignerRole.CHIEF_TECH.value,
                     SignerRole.QC.value,
                     SignerRole.APPROVER.value):
            approve(s, ecn_id=eid, role=role,
                    user_id=seed['user'])
        s.commit()
    with db_manager.get_session() as s:
        ecn = s.get(ECN, eid)
        assert ecn.status == S.APPROVED
        assert ecn.closed_at is not None


def test_ecn_rejection_short_circuits(db_manager, seed):
    from modules.ecn import create_ecn, submit_for_review, reject
    from database.models import ECNStatus as S
    with db_manager.get_session() as s:
        ecn = create_ecn(s, title='X', reason='Y',
                         created_by=seed['user'])
        s.commit()
        eid = ecn.id

    with db_manager.get_session() as s:
        submit_for_review(s, ecn_id=eid)
        reject(s, ecn_id=eid, role=SignerRole.QC.value,
               user_id=seed['user'], comment='Нет')
        s.commit()
    with db_manager.get_session() as s:
        ecn = s.get(ECN, eid)
        assert ecn.status == S.REJECTED


# ──────────────────────────────────────────────────────────────────
# 9) Scrap journal + photo + analytics
# ──────────────────────────────────────────────────────────────────

def test_scrap_journal_create_and_analytics(db_manager, seed, tmp_path):
    from modules.scrap_journal import (
        create_scrap, attach_photo, scrap_by_reason,
        scrap_by_operation, total_scrap_qty,
    )
    # Сделаем фейковый файл-«фото»
    img = tmp_path / 'photo.png'
    img.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 64)

    with db_manager.get_session() as s:
        r1 = create_scrap(s, work_order_id=seed['wo'],
                          operation_id=seed['op1'], qty_scrap=3,
                          reason=ScrapReason.OPERATOR,
                          description='Сорвал резьбу',
                          reported_by=seed['user'])
        s.flush()
        r1_id = r1.id
        attach_photo(s, scrap_id=r1_id, src_path=str(img),
                     uploaded_by=seed['user'])
        create_scrap(s, work_order_id=seed['wo'],
                     operation_id=seed['op1'], qty_scrap=2,
                     reason=ScrapReason.MATERIAL,
                     description='Раковина',
                     reported_by=seed['user'])
        s.commit()

    with db_manager.get_session() as s:
        assert total_scrap_qty(s, days=30) == 5
        by_reason = dict((r[0], r[2]) for r in scrap_by_reason(s, days=30))
        assert by_reason.get('Ошибка оператора') == 3
        assert by_reason.get('Дефект материала') == 2
        top = scrap_by_operation(s, days=30, top=3)
        assert top and top[0][1] == 5

    # Проверим что файлы реально сохранены
    photos = list((Path('data/scrap') / str(r1_id)).iterdir())
    assert any(p.suffix == '.png' for p in photos)


# ──────────────────────────────────────────────────────────────────
# 10) Metrology
# ──────────────────────────────────────────────────────────────────

def test_metrology_calibration_updates_next_due(db_manager, seed):
    from modules.metrology import add_calibration, instruments_due_soon
    with db_manager.get_session() as s:
        inst = Instrument(inventory_no='M-001', name='Штангенциркуль',
                          type='ШЦ-150', range_str='0-150 мм',
                          cal_interval_months=12)
        s.add(inst)
        s.commit()
        iid = inst.id

    # Поверка год назад → next_cal_date уже прошло
    with db_manager.get_session() as s:
        add_calibration(s, instrument_id=iid,
                        performed_at=date.today() - timedelta(days=370),
                        organization='ВНИИМС', result='годен',
                        created_by=seed['user'])
        s.commit()

    with db_manager.get_session() as s:
        due = instruments_due_soon(s, days=30)
        assert any(i.id == iid for i in due)

    # Свежая поверка → выпадает из due
    with db_manager.get_session() as s:
        add_calibration(s, instrument_id=iid,
                        performed_at=date.today(),
                        organization='ВНИИМС', result='годен',
                        created_by=seed['user'])
        s.commit()
    with db_manager.get_session() as s:
        due = instruments_due_soon(s, days=30)
        assert not any(i.id == iid for i in due)
        inst = s.get(Instrument, iid)
        assert inst.next_cal_date is not None
        assert inst.next_cal_date > date.today() + timedelta(days=300)
