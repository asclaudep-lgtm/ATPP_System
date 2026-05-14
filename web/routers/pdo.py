"""PDO API v3 — real workflow with OMTS, Tech Dept, Deputy approval."""

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional

from web.deps import get_db, get_current_user
from modules import pdo_module

router = APIRouter(tags=["pdo"])


@router.get("/pdo/orders")
def list_orders(
    status: str = Query(""),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    from database.models import PDOStatus
    st = None
    if status:
        try:
            st = PDOStatus[status]
        except KeyError:
            pass
    orders = pdo_module.list_orders_by_status(db, st)
    return [pdo_module.get_order_detail(db, o.id) for o in orders]


@router.get("/pdo/orders/{order_id}")
def get_order(order_id: int,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    detail = pdo_module.get_order_detail(db, order_id)
    if not detail:
        raise HTTPException(404, "Order not found")
    return detail


@router.post("/pdo/orders")
def create_order(
    product_id: int = Query(...),
    qty: int = Query(...),
    due_date: str = Query(""),
    customer: str = Query(""),
    aircraft_type: str = Query(""),
    work_scope: str = Query(""),
    priority: int = Query(3),
    notes: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dd = date.fromisoformat(due_date) if due_date else date.today()
    order = pdo_module.create_order(
        db, product_id=product_id, qty=qty, due_date=dd,
        customer=customer, aircraft_type=aircraft_type,
        work_scope=work_scope, priority=priority, notes=notes,
        created_by=current_user['id'],
    )
    return pdo_module.get_order_detail(db, order.id)


@router.post("/pdo/orders/{order_id}/omts-review")
def start_omts_review(
    order_id: int,
    memo_number: str = Query(""),
    content: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    pdo_module.omts_start_review(
        db, order_id=order_id, memo_number=memo_number,
        issued_by=current_user['id'], content=content,
    )
    return pdo_module.get_order_detail(db, order_id)


@router.post("/pdo/orders/{order_id}/tech-review")
def start_tech_review(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pdo_module.tech_dept_review(db, order_id=order_id)
    return pdo_module.get_order_detail(db, order_id)


@router.post("/pdo/nomenclature/{item_id}/feasibility")
def set_item_feasibility(
    item_id: int,
    feasible: bool = Query(...),
    kd_ready: bool = Query(False),
    material_name: str = Query(""),
    tech_notes: str = Query(""),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    item = pdo_module.set_feasibility(
        db, item_id=item_id, feasible=feasible,
        kd_ready=kd_ready, material_name=material_name,
        tech_notes=tech_notes,
    )
    return {"id": item.id, "tech_feasible": item.tech_feasible}


@router.post("/pdo/orders/{order_id}/complete-tech-review")
def complete_tech_review(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    order = pdo_module.complete_tech_review(db, order_id=order_id)
    return pdo_module.get_order_detail(db, order.id)


@router.post("/pdo/orders/{order_id}/deputy-approve")
def deputy_approve(
    order_id: int,
    memo_number: str = Query(""),
    content: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    pdo_module.deputy_approve(
        db, order_id=order_id, memo_number=memo_number,
        issued_by=current_user['id'], content=content,
    )
    return pdo_module.get_order_detail(db, order_id)


@router.post("/pdo/orders/{order_id}/approve")
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pdo_module.approve_order(db, order_id=order_id)
    return pdo_module.get_order_detail(db, order_id)


@router.post("/pdo/orders/{order_id}/sign-mtp")
def sign_mtp(
    order_id: int,
    tech_process_id: int = Query(...),
    comment: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.get('role') not in ('technologist', 'admin'):
        raise HTTPException(403, "Только технолог")
    try:
        pdo_module.sign_mtp(
            db, order_id=order_id, tech_process_id=tech_process_id,
            signed_by=current_user['id'], comment=comment,
        )
        return pdo_module.get_order_detail(db, order_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/pdo/orders/{order_id}/release")
def release_order(
    order_id: int,
    shop: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        pdo_module.release_to_shop(
            db, order_id=order_id, shop=shop,
            released_by=current_user['id'],
        )
        return pdo_module.get_order_detail(db, order_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/pdo/orders/{order_id}/close")
def close_order(
    order_id: int,
    qty_done: int = Query(0),
    qty_scrap: int = Query(0),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pdo_module.close_order(
        db, order_id=order_id,
        qty_done=qty_done, qty_scrap=qty_scrap,
    )
    return pdo_module.get_order_detail(db, order_id)
