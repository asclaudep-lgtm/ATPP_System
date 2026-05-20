"""
v9-2: Расчёт загрузки оборудования.

Загрузка =
   сумма реального времени RouteStep за период
   / общее доступное время (рабочая смена × кол-во дней)

Если фактического времени нет — используем плановое
``Operation.t_setup + t_piece × qty`` из связанных нарядов как
прогноз ожидаемой загрузки.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, NamedTuple

from database.models import (
    Equipment,
    Operation,
    RouteStep,
    WorkOrder,
    WorkOrderStatus,
)

# Стандартная рабочая смена, ч.
DEFAULT_SHIFT_HOURS = 8.0
DEFAULT_SHIFTS_PER_DAY = 1
DEFAULT_WORK_DAYS_RATIO = 5.0 / 7.0   # 5 рабочих дней из 7


class EquipmentLoadRow(NamedTuple):
    equipment_id: int
    equipment_name: str
    equipment_model: str
    busy_minutes: float
    available_minutes: float
    load_percent: float


def _period_available_minutes(days: int,
                              shift_hours: float = DEFAULT_SHIFT_HOURS,
                              shifts: int = DEFAULT_SHIFTS_PER_DAY,
                              work_ratio: float = DEFAULT_WORK_DAYS_RATIO,
                              ) -> float:
    """Сколько минут оборудование доступно за период."""
    return days * work_ratio * shifts * shift_hours * 60.0


def equipment_load(
    session,
    *,
    days: int = 30,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
    shifts: int = DEFAULT_SHIFTS_PER_DAY,
) -> List[EquipmentLoadRow]:
    """Загрузка по каждому оборудованию за последние N дней.

    Берёт фактическое время из RouteStep (finished_at - started_at),
    нормирует на доступное время.
    """
    since = datetime.now() - timedelta(days=days)
    avail = _period_available_minutes(days, shift_hours, shifts)

    # Сумма реальных минут по операциям → по оборудованию.
    # SQLite не умеет джулиан-разницу для DateTime в выражении, считаем в Python.
    rows = (session.query(Equipment.id, Equipment.name, Equipment.model,
                          RouteStep.started_at, RouteStep.finished_at)
            .join(Operation, Operation.equipment_id == Equipment.id)
            .join(RouteStep, RouteStep.operation_id == Operation.id)
            .filter(RouteStep.started_at.isnot(None),
                    RouteStep.finished_at.isnot(None),
                    RouteStep.finished_at >= since)
            .all())
    busy_by_eq: Dict[int, float] = {}
    name_by_eq: Dict[int, str] = {}
    model_by_eq: Dict[int, str] = {}
    for eq_id, eq_name, eq_model, sa, fa in rows:
        dur_min = (fa - sa).total_seconds() / 60.0
        if dur_min < 0:
            continue
        busy_by_eq[eq_id] = busy_by_eq.get(eq_id, 0.0) + dur_min
        name_by_eq[eq_id] = eq_name or '—'
        model_by_eq[eq_id] = eq_model or ''

    # Добавим оборудование без занятости.
    for eq in session.query(Equipment).all():
        busy_by_eq.setdefault(eq.id, 0.0)
        name_by_eq.setdefault(eq.id, eq.name or '—')
        model_by_eq.setdefault(eq.id, eq.model or '')

    out: List[EquipmentLoadRow] = []
    for eq_id, busy in busy_by_eq.items():
        load = (busy / avail * 100.0) if avail > 0 else 0.0
        out.append(EquipmentLoadRow(
            equipment_id=eq_id,
            equipment_name=name_by_eq[eq_id],
            equipment_model=model_by_eq[eq_id],
            busy_minutes=busy,
            available_minutes=avail,
            load_percent=load,
        ))
    out.sort(key=lambda r: -r.load_percent)
    return out


def planned_equipment_load(session, *, horizon_days: int = 7
                           ) -> List[EquipmentLoadRow]:
    """Прогноз загрузки на ближайшие N дней по открытым нарядам.

    Использует плановые ``Operation.t_setup`` + ``t_piece * qty_total``
    из нарядов, статус которых не «Закрыт/Отменён».
    """
    avail = _period_available_minutes(horizon_days)
    open_statuses = {WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS}

    rows = (session.query(Equipment.id, Equipment.name, Equipment.model,
                          Operation.t_setup, Operation.t_piece,
                          WorkOrder.qty_total)
            .join(Operation, Operation.equipment_id == Equipment.id)
            .join(WorkOrder,
                  WorkOrder.tech_process_id == Operation.tech_process_id)
            .filter(WorkOrder.status.in_(open_statuses))
            .all())
    busy: Dict[int, float] = {}
    name: Dict[int, str] = {}
    model: Dict[int, str] = {}
    for eq_id, eq_name, eq_model, ts, tp, qty in rows:
        ts = float(ts or 0)
        tp = float(tp or 0)
        qty = int(qty or 0)
        plan_min = ts + tp * qty
        busy[eq_id] = busy.get(eq_id, 0.0) + plan_min
        name[eq_id] = eq_name or '—'
        model[eq_id] = eq_model or ''

    for eq in session.query(Equipment).all():
        busy.setdefault(eq.id, 0.0)
        name.setdefault(eq.id, eq.name or '—')
        model.setdefault(eq.id, eq.model or '')

    out = []
    for eq_id, b in busy.items():
        load = (b / avail * 100.0) if avail > 0 else 0.0
        out.append(EquipmentLoadRow(
            equipment_id=eq_id,
            equipment_name=name[eq_id],
            equipment_model=model[eq_id],
            busy_minutes=b,
            available_minutes=avail,
            load_percent=load,
        ))
    out.sort(key=lambda r: -r.load_percent)
    return out
