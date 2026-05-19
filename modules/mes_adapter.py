"""V12: MES Integration — OPC-UA collector, SPC, tool life tracking.

OPC-UA коллектор (альтернатива MQTT), Statistical Process Control,
учёт стойкости инструмента.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session


# ═══════════════════════════════════════════════════════════════════
# 6.1 OPC-UA Collector (simulator-based, real OPC-UA requires async)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class OPCUANode:
    """Тег OPC-UA сервера."""
    node_id: str
    display_name: str
    value: float = 0.0
    data_type: str = 'Double'
    timestamp: Optional[datetime] = None


@dataclass
class MachineReading:
    """Показания со станка через OPC-UA."""
    equipment_id: int
    timestamp: datetime
    status: str = 'idle'
    spindle_speed: float = 0.0
    feed_rate: float = 0.0
    power: float = 0.0
    program_number: Optional[str] = None
    temperature: float = 25.0
    vibration: float = 0.0


def simulate_opcua_read(equipment_id: int,
                        machine_name: str = '') -> MachineReading:
    """Симулировать чтение OPC-UA тегов для тестирования."""
    from random import random, seed
    seed(hash(equipment_id) ^ hash(datetime.now().second))

    status_roll = random()
    if status_roll < 0.02:
        status = 'alarm'
    elif status_roll < 0.07:
        status = 'idle'
    elif status_roll < 0.10:
        status = 'offline'
    else:
        status = 'running'

    return MachineReading(
        equipment_id=equipment_id,
        timestamp=datetime.now(),
        status=status,
        spindle_speed=random() * 3000 if status == 'running' else 0,
        feed_rate=random() * 500 if status == 'running' else 0,
        power=random() * 15 if status == 'running' else random() * 2,
        program_number=f'PGM-{int(random()*100):04d}' if status == 'running' else None,
        temperature=25 + random() * 40 if status == 'running' else 25,
        vibration=random() * 5 if status == 'running' else random() * 0.5,
    )


def store_machine_reading(session: Session,
                          reading: MachineReading) -> None:
    """Сохранить показания в БД (MachineStatus)."""
    from database.models._v9 import MachineStatus
    ms = MachineStatus(
        equipment_id=reading.equipment_id,
        status=reading.status,
        recorded_at=reading.timestamp,
        reported_at=reading.timestamp,
        spindle_speed=reading.spindle_speed,
        feed_rate=reading.feed_rate,
        power_consumption=reading.power,
        program_number=reading.program_number,
        is_simulated=True,
    )
    session.add(ms)


def collect_opcua(session: Session, *,
                  equipment_ids: List[int],
                  count: int = 10) -> List[MachineReading]:
    """Собрать показания с перечисленных станков (симуляция)."""
    readings = []
    for _ in range(count):
        for eq_id in equipment_ids:
            r = simulate_opcua_read(eq_id)
            readings.append(r)
            store_machine_reading(session, r)
    return readings


# ═══════════════════════════════════════════════════════════════════
# 6.3 SPC — Statistical Process Control
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SPCResult:
    """Результат SPC-анализа."""
    dimension_name: str
    nominal: float
    upper_spec: float
    lower_spec: float
    mean: float
    stddev: float
    cp: float
    cpk: float
    measurements_count: int
    in_control: bool = True
    xbar_violations: List[int] = field(default_factory=list)
    r_violations: List[int] = field(default_factory=list)


def calculate_spc(measurements: List[float], *,
                  nominal: float,
                  upper_spec: float,
                  lower_spec: float,
                  subgroup_size: int = 5,
                  dimension_name: str = 'Размер',
                  ) -> SPCResult:
    """Рассчитать Cp, Cpk и контрольные карты X-bar / R.

    measurements: список измерений в хронологическом порядке.
    subgroup_size: размер подгруппы для X-bar/R-chart.
    """
    if len(measurements) < 10:
        return SPCResult(
            dimension_name=dimension_name,
            nominal=nominal, upper_spec=upper_spec,
            lower_spec=lower_spec,
            mean=np.mean(measurements) if measurements else 0,
            stddev=np.std(measurements) if measurements else 0,
            cp=0, cpk=0, measurements_count=len(measurements),
        )

    arr = np.array(measurements, dtype=np.float64)
    mean = np.mean(arr)
    stddev = np.std(arr, ddof=1)

    # Cp = (USL - LSL) / (6 * sigma)
    spec_range = upper_spec - lower_spec
    cp = spec_range / (6 * stddev) if stddev > 0 else 0.0

    # Cpk = min((USL - mean), (mean - LSL)) / (3 * sigma)
    cpk_upper = (upper_spec - mean) / (3 * stddev) if stddev > 0 else 0.0
    cpk_lower = (mean - lower_spec) / (3 * stddev) if stddev > 0 else 0.0
    cpk = min(cpk_upper, cpk_lower)

    # X-bar / R-chart
    n_subgroups = len(arr) // subgroup_size
    xbar_violations = []
    r_violations = []

    if n_subgroups >= 4:
        subgroups = arr[:n_subgroups * subgroup_size].reshape(
            n_subgroups, subgroup_size)
        xbars = np.mean(subgroups, axis=1)
        ranges = np.ptp(subgroups, axis=1)

        xbar_mean = np.mean(xbars)
        r_mean = np.mean(ranges)

        # A2 constant for n=5 is 0.577
        a2 = 0.577
        ucl_xbar = xbar_mean + a2 * r_mean
        lcl_xbar = xbar_mean - a2 * r_mean

        # D3, D4 for n=5: D3=0, D4=2.114
        ucl_r = 2.114 * r_mean
        lcl_r = 0.0

        xbar_violations = [
            i + 1 for i, v in enumerate(xbars)
            if v > ucl_xbar or v < lcl_xbar
        ]
        r_violations = [
            i + 1 for i, v in enumerate(ranges)
            if v > ucl_r
        ]

    in_control = len(xbar_violations) == 0 and len(r_violations) == 0

    return SPCResult(
        dimension_name=dimension_name,
        nominal=nominal, upper_spec=upper_spec,
        lower_spec=lower_spec,
        mean=round(mean, 4),
        stddev=round(stddev, 4),
        cp=round(cp, 3),
        cpk=round(cpk, 3),
        measurements_count=len(measurements),
        in_control=in_control,
        xbar_violations=xbar_violations,
        r_violations=r_violations,
    )


# ═══════════════════════════════════════════════════════════════════
# 6.4 Tool life tracking
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ToolLifeStatus:
    """Статус износа инструмента."""
    tool_id: int
    tool_name: str
    inventory_no: str
    cycles_used: int
    cycles_limit: int
    remaining_pct: float
    needs_replacement: bool = False
    warning: bool = False


def check_tool_life(session: Session, *,
                    warning_threshold: float = 20.0,
                    critical_threshold: float = 5.0) -> List[ToolLifeStatus]:
    """Проверить износ оснастки.

    Использует wear_percent (0-100%) для оценки необходимости замены.
    """
    from database.models._v9 import ToolingItem

    tools = session.query(ToolingItem).all()

    results = []
    for tool in tools:
        wear = tool.wear_percent or 0
        remaining = 100.0 - wear
        remaining_pct = remaining

        needs = remaining_pct <= critical_threshold
        warn = remaining_pct <= warning_threshold and not needs

        results.append(ToolLifeStatus(
            tool_id=tool.id,
            tool_name=tool.name or f'Оснастка #{tool.id}',
            inventory_no=tool.inventory_no or '',
            cycles_used=wear,
            cycles_limit=100,
            remaining_pct=round(remaining_pct, 1),
            needs_replacement=needs,
            warning=warn,
        ))

    return results


def increment_tool_cycles(session: Session, *,
                          tool_id: int,
                          cycles: int = 1) -> Optional[ToolLifeStatus]:
    """Увеличить износ оснастки (wear_percent)."""
    from database.models._v9 import ToolingItem

    tool = session.get(ToolingItem, tool_id)
    if not tool:
        return None

    tool.wear_percent = min(100, (tool.wear_percent or 0) + cycles)

    remaining = 100.0 - tool.wear_percent
    remaining_pct = remaining

    session.flush()

    return ToolLifeStatus(
        tool_id=tool.id,
        tool_name=tool.name or '',
        inventory_no=tool.inventory_no or '',
        cycles_used=tool.wear_percent,
        cycles_limit=100,
        remaining_pct=round(remaining_pct, 1),
        needs_replacement=remaining_pct <= 5.0,
        warning=5.0 < remaining_pct <= 20.0,
    )
