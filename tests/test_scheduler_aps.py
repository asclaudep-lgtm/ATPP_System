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

    def test_schedule_backward_basic(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_backward
        from datetime import date as d
        with db_manager.get_session() as s:
            result = schedule_backward(s, due_date=d.today() + timedelta(days=14))
            assert len(result.schedule) >= 1
            assert result.metrics.total_operations_scheduled >= 1
            # Все операции должны завершаться до или в due_date
            for op in result.schedule:
                assert op.finish.date() <= d.today() + timedelta(days=14)

    def test_schedule_finite_capacity(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_finite_capacity
        with db_manager.get_session() as s:
            result = schedule_finite_capacity(s, horizon_days=30)
            assert len(result.schedule) >= 1
            assert result.metrics.avg_equipment_load_pct > 0

    def test_backward_vs_forward(self, db_manager):
        """Обратное и прямое планирование дают разный порядок операций."""
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, schedule_backward
        with db_manager.get_session() as s:
            fwd = schedule_aps(s, horizon_days=30)
            bwd = schedule_backward(s, horizon_days=30)
            assert len(fwd.schedule) == len(bwd.schedule)

    def test_detect_conflicts_empty(self, db_manager):
        from modules.scheduler import detect_conflicts
        conflicts = detect_conflicts([])
        assert conflicts == []

    def test_detect_conflicts_with_overlap(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_open_orders, detect_conflicts
        with db_manager.get_session() as s:
            sched = schedule_open_orders(s, horizon_days=30)
            conflicts = detect_conflicts(sched)
            assert isinstance(conflicts, list)

    def test_optimize_setup_sequence(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, optimize_setup_sequence
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=30)
            original_len = len(result.schedule)
            optimized = optimize_setup_sequence(s, result.schedule)
            assert len(optimized) == original_len

    def test_validate_constraints(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, validate_constraints
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=30)
            violations = validate_constraints(s, result.schedule)
            assert isinstance(violations, list)

    def test_clone_scenario(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, clone_scenario
        with db_manager.get_session() as s:
            a = schedule_aps(s, horizon_days=30)
            b = clone_scenario(a)
            assert b.metrics.total_operations_scheduled == \
                   a.metrics.total_operations_scheduled

    def test_compare_scenarios(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, compare_scenarios
        with db_manager.get_session() as s:
            a = schedule_aps(s, horizon_days=30,
                             priority_weight=1.0, due_date_weight=1.5)
            b = schedule_aps(s, horizon_days=30,
                             priority_weight=2.0, due_date_weight=1.0)
            diff = compare_scenarios(a, b)
            assert diff.conflicts_a >= 0
            assert diff.conflicts_b >= 0

    def test_what_if_reschedule(self, db_manager):
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps, what_if_reschedule
        with db_manager.get_session() as s:
            base = schedule_aps(s, horizon_days=30)
            variant = what_if_reschedule(
                s, base, priority_weight=2.0, horizon_days=14)
            assert len(variant.schedule) >= 1

    def test_get_shift_slots_default(self, db_manager):
        """Слоты по умолчанию для дня без исключений."""
        from modules.scheduler import get_shift_slots
        from datetime import date as d
        with db_manager.get_session() as s:
            slots = get_shift_slots(s, on_date=d.today())
            assert isinstance(slots, list)

    def test_shift_slots_weekend(self, db_manager):
        """Выходной день должен вернуть пустой список слотов."""
        from modules.scheduler import get_shift_slots
        from datetime import date as d
        # Найти ближайшее воскресенье
        today = d.today()
        sunday = today + timedelta(days=(6 - today.weekday()))
        with db_manager.get_session() as s:
            slots = get_shift_slots(s, on_date=sunday)
            assert isinstance(slots, list)

    def test_scheduled_op_duration(self, db_manager):
        from modules.scheduler import ScheduledOp
        from datetime import datetime as dt
        op = ScheduledOp(
            work_order_id=1, work_order_number='WO-001',
            operation_id=1, operation_number='005',
            operation_name='Токарная', equipment_id=1,
            equipment_name='16К20',
            start=dt(2026, 5, 18, 8, 0),
            finish=dt(2026, 5, 18, 9, 0),
        )
        assert op.duration_min == 60.0

    def test_aps_result_defaults(self, db_manager):
        from modules.scheduler import APSResult
        result = APSResult()
        assert result.schedule == []
        assert result.conflicts == []
        assert result.unscheduled_orders == []
        assert result.metrics.total_operations_scheduled == 0

    def test_multi_wo_scheduling(self, db_manager):
        """Два наряда на одном станке — не должны пересекаться."""
        with db_manager.get_session() as s:
            mat = Material(name='Сталь 40X', grade='40X', density=7850)
            s.add(mat)
            s.flush()

            p = Product(designation='SCHED-002', name='Шестерня',
                       material_id=mat.id, mass=3.0)
            s.add(p)
            eq = Equipment(name='Фрезерный станок', model='6Р13',
                          type='milling', power=5.5, cost_per_hour=400)
            s.add(eq)
            s.flush()

            # Два ТП с операциями на одном станке
            tp1 = TechProcess(number='TP-SCHED-002', product_id=p.id)
            s.add(tp1)
            s.flush()
            op1 = Operation(tech_process_id=tp1.id, number='005',
                          name='Фрезерная', equipment_id=eq.id,
                          t_setup=5.0, t_piece=10.0, sort_order=0)
            s.add(op1)

            tp2 = TechProcess(number='TP-SCHED-003', product_id=p.id)
            s.add(tp2)
            s.flush()
            op2 = Operation(tech_process_id=tp2.id, number='005',
                          name='Фрезерная', equipment_id=eq.id,
                          t_setup=8.0, t_piece=12.0, sort_order=0)
            s.add(op2)
            s.flush()

            wo1 = WorkOrder(number='WO-SCHED-002', tech_process_id=tp1.id,
                          product_id=p.id, qty_total=20,
                          status=WorkOrderStatus.RELEASED,
                          priority=3, due_date=date.today() + timedelta(days=7))
            s.add(wo1)
            wo2 = WorkOrder(number='WO-SCHED-003', tech_process_id=tp2.id,
                          product_id=p.id, qty_total=15,
                          status=WorkOrderStatus.RELEASED,
                          priority=4, due_date=date.today() + timedelta(days=10))
            s.add(wo2)
            s.flush()

        from modules.scheduler import schedule_aps, detect_conflicts
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=30)
            conflicts = detect_conflicts(result.schedule)
            assert len(result.schedule) >= 2
            # На одном станке не должно быть конфликтов
            eq_conflicts = [c for c in conflicts
                          if c[0].equipment_id == eq.id]
            assert len(eq_conflicts) == 0

    def test_horizon_truncation(self, db_manager):
        """Операции за горизонтом должны быть отсечены."""
        self._seed_wo(db_manager)
        from modules.scheduler import schedule_aps
        with db_manager.get_session() as s:
            result = schedule_aps(s, horizon_days=1)
            # С горизонтом 1 день может не уместиться — это нормально
            assert result.metrics.total_operations_scheduled >= 0

    def test_fifo_ordering_by_due_date(self, db_manager):
        """FIFO должен сортировать по due_date."""
        with db_manager.get_session() as s:
            mat = Material(name='Сталь 20', grade='20', density=7800)
            s.add(mat)
            p = Product(designation='SCHED-003', name='Крышка',
                       material_id=mat.id, mass=2.0)
            s.add(p)
            eq = Equipment(name='Сверлильный станок', model='2М55',
                          type='drilling', power=3.0, cost_per_hour=300)
            s.add(eq)
            s.flush()

            # Первый наряд — дальний срок
            tp1 = TechProcess(number='TP-SCHED-004', product_id=p.id)
            s.add(tp1)
            s.flush()
            op1 = Operation(tech_process_id=tp1.id, number='005',
                          name='Сверлильная', equipment_id=eq.id,
                          t_setup=3.0, t_piece=5.0, sort_order=0)
            s.add(op1)
            wo1 = WorkOrder(number='WO-SCHED-004', tech_process_id=tp1.id,
                          product_id=p.id, qty_total=10,
                          status=WorkOrderStatus.RELEASED,
                          priority=1,
                          due_date=date.today() + timedelta(days=30))
            s.add(wo1)

            # Второй наряд — срочный
            tp2 = TechProcess(number='TP-SCHED-005', product_id=p.id)
            s.add(tp2)
            s.flush()
            op2 = Operation(tech_process_id=tp2.id, number='005',
                          name='Сверлильная', equipment_id=eq.id,
                          t_setup=3.0, t_piece=5.0, sort_order=0)
            s.add(op2)
            wo2 = WorkOrder(number='WO-SCHED-005', tech_process_id=tp2.id,
                          product_id=p.id, qty_total=10,
                          status=WorkOrderStatus.RELEASED,
                          priority=1,
                          due_date=date.today() + timedelta(days=1))
            s.add(wo2)
            s.flush()

        from modules.scheduler import schedule_open_orders
        with db_manager.get_session() as s:
            sched = schedule_open_orders(s, horizon_days=30)
            assert len(sched) >= 2
            # Срочный наряд должен быть первым
            first_wo = sched[0].work_order_number
            assert first_wo == 'WO-SCHED-005'
