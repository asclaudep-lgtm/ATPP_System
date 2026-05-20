"""PDO analytics — bottleneck detection, average time per status, Gantt data."""

from datetime import date, datetime
from typing import List

from sqlalchemy import func

from database.models import PDOHandoff, PDOStatus, ProductionOrder


def average_time_per_status(session, days: int = 90) -> List[dict]:
    """Average days spent in each PDO status for orders closed in the last N days.

    Returns list of {status, count, avg_days, max_days, bottleneck (bool)}.
    """
    cutoff = date.today()
    orders = session.query(ProductionOrder).filter(
        ProductionOrder.created_at >= func.date(cutoff, f'-{days} days')
    ).all()

    status_times = {}
    for o in orders:
        handoffs = session.query(PDOHandoff).filter(
            PDOHandoff.order_id == o.id,
        ).order_by(PDOHandoff.created_at).all()

        for i, h in enumerate(handoffs):
            t0 = h.created_at
            t1 = handoffs[i + 1].created_at if i + 1 < len(handoffs) else (
                o.closed_at or datetime.now())
            if t0 and t1:
                days_in_status = (t1 - t0).total_seconds() / 86400
                key = h.from_dept
                if key not in status_times:
                    status_times[key] = []
                status_times[key].append(days_in_status)

    result = []
    max_avg = 0
    for dept, times in status_times.items():
        avg = sum(times) / len(times)
        max_t = max(times)
        max_avg = max(max_avg, avg)
        result.append({
            'status': dept,
            'count': len(times),
            'avg_days': round(avg, 1),
            'max_days': round(max_t, 1),
        })

    # Mark bottlenecks (top 30% by average time)
    for r in result:
        r['bottleneck'] = r['avg_days'] >= max_avg * 0.7

    return sorted(result, key=lambda r: r['avg_days'], reverse=True)


def orders_stuck(session, min_days: int = 14) -> List[dict]:
    """Find orders stuck in the same status for too long."""
    stuck = []
    active = session.query(ProductionOrder).filter(
        ProductionOrder.status.in_([
            PDOStatus.OMTS_REVIEW, PDOStatus.TECH_DEPT,
            PDOStatus.DEPUTY_APPROVAL,
        ])
    ).all()

    for o in active:
        last_handoff = session.query(PDOHandoff).filter(
            PDOHandoff.order_id == o.id,
        ).order_by(PDOHandoff.created_at.desc()).first()

        if last_handoff and last_handoff.created_at:
            days = (datetime.now() - last_handoff.created_at).days
            if days >= min_days:
                stuck.append({
                    'number': o.number,
                    'product': o.product.designation if o.product else '',
                    'status': o.status.value,
                    'days_stuck': days,
                    'dept': last_handoff.to_dept,
                })

    return sorted(stuck, key=lambda r: r['days_stuck'], reverse=True)


def gantt_data(session, limit: int = 20) -> List[dict]:
    """Generate Gantt chart data for active PDO orders."""
    orders = session.query(ProductionOrder).filter(
        ProductionOrder.status != PDOStatus.CLOSED,
    ).order_by(ProductionOrder.created_at.desc()).limit(limit).all()

    result = []
    for o in orders:
        handoffs = session.query(PDOHandoff).filter(
            PDOHandoff.order_id == o.id,
        ).order_by(PDOHandoff.created_at).all()

        phases = []
        for h in handoffs:
            phases.append({
                'dept': h.to_dept,
                'start': str(h.created_at.date()) if h.created_at else '',
                'comment': h.comment or '',
            })

        if o.due_date:
            phases.append({
                'dept': 'Срок',
                'start': str(o.due_date),
                'comment': f'Приоритет {o.priority}',
            })

        result.append({
            'number': o.number,
            'product': o.product.designation if o.product else '',
            'status': o.status.value,
            'phases': phases,
        })

    return result
