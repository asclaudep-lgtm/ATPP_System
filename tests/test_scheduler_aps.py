"""Тесты APS-планировщика."""
import pytest
from datetime import date, timedelta

from database.models import (Product, Material, TechProcess, Operation,
                              WorkOrder, WorkOrderStatus, Equipment,
                              Workshop)


class TestSchedulerAPS:
    def _seed_wo(self, db_manager):
        """Создать тестовый наряд с ТП и операциями."""
        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()

            p = Product(designation='SCHED-001', name='Вал',
                       material_id=mat.id, mass=5.0)
            s.add(p)
            s.flush()

            eq = Equipment(name='Токарный станок', model='16К20',
                          type='turning', power=7.5, cost_per_hour=500)
            s.add(eq)
            s.flush()

            tp = TechProcess(number='TP-SCHED-001', product_id=p.id)
            s.add(tp)
            s.flush()

            op = Operation(tech_process_id=tp.id, number='005',
                          name='Токарная', equipment_id=eq.id,
                          t_setup=10.0, t_piece=15.0, sort_order=0)
            s.add(op)
            s.flush()

            wo = WorkOrder(number='WO-SCHED-001',
                          tech_process_id=tp.id,
                          product_id=p.id,
                          qty_total=10,
                          status=WorkOrderStatus.RELEASED,
                          priority=5,
                          due_date=date.today() + timedelta(days=14))
            s.add(wo)
            s.flush()

    def test_schedule_aps_basic(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=30)
            assert len(result.schedule) >= 1
            assert result.metrics.total_operations_scheduled >= 1

    def test_schedule_aps_metrics(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=30)
            assert result.metrics.total_orders_scheduled >= 1

    def test_fifo_still_works(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_open_orders
        with db_manager.get_session() as s:
            sched = schedule_open_orders(s, horizon_days=30)
            assert len(sched) >= 1
            for op in sched:
                assert op.start < op.finish

    def test_estimate_setup_time_same(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import estimate_setup_time
        with db_manager.get_session() as s:
            t = estimate_setup_time(s, from_product_id=1,
                                    to_product_id=1, equipment_id=1)
            assert t == 0.0

    def test_plan_for_week(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import plan_for_week
        from datetime import date as d
        with db_manager.get_session() as s:
            plan = plan_for_week(s, week_start=d.today())
            assert 'work_order_ids' in plan
            assert 'total_hours' in plan

    def test_preloaded_equipment_map(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import get_preloaded_equipment_map
        with db_manager.get_session() as s:
            emap = get_preloaded_equipment_map(s)
            assert isinstance(emap, dict)
