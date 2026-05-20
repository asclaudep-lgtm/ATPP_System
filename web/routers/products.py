"""API изделий."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.models import Product
from web.deps import get_current_user, get_db
from web.schemas import ProductListOut, ProductOut

router = APIRouter(tags=["products"])


@router.get("/products/workshops",
    summary="Список цехов",
    description="Возвращает все производственные цеха для фильтров")
def list_workshops(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from database.models._production import Workshop
    rows = db.query(Workshop).order_by(Workshop.code).all()
    return [{'id': r.id, 'code': r.code, 'name': r.name} for r in rows]


@router.get("/products", response_model=ProductListOut,
    summary="Список изделий",
    description="Поиск по обозначению с пагинацией")
def list_products(
    search: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Product).filter(not Product.is_deleted)
    if search:
        q = q.filter(Product.designation.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Product.designation) \
        .offset((page - 1) * page_size).limit(page_size).all()
    return ProductListOut(
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    p = db.get(Product, product_id)
    if not p or p.is_deleted:
        raise HTTPException(404, "Product not found")
    return ProductOut.model_validate(p)
