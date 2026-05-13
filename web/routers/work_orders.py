"""API производственных нарядов."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from web.schemas import WorkOrderOut, WOListOut
from database.models import WorkOrder

router = APIRouter(tags=["work-orders"])


def _status_str(wo) -> str:
    if hasattr(wo.status, 'value'):
        return wo.status.value
    return str(wo.status)


@router.get("/work-orders", response_model=WOListOut)
def list_work_orders(
    status: str = Query(""),
    search: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(WorkOrder).filter(WorkOrder.is_deleted == False)
    if status:
        q = q.filter(WorkOrder.status == status)
    if search:
        q = q.filter(WorkOrder.number.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(WorkOrder.number.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    return WOListOut(
        items=[WorkOrderOut(
            id=wo.id, number=wo.number, status=_status_str(wo),
            product_id=wo.product_id,
            qty_total=wo.qty_total or 0,
            qty_done=wo.qty_done or 0,
            qty_scrap=wo.qty_scrap or 0,
            due_date=wo.due_date.isoformat() if wo.due_date else None,
            created_at=wo.created_at,
        ) for wo in items],
        total=total,
    )


@router.get("/work-orders/{wo_id}")
def get_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    wo = db.query(WorkOrder).get(wo_id)
    if not wo or wo.is_deleted:
        raise HTTPException(404, "WorkOrder not found")
    return {
        "id": wo.id,
        "number": wo.number,
        "status": _status_str(wo),
        "product_designation": wo.product.designation if wo.product else "",
        "product_name": wo.product.name if wo.product else "",
        "qty_total": wo.qty_total,
        "qty_done": wo.qty_done or 0,
        "qty_scrap": wo.qty_scrap or 0,
        "due_date": wo.due_date.isoformat() if wo.due_date else None,
        "priority": wo.priority or 0,
        "items": [
            {
                "barcode": item.barcode,
                "serial": item.serial,
                "qty": item.qty,
                "qty_good": item.qty_good,
                "status": item.status.value
                if hasattr(item.status, 'value')
                else str(item.status),
                "workshop": item.current_workshop.name
                if item.current_workshop else "",
            }
            for item in wo.items
        ],
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
    }
