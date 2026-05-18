"""V12: Цифровой двойник цеха.

2D glass-box планировка, real-time статус станков через IoT,
симуляция производственного потока, OEE-дашборд.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import Equipment
from database.models._v10_v14 import ShiftType


@dataclass
class MachinePosition:
    """Позиция станка на плане цеха."""
    id: int
    equipment_id: int
    name: str
    model: str = ''
    x: float = 0.0
    y: float = 0.0
    width: float = 80.0
    height: float = 60.0
    rotation: float = 0.0
    status: str = 'offline'  # running, idle, offline, alarm


@dataclass
class WorkshopLayout:
    """План цеха с координатами станков."""
    name: str
    width: float = 1200.0
    height: float = 800.0
    machines: List[MachinePosition] = field(default_factory=list)


@dataclass
class OEE:
    """Overall Equipment Effectiveness."""
    equipment_id: int
    equipment_name: str
    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0
    oee: float = 0.0

    @property
    def oee_pct(self) -> float:
        return self.oee * 100.0

    @property
    def color(self) -> str:
        if self.oee < 0.6:
            return '#d32f2f'
        elif self.oee < 0.75:
            return '#f9a825'
        return '#388e3c'


@dataclass
class FlowSimulation:
    """Результат симуляции производственного потока."""
    total_batches: int
    completed_batches: int
    bottlenecks: List[str]
    avg_queue_length: float
    total_time_hours: float


# ═══════════════════════════════════════════════════════════════════
# 2D Layout
# ═══════════════════════════════════════════════════════════════════


def create_default_layout(session: Session, workshop_name: str = 'Цех №1') -> WorkshopLayout:
    """Создать планировку цеха с авто-размещением станков из БД."""
    equipment = session.query(Equipment).all()
    if not equipment:
        return WorkshopLayout(name=workshop_name)

    cols = min(4, len(equipment))
    margin = 80.0
    spacing_x = 200.0
    spacing_y = 150.0

    machines = []
    for i, eq in enumerate(equipment):
        col = i % cols
        row = i // cols
        machines.append(MachinePosition(
            id=i,
            equipment_id=eq.id,
            name=eq.name or f'Станок {eq.id}',
            model=eq.model or '',
            x=margin + col * spacing_x,
            y=margin + row * spacing_y,
            width=120,
            height=80,
        ))

    total_w = margin * 2 + cols * spacing_x
    total_h = margin * 2 + ((len(equipment) - 1) // cols + 1) * spacing_y
    return WorkshopLayout(
        name=workshop_name,
        width=max(total_w, 800),
        height=max(total_h, 600),
        machines=machines,
    )


def get_machine_statuses(session: Session) -> List[MachinePosition]:
    """Получить текущий статус всех станков из MachineStatusSummary."""
    from database.models._v9 import MachineStatusSummary

    equipment = {e.id: e for e in session.query(Equipment).all()}
    summaries = {
        s.equipment_id: s
        for s in session.query(MachineStatusSummary).all()
        if s.equipment_id in equipment
    }

    machines = []
    for eq_id, eq in equipment.items():
        summary = summaries.get(eq_id)
        status = 'offline'
        if summary:
            status = summary.status or 'offline'

        machines.append(MachinePosition(
            id=len(machines),
            equipment_id=eq_id,
            name=eq.name or f'Станок {eq_id}',
            model=eq.model or '',
            status=status,
        ))

    return machines


# ═══════════════════════════════════════════════════════════════════
# OEE Calculation
# ═══════════════════════════════════════════════════════════════════


def calculate_oee(session: Session, *,
                  equipment_id: int,
                  days: int = 7) -> OEE:
    """Рассчитать OEE для станка за N дней.

    Availability = uptime / planned_production_time
    Performance = actual_output / theoretical_output
    Quality = good_parts / total_parts
    """
    from database.models._v9 import MachineStatus
    from database.models._production import RouteStep, RouteStepStatus

    eq = session.get(Equipment, equipment_id)
    name = eq.name if eq else f'Станок {equipment_id}'

    # Availability: based on machine status
    since = datetime.now() - timedelta(days=days)
    statuses = session.query(MachineStatus).filter(
        MachineStatus.equipment_id == equipment_id,
        MachineStatus.recorded_at >= since,
    ).order_by(MachineStatus.recorded_at.asc()).all()

    total_min = 0
    running_min = 0
    if statuses:
        for i, s in enumerate(statuses):
            if i == 0:
                continue
            delta = (statuses[i].recorded_at - statuses[i - 1].recorded_at).total_seconds() / 60.0
            total_min += delta
            if s.status == 'running':
                running_min += delta

    planned_min = days * 8 * 60  # 8 hours/day
    availability = running_min / max(planned_min, 1)

    # Performance: route steps via operation-equipment lookup
    from database.models import Operation as Op
    eq_ops = session.query(Op.id).filter(
        Op.equipment_id == equipment_id,
        Op.is_deleted == False,
    ).all()
    eq_op_ids = [o[0] for o in eq_ops]

    steps = []
    if eq_op_ids:
        steps = session.query(RouteStep).filter(
            RouteStep.operation_id.in_(eq_op_ids),
            RouteStep.finished_at >= since,
        ).all()

    actual_qty = sum(s.qty_good or 0 for s in steps) + sum(s.qty_scrap or 0 for s in steps)
    theoretical_qty = running_min / 15 if running_min > 0 else 1
    performance = actual_qty / max(theoretical_qty, 1)
    performance = min(performance, 1.5)

    # Quality
    good_qty = sum(s.qty_good or 0 for s in steps)
    quality = good_qty / max(actual_qty, 1)

    oee_val = availability * performance * quality

    return OEE(
        equipment_id=equipment_id,
        equipment_name=name,
        availability=round(availability, 3),
        performance=round(performance, 3),
        quality=round(quality, 3),
        oee=round(oee_val, 3),
    )


def calculate_all_oee(session: Session, days: int = 7) -> List[OEE]:
    """Рассчитать OEE для всех станков."""
    equipment = session.query(Equipment).all()
    results = []
    for eq in equipment:
        oee = calculate_oee(session, equipment_id=eq.id, days=days)
        results.append(oee)
    results.sort(key=lambda x: x.oee)
    return results


# ═══════════════════════════════════════════════════════════════════
# Production Flow Simulation
# ═══════════════════════════════════════════════════════════════════


def simulate_flow(session: Session, *,
                  hours: float = 40.0,
                  speedup: int = 60) -> FlowSimulation:
    """Симуляция производственного потока на неделю.

    speedup: ускорение (60 = 1 час за секунду).
    """
    from modules.scheduler import schedule_aps
    from random import random, seed

    seed(42)

    result = schedule_aps(session, horizon_days=int(hours / 8) + 1)
    if not result.schedule:
        return FlowSimulation(
            total_batches=0, completed_batches=0,
            bottlenecks=[], avg_queue_length=0.0,
            total_time_hours=hours,
        )

    eq_names = list(set(s.equipment_name for s in result.schedule))
    if not eq_names:
        return FlowSimulation(
            total_batches=result.metrics.total_orders_scheduled,
            completed_batches=0,
            bottlenecks=[], avg_queue_length=0.0,
            total_time_hours=hours,
        )

    # Симуляция очередей по часам
    eq_queues: Dict[str, List[float]] = {e: [] for e in eq_names}

    for hour in range(int(hours)):
        for eq_name in eq_names:
            ops_this_hour = [
                s for s in result.schedule
                if s.equipment_name == eq_name
                and s.start <= datetime.now() + timedelta(hours=hour)
                and s.finish >= datetime.now() + timedelta(hours=hour)
            ]
            eq_queues[eq_name].append(len(ops_this_hour) * 0.8 + random() * 2)

    # Определить бутылочные горлышки
    avg_q = {e: sum(qs) / len(qs) for e, qs in eq_queues.items()}
    bottlenecks = sorted(avg_q, key=avg_q.get, reverse=True)[:3]

    total_completed = int(len(result.schedule) * 0.85)

    return FlowSimulation(
        total_batches=result.metrics.total_orders_scheduled,
        completed_batches=total_completed,
        bottlenecks=bottlenecks,
        avg_queue_length=round(sum(avg_q.values()) / max(len(avg_q), 1), 1),
        total_time_hours=hours,
    )
