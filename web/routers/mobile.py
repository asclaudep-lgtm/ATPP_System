"""Mobile-friendly REST API — consistent pagination, filtering, sorting.

All endpoints return {items, total, page, page_size} for list operations.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from web.deps import get_db, get_current_user
from database.models import (
    Product, TechProcess, WorkOrder, Material, Equipment,
    Operation, TPStatus, WorkOrderStatus,
)

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
    q = db.query(Product).filter(Product.is_deleted == False)
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
    p = db.query(Product).get(product_id)
    if not p or p.is_deleted:
        raise HTTPException(404, "Product not found")
    tps = db.query(TechProcess).filter(
        TechProcess.product_id == product_id,
        TechProcess.is_deleted == False,
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
    q = db.query(TechProcess).filter(TechProcess.is_deleted == False)
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
    tp = db.query(TechProcess).get(tp_id)
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
    q = db.query(WorkOrder).filter(WorkOrder.is_deleted == False)
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
