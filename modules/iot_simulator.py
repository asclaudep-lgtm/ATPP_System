"""IoT-симулятор телеметрии станков.

Генерирует правдоподобную телеметрию для демонстрации и тестирования.
Реальные станки не требуются.  Учитывает рабочие часы (8-17 с обедом
12-13) и выходные.

Запуск:  TelemetrySimulator(db_manager).start()
Остановка: TelemetrySimulator(db_manager).stop()
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, date as date_type
from typing import Optional, Callable, List
from threading import Thread, Event

from sqlalchemy.orm import Session

from database.models import Equipment
from modules.iot_collector import MachineTelemetry, store_telemetry


# ──────────────────────────────────────────────────────────────
# Simulated Machine
# ──────────────────────────────────────────────────────────────


class SimulatedMachine:
    """Один симулированный станок."""

    def __init__(self, equipment_id: int, name: str = '',
                 nominal_rpm: float = 1500.0,
                 nominal_power_kw: float = 10.0):
        self.equipment_id = equipment_id
        self.name = name
        self.nominal_rpm = nominal_rpm
        self.nominal_power = nominal_power_kw
        self.status = 'offline'
        self.rpm = 0.0
        self.power = 0.0
        self.feed = 0.0
        self.program = ''
        # Счётчик минут uptime для суммарной статистики
        self._uptime_min = 0

    def tick(self, is_working_hours: bool):
        """Один шаг симуляции (~1 мин)."""
        if not is_working_hours:
            self.status = 'offline'
            self.rpm = 0.0
            self.power = 0.0
            self.feed = 0.0
            return

        # 5% шанс аварии
        if random.random() < 0.02:
            self.status = 'alarm'
            self.rpm = 0.0
            self.power = self.nominal_power * 0.1
            self.feed = 0.0
        elif random.random() < 0.05:
            self.status = 'idle'
            self.rpm = 0.0
            self.power = self.nominal_power * 0.15
            self.feed = 0.0
        else:
            self.status = 'running'
            self.rpm = self.nominal_rpm * random.uniform(0.9, 1.1)
            self.power = self.nominal_power * random.uniform(0.7, 1.0)
            self.feed = random.uniform(50, 300)
            self._uptime_min += 1


# ──────────────────────────────────────────────────────────────
# Telemetry Simulator
# ──────────────────────────────────────────────────────────────


class TelemetrySimulator:
    """Генератор телеметрии для демо / тестирования.

    Пример:
        sim = TelemetrySimulator(db_manager)
        sim.load_from_db(session)
        sim.start()
        # ... работает в фоне ...
        sim.stop()
    """

    def __init__(self, db_manager,
                 machines: Optional[List[SimulatedMachine]] = None):
        self.db = db_manager
        self.machines: List[SimulatedMachine] = machines or []
        self._thread: Optional[Thread] = None
        self._stop = Event()
        self.on_telemetry: Optional[Callable[[MachineTelemetry], None]] = None
        self.speedup_factor: float = 1.0  # 1 = real-time, 60 = 1 min = 1 sec

    def add_machine(self, equipment_id: int, *, name: str = '',
                    nominal_rpm: float = 1500.0,
                    nominal_power: float = 10.0):
        self.machines.append(SimulatedMachine(
            equipment_id=equipment_id,
            name=name,
            nominal_rpm=nominal_rpm,
            nominal_power_kw=nominal_power,
        ))

    def load_from_db(self, session: Session):
        """Загрузить все Equipment как симулированные станки."""
        for eq in session.query(Equipment).all():
            rpm = 1500.0
            power = float(eq.power or 10.0)
            if 'фрез' in (eq.name or '').lower():
                rpm = 3000.0
            elif 'шлиф' in (eq.name or '').lower():
                rpm = 6000.0
            self.add_machine(eq.id, name=eq.name or f'EQ-{eq.id}',
                             nominal_rpm=rpm, nominal_power=power)

    def start(self):
        """Запустить симуляцию в фоновом потоке."""
        self._stop.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Остановить симуляцию."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _is_working_hours(self, dt: datetime) -> bool:
        """Проверить, рабочее ли сейчас время."""
        if dt.weekday() >= 5:  # суббота, воскресенье
            return False
        t = dt.time()
        if t.hour < 8 or t.hour >= 17:
            return False
        if 12 <= t.hour < 13:
            return False
        return True

    def _run(self):
        """Основной цикл симуляции."""
        interval = 60.0 / self.speedup_factor
        while not self._stop.is_set():
            now = datetime.now()
            working = self._is_working_hours(now)

            for m in self.machines:
                m.tick(working)

                telemetry = MachineTelemetry(
                    equipment_id=m.equipment_id,
                    status=m.status,
                    spindle_speed=round(m.rpm, 1),
                    feed_rate=round(m.feed, 1),
                    power_consumption=round(m.power, 2),
                    program_number=m.program or None,
                    reported_at=now,
                )

                # Сохранить в БД
                try:
                    with self.db.get_session() as s:
                        store_telemetry(s, telemetry=telemetry)
                except Exception:
                    pass

                # Callback (напр. для UI-обновления)
                if self.on_telemetry:
                    try:
                        self.on_telemetry(telemetry)
                    except Exception:
                        pass

            time.sleep(max(interval, 0.1))
