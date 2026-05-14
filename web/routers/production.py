"""Production API — route slips, barcode lookup, QA terminal."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from web.deps import get_db, get_current_user
from database.models import (
    WorkOrder, WorkOrderItem, RouteStep, ProductionEvent,
    ProductionIssue, IssuePhoto,
)

router = APIRouter(tags=["production"])


@router.get("/production/route/{work_order_id}")
def get_route_slip(work_order_id: int,
                   db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    wo = db.query(WorkOrder).get(work_order_id)
    if not wo:
        raise HTTPException(404, "Work order not found")
    items = db.query(WorkOrderItem).filter(
        WorkOrderItem.work_order_id == work_order_id).all()
    steps = db.query(RouteStep).filter(
        RouteStep.work_order_item_id.in_([i.id for i in items])
    ).order_by(RouteStep.sort_order).all()

    return {
        "work_order": {
            "id": wo.id, "number": wo.number,
            "product_designation": wo.product.designation if wo.product else "",
            "product_name": wo.product.name if wo.product else "",
            "status": wo.status.value if hasattr(wo.status, 'value') else str(wo.status),
            "qty_total": wo.qty_total, "qty_done": wo.qty_done,
        },
        "items": [{"id": i.id, "name": i.name, "qty": i.quantity,
                   "barcode": i.barcode} for i in items],
        "steps": [{"id": s.id, "item_id": s.work_order_item_id,
                   "operation": s.operation_name,
                   "workshop": s.workshop,
                   "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                   "planned_start": str(s.planned_start) if s.planned_start else None,
                   "actual_start": str(s.actual_start) if s.actual_start else None,
                   "actual_end": str(s.actual_end) if s.actual_end else None,
                   } for s in steps],
    }


@router.get("/production/barcode/{code}")
def lookup_barcode(code: str,
                   db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(
        (WorkOrder.barcode == code) | (WorkOrder.number == code)
    ).first()
    if wo:
        return {"type": "work_order", "id": wo.id, "number": wo.number}
    item = db.query(WorkOrderItem).filter_by(barcode=code).first()
    if item:
        return {"type": "work_order_item", "id": item.id,
                "name": item.name, "work_order_id": item.work_order_id}
    raise HTTPException(404, f"Barcode '{code}' not found")


@router.get("/production/qa/pending")
def get_qa_pending(db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    """List items awaiting QC inspection."""
    steps = db.query(RouteStep).filter(
        RouteStep.status == "Ожидает ОТК"
    ).order_by(RouteStep.sort_order).all()
    return [{
        "id": s.id, "operation": s.operation_name,
        "workshop": s.workshop,
        "actual_end": str(s.actual_end) if s.actual_end else None,
    } for s in steps]


@router.get("/production/issues")
def list_issues(work_order_id: Optional[int] = Query(None),
                db: Session = Depends(get_db),
                _=Depends(get_current_user)):
    q = db.query(ProductionIssue)
    if work_order_id:
        q = q.filter(ProductionIssue.work_order_id == work_order_id)
    issues = q.order_by(ProductionIssue.created_at.desc()).limit(100).all()
    return [{
        "id": i.id, "work_order_id": i.work_order_id,
        "title": i.title, "category": i.category,
        "status": i.status.value if hasattr(i.status, 'value') else str(i.status),
        "photos": [p.stored_path for p in i.photos],
        "created_at": str(i.created_at) if i.created_at else None,
    } for i in issues]


@router.get("/production/equipment-load")
def get_equipment_load(db: Session = Depends(get_db),
                       _=Depends(get_current_user)):
    """Aggregated equipment load data for dashboard."""
    from database.models import Equipment
    equipments = db.query(Equipment).all()
    result = []
    for eq in equipments:
        # Count active operations on this equipment
        active = db.query(RouteStep).filter(
            RouteStep.equipment_name == eq.name,
            RouteStep.status.in_(["В работе", "Назначен"])
        ).count()
        result.append({
            "name": eq.name, "model": eq.model or "",
            "active_ops": active,
            "capacity_pct": min(100, active * 100 // max(eq.machine_count or 1, 1)),
        })
    return result
