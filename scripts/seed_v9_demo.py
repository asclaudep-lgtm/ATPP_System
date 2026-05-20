"""
Сидер для v9-демо: создаёт записи в новых таблицах,
чтобы виджеты не были пустыми на скриншотах.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.db_manager import DatabaseManager
from database.models import (
    ECN,
    ECNApproval,
    ECNStatus,
    Instrument,
    InstrumentStatus,
    Material,
    MaterialBatch,
    Operation,
    Product,
    RouteStep,
    RouteStepStatus,
    ScrapDecision,
    ScrapReason,
    ScrapRecord,
    SignerRole,
    TechProcess,
    ToolingIssue,
    ToolingItem,
    ToolingStatus,
    User,
    WorkOrder,
    WorkOrderItem,
)


def main():
    db = DatabaseManager('sqlite:///data/atpp.db')
    db.init_database()
    with db.get_session() as s:
        # Найдём существующего пользователя (admin)
        u = s.query(User).filter(User.username == 'admin').first()
        if u is None:
            print('admin не найден — пропуск')
            return
        u_id = u.id

        # Оснастка
        if not s.query(ToolingItem).first():
            items = [
                ToolingItem(inventory_no='ОСН-001', name='Кондуктор сверлильный К-1',
                            location='Стеллаж А-3', status=ToolingStatus.AVAILABLE,
                            wear_percent=5, cost=42000),
                ToolingItem(inventory_no='ОСН-002', name='Приспособление фрезерное Ф-1',
                            location='Стеллаж А-3', status=ToolingStatus.ISSUED,
                            wear_percent=22, cost=68000),
                ToolingItem(inventory_no='ОСН-003', name='Штамп вытяжной Ш-15',
                            location='Цех 2, стенд 7', status=ToolingStatus.REPAIR,
                            wear_percent=70, cost=185000),
                ToolingItem(inventory_no='ОСН-004', name='Зажимной патрон 3-х кулачк.',
                            location='Стеллаж Б-1', status=ToolingStatus.AVAILABLE,
                            wear_percent=12, cost=24000),
                ToolingItem(inventory_no='ОСН-005', name='Кондуктор сверлильный К-2',
                            location='Стеллаж А-3', status=ToolingStatus.AVAILABLE,
                            wear_percent=0, cost=51000),
            ]
            s.add_all(items)
            s.flush()
            # Активная выдача
            iss = ToolingIssue(tooling_item_id=items[1].id,
                               issued_to=u_id, issued_by=u_id,
                               issued_at=datetime.now() - timedelta(days=2),
                               notes='Под наряд WO-2026-001')
            s.add(iss)

        # Материал-партии (нужен Material)
        mat = s.query(Material).first()
        if mat and not s.query(MaterialBatch).first():
            b1 = MaterialBatch(material_id=mat.id, lot_no='LOT-2025-A12',
                               qty_received=500, qty_reserved=120,
                               qty_consumed=60, unit='кг',
                               supplier='ОАО «Мечел»',
                               received_date=date.today() - timedelta(days=18),
                               notes='Прокат круг 50')
            b2 = MaterialBatch(material_id=mat.id, lot_no='LOT-2025-B07',
                               qty_received=300, qty_reserved=50,
                               qty_consumed=200, unit='кг',
                               supplier='ОАО «Северсталь»',
                               received_date=date.today() - timedelta(days=42))
            s.add_all([b1, b2])

        # Метрология
        if not s.query(Instrument).first():
            insts = [
                Instrument(inventory_no='СИ-001', name='Штангенциркуль ШЦ-150',
                           type='ШЦ', range_str='0-150 мм', accuracy='0.02',
                           last_cal_date=date.today() - timedelta(days=350),
                           next_cal_date=date.today() + timedelta(days=15),
                           cal_interval_months=12,
                           status=InstrumentStatus.ACTIVE),
                Instrument(inventory_no='СИ-002', name='Микрометр МК 0-25',
                           type='МК', range_str='0-25 мм', accuracy='0.01',
                           last_cal_date=date.today() - timedelta(days=395),
                           next_cal_date=date.today() - timedelta(days=30),
                           cal_interval_months=12,
                           status=InstrumentStatus.EXPIRED),
                Instrument(inventory_no='СИ-003', name='Калибр-пробка Ø8H7',
                           type='Калибр', range_str='Ø8 H7', accuracy='+0.015/0',
                           last_cal_date=date.today() - timedelta(days=120),
                           next_cal_date=date.today() + timedelta(days=245),
                           cal_interval_months=12,
                           status=InstrumentStatus.ACTIVE),
                Instrument(inventory_no='СИ-004', name='Угольник 90° L-200',
                           type='Угольник', range_str='200 мм', accuracy='3 кл.',
                           last_cal_date=date.today() - timedelta(days=720),
                           next_cal_date=date.today() - timedelta(days=355),
                           cal_interval_months=12,
                           status=InstrumentStatus.EXPIRED),
            ]
            s.add_all(insts)

        # Брак
        wo = s.query(WorkOrder).first()
        op = s.query(Operation).first()
        if wo and op and not s.query(ScrapRecord).first():
            scraps = [
                ScrapRecord(work_order_id=wo.id, operation_id=op.id,
                            qty_scrap=2, reason=ScrapReason.MATERIAL,
                            description='Раковина в материале',
                            decision=ScrapDecision.SCRAP,
                            reported_by=u_id, decided_by=u_id,
                            reported_at=datetime.now() - timedelta(days=4),
                            decided_at=datetime.now() - timedelta(days=4)),
                ScrapRecord(work_order_id=wo.id, operation_id=op.id,
                            qty_scrap=1, reason=ScrapReason.OPERATOR,
                            description='Сорвана резьба М6',
                            decision=ScrapDecision.REWORK,
                            reported_by=u_id, decided_by=u_id,
                            reported_at=datetime.now() - timedelta(days=2),
                            decided_at=datetime.now() - timedelta(days=2)),
                ScrapRecord(work_order_id=wo.id, operation_id=op.id,
                            qty_scrap=3, reason=ScrapReason.SETUP,
                            description='Сбита нулевая точка ЧПУ',
                            decision=ScrapDecision.PENDING,
                            reported_by=u_id,
                            reported_at=datetime.now() - timedelta(hours=12)),
            ]
            s.add_all(scraps)

        # ECN
        if not s.query(ECN).first():
            tp = s.query(TechProcess).first()
            prod = s.query(Product).first()
            e = ECN(number='ECN-2025-001',
                    title='Замена шероховатости Ra 3.2 на Ra 1.6',
                    reason='Требование заказчика — повышение долговечности',
                    proposed_change='В операции 015 заменить Ra 3.2 на Ra 1.6, '
                                    'добавить операцию 020 «Шлифовальная»',
                    status=ECNStatus.UNDER_REVIEW,
                    created_by=u_id,
                    product_id=prod.id if prod else None,
                    tech_process_id=tp.id if tp else None,
                    created_at=datetime.now() - timedelta(days=1))
            s.add(e)
            s.flush()
            s.add_all([
                ECNApproval(ecn_id=e.id, role=SignerRole.CHIEF_TECH.value,
                            decision='APPROVED', decided_at=datetime.now(),
                            user_id=u_id),
                ECNApproval(ecn_id=e.id, role=SignerRole.QC.value,
                            decision='PENDING'),
                ECNApproval(ecn_id=e.id, role=SignerRole.APPROVER.value,
                            decision='PENDING'),
            ])

        # RouteStep — пара завершённых, чтобы загрузка оборудования была не нулевой
        if not s.query(RouteStep).first():
            items = s.query(WorkOrderItem).limit(3).all()
            ops = s.query(Operation).limit(2).all()
            if items and ops:
                base = datetime.now() - timedelta(days=2)
                for i, it in enumerate(items):
                    for j, o in enumerate(ops):
                        st = base + timedelta(hours=i * 4 + j)
                        fn = st + timedelta(minutes=45 + j * 10)
                        s.add(RouteStep(work_order_item_id=it.id,
                                        operation_id=o.id, seq=j + 1,
                                        status=RouteStepStatus.DONE,
                                        started_at=st, finished_at=fn))

        s.commit()
        print('Seed v9 OK.')


if __name__ == '__main__':
    main()
