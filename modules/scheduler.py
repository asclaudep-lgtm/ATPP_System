"""
v9-1: Простой APS-lite планировщик.

Раскладывает операции открытых нарядов на ось времени по оборудованию,
не допуская одновременного занятия одного и того же станка. Сейчас —
наивная жадная стратегия (FIFO по `due_date`, затем по созданию наряда),
без учёта смен и переналадок, но уже визуализирует конфликты.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional

from database.models import (
    WorkOrder,
    WorkOrderStatus,
)

# Рабочий день по умолчанию: 08:00–17:00 (с учётом обеда).
WORK_START = time(8, 0)
WORK_END = time(17, 0)
LUNCH_START = time(12, 0)
LUNCH_END = time(13, 0)


@dataclass
class ScheduledOp:
    work_order_id: int
    work_order_number: str
    operation_id: int
    operation_number: str
    operation_name: str
    equipment_id: Optional[int]
    equipment_name: str
    start: datetime
    finish: datetime

    @property
    def duration_min(self) -> float:
        return (self.finish - self.start).total_seconds() / 60.0


def _next_workday_start(dt: datetime) -> datetime:
    """Следующее «начало рабочего дня» после dt."""
    cur = datetime.combine(dt.date(), WORK_START)
    if dt < cur:
        return cur
    next_day = dt.date() + timedelta(days=1)
    return datetime.combine(next_day, WORK_START)


def _advance(dt: datetime, minutes: float) -> datetime:
    """Прибавить minutes рабочих минут с учётом обеда и конца смены."""
    cur = dt
    remaining = minutes
    while remaining > 1e-6:
        # Привести к рабочему дню
        if cur.time() < WORK_START:
            cur = datetime.combine(cur.date(), WORK_START)
        if cur.time() >= WORK_END:
            cur = _next_workday_start(cur)
        # Сколько до ближайшей границы (обед или конец смены)
        if cur.time() < LUNCH_START:
            boundary = datetime.combine(cur.date(), LUNCH_START)
        elif cur.time() < LUNCH_END:
            cur = datetime.combine(cur.date(), LUNCH_END)
            continue
        else:
            boundary = datetime.combine(cur.date(), WORK_END)
        slot = (boundary - cur).total_seconds() / 60.0
        if slot <= 0:
            cur = _next_workday_start(cur)
            continue
        step = min(slot, remaining)
        cur = cur + timedelta(minutes=step)
        remaining -= step
        if remaining > 1e-6 and cur >= boundary:
            # перепрыгнуть через обед / на следующий день
            if cur.time() >= WORK_END:
                cur = _next_workday_start(cur)
            elif cur.time() >= LUNCH_START and cur.time() < LUNCH_END:
                cur = datetime.combine(cur.date(), LUNCH_END)
    return cur


def schedule_open_orders(session,
                         *, start: Optional[datetime] = None,
                         horizon_days: int = 30
                         ) -> List[ScheduledOp]:
    """Распланировать все открытые наряды жадно по оборудованию."""
    if start is None:
        start = datetime.now()
        # Округлим к ближайшему началу часа
        start = start.replace(minute=0, second=0, microsecond=0)

    open_statuses = {WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS}
    wos = (session.query(WorkOrder)
           .filter(WorkOrder.status.in_(open_statuses))
           .order_by(WorkOrder.due_date.asc().nulls_last(),
                     WorkOrder.created_at.asc())
           .all())

    next_free: Dict[int, datetime] = {}     # eq_id → next free
    unassigned_next_free = start            # очередь для операций без станка
    sched: List[ScheduledOp] = []

    horizon_end = start + timedelta(days=horizon_days)

    for wo in wos:
        tp = wo.tech_process
        if tp is None:
            continue
        ops = sorted([o for o in tp.operations
                      if not getattr(o, 'is_deleted', False)],
                     key=lambda o: (o.sort_order or 0))
        wo_cursor = start  # «когда станет доступен этот наряд»
        qty = int(wo.qty_total or 1)
        for op in ops:
            duration = float(op.t_setup or 0) + float(op.t_piece or 0) * qty
            if duration <= 0:
                continue
            eq = op.equipment
            eq_id = eq.id if eq else None
            eq_name = (eq.name if eq else '— без оборудования —')
            avail = next_free.get(eq_id, start) if eq_id is not None \
                else unassigned_next_free
            op_start = max(wo_cursor, avail)
            if op_start.time() >= WORK_END or op_start.time() < WORK_START:
                op_start = _next_workday_start(op_start)
            op_finish = _advance(op_start, duration)
            if op_finish > horizon_end:
                # пропускаем — за горизонтом планирования
                break
            sched.append(ScheduledOp(
                work_order_id=wo.id,
                work_order_number=wo.number or f'WO-{wo.id}',
                operation_id=op.id,
                operation_number=op.number or '—',
                operation_name=op.name or '',
                equipment_id=eq_id,
                equipment_name=eq_name,
                start=op_start,
                finish=op_finish,
            ))
            if eq_id is not None:
                next_free[eq_id] = op_finish
            else:
                unassigned_next_free = op_finish
            wo_cursor = op_finish  # следующая операция этого WO начнётся не раньше
    return sched


def detect_conflicts(sched: List[ScheduledOp]) -> List[tuple]:
    """Найти конфликты (пересечения по одному и тому же оборудованию)."""
    by_eq: Dict[int, List[ScheduledOp]] = {}
    for s in sched:
        if s.equipment_id is None:
            continue
        by_eq.setdefault(s.equipment_id, []).append(s)
    conflicts = []
    for eq_id, items in by_eq.items():
        items.sort(key=lambda x: x.start)
        for i in range(len(items) - 1):
            a, b = items[i], items[i + 1]
            if b.start < a.finish:
                conflicts.append((a, b))
    return conflicts


# ──────────────────────────────────────────────────────────────
# v10: APS — priority-weighted scheduling with setup times
# ──────────────────────────────────────────────────────────────


@dataclass
class APSMetrics:
    total_orders_scheduled: int = 0
    total_operations_scheduled: int = 0
    total_setup_time_min: float = 0.0
    avg_equipment_load_pct: float = 0.0
    max_equipment_load_pct: float = 0.0
    orders_past_due: int = 0
    makespan_hours: float = 0.0


@dataclass
class APSResult:
    schedule: List[ScheduledOp] = None
    metrics: APSMetrics = None
    conflicts: List[tuple] = None
    unscheduled_orders: List[int] = None

    def __post_init__(self):
        if self.schedule is None:
            self.schedule = []
        if self.metrics is None:
            self.metrics = APSMetrics()
        if self.conflicts is None:
            self.conflicts = []
        if self.unscheduled_orders is None:
            self.unscheduled_orders = []


def get_preloaded_equipment_map(session) -> Dict[int, dict]:
    """Предзагрузить справочник оборудования для планировщика."""
    from database.models import Equipment as Eq
    result: Dict[int, dict] = {}
    for eq in session.query(Eq).all():
        result[eq.id] = {
            'name': eq.name or '',
            'model': eq.model or '',
            'cost_per_hour': float(eq.cost_per_hour or 0),
        }
    return result


def estimate_setup_time(session, *,
                        from_product_id: Optional[int],
                        to_product_id: int,
                        equipment_id: int) -> float:
    """Оценить время переналадки между изделиями на оборудовании.

    Если изделие то же → 0.
    Иначе → берём T_setup первой операции нового изделия на этом
    оборудовании как эвристику.
    """
    if from_product_id == to_product_id:
        return 0.0

    from database.models import Operation as Op
    from database.models import TechProcess as TP
    tp = session.query(TP).filter(
        TP.product_id == to_product_id,
        not TP.is_deleted,
    ).order_by(TP.id).first()
    if tp is None:
        return 15.0  # дефолт: 15 минут

    first_op = session.query(Op).filter(
        Op.tech_process_id == tp.id,
        Op.equipment_id == equipment_id,
        not Op.is_deleted,
    ).order_by(Op.sort_order).first()

    if first_op:
        return float(first_op.t_setup or 15.0)
    return 15.0


def schedule_aps(session, *,
                 start: Optional[datetime] = None,
                 horizon_days: int = 30,
                 priority_weight: float = 1.0,
                 due_date_weight: float = 1.5,
                 setup_time_weight: float = 0.8,
                 ) -> APSResult:
    """Планирование с учётом приоритетов, сроков и переналадок.

    Отличие от schedule_open_orders():
    - Приоритеты заказов (priority * priority_weight)
    - Близость due_date (due_date_weight)
    - Setup time между разными изделиями на одном оборудовании
    - Возвращает метрики качества расписания
    """
    if start is None:
        start = datetime.now().replace(minute=0, second=0, microsecond=0)

    result = APSResult()

    open_statuses = {WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS}
    wos = session.query(WorkOrder).filter(
        WorkOrder.status.in_(open_statuses),
    ).all()

    # Scoring: priority + due_date proximity
    now = datetime.now()
    scored = []
    for wo in wos:
        priority_score = float(wo.priority or 0) * priority_weight
        due_score = 0.0
        if wo.due_date:
            days_left = (wo.due_date - now.date()).days
            due_score = max(0, (horizon_days - days_left) / horizon_days) \
                * due_date_weight
        scored.append((priority_score + due_score, wo))

    scored.sort(key=lambda x: x[0], reverse=True)

    next_free: Dict[int, datetime] = {}
    last_product: Dict[int, Optional[int]] = {}  # eq_id → last product_id
    unassigned_next_free = start
    sched: List[ScheduledOp] = []
    total_setup = 0.0
    unscheduled: List[int] = []

    horizon_end = start + timedelta(days=horizon_days)

    for score, wo in scored:
        tp = wo.tech_process
        if tp is None:
            unscheduled.append(wo.id)
            continue
        ops = sorted([o for o in tp.operations
                      if not getattr(o, 'is_deleted', False)],
                     key=lambda o: (o.sort_order or 0))
        wo_cursor = start
        qty = int(wo.qty_total or 1)
        product_id = wo.product_id

        for op in ops:
            duration = float(op.t_setup or 0) + float(op.t_piece or 0) * qty
            if duration <= 0:
                continue
            eq = op.equipment
            eq_id = eq.id if eq else None
            eq_name = eq.name if eq else '— без оборудования —'

            # Setup time
            setup = 0.0
            if eq_id is not None:
                prev_product = last_product.get(eq_id)
                setup = estimate_setup_time(
                    session,
                    from_product_id=prev_product,
                    to_product_id=product_id,
                    equipment_id=eq_id,
                ) * setup_time_weight
                total_setup += setup

            avail = next_free.get(eq_id, start) if eq_id is not None \
                else unassigned_next_free
            if eq_id is not None and setup > 0:
                avail = _advance(avail, setup)

            op_start = max(wo_cursor, avail)
            if op_start.time() >= WORK_END or op_start.time() < WORK_START:
                op_start = _next_workday_start(op_start)
            op_finish = _advance(op_start, duration)
            if op_finish > horizon_end:
                unscheduled.append(wo.id)
                break

            sched.append(ScheduledOp(
                work_order_id=wo.id,
                work_order_number=wo.number or f'WO-{wo.id}',
                operation_id=op.id,
                operation_number=op.number or '—',
                operation_name=op.name or '',
                equipment_id=eq_id,
                equipment_name=eq_name,
                start=op_start,
                finish=op_finish,
            ))

            if eq_id is not None:
                next_free[eq_id] = op_finish
                last_product[eq_id] = product_id
            else:
                unassigned_next_free = op_finish
            wo_cursor = op_finish

    result.schedule = sched
    result.unscheduled_orders = unscheduled
    result.conflicts = detect_conflicts(sched)

    # Метрики
    metrics = APSMetrics()
    metrics.total_operations_scheduled = len(sched)
    metrics.total_setup_time_min = total_setup
    metrics.orders_past_due = sum(
        1 for wo in wos if wo.due_date and wo.due_date < now.date()
    )

    # Считаем загрузку оборудования
    if sched:
        eq_hours: Dict[str, float] = {}
        for s in sched:
            eq_hours[s.equipment_name] = eq_hours.get(
                s.equipment_name, 0) + s.duration_min / 60.0

        total_capacity = horizon_days * 8.0  # 8 часов в день
        loads = [min(h / total_capacity * 100, 100) for h in eq_hours.values()]
        if loads:
            metrics.avg_equipment_load_pct = sum(loads) / len(loads)
            metrics.max_equipment_load_pct = max(loads)

        first_start = min(s.start for s in sched)
        last_finish = max(s.finish for s in sched)
        metrics.makespan_hours = \
            (last_finish - first_start).total_seconds() / 3600.0

    scheduled_wo_ids = set(s.work_order_id for s in sched)
    metrics.total_orders_scheduled = len(scheduled_wo_ids)
    result.metrics = metrics

    return result


def plan_for_week(session, *,
                  week_start: 'date_type',
                  equipment_ids: Optional[List[int]] = None,
                  ) -> dict:
    """Оптимизировать расписание на конкретную неделю.

    Выбирает наряды, которые помещаются в ёмкость недели.
    Возвращает: {work_order_ids, equipment_hours, total_hours, week_start,
                  week_end}
    """

    week_end = week_start + timedelta(days=6)
    week_start_dt = datetime.combine(week_start, WORK_START)

    result_aps = schedule_aps(
        session, start=week_start_dt, horizon_days=7,
        priority_weight=1.2, due_date_weight=2.0, setup_time_weight=1.0,
    )

    eq_hours: Dict[int, float] = {}
    for s in result_aps.schedule:
        if s.equipment_id:
            eq_hours[s.equipment_id] = eq_hours.get(
                s.equipment_id, 0) + s.duration_min / 60.0

    wo_ids = list(set(s.work_order_id for s in result_aps.schedule))
    total_hours = sum(eq_hours.values())

    return {
        'work_order_ids': wo_ids,
        'equipment_hours': eq_hours,
        'total_hours': total_hours,
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'operations_scheduled': len(result_aps.schedule),
        'setup_time_total_min': result_aps.metrics.total_setup_time_min,
        'avg_load_pct': result_aps.metrics.avg_equipment_load_pct,
        'unscheduled': result_aps.unscheduled_orders,
    }


# ═══════════════════════════════════════════════════════════════════
# V12: Full APS — shift calendars, backward scheduling, finite
#      capacity, setup optimization, constraint validation,
#      what-if scenarios, scenario comparison
# ═══════════════════════════════════════════════════════════════════


@dataclass
class TimeSlot:
    """Рабочий временной интервал."""
    start: datetime
    end: datetime
    equipment_id: Optional[int] = None
    max_hours: float = 8.0


@dataclass
class ConstraintViolation:
    """Нарушение ограничения планирования."""
    operation_id: int
    equipment_id: int
    constraint_type: str  # 'material', 'tooling', 'worker', 'capacity'
    description: str
    severity: str = 'warning'  # 'warning', 'error', 'critical'


@dataclass
class ScenarioDiff:
    """Разница между двумя сценариями планирования."""
    makespan_delta_hours: float = 0.0
    avg_load_delta_pct: float = 0.0
    setup_delta_min: float = 0.0
    conflicts_a: int = 0
    conflicts_b: int = 0
    orders_scheduled_a: int = 0
    orders_scheduled_b: int = 0
    past_due_a: int = 0
    past_due_b: int = 0


def _parse_time(time_str: str) -> time:
    """Разобрать HH:MM в time."""
    h, m = time_str.split(':')
    return time(int(h), int(m))


def get_shift_slots(session, *,
                    equipment_id: Optional[int] = None,
                    on_date: Optional['date_type'] = None) -> List[TimeSlot]:
    """Получить рабочие слоты для оборудования на дату."""
    from database.models._v10_v14 import CalendarException, ShiftSlot, ShiftType

    if on_date is None:
        on_date = datetime.now().date()

    day_of_week = on_date.weekday()

    # Проверить исключения календаря (выходные, ремонты)
    exc = session.query(CalendarException).filter(
        CalendarException.exception_date == on_date,
    )
    if equipment_id is not None:
        exc = exc.filter(
            (CalendarException.equipment_id == equipment_id) |
            (CalendarException.equipment_id.is_(None))
        )
    exceptions = exc.all()

    if exceptions:
        working_exc = [e for e in exceptions if e.is_working]
        if working_exc:
            slots = []
            for e in working_exc:
                st = _parse_time(e.start_time or '08:00')
                et = _parse_time(e.end_time or '17:00')
                slots.append(TimeSlot(
                    start=datetime.combine(on_date, st),
                    end=datetime.combine(on_date, et),
                    equipment_id=equipment_id,
                    max_hours=(et.hour + et.minute / 60) -
                              (st.hour + st.minute / 60),
                ))
            return slots
        else:
            return []  # нерабочий день

    # Обычные слоты смен
    query = session.query(ShiftSlot).filter(
        ShiftSlot.day_of_week == day_of_week,
        ShiftSlot.is_active,
        ShiftSlot.shift_type.in_([ShiftType.DAY, ShiftType.NIGHT]),
    )
    if equipment_id is not None:
        query = query.filter(
            (ShiftSlot.equipment_id == equipment_id) |
            (ShiftSlot.equipment_id.is_(None))
        )

    slots = []
    for s in query.all():
        st = _parse_time(s.start_time)
        et = _parse_time(s.end_time)
        slot_date = on_date
        # Ночная смена может переходить на следующий день
        if s.shift_type == ShiftType.NIGHT and et < st:
            slot_end_date = on_date + timedelta(days=1)
        else:
            slot_end_date = on_date
        slots.append(TimeSlot(
            start=datetime.combine(slot_date, st),
            end=datetime.combine(slot_end_date, et),
            equipment_id=equipment_id,
            max_hours=s.max_hours or 8.0,
        ))
    return slots


def get_available_slots(session, *,
                        equipment_id: Optional[int] = None,
                        from_dt: datetime = None,
                        to_dt: datetime = None) -> List[TimeSlot]:
    """Получить все рабочие слоты в диапазоне [from_dt, to_dt]."""
    if from_dt is None:
        from_dt = datetime.now()
    if to_dt is None:
        to_dt = from_dt + timedelta(days=30)

    slots = []
    cur = from_dt.date()
    end_date = to_dt.date()
    while cur <= end_date:
        slots.extend(get_shift_slots(
            session, equipment_id=equipment_id, on_date=cur))
        cur += timedelta(days=1)
    return [s for s in slots if s.end > from_dt and s.start < to_dt]


def _advance_v12(dt: datetime, minutes: float,
                 slots: List[TimeSlot]) -> datetime:
    """Продвинуть время на minutes рабочих минут, используя слоты смен."""
    cur = dt
    remaining = minutes
    max_iter = 10000
    iters = 0
    while remaining > 1e-6 and iters < max_iter:
        iters += 1
        # Найти слот, в который попадает cur
        active = [s for s in slots if s.start <= cur < s.end]
        if not active:
            # Найти следующий слот
            future = [s for s in slots if s.start > cur]
            if not future:
                return cur + timedelta(minutes=remaining)
            cur = future[0].start
            continue
        slot = active[0]
        available = (slot.end - cur).total_seconds() / 60.0
        step = min(available, remaining)
        cur += timedelta(minutes=step)
        remaining -= step
    return cur


def _adjust_to_working(dt: datetime, slots: List[TimeSlot]) -> datetime:
    """Скорректировать dt к ближайшему началу рабочего слота."""
    for s in sorted(slots, key=lambda x: x.start):
        if s.start <= dt < s.end:
            return dt
        if s.start > dt:
            return s.start
    return dt


def schedule_backward(session, *,
                      due_date: Optional['date_type'] = None,
                      horizon_days: int = 30,
                      priority_weight: float = 1.0,
                      due_date_weight: float = 2.0,
                      setup_time_weight: float = 0.8) -> APSResult:
    """Обратное планирование: от due_date назад.

    Операции размещаются на оси времени в обратном порядке —
    последняя операция завершается к due_date.
    """

    if due_date is None:
        due_date = datetime.now().date() + timedelta(days=14)

    result = APSResult()
    open_statuses = {WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS}
    wos = session.query(WorkOrder).filter(
        WorkOrder.status.in_(open_statuses),
    ).all()

    now = datetime.now()
    scored = []
    for wo in wos:
        priority_score = float(wo.priority or 0) * priority_weight
        due_score = 0.0
        if wo.due_date:
            days_left = (wo.due_date - now.date()).days
            due_score = max(0, (horizon_days - days_left) / horizon_days) \
                * due_date_weight
        scored.append((priority_score + due_score, wo))
    scored.sort(key=lambda x: x[0], reverse=True)

    # Обратное планирование: начинаем с due_date и идём назад
    schedule_end = datetime.combine(due_date, WORK_END)
    horizon_start = schedule_end - timedelta(days=horizon_days)

    next_free: Dict[int, datetime] = {}
    last_product: Dict[int, Optional[int]] = {}
    unassigned_next_free = schedule_end
    sched: List[ScheduledOp] = []
    total_setup = 0.0
    unscheduled: List[int] = []

    for score, wo in scored:
        tp = wo.tech_process
        if tp is None:
            unscheduled.append(wo.id)
            continue
        ops = sorted([o for o in tp.operations
                      if not getattr(o, 'is_deleted', False)],
                     key=lambda o: (o.sort_order or 0), reverse=True)
        qty = int(wo.qty_total or 1)
        product_id = wo.product_id

        wo_cursor = schedule_end
        for op in ops:
            duration = float(op.t_setup or 0) + float(op.t_piece or 0) * qty
            if duration <= 0:
                continue
            eq = op.equipment
            eq_id = eq.id if eq else None
            eq_name = eq.name if eq else '— без оборудования —'

            setup = 0.0
            if eq_id is not None:
                prev_product = last_product.get(eq_id)
                setup = estimate_setup_time(
                    session, from_product_id=prev_product,
                    to_product_id=product_id, equipment_id=eq_id,
                ) * setup_time_weight
                total_setup += setup

            avail = next_free.get(eq_id, schedule_end) if eq_id is not None \
                else unassigned_next_free

            op_finish = min(wo_cursor, avail)
            op_start = op_finish - timedelta(minutes=duration + setup)
            if op_start < horizon_start:
                unscheduled.append(wo.id)
                break

            sched.append(ScheduledOp(
                work_order_id=wo.id,
                work_order_number=wo.number or f'WO-{wo.id}',
                operation_id=op.id,
                operation_number=op.number or '—',
                operation_name=op.name or '',
                equipment_id=eq_id,
                equipment_name=eq_name,
                start=op_start,
                finish=op_finish,
            ))

            if eq_id is not None:
                next_free[eq_id] = op_start
                last_product[eq_id] = product_id
            else:
                unassigned_next_free = op_start
            wo_cursor = op_start

    # Перевернуть для хронологического порядка
    sched.reverse()

    result.schedule = sched
    result.unscheduled_orders = unscheduled
    result.conflicts = detect_conflicts(sched)

    metrics = APSMetrics()
    metrics.total_operations_scheduled = len(sched)
    metrics.total_setup_time_min = total_setup
    metrics.orders_past_due = sum(
        1 for wo in wos if wo.due_date and wo.due_date < now.date())

    if sched:
        eq_hours: Dict[str, float] = {}
        for s in sched:
            eq_hours[s.equipment_name] = eq_hours.get(
                s.equipment_name, 0) + s.duration_min / 60.0
        total_capacity = horizon_days * 8.0
        loads = [min(h / total_capacity * 100, 100) for h in eq_hours.values()]
        if loads:
            metrics.avg_equipment_load_pct = sum(loads) / len(loads)
            metrics.max_equipment_load_pct = max(loads)
        first_start = min(s.start for s in sched)
        last_finish = max(s.finish for s in sched)
        metrics.makespan_hours = \
            (last_finish - first_start).total_seconds() / 3600.0

    scheduled_wo_ids = set(s.work_order_id for s in sched)
    metrics.total_orders_scheduled = len(scheduled_wo_ids)
    result.metrics = metrics
    return result


def schedule_finite_capacity(session, *,
                             start: Optional[datetime] = None,
                             horizon_days: int = 30,
                             priority_weight: float = 1.0,
                             due_date_weight: float = 1.5,
                             setup_time_weight: float = 0.8) -> APSResult:
    """Планирование с конечной мощностью оборудования.

    Каждый станок имеет max_hours_per_day. При исчерпании лимита
    операция переносится на следующий день.
    """
    if start is None:
        start = datetime.now().replace(minute=0, second=0, microsecond=0)

    result = APSResult()
    open_statuses = {WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS}
    wos = session.query(WorkOrder).filter(
        WorkOrder.status.in_(open_statuses),
    ).all()

    now = datetime.now()
    scored = []
    for wo in wos:
        priority_score = float(wo.priority or 0) * priority_weight
        due_score = 0.0
        if wo.due_date:
            days_left = (wo.due_date - now.date()).days
            due_score = max(0, (horizon_days - days_left) / horizon_days) \
                * due_date_weight
        scored.append((priority_score + due_score, wo))
    scored.sort(key=lambda x: x[0], reverse=True)

    next_free: Dict[int, datetime] = {}
    eq_hours_today: Dict[int, float] = {}  # eq_id → hours used today
    last_product: Dict[int, Optional[int]] = {}
    unassigned_next_free = start
    sched: List[ScheduledOp] = []
    total_setup = 0.0
    unscheduled: List[int] = []

    horizon_end = start + timedelta(days=horizon_days)
    max_hours_per_day = 8.0

    for score, wo in scored:
        tp = wo.tech_process
        if tp is None:
            unscheduled.append(wo.id)
            continue
        ops = sorted([o for o in tp.operations
                      if not getattr(o, 'is_deleted', False)],
                     key=lambda o: (o.sort_order or 0))
        wo_cursor = start
        qty = int(wo.qty_total or 1)
        product_id = wo.product_id

        for op in ops:
            duration = float(op.t_setup or 0) + float(op.t_piece or 0) * qty
            if duration <= 0:
                continue
            eq = op.equipment
            eq_id = eq.id if eq else None
            eq_name = eq.name if eq else '— без оборудования —'

            setup = 0.0
            if eq_id is not None:
                prev_product = last_product.get(eq_id)
                setup = estimate_setup_time(
                    session, from_product_id=prev_product,
                    to_product_id=product_id, equipment_id=eq_id,
                ) * setup_time_weight
                total_setup += setup

            avail = next_free.get(eq_id, start) if eq_id is not None \
                else unassigned_next_free

            if eq_id is not None:
                total_minutes = duration + setup
                hours = eq_hours_today.get(eq_id, 0.0) + total_minutes / 60.0

                if hours > max_hours_per_day:
                    overflow_min = (hours - max_hours_per_day) * 60.0
                    while overflow_min > 0:
                        avail = _next_workday_start(avail)
                        next_free[eq_id] = avail
                        eq_hours_today[eq_id] = 0.0
                        can_fit = min(overflow_min,
                                      max_hours_per_day * 60.0)
                        overflow_min -= can_fit

            if eq_id is not None and setup > 0:
                avail = _advance(avail, setup)

            op_start = max(wo_cursor, avail)
            if op_start.time() >= WORK_END or op_start.time() < WORK_START:
                op_start = _next_workday_start(op_start)
            op_finish = _advance(op_start, duration)
            if op_finish > horizon_end:
                unscheduled.append(wo.id)
                break

            sched.append(ScheduledOp(
                work_order_id=wo.id,
                work_order_number=wo.number or f'WO-{wo.id}',
                operation_id=op.id,
                operation_number=op.number or '—',
                operation_name=op.name or '',
                equipment_id=eq_id,
                equipment_name=eq_name,
                start=op_start,
                finish=op_finish,
            ))

            if eq_id is not None:
                next_free[eq_id] = op_finish
                last_product[eq_id] = product_id
                eq_hours_today[eq_id] = eq_hours_today.get(
                    eq_id, 0.0) + duration / 60.0
            else:
                unassigned_next_free = op_finish
            wo_cursor = op_finish

    result.schedule = sched
    result.unscheduled_orders = unscheduled
    result.conflicts = detect_conflicts(sched)

    metrics = APSMetrics()
    metrics.total_operations_scheduled = len(sched)
    metrics.total_setup_time_min = total_setup
    metrics.orders_past_due = sum(
        1 for wo in wos if wo.due_date and wo.due_date < now.date())

    if sched:
        eq_hours: Dict[str, float] = {}
        for s in sched:
            eq_hours[s.equipment_name] = eq_hours.get(
                s.equipment_name, 0) + s.duration_min / 60.0
        total_capacity = horizon_days * max_hours_per_day
        loads = [min(h / total_capacity * 100, 100) for h in eq_hours.values()]
        if loads:
            metrics.avg_equipment_load_pct = sum(loads) / len(loads)
            metrics.max_equipment_load_pct = max(loads)
        first_start = min(s.start for s in sched)
        last_finish = max(s.finish for s in sched)
        metrics.makespan_hours = \
            (last_finish - first_start).total_seconds() / 3600.0

    scheduled_wo_ids = set(s.work_order_id for s in sched)
    metrics.total_orders_scheduled = len(scheduled_wo_ids)
    result.metrics = metrics
    return result


def optimize_setup_sequence(session,
                            sched: List[ScheduledOp]) -> List[ScheduledOp]:
    """Оптимизировать последовательность на каждом станке по переналадкам.

    Сортирует операции на одном оборудовании для минимизации
    суммарного времени переналадок (greedy nearest-neighbor).
    """
    from database.models._v10_v14 import SetupMatrix

    # Группировка по оборудованию
    by_eq: Dict[Optional[int], List[ScheduledOp]] = {}
    for s in sched:
        by_eq.setdefault(s.equipment_id, []).append(s)

    # Загрузить матрицу переналадок
    matrix: Dict[tuple, float] = {}
    for row in session.query(SetupMatrix).all():
        key = (row.equipment_id, row.from_group, row.to_group)
        matrix[key] = row.setup_minutes

    optimized: List[ScheduledOp] = []
    for eq_id, ops in by_eq.items():
        if len(ops) <= 2:
            optimized.extend(ops)
            continue

        # Greedy nearest-neighbor TSP
        remaining = list(ops)
        current = remaining.pop(0)
        ordered = [current]

        while remaining:
            best_idx = 0
            best_cost = float('inf')
            for i, candidate in enumerate(remaining):
                cost = matrix.get(
                    (eq_id, current.operation_name,
                     candidate.operation_name), 15.0)
                if cost < best_cost:
                    best_cost = cost
                    best_idx = i
            current = remaining.pop(best_idx)
            ordered.append(current)

        optimized.extend(ordered)

    return optimized


def validate_constraints(session,
                         sched: List[ScheduledOp]) -> List[ConstraintViolation]:
    """Проверить расписание на нарушения ограничений.

    Проверяет: доступность материалов, оснастки, рабочих,
    превышение мощности.
    """
    violations = []

    if not sched:
        return violations

    # Проверка мощности по дням
    eq_day_load: Dict[tuple, float] = {}  # (eq_id, date) → hours
    for s in sched:
        if s.equipment_id is None:
            continue
        key = (s.equipment_id, s.start.date())
        eq_day_load[key] = eq_day_load.get(key, 0.0) + s.duration_min / 60.0

    for (eq_id, day), hours in eq_day_load.items():
        if hours > 16.0:
            violations.append(ConstraintViolation(
                operation_id=0,
                equipment_id=eq_id,
                constraint_type='capacity',
                description=f'Превышение мощности {hours:.1f}ч на '
                            f'{day.isoformat()} (лимит 16ч)',
                severity='critical',
            ))
        elif hours > 8.0:
            violations.append(ConstraintViolation(
                operation_id=0,
                equipment_id=eq_id,
                constraint_type='capacity',
                description=f'Высокая загрузка {hours:.1f}ч на '
                            f'{day.isoformat()}',
                severity='warning',
            ))

    # Проверка доступности материала (упрощённая — наличие MaterialBatch)
    from database.models._v9 import MaterialBatch, MaterialReservation
    wo_ids = set(s.work_order_id for s in sched)
    for wo_id in wo_ids:
        reservations = session.query(MaterialReservation).filter(
            MaterialReservation.work_order_id == wo_id,
            MaterialReservation.released_at.is_(None),
        ).all()
        for res in reservations:
            batch = session.query(MaterialBatch).filter(
                MaterialBatch.id == res.batch_id,
            ).first()
            if batch and batch.qty_available <= 0:
                violations.append(ConstraintViolation(
                    operation_id=0,
                    equipment_id=0,
                    constraint_type='material',
                    description=f'Материал исчерпан для WO {wo_id}: '
                                f'{batch.batch_number}',
                    severity='error',
                ))

    return violations


def clone_scenario(result: APSResult) -> APSResult:
    """Создать копию результата планирования для what-if."""
    import copy
    return APSResult(
        schedule=copy.deepcopy(result.schedule),
        metrics=APSMetrics(
            total_orders_scheduled=result.metrics.total_orders_scheduled,
            total_operations_scheduled=result.metrics.total_operations_scheduled,
            total_setup_time_min=result.metrics.total_setup_time_min,
            avg_equipment_load_pct=result.metrics.avg_equipment_load_pct,
            max_equipment_load_pct=result.metrics.max_equipment_load_pct,
            orders_past_due=result.metrics.orders_past_due,
            makespan_hours=result.metrics.makespan_hours,
        ),
        conflicts=list(result.conflicts),
        unscheduled_orders=list(result.unscheduled_orders),
    )


def compare_scenarios(a: APSResult, b: APSResult) -> ScenarioDiff:
    """Сравнить два сценария планирования."""
    return ScenarioDiff(
        makespan_delta_hours=b.metrics.makespan_hours -
                           a.metrics.makespan_hours,
        avg_load_delta_pct=b.metrics.avg_equipment_load_pct -
                          a.metrics.avg_equipment_load_pct,
        setup_delta_min=b.metrics.total_setup_time_min -
                       a.metrics.total_setup_time_min,
        conflicts_a=len(a.conflicts),
        conflicts_b=len(b.conflicts),
        orders_scheduled_a=a.metrics.total_orders_scheduled,
        orders_scheduled_b=b.metrics.total_orders_scheduled,
        past_due_a=a.metrics.orders_past_due,
        past_due_b=b.metrics.orders_past_due,
    )


def what_if_reschedule(session, result: APSResult, *,
                       priority_weight: Optional[float] = None,
                       due_date_weight: Optional[float] = None,
                       setup_time_weight: Optional[float] = None,
                       horizon_days: Optional[int] = None) -> APSResult:
    """Перепланировать с изменёнными параметрами (what-if анализ)."""
    return schedule_aps(
        session,
        start=None,
        horizon_days=horizon_days or 30,
        priority_weight=priority_weight or 1.0,
        due_date_weight=due_date_weight or 1.5,
        setup_time_weight=setup_time_weight or 0.8,
    )
