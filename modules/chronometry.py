"""Хронометраж — замер фактического времени операций.

Сравнение план/факт, накопление статистики для AI-помощника и APS.
Использует данные из RouteStep (факт) и Operation (план).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass

from sqlalchemy.orm import Session
from database.models import (Operation, RouteStep, WorkOrder,
                              WorkOrderItem, ProductionEvent)


@dataclass
class ChronoRecord:
    operation_id: int
    operation_name: str
    tech_process_id: int
    work_order_id: int
    work_order_number: str
    planned_t_piece: float
    planned_t_setup: float
    actual_minutes: Optional[float]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    worker: str
    deviation_pct: Optional[float]  # +% означает дольше плана


@dataclass
class ChronoSummary:
    total_measurements: int
    avg_deviation_pct: float
    over_perform_count: int     # быстрее плана
    under_perform_count: int    # дольше плана
    most_deviated_ops: List[ChronoRecord]
    recommendations: List[str]


def collect_chrono_data(session: Session, *,
                        since: Optional[datetime] = None,
                        limit: int = 200) -> List[ChronoRecord]:
    """Собрать данные хронометража из выполненных RouteStep."""
    if since is None:
        since = datetime.now() - timedelta(days=90)

    steps = session.query(RouteStep).filter(
        RouteStep.finished_at.isnot(None),
        RouteStep.finished_at >= since,
        RouteStep.started_at.isnot(None),
    ).order_by(RouteStep.finished_at.desc()).limit(limit).all()

    records: List[ChronoRecord] = []
    for step in steps:
        op = step.operation
        if op is None:
            continue
        actual_min = (step.finished_at - step.started_at).total_seconds() / 60.0
        planned = float(op.t_piece or 0) + float(op.t_setup or 0)
        dev = ((actual_min - planned) / planned * 100) if planned > 0 else None

        records.append(ChronoRecord(
            operation_id=op.id,
            operation_name=op.name or '',
            tech_process_id=op.tech_process_id,
            work_order_id=step.work_order_item.work_order_id
            if step.work_order_item else 0,
            work_order_number=step.work_order_item.work_order.number
            if step.work_order_item and step.work_order_item.work_order
            else '',
            planned_t_piece=float(op.t_piece or 0),
            planned_t_setup=float(op.t_setup or 0),
            actual_minutes=round(actual_min, 2),
            started_at=step.started_at,
            finished_at=step.finished_at,
            worker=step.worker.full_name if step.worker else '',
            deviation_pct=round(dev, 1) if dev is not None else None,
        ))
    return records


def chrono_summary(session: Session, *,
                   since: Optional[datetime] = None) -> ChronoSummary:
    """Сводка хронометража с рекомендациями."""
    records = collect_chrono_data(session, since=since)
    if not records:
        return ChronoSummary(
            total_measurements=0, avg_deviation_pct=0.0,
            over_perform_count=0, under_perform_count=0,
            most_deviated_ops=[], recommendations=[],
        )

    devs = [r.deviation_pct for r in records if r.deviation_pct is not None]
    avg_dev = sum(devs) / len(devs) if devs else 0.0
    over = sum(1 for d in devs if d < -10)
    under = sum(1 for d in devs if d > 10)

    most_dev = sorted(
        [r for r in records if r.deviation_pct is not None],
        key=lambda r: abs(r.deviation_pct), reverse=True,
    )[:10]

    recs: List[str] = []
    if avg_dev > 15:
        recs.append('Среднее превышение плана >15% — рекомендован пересмотр норм.')
    if under > over and under > 5:
        recs.append(
            f'{under} операций значительно дольше плана — проверьте нормы.')
    op_groups: Dict[str, List[float]] = {}
    for r in records:
        if r.deviation_pct is not None:
            op_groups.setdefault(r.operation_name, []).append(r.deviation_pct)
    for op_name, dev_list in op_groups.items():
        avg = sum(dev_list) / len(dev_list)
        if abs(avg) > 25 and len(dev_list) >= 3:
            recs.append(
                f'Операция «{op_name}»: среднее отклонение {avg:.0f}% '
                f'(из {len(dev_list)} замеров) — норма требует корректировки.')

    return ChronoSummary(
        total_measurements=len(records),
        avg_deviation_pct=round(avg_dev, 1),
        over_perform_count=over,
        under_perform_count=under,
        most_deviated_ops=most_dev[:5],
        recommendations=recs,
    )


def update_norms_from_chrono(session: Session, *,
                             operation_id: int,
                             factor: float = 0.3) -> Optional[float]:
    """Скорректировать норму на основе хронометража.

    Новое_время = старое * (1 - factor) + среднее_фактическое * factor
    factor = 0..1 (0.3 = плавная коррекция)
    """
    records = collect_chrono_data(session)
    op_records = [r for r in records if r.operation_id == operation_id
                  and r.actual_minutes is not None]
    if len(op_records) < 3:
        return None  # недостаточно данных

    avg_actual = sum(r.actual_minutes for r in op_records) / len(op_records)
    op = session.query(Operation).get(operation_id)
    if op is None:
        return None

    old_t_piece = float(op.t_piece or 0)
    new_t_piece = old_t_piece * (1 - factor) + avg_actual * factor

    op.t_piece = round(new_t_piece, 2)
    session.flush()
    return new_t_piece
