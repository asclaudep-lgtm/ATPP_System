"""V12: Тесты MES-интеграции."""
from database.models import Equipment


class TestMESAdapter:
    def _seed(self, db_manager):
        with db_manager.get_session() as s:
            eq = Equipment(name='Токарный 16К20', model='16К20',
                          type='turning', power=7.5, cost_per_hour=500)
            s.add(eq)
            s.flush()

    def test_simulate_opcua_read(self, db_manager):
        from modules.mes_adapter import simulate_opcua_read
        reading = simulate_opcua_read(1, '16К20')
        assert reading.equipment_id == 1
        assert reading.status in ('running', 'idle', 'offline', 'alarm')
        assert reading.spindle_speed >= 0
        assert isinstance(reading.timestamp, __import__('datetime').datetime)

    def test_store_machine_reading(self, db_manager):
        self._seed(db_manager)
        from modules.mes_adapter import simulate_opcua_read, store_machine_reading
        reading = simulate_opcua_read(1)
        with db_manager.get_session() as s:
            store_machine_reading(s, reading)
            s.commit()

    def test_collect_opcua(self, db_manager):
        self._seed(db_manager)
        from modules.mes_adapter import collect_opcua
        with db_manager.get_session() as s:
            readings = collect_opcua(s, equipment_ids=[1], count=3)
            assert len(readings) == 3

    def test_calculate_spc(self, db_manager):
        from modules.mes_adapter import calculate_spc
        import numpy as np
        np.random.seed(42)
        measurements = list(np.random.normal(50.0, 0.1, 100))

        result = calculate_spc(
            measurements, nominal=50.0,
            upper_spec=50.5, lower_spec=49.5,
            dimension_name='Диаметр Ø50',
        )
        assert result.cp > 0
        assert result.cpk > 0
        assert result.measurements_count == 100
        assert result.dimension_name == 'Диаметр Ø50'

    def test_calculate_spc_out_of_control(self, db_manager):
        from modules.mes_adapter import calculate_spc
        import numpy as np
        np.random.seed(42)
        # Специально сдвинутые измерения
        measurements = list(np.random.normal(50.4, 0.15, 100))

        result = calculate_spc(
            measurements, nominal=50.0,
            upper_spec=50.3, lower_spec=49.7,
        )
        assert result.cpk < result.cp or result.cpk <= 1.0

    def test_calculate_spc_small_sample(self, db_manager):
        """Маленькая выборка — возвращает cp=cpk=0."""
        from modules.mes_adapter import calculate_spc
        result = calculate_spc(
            [50.0, 50.1], nominal=50.0,
            upper_spec=50.5, lower_spec=49.5,
        )
        assert result.cp == 0
        assert result.measurements_count == 2

    def test_tool_life_status(self, db_manager):
        from modules.mes_adapter import ToolLifeStatus
        ts = ToolLifeStatus(
            tool_id=1, tool_name='Резец Т15К6', inventory_no='INV-001',
            cycles_used=85, cycles_limit=100, remaining_pct=15.0,
        )
        assert ts.remaining_pct == 15.0
        assert not ts.needs_replacement

    def test_check_tool_life_empty(self, db_manager):
        from modules.mes_adapter import check_tool_life
        with db_manager.get_session() as s:
            results = check_tool_life(s)
            assert isinstance(results, list)

    def test_increment_tool_cycles_invalid(self, db_manager):
        from modules.mes_adapter import increment_tool_cycles
        with db_manager.get_session() as s:
            result = increment_tool_cycles(s, tool_id=999, cycles=1)
            assert result is None
