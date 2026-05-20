"""Mobile-friendly REST API — consistent pagination, filtering, sorting.

All endpoints return {items, total, page, page_size} for list operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import (
    Equipment,
    Material,
    Operation,
    Product,
    TechProcess,
    WorkOrder,
)
from web.deps import get_current_user, get_db

router = APIRouter(tags=["mobile"])


# ——— Helpers ——————————————————————————————————————————————————————


def _paginate(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def _list_response(items, total, page, page_size):
    return {
        'items': [i for i in items],  # serialized by FastAPI
        'total': total,
        'page': page,
        'page_size': page_size,
    }


# ——— Products —————————————————————————————————————————————————————


@router.get("/mobile/products")
def mobile_products(
    search: str = Query(""),
    material_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = Query("designation"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Product).filter(not Product.is_deleted)
    if search:
        q = q.filter(
            (Product.designation.ilike(f"%{search}%")) |
            (Product.name.ilike(f"%{search}%"))
        )
    if material_id:
        q = q.filter(Product.material_id == material_id)
    q = q.order_by(getattr(Product, sort_by, Product.designation))
    items, total = _paginate(q, page, page_size)
    return _list_response([
        {'id': p.id, 'designation': p.designation, 'name': p.name,
         'mass': p.mass, 'dimensions': p.dimensions,
         'blank_type': p.blank_type, 'accuracy_class': p.accuracy_class}
        for p in items
    ], total, page, page_size)


@router.get("/mobile/products/{product_id}")
def mobile_product_detail(
    product_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    p = db.get(Product, product_id)
    if not p or p.is_deleted:
        raise HTTPException(404, "Product not found")
    tps = db.query(TechProcess).filter(
        TechProcess.product_id == product_id,
        not TechProcess.is_deleted,
    ).all()
    return {
        'id': p.id, 'designation': p.designation, 'name': p.name,
        'mass': p.mass, 'dimensions': p.dimensions,
        'blank_type': p.blank_type, 'accuracy_class': p.accuracy_class,
        'roughness': p.roughness,
        'material': p.material.name if p.material else None,
        'tech_processes': [
            {'id': tp.id, 'number': tp.number,
             'status': tp.status.value if hasattr(tp.status, 'value') else str(tp.status),
             'version': tp.version}
            for tp in tps
        ],
    }


# ——— Tech Processes ———————————————————————————————————————————————


@router.get("/mobile/tech-processes")
def mobile_tps(
    search: str = Query(""),
    status: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = Query("number"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(TechProcess).filter(not TechProcess.is_deleted)
    if search:
        q = q.filter(TechProcess.number.ilike(f"%{search}%"))
    if status:
        q = q.filter(TechProcess.status == status)
    if product_id:
        q = q.filter(TechProcess.product_id == product_id)
    q = q.order_by(getattr(TechProcess, sort_by, TechProcess.number))
    items, total = _paginate(q, page, page_size)
    return _list_response([
        {'id': tp.id, 'number': tp.number,
         'status': tp.status.value if hasattr(tp.status, 'value') else str(tp.status),
         'version': tp.version,
         'product_designation': tp.product.designation if tp.product else None,
         'product_name': tp.product.name if tp.product else None,
         'execution_variant': getattr(tp, 'execution_variant', None)}
        for tp in items
    ], total, page, page_size)


@router.get("/mobile/tech-processes/{tp_id}")
def mobile_tp_detail(
    tp_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    tp = db.get(TechProcess, tp_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TP not found")
    ops = sorted(
        [o for o in tp.operations if not getattr(o, 'is_deleted', False)],
        key=lambda o: o.sort_order or 0,
    )
    return {
        'id': tp.id, 'number': tp.number, 'version': tp.version,
        'status': tp.status.value if hasattr(tp.status, 'value') else str(tp.status),
        'product_designation': tp.product.designation if tp.product else None,
        'product_name': tp.product.name if tp.product else None,
        'operations': [
            {'number': op.number, 'name': op.name,
             't_piece': op.t_piece, 't_setup': op.t_setup,
             'equipment': op.equipment.name if op.equipment else None,
             'shop': op.shop}
            for op in ops
        ],
    }


# ——— Work Orders ——————————————————————————————————————————————————


@router.get("/mobile/work-orders")
def mobile_work_orders(
    search: str = Query(""),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(WorkOrder).filter(not WorkOrder.is_deleted)
    if search:
        q = q.filter(WorkOrder.number.ilike(f"%{search}%"))
    if status:
        q = q.filter(WorkOrder.status == status)
    q = q.order_by(WorkOrder.created_at.desc())
    items, total = _paginate(q, page, page_size)
    return _list_response([
        {'id': wo.id, 'number': wo.number,
         'status': wo.status.value if hasattr(wo.status, 'value') else str(wo.status),
         'qty_total': wo.qty_total, 'qty_done': wo.qty_done,
         'due_date': str(wo.due_date) if wo.due_date else None,
         'product_designation': wo.product.designation if wo.product else None}
        for wo in items
    ], total, page, page_size)


# ——— References (materials, equipment) ————————————————————————————


@router.get("/mobile/materials")
def mobile_materials(
    search: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Material)
    if search:
        q = q.filter(
            (Material.name.ilike(f"%{search}%")) |
            (Material.grade.ilike(f"%{search}%"))
        )
    q = q.order_by(Material.name)
    items, total = _paginate(q, page, page_size)
    return _list_response([
        {'id': m.id, 'name': m.name, 'grade': m.grade,
         'gost': m.gost, 'density': m.density, 'price_per_kg': m.price_per_kg}
        for m in items
    ], total, page, page_size)


@router.get("/mobile/equipment")
def mobile_equipment(
    search: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Equipment)
    if search:
        q = q.filter(Equipment.name.ilike(f"%{search}%"))
    q = q.order_by(Equipment.name)
    items, total = _paginate(q, page, page_size)
    return _list_response([
        {'id': e.id, 'name': e.name, 'model': e.model,
         'type': e.type, 'power': e.power, 'cost_per_hour': e.cost_per_hour}
        for e in items
    ], total, page, page_size)


# ——— V12: Mobile production floor actions —————————————————————————


@router.get("/mobile/barcode/{code}",
    summary="Сканировать штрихкод",
    description="Возвращает информацию о партии/наряде по штрихкоду")
def scan_barcode(code: str,
                 db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    """Поиск по штрихкоду WorkOrderItem."""
    from database.models import WorkOrderItem
    woi = db.query(WorkOrderItem).filter(
        WorkOrderItem.barcode == code,
    ).first()

    if not woi:
        raise HTTPException(404, f"Barcode not found: {code}")

    wo = woi.work_order
    product = wo.product if wo else None

    # Найти текущую операцию
    current_op = None
    if woi.current_operation_id:
        op = db.get(Operation, woi.current_operation_id)
        if op:
            current_op = {
                'id': op.id, 'number': op.number, 'name': op.name,
                't_setup': op.t_setup, 't_piece': op.t_piece,
            }

    return {
        'barcode': code,
        'work_order_item_id': woi.id,
        'work_order_id': wo.id if wo else None,
        'work_order_number': wo.number if wo else None,
        'product': product.designation if product else None,
        'qty_total': woi.qty,
        'qty_good': woi.qty_good,
        'qty_scrap': woi.qty_scrap,
        'status': woi.status.value if woi.status else None,
        'current_operation': current_op,
    }


class MobileActionRequest(BaseModel):
    barcode: str
    action: str  # 'start', 'complete', 'scrap'
    qty: int = 1
    note: Optional[str] = None


@router.post("/mobile/action",
    summary="Действие на участке",
    description="start, complete или scrap для партии по штрихкоду")
def mobile_action(body: MobileActionRequest,
                  db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    from datetime import datetime as dt

    from database.models import WorkOrderItem, WorkOrderItemStatus
    from database.models._production import RouteStep, RouteStepStatus

    woi = db.query(WorkOrderItem).filter(
        WorkOrderItem.barcode == body.barcode,
    ).first()
    if not woi:
        raise HTTPException(404, f"Barcode not found: {body.barcode}")

    if body.action == 'start':
        woi.status = WorkOrderItemStatus.IN_PROGRESS
        # Найти первый PENDING RouteStep
        step = db.query(RouteStep).filter(
            RouteStep.work_order_item_id == woi.id,
            RouteStep.status == RouteStepStatus.PENDING,
        ).order_by(RouteStep.seq).first()
        if step:
            step.status = RouteStepStatus.IN_PROGRESS
            step.started_at = dt.now()
            step.worker_user_id = user.id if hasattr(user, 'id') else None
            woi.current_operation_id = step.operation_id
        db.commit()
        return {'action': 'start', 'status': 'ok'}

    elif body.action == 'complete':
        step = db.query(RouteStep).filter(
            RouteStep.work_order_item_id == woi.id,
            RouteStep.status == RouteStepStatus.IN_PROGRESS,
        ).order_by(RouteStep.seq).first()
        if step:
            step.status = RouteStepStatus.DONE
            step.finished_at = dt.now()
            step.qty_good = body.qty
        woi.qty_good += body.qty
        db.commit()
        return {'action': 'complete', 'status': 'ok', 'qty_good': woi.qty_good}

    elif body.action == 'scrap':
        step = db.query(RouteStep).filter(
            RouteStep.work_order_item_id == woi.id,
            RouteStep.status == RouteStepStatus.IN_PROGRESS,
        ).order_by(RouteStep.seq).first()
        if step:
            step.qty_scrap = (step.qty_scrap or 0) + body.qty
        woi.qty_scrap += body.qty
        db.commit()
        return {'action': 'scrap', 'status': 'ok', 'qty_scrap': woi.qty_scrap}

    raise HTTPException(400, f"Unknown action: {body.action}")


