"""PDO API — production orders, handoffs, MTP signoff."""

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from modules import pdo_module

router = APIRouter(tags=["pdo"])


@router.get("/pdo/orders")
def list_orders(
    status: str = Query(""),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """List all PDO orders, optionally by status."""
    st = None
    from database.models import PDOStatus
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
    priority: int = Query(3),
    notes: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new PDO production order."""
    dd = date.fromisoformat(due_date) if due_date else date.today()
    order = pdo_module.create_order(
        db, product_id=product_id, qty=qty, due_date=dd,
        customer=customer, priority=priority, notes=notes,
        created_by=current_user['id'],
    )
    return pdo_module.get_order_detail(db, order.id)


@router.post("/pdo/orders/{order_id}/sign-mtp")
def sign_mtp(
    order_id: int,
    tech_process_id: int = Query(...),
    comment: str = Query(""),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Technologist signs the MTP for an order."""
    if current_user.get('role') not in ('technologist', 'admin'):
        raise HTTPException(403, "Только технолог может подписать МТП")
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
    """PDO dispatcher releases order to workshop."""
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
    current_user=Depends(get_current_user),
):
    """QC closes the order."""
    pdo_module.close_order(
        db, order_id=order_id,
        qty_done=qty_done, qty_scrap=qty_scrap,
    )
    return pdo_module.get_order_detail(db, order_id)
