"""V12: Тесты OEE и цифрового двойника."""
import pytest
from database.models import Equipment, RouteStep


class TestDigitalTwin:
    def _seed(self, db_manager):
        with db_manager.get_session() as s:
            eq = Equipment(name='Токарный 16К20', model='16К20',
                          type='turning', power=7.5, cost_per_hour=500)
            s.add(eq)
            s.flush()

    def test_create_default_layout(self, db_manager):
        self._seed(db_manager)
        from modules.digital_twin import create_default_layout
        with db_manager.get_session() as s:
            layout = create_default_layout(s, 'Тестовый цех')
            assert layout.name == 'Тестовый цех'
            assert len(layout.machines) >= 1
            assert layout.width > 0

    def test_create_layout_empty(self, db_manager):
        from modules.digital_twin import create_default_layout
        with db_manager.get_session() as s:
            layout = create_default_layout(s)
            assert layout.name != ''

    def test_get_machine_statuses(self, db_manager):
        self._seed(db_manager)
        from modules.digital_twin import get_machine_statuses
        with db_manager.get_session() as s:
            machines = get_machine_statuses(s)
            assert isinstance(machines, list)
            if machines:
                assert machines[0].status in ('running', 'idle', 'offline', 'alarm')

    def test_calculate_oee(self, db_manager):
        self._seed(db_manager)
        from modules.digital_twin import calculate_oee
        with db_manager.get_session() as s:
            oee = calculate_oee(s, equipment_id=1, days=7)
            assert 0 <= oee.oee <= 1.5
            assert oee.equipment_name != ''

    def test_calculate_all_oee(self, db_manager):
        self._seed(db_manager)
        from modules.digital_twin import calculate_all_oee
        with db_manager.get_session() as s:
            results = calculate_all_oee(s, days=7)
            assert isinstance(results, list)

    def test_simulate_flow(self, db_manager):
        self._seed(db_manager)
        from modules.digital_twin import simulate_flow
        with db_manager.get_session() as s:
            flow = simulate_flow(s, hours=8, speedup=1)
            assert flow.total_time_hours == 8
            assert isinstance(flow.bottlenecks, list)

    def test_oee_color(self, db_manager):
        from modules.digital_twin import OEE
        low = OEE(equipment_id=1, equipment_name='', oee=0.4)
        assert low.color == '#d32f2f'
        mid = OEE(equipment_id=1, equipment_name='', oee=0.7)
        assert mid.color == '#f9a825'
        high = OEE(equipment_id=1, equipment_name='', oee=0.85)
        assert high.color == '#388e3c'

    def test_flow_simulation_defaults(self, db_manager):
        from modules.digital_twin import FlowSimulation
        fs = FlowSimulation(
            total_batches=0, completed_batches=0,
            bottlenecks=[], avg_queue_length=0.0, total_time_hours=0.0,
        )
        assert fs.total_batches == 0
