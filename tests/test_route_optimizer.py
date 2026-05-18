"""V12: Тесты AI-оптимизатора маршрутов."""
import pytest
from datetime import date, timedelta

from database.models import (
    Product, Material, TechProcess, Operation, Equipment, WorkOrder,
    WorkOrderStatus, WorkOrderItem, RouteStep, TPStatus, TechnologyType,
)


class TestRouteOptimizer:
    def _seed(self, db_manager):
        """Создать тестовые данные с несколькими ТП."""
        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()

            eq1 = Equipment(name='Токарный 16К20', model='16К20',
                           type='turning', power=7.5, cost_per_hour=500)
            eq2 = Equipment(name='Фрезерный 6Р13', model='6Р13',
                           type='milling', power=5.5, cost_per_hour=400)
            s.add_all([eq1, eq2])
            s.flush()

            # Первое изделие с ТП (токарная → фрезерная)
            p1 = Product(designation='AI-001', name='Вал',
                        material_id=mat.id, mass=5.0, accuracy_class='IT7',
                        blank_type='круг')
            s.add(p1)
            s.flush()

            tp1 = TechProcess(number='TP-AI-001', product_id=p1.id,
                            status=TPStatus.APPROVED,
                            technology_type=TechnologyType.MACHINING)
            s.add(tp1)
            s.flush()

            op1a = Operation(tech_process_id=tp1.id, number='005',
                           name='Токарная', equipment_id=eq1.id,
                           t_setup=10.0, t_piece=15.0, grade=4, sort_order=0)
            op1b = Operation(tech_process_id=tp1.id, number='010',
                           name='Фрезерная', equipment_id=eq2.id,
                           t_setup=8.0, t_piece=12.0, grade=3, sort_order=1)
            s.add_all([op1a, op1b])
            s.flush()

            # Второе изделие с ТП (токарная → сверлильная)
            p2 = Product(designation='AI-002', name='Втулка',
                        material_id=mat.id, mass=2.0, accuracy_class='IT8',
                        blank_type='труба')
            s.add(p2)
            s.flush()

            tp2 = TechProcess(number='TP-AI-002', product_id=p2.id,
                            status=TPStatus.APPROVED,
                            technology_type=TechnologyType.MACHINING)
            s.add(tp2)
            s.flush()

            eq3 = Equipment(name='Сверлильный 2М55', model='2М55',
                           type='drilling', power=3.0, cost_per_hour=300)
            s.add(eq3)
            s.flush()

            op2a = Operation(tech_process_id=tp2.id, number='005',
                           name='Токарная', equipment_id=eq1.id,
                           t_setup=8.0, t_piece=10.0, grade=4, sort_order=0)
            op2b = Operation(tech_process_id=tp2.id, number='010',
                           name='Сверлильная', equipment_id=eq3.id,
                           t_setup=5.0, t_piece=7.0, grade=3, sort_order=1)
            s.add_all([op2a, op2b])
            s.flush()

            # Третье изделие без ТП (для теста predict)
            p3 = Product(designation='AI-003', name='Шестерня',
                        material_id=mat.id, mass=3.0, accuracy_class='IT6',
                        blank_type='поковка')
            s.add(p3)
            s.flush()

            # Данные хронометража
            wo = WorkOrder(number='WO-CHRONO-001', product_id=p1.id,
                         tech_process_id=tp1.id, qty_total=10,
                         status=WorkOrderStatus.RELEASED,
                         due_date=date.today() + timedelta(days=7))
            s.add(wo)
            s.flush()

            woi = WorkOrderItem(
                work_order_id=wo.id, barcode='BC-CHRONO-001',
                serial='SN-001', qty=10,
            )
            s.add(woi)
            s.flush()

            from datetime import datetime as dt
            for i in range(5):
                rs = RouteStep(
                    work_order_item_id=woi.id, operation_id=op1a.id,
                    seq=i, status='DONE',
                    started_at=dt(2026, 5, 10, 8, 0),
                    finished_at=dt(2026, 5, 10, 8, 15 + i),
                )
                s.add(rs)
            s.flush()

    # ── 2.1 Sequence model ──

    def test_build_transition_model(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import _build_transition_model
        with db_manager.get_session() as s:
            model = _build_transition_model(s)
            assert isinstance(model, dict)
            assert len(model) > 0

    def test_predict_next_op(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import predict_next_op
        with db_manager.get_session() as s:
            preds = predict_next_op(s, current_ops=['Токарная'])
            assert isinstance(preds, list)
            if preds:
                assert preds[0].probability > 0

    def test_predict_next_op_empty(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import predict_next_op
        with db_manager.get_session() as s:
            preds = predict_next_op(s, current_ops=[])
            assert isinstance(preds, list)

    def test_predict_next_op_top_n(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import predict_next_op
        with db_manager.get_session() as s:
            preds = predict_next_op(s, current_ops=['Токарная'], top_n=2)
            assert len(preds) <= 2

    # ── 2.2 Multi-objective optimization ──

    def test_optimize_route(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import optimize_route
        with db_manager.get_session() as s:
            route = optimize_route(s, product_id=1)
            assert route.product_id == 1
            assert len(route.operations) > 0
            assert route.total_cost >= 0
            assert route.total_time >= 0
            assert 0 <= route.quality_score <= 1

    def test_optimize_route_custom_weights(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import optimize_route
        with db_manager.get_session() as s:
            route = optimize_route(
                s, product_id=1,
                weights={'cost': 0.7, 'time': 0.2, 'quality': 0.1},
            )
            assert len(route.operations) > 0

    def test_optimize_route_invalid_product(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import optimize_route
        with db_manager.get_session() as s:
            with pytest.raises(ValueError):
                optimize_route(s, product_id=999)

    # ── 2.3 Equipment assignment ──

    def test_assign_equipment(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import assign_equipment
        with db_manager.get_session() as s:
            ops = [
                {'name': 'Токарная', 't_piece': 15.0},
                {'name': 'Фрезерная', 't_piece': 12.0},
            ]
            assignments = assign_equipment(s, operations=ops, criteria='cost')
            assert isinstance(assignments, dict)
            assert len(assignments) <= len(ops)

    def test_assign_equipment_empty(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import assign_equipment
        with db_manager.get_session() as s:
            assignments = assign_equipment(s, operations=[], criteria='cost')
            assert assignments == {}

    def test_assign_equipment_time_criteria(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import assign_equipment
        with db_manager.get_session() as s:
            ops = [{'name': 'Токарная', 't_piece': 15.0}]
            assignments = assign_equipment(s, operations=ops, criteria='time')
            assert isinstance(assignments, dict)

    # ── 2.4 Time norm prediction ──

    def test_predict_time_norms(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import predict_time_norms
        with db_manager.get_session() as s:
            estimate = predict_time_norms(s, operation_params={
                'name': 'Токарная', 'power': 7.5,
                'cost_per_hour': 500, 'grade': 4, 't_setup': 10.0,
            })
            assert estimate.t_piece > 0
            assert estimate.t_setup > 0
            assert 0 <= estimate.confidence <= 1

    def test_predict_time_norms_fallback(self, db_manager):
        """Без данных — возвращает значения по умолчанию."""
        from modules.route_optimizer import predict_time_norms
        with db_manager.get_session() as s:
            estimate = predict_time_norms(s, operation_params={
                'name': 'Неизвестная', 't_piece': 20.0, 't_setup': 10.0,
            })
            assert estimate.t_piece == 20.0

    # ── 2.5 Chronometry feedback ──

    def test_calibrate_from_chrono(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import calibrate_from_chrono
        with db_manager.get_session() as s:
            report = calibrate_from_chrono(s, threshold_pct=10.0)
            assert report.operations_checked >= 0
            assert report.avg_deviation_pct >= 0
            assert isinstance(report.recommendations, list)

    # ── 2.6 Route generation ──

    def test_generate_route_sequence(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import generate_route_sequence
        with db_manager.get_session() as s:
            route = generate_route_sequence(s, product_id=1, max_ops=5)
            assert isinstance(route, list)
            assert len(route) <= 5

    def test_generate_route_sequence_invalid(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import generate_route_sequence
        with db_manager.get_session() as s:
            route = generate_route_sequence(s, product_id=999)
            assert route == []

    # ── Data classes ──

    def test_op_sequence_prediction(self):
        from modules.route_optimizer import OpSequencePrediction
        p = OpSequencePrediction(
            operation_name='Токарная', probability=0.8,
            equipment_name='16К20', t_setup=10.0, t_piece=15.0, grade=4,
        )
        assert p.probability == 0.8
        assert p.operation_name == 'Токарная'

    def test_time_estimate(self):
        from modules.route_optimizer import TimeEstimate
        e = TimeEstimate(t_piece=12.5, t_setup=8.0, confidence=0.85)
        assert e.t_piece == 12.5

    def test_calibration_report_defaults(self):
        from modules.route_optimizer import CalibrationReport
        r = CalibrationReport(
            operations_checked=10, operations_updated=3,
            avg_deviation_pct=12.0, max_deviation_pct=35.0,
        )
        assert r.operations_checked == 10
        assert r.recommendations == []

    def test_optimized_route_scores(self, db_manager):
        self._seed(db_manager)
        from modules.route_optimizer import optimize_route
        with db_manager.get_session() as s:
            route = optimize_route(s, product_id=1)
            assert 'cost_score' in route.scores
            assert 'time_score' in route.scores
            assert 'quality_score' in route.scores
            assert 0 <= route.scores['cost_score'] <= 1
