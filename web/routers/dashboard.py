"""API дашборда (агрегированная статистика)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from web.schemas import DashboardStats
from database.models import Product, TechProcess, WorkOrder, User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    total_products = db.query(Product).filter(
        Product.is_deleted == False).count()
    total_tps = db.query(TechProcess).filter(
        TechProcess.is_deleted == False).count()
    total_wos = db.query(WorkOrder).filter(
        WorkOrder.is_deleted == False).count()
    active_wos = db.query(WorkOrder).filter(
        WorkOrder.is_deleted == False,
        WorkOrder.status.in_(["Передан в производство", "В работе"]),
    ).count()
    total_users = db.query(User).filter(User.is_active == True).count()

    return DashboardStats(
        total_products=total_products,
        total_tech_processes=total_tps,
        total_work_orders=total_wos,
        active_work_orders=active_wos,
        total_users=total_users,
    )


@router.get("/dashboard/equipment-load")
def get_equipment_load(
    days: int = 7,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    from modules.equipment_load import equipment_load
    rows = equipment_load(db, days=days)
    return {"rows": [r._asdict() for r in rows]}
