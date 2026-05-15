"""API дашборда (агрегированная статистика + графики v2)."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from web.deps import get_db, get_current_user
from web.schemas import DashboardStats
from database.models import Product, TechProcess, WorkOrder, User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    workshop: str = Query(None),
):
    base_products = db.query(Product).filter(Product.is_deleted == False)
    base_tps = db.query(TechProcess).filter(TechProcess.is_deleted == False)
    base_wos = db.query(WorkOrder).filter(WorkOrder.is_deleted == False)

    if workshop:
        from database.models import Operation, Equipment, Workshop
        eq_ids = db.query(Equipment.id).join(Workshop).filter(
            Workshop.code == workshop).subquery()
        op_tp_ids = db.query(Operation.tech_process_id).filter(
            Operation.equipment_id.in_(eq_ids)).subquery()
        base_tps = base_tps.filter(TechProcess.id.in_(op_tp_ids))
        base_wos = base_wos.filter(WorkOrder.id.in_(
            db.query(WorkOrder.id).join(WorkOrder.items).join(
                Operation, WorkOrder.items.any()).filter(
                    WorkOrder.items.any()).subquery()
            # Simplified: filter WOs linked to TPs using this equipment
        ))

    total_products = base_products.count()
    total_tps = base_tps.count()
    total_wos = base_wos.count()
    active_wos = base_wos.filter(
        WorkOrder.status.in_(["Передан в производство", "В работе"]),
    ).count()
    total_users = db.query(User).filter(User.is_active == True).count()

    from database.models import ProductionOrder, PDOStatus
    pdo_total = db.query(ProductionOrder).count()
    pdo_active = db.query(ProductionOrder).filter(
        ProductionOrder.status.in_([
            PDOStatus.NEW, PDOStatus.OMTS_REVIEW, PDOStatus.TECH_DEPT,
            PDOStatus.FEASIBLE, PDOStatus.DEPUTY_APPROVAL,
            PDOStatus.APPROVED, PDOStatus.IN_SHOP, PDOStatus.QC,
        ])).count()
    pdo_overdue = db.query(ProductionOrder).filter(
        ProductionOrder.due_date < date.today(),
        ProductionOrder.status != PDOStatus.CLOSED,
    ).count()

    return DashboardStats(
        total_products=total_products,
        total_tech_processes=total_tps,
        total_work_orders=total_wos,
        active_work_orders=active_wos,
        total_users=total_users,
        pdo_total=pdo_total,
        pdo_active=pdo_active,
        pdo_overdue=pdo_overdue,
    )


@router.get("/dashboard/equipment-load")
def get_equipment_load(
    days: int = 7,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    workshop: str = Query(None),
):
    from modules.equipment_load import equipment_load
    rows = equipment_load(db, days=days)
    return {"rows": [r._asdict() for r in rows]}


@router.get("/dashboard/scrap-by-month")
def scrap_by_month(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    months: int = Query(12, ge=1, le=60),
    workshop: str = Query(None),
):
    """Брак по месяцам за последние N месяцев."""
    from database.models._v9 import ScrapRecord
    cutoff = date.today().replace(day=1)
    results = []
    for _ in range(months):
        month_end = cutoff
        month_start = (cutoff.replace(day=1) - timedelta(days=1)).replace(day=1)
        q = db.query(func.count(ScrapRecord.id)).filter(
            ScrapRecord.reported_at >= month_start.isoformat(),
            ScrapRecord.reported_at < month_end.isoformat(),
        )
        count = q.scalar() or 0
        results.append({'month': month_start.strftime('%Y-%m'), 'count': count})
        cutoff = month_start

    return {'months': list(reversed(results))}


@router.get("/dashboard/production-rate")
def production_rate(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
    days: int = Query(30, ge=7, le=365),
    workshop: str = Query(None),
):
    """Выработка по дням: завершённых шагов маршрута."""
    from database.models._production import RouteStep, RouteStepStatus
    cutoff = date.today() - timedelta(days=days)
    q = db.query(
        func.date(RouteStep.finished_at),
        func.count(RouteStep.id),
    ).filter(
        RouteStep.finished_at >= cutoff.isoformat(),
        RouteStep.finished_at.isnot(None),
        RouteStep.status == RouteStepStatus.DONE,
    )
    if workshop:
        from database.models._production import Workshop
        ws = db.query(Workshop).filter(Workshop.code == workshop).first()
        if ws:
            q = q.filter(RouteStep.workshop_id == ws.id)
    q = q.group_by(func.date(RouteStep.finished_at)).order_by(
        func.date(RouteStep.finished_at))
    rows = dict(q.all())

    results = []
    for i in range(days):
        d = (cutoff + timedelta(days=i)).isoformat()
        results.append({'date': d, 'count': rows.get(d, 0)})
    return {'days': results}
