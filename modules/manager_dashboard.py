"""
v9-6: Дашборд руководителя.

Считает KPI для главной страницы:
- % выполнения плана за период,
- средний % брака,
- топ-5 узких мест (операций с самым высоким временем выполнения),
- прогноз срыва сроков (наряды просрочены / в риске).

Дополнительно умеет собрать PDF-отчёт за период.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, NamedTuple

from sqlalchemy import func

from database.models import (
    Operation,
    RouteStep,
    ScrapRecord,
    WorkOrder,
    WorkOrderItem,
    WorkOrderStatus,
)
from modules.equipment_load import equipment_load


class KPISnapshot(NamedTuple):
    period_days: int
    wo_total: int
    wo_done: int
    wo_in_progress: int
    wo_overdue: int
    plan_completion_percent: float
    items_total: int
    items_good: int
    items_scrap: int
    scrap_percent: float
    top_bottleneck_ops: List[tuple]  # (operation_name, total_minutes)
    top_loaded_equipment: List[tuple]  # (equipment_name, load_percent)


def kpi_snapshot(session, *, days: int = 30) -> KPISnapshot:
    """Снять текущий KPI-снимок за последние N дней."""
    since = datetime.now() - timedelta(days=days)

    wo_query = session.query(WorkOrder).filter(WorkOrder.created_at >= since)
    wo_total = wo_query.count()
    wo_done = wo_query.filter(WorkOrder.status == WorkOrderStatus.DONE).count()
    wo_inprog = wo_query.filter(
        WorkOrder.status == WorkOrderStatus.IN_PROGRESS).count()

    # Просрочка считается так: WO открыт, due_date < сегодня.
    today = datetime.now()
    open_statuses = (WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS)
    wo_overdue = (session.query(WorkOrder)
                  .filter(WorkOrder.status.in_(open_statuses),
                          WorkOrder.due_date.isnot(None),
                          WorkOrder.due_date < today)
                  .count())

    plan_pct = (wo_done / wo_total * 100.0) if wo_total > 0 else 0.0

    items_total = (session.query(func.coalesce(func.sum(WorkOrderItem.qty), 0))
                   .join(WorkOrder, WorkOrder.id == WorkOrderItem.work_order_id)
                   .filter(WorkOrder.created_at >= since).scalar()) or 0
    items_good = (session.query(
        func.coalesce(func.sum(WorkOrderItem.qty_good), 0))
        .join(WorkOrder, WorkOrder.id == WorkOrderItem.work_order_id)
        .filter(WorkOrder.created_at >= since).scalar()) or 0
    items_scrap = (session.query(
        func.coalesce(func.sum(WorkOrderItem.qty_scrap), 0))
        .join(WorkOrder, WorkOrder.id == WorkOrderItem.work_order_id)
        .filter(WorkOrder.created_at >= since).scalar()) or 0

    # дополнительно — учтём scrap_records (более точный учёт)
    scrap_extra = (session.query(
        func.coalesce(func.sum(ScrapRecord.qty_scrap), 0))
        .filter(ScrapRecord.reported_at >= since).scalar()) or 0
    items_scrap = max(int(items_scrap), int(scrap_extra))

    scrap_pct = (items_scrap / items_total * 100.0) if items_total else 0.0

    # топ операций по фактическому времени
    op_rows = (session.query(Operation.name,
                             RouteStep.started_at, RouteStep.finished_at)
               .join(RouteStep, RouteStep.operation_id == Operation.id)
               .filter(RouteStep.started_at.isnot(None),
                       RouteStep.finished_at.isnot(None),
                       RouteStep.finished_at >= since)
               .all())
    by_op: Dict[str, float] = {}
    for name, sa, fa in op_rows:
        dur = (fa - sa).total_seconds() / 60.0
        if dur < 0:
            continue
        by_op[name or '—'] = by_op.get(name or '—', 0.0) + dur
    top_ops = sorted(by_op.items(), key=lambda kv: -kv[1])[:5]

    # топ оборудования
    loads = equipment_load(session, days=days)
    top_eq = [(r.equipment_name + (f' ({r.equipment_model})'
                                   if r.equipment_model else ''),
               r.load_percent) for r in loads[:5]]

    return KPISnapshot(
        period_days=days,
        wo_total=int(wo_total),
        wo_done=int(wo_done),
        wo_in_progress=int(wo_inprog),
        wo_overdue=int(wo_overdue),
        plan_completion_percent=plan_pct,
        items_total=int(items_total),
        items_good=int(items_good),
        items_scrap=int(items_scrap),
        scrap_percent=scrap_pct,
        top_bottleneck_ops=top_ops,
        top_loaded_equipment=top_eq,
    )


# ── PDF отчёт ─────────────────────────────────────────────────────

def export_pdf(snapshot: KPISnapshot, out_path: str,
               title: str = 'Дашборд руководителя') -> str:
    """Сохранить PDF-отчёт с KPI-снимком."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    # Регистрация шрифтов для кириллицы.
    fonts_dir = Path('resources/fonts')
    try:
        pdfmetrics.registerFont(
            TTFont('DejaVuSans', str(fonts_dir / 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(
            TTFont('DejaVuSans-Bold', str(fonts_dir / 'DejaVuSans-Bold.ttf')))
    except Exception:
        pass  # шрифты могут уже быть зарегистрированы

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Heading1'],
                        fontName='DejaVuSans-Bold', fontSize=18,
                        leading=22, alignment=1)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'],
                        fontName='DejaVuSans-Bold', fontSize=13, leading=16)
    p = ParagraphStyle('p', parent=styles['BodyText'],
                       fontName='DejaVuSans', fontSize=10, leading=13)

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    story = []
    today = datetime.now().strftime('%d.%m.%Y')
    story.append(Paragraph(title, h1))
    story.append(Paragraph(
        f'за последние {snapshot.period_days} дней&nbsp;&nbsp;·&nbsp;&nbsp;'
        f'сформировано {today}', p))
    story.append(Spacer(1, 8 * mm))

    # KPI таблица
    kpi_data = [
        ['Показатель', 'Значение'],
        ['Нарядов за период', str(snapshot.wo_total)],
        ['Выполнено', str(snapshot.wo_done)],
        ['В работе', str(snapshot.wo_in_progress)],
        ['Просрочено', str(snapshot.wo_overdue)],
        ['% выполнения плана',
         f'{snapshot.plan_completion_percent:.1f} %'],
        ['Деталей в производстве', str(snapshot.items_total)],
        ['Принято / брак',
         f'{snapshot.items_good} / {snapshot.items_scrap}'],
        ['% брака', f'{snapshot.scrap_percent:.2f} %'],
    ]
    t = Table(kpi_data, colWidths=[90 * mm, 70 * mm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'DejaVuSans'),
        ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # Топ-узкие места
    story.append(Paragraph('Топ-5 операций по фактическому времени', h2))
    if snapshot.top_bottleneck_ops:
        rows = [['№', 'Операция', 'Минут']]
        for i, (name, mins) in enumerate(snapshot.top_bottleneck_ops, 1):
            rows.append([str(i), name, f'{mins:.0f}'])
        t2 = Table(rows, colWidths=[12 * mm, 110 * mm, 30 * mm])
        t2.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'DejaVuSans'),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ]))
        story.append(t2)
    else:
        story.append(Paragraph(
            'За период нет завершённых операций (RouteStep).', p))
    story.append(Spacer(1, 8 * mm))

    # Топ-оборудование
    story.append(Paragraph('Топ-5 оборудования по загрузке (%)', h2))
    if snapshot.top_loaded_equipment:
        rows = [['№', 'Оборудование', 'Загрузка']]
        for i, (name, pct) in enumerate(snapshot.top_loaded_equipment, 1):
            rows.append([str(i), name, f'{pct:.0f} %'])
        t3 = Table(rows, colWidths=[12 * mm, 110 * mm, 30 * mm])
        t3.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'DejaVuSans'),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ]))
        story.append(t3)
    else:
        story.append(Paragraph('Нет данных по загрузке оборудования.', p))

    doc.build(story)
    return out_path
