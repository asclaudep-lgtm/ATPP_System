"""Отчёты по производству (B7–B10).

Все функции — чистые «pull from DB», возвращают list[dict]. Экспорт в
Excel/PDF — отдельным слоем (см. UI или модуль ``modules.exports``).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, case
from sqlalchemy.orm import Session

from database.models import (
    IssueStatus, ProductionEvent, ProductionIssue, RouteStep,
    RouteStepStatus, User, Workshop, WorkOrder, WorkOrderItem,
)


# ────────────────────────────────────────────────────────────────────────────
# B7. Выработка за период
# ────────────────────────────────────────────────────────────────────────────

def throughput(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    workshop_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> list[dict]:
    """Сводка по завершённым операциям: кто, на каком участке,
    сколько годных/брака. Период определяется по
    ``RouteStep.completed_at``.

    Возвращает список словарей:
        worker_id, worker_name, workshop_id, workshop_name,
        finished_steps, qty_good_total, qty_scrap_total
    """
    q = (session.query(
        RouteStep.worker_user_id.label('worker_id'),
        User.full_name.label('worker_full'),
        User.username.label('worker_login'),
        RouteStep.workshop_id.label('workshop_id'),
        Workshop.name.label('workshop_name'),
        func.count(RouteStep.id).label('finished_steps'),
        func.coalesce(func.sum(RouteStep.qty_good), 0).label('qty_good_total'),
        func.coalesce(func.sum(RouteStep.qty_scrap), 0).label('qty_scrap_total'),
    )
        .outerjoin(User, User.id == RouteStep.worker_user_id)
        .outerjoin(Workshop, Workshop.id == RouteStep.workshop_id)
        .filter(RouteStep.status == RouteStepStatus.DONE)
        .filter(RouteStep.finished_at.isnot(None))
        .filter(RouteStep.finished_at >= date_from)
        .filter(RouteStep.finished_at <= date_to))
    if workshop_id:
        q = q.filter(RouteStep.workshop_id == workshop_id)
    if user_id:
        q = q.filter(RouteStep.worker_user_id == user_id)
    q = q.group_by(RouteStep.worker_user_id, User.full_name, User.username,
                   RouteStep.workshop_id, Workshop.name)
    q = q.order_by(func.count(RouteStep.id).desc())
    rows = []
    for r in q.all():
        rows.append({
            'worker_id': r.worker_id,
            'worker_name': r.worker_full or r.worker_login or '—',
            'workshop_id': r.workshop_id,
            'workshop_name': r.workshop_name or '—',
            'finished_steps': int(r.finished_steps or 0),
            'qty_good_total': int(r.qty_good_total or 0),
            'qty_scrap_total': int(r.qty_scrap_total or 0),
        })
    return rows


# ────────────────────────────────────────────────────────────────────────────
# B8. Среднее время прохождения
# ────────────────────────────────────────────────────────────────────────────

def lead_time(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    """Для каждого участка — среднее, минимальное, максимальное время
    одной операции (минуты), посчитанное как ``completed_at -
    started_at``. Берём только завершённые шаги.

    Возвращает список:
        workshop_id, workshop_name, count_steps, avg_minutes,
        min_minutes, max_minutes, total_qty_good, total_qty_scrap.
    """
    rows = (session.query(
        RouteStep.workshop_id.label('workshop_id'),
        Workshop.name.label('workshop_name'),
        RouteStep.id,
        RouteStep.started_at,
        RouteStep.finished_at,
        RouteStep.qty_good,
        RouteStep.qty_scrap,
    )
        .outerjoin(Workshop, Workshop.id == RouteStep.workshop_id)
        .filter(RouteStep.status == RouteStepStatus.DONE)
        .filter(RouteStep.started_at.isnot(None))
        .filter(RouteStep.finished_at.isnot(None))
        .filter(RouteStep.finished_at >= date_from)
        .filter(RouteStep.finished_at <= date_to).all())

    # Агрегация в Python для совместимости и SQLite, и PostgreSQL.
    agg: dict[tuple, dict] = {}
    for r in rows:
        if not r.started_at or not r.finished_at:
            continue
        delta = (r.finished_at - r.started_at).total_seconds() / 60.0
        if delta < 0:
            continue
        key = (r.workshop_id, r.workshop_name or '—')
        a = agg.setdefault(key, {
            'workshop_id': r.workshop_id,
            'workshop_name': r.workshop_name or '—',
            'count_steps': 0,
            'sum_minutes': 0.0,
            'min_minutes': delta,
            'max_minutes': delta,
            'total_qty_good': 0,
            'total_qty_scrap': 0,
        })
        a['count_steps'] += 1
        a['sum_minutes'] += delta
        a['min_minutes'] = min(a['min_minutes'], delta)
        a['max_minutes'] = max(a['max_minutes'], delta)
        a['total_qty_good'] += int(r.qty_good or 0)
        a['total_qty_scrap'] += int(r.qty_scrap or 0)

    out: list[dict] = []
    for d in agg.values():
        n = d.pop('count_steps', 0)
        s = d.pop('sum_minutes', 0.0)
        d['count_steps'] = n
        d['avg_minutes'] = round(s / n, 1) if n else 0.0
        d['min_minutes'] = round(d['min_minutes'], 1)
        d['max_minutes'] = round(d['max_minutes'], 1)
        out.append(d)
    out.sort(key=lambda x: x['avg_minutes'], reverse=True)
    return out


# ────────────────────────────────────────────────────────────────────────────
# B9. Журнал производства за смену
# ────────────────────────────────────────────────────────────────────────────

def shift_journal(
    session: Session,
    *,
    day: date,
    shift_start_hour: int = 8,
    shift_hours: int = 8,
) -> list[dict]:
    """События за конкретную смену.

    По умолчанию: с ``day 08:00`` до ``day 16:00``. Можно сдвинуть через
    ``shift_start_hour`` и ``shift_hours``.
    """
    start = datetime.combine(day, datetime.min.time()).replace(
        hour=shift_start_hour)
    end = start + timedelta(hours=shift_hours)
    q = (session.query(ProductionEvent, User.username, User.full_name,
                       WorkOrder.number)
         .outerjoin(User, User.id == ProductionEvent.user_id)
         .outerjoin(WorkOrder, WorkOrder.id == ProductionEvent.work_order_id)
         .filter(ProductionEvent.at >= start)
         .filter(ProductionEvent.at < end)
         .order_by(ProductionEvent.at.asc()))
    out: list[dict] = []
    for ev, login, full, wo_number in q.all():
        out.append({
            'at': ev.at,
            'event_type': ev.event_type,
            'work_order_number': wo_number or '—',
            'work_order_id': ev.work_order_id,
            'workshop_id': ev.workshop_id,
            'actor_user_id': ev.user_id,
            'actor': full or login or '—',
            'payload_summary': _short_payload(ev.payload),
        })
    return out


def _short_payload(payload) -> str:
    if not payload:
        return ''
    try:
        if isinstance(payload, dict):
            data = payload
        else:
            import json as _j
            data = _j.loads(str(payload))
        # Берём 2-3 «важных» поля, чтобы строка читалась.
        important = ('reason', 'kind', 'severity', 'qty_good', 'qty_scrap',
                     'next_workshop_id', 'title', 'resolution', 'count')
        parts = []
        for k in important:
            if k in data:
                parts.append(f'{k}={data[k]}')
        return ', '.join(parts) if parts else str(data)[:120]
    except Exception:
        return str(payload)[:120]


# ────────────────────────────────────────────────────────────────────────────
# B10. Аналитика проблем
# ────────────────────────────────────────────────────────────────────────────

def issues_summary(
    session: Session,
    *,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    """Топ причин простоев: по типам, со средним временем устранения
    и числом блокирующих случаев.
    """
    q = (session.query(
        ProductionIssue.kind,
        func.count(ProductionIssue.id).label('cnt'),
        func.sum(case((ProductionIssue.blocks_production.is_(True), 1),
                       else_=0)).label('blocking'),
        func.sum(case((ProductionIssue.status == IssueStatus.RESOLVED, 1),
                       else_=0)).label('resolved'),
    )
        .filter(ProductionIssue.opened_at >= date_from)
        .filter(ProductionIssue.opened_at <= date_to)
        .group_by(ProductionIssue.kind)
        .order_by(func.count(ProductionIssue.id).desc()))

    rows: list[dict] = []
    for kind, cnt, blocking, resolved in q.all():
        # Считаем avg(resolved_at - opened_at) отдельным запросом, в Python
        durations = []
        for issue in (session.query(ProductionIssue)
                      .filter(ProductionIssue.kind == kind,
                              ProductionIssue.opened_at >= date_from,
                              ProductionIssue.opened_at <= date_to,
                              ProductionIssue.resolved_at.isnot(None))
                      .all()):
            d = (issue.resolved_at - issue.opened_at).total_seconds() / 3600.0
            if d >= 0:
                durations.append(d)
        avg_h = round(sum(durations) / len(durations), 2) if durations else 0.0
        rows.append({
            'kind': kind.value if hasattr(kind, 'value') else str(kind),
            'count': int(cnt or 0),
            'blocking': int(blocking or 0),
            'resolved': int(resolved or 0),
            'avg_resolve_hours': avg_h,
        })
    return rows
