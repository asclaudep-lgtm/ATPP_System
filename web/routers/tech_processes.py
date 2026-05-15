"""API технологических процессов."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from web.schemas import TechProcessOut, TPListOut
from database.models import TechProcess

router = APIRouter(tags=["tech-processes"])


@router.get("/tech-processes", response_model=TPListOut)
def list_tps(
    search: str = Query(""),
    status: str = Query(""),
    product_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
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
    total = q.count()
    items = q.order_by(TechProcess.number) \
        .offset((page - 1) * page_size).limit(page_size).all()

    def _status_str(tp):
        return tp.status.value if hasattr(tp.status, 'value') \
            else str(tp.status)

    def _tech_str(tp):
        return tp.technology_type.value \
            if tp.technology_type and hasattr(tp.technology_type, 'value') \
            else str(tp.technology_type or '')

    return TPListOut(
        items=[TechProcessOut(
            id=tp.id, number=tp.number, product_id=tp.product_id,
            status=_status_str(tp), version=tp.version,
            technology_type=_tech_str(tp),
            execution_variant=tp.execution_variant,
            created_at=tp.created_at,
        ) for tp in items],
        total=total,
    )


@router.get("/tech-processes/{tp_id}")
def get_tp(
    tp_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    tp = db.get(TechProcess, tp_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")

    def _status_str(t):
        return t.status.value if hasattr(t.status, 'value') else str(t.status)

    def _tech_str(t):
        return t.technology_type.value \
            if t.technology_type and hasattr(t.technology_type, 'value') \
            else str(t.technology_type or '')

    return {
        "id": tp.id,
        "number": tp.number,
        "product_id": tp.product_id,
        "product_designation": tp.product.designation if tp.product else "",
        "product_name": tp.product.name if tp.product else "",
        "status": _status_str(tp),
        "technology_type": _tech_str(tp),
        "version": tp.version,
        "execution_variant": tp.execution_variant,
        "operations": [
            {
                "number": op.number,
                "name": op.name,
                "equipment": op.equipment.name if op.equipment else "",
                "t_setup": op.t_setup,
                "t_piece": op.t_piece,
                "shop": op.shop,
            }
            for op in sorted(tp.operations, key=lambda o: o.sort_order or 0)
            if not op.is_deleted
        ],
        "created_at": tp.created_at.isoformat() if tp.created_at else None,
    }
