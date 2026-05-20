"""V12: CRUD API — создание, редактирование, удаление основных сущностей."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import (
    Operation,
    Product,
    TechProcess,
    TPStatus,
    WorkOrder,
    WorkOrderStatus,
)
from web.deps import get_current_user, get_db

router = APIRouter(prefix="/api/editor", tags=["editor"])


# ═══════════════════════════════════════════════════════════════════
# Products CRUD
# ═══════════════════════════════════════════════════════════════════

class ProductCreate(BaseModel):
    designation: str
    name: str
    material_id: Optional[int] = None
    mass: Optional[float] = None
    dimensions: Optional[str] = None
    accuracy_class: Optional[str] = None
    blank_type: Optional[str] = None
    roughness: Optional[str] = None
    group_id: Optional[int] = None


class ProductUpdate(BaseModel):
    designation: Optional[str] = None
    name: Optional[str] = None
    material_id: Optional[int] = None
    mass: Optional[float] = None
    dimensions: Optional[str] = None
    accuracy_class: Optional[str] = None
    blank_type: Optional[str] = None
    roughness: Optional[str] = None
    group_id: Optional[int] = None


@router.post("/products", summary="Создать изделие")
def create_product(body: ProductCreate,
                   db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "designation": p.designation, "name": p.name}


@router.put("/products/{product_id}", summary="Обновить изделие")
def update_product(product_id: int, body: ProductUpdate,
                   db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    p = db.get(Product, product_id)
    if not p or p.is_deleted:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return {"id": p.id, "designation": p.designation}


@router.delete("/products/{product_id}", summary="Удалить изделие (soft)")
def delete_product(product_id: int,
                   db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    p = db.get(Product, product_id)
    if not p or p.is_deleted:
        raise HTTPException(404, "Product not found")
    p.is_deleted = True
    db.commit()
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════════
# TechProcess CRUD
# ═══════════════════════════════════════════════════════════════════

class TPCreate(BaseModel):
    product_id: int
    number: str
    tp_type: Optional[str] = "SINGLE"
    technology_type: Optional[str] = "MACHINING"
    description: Optional[str] = None
    author_id: Optional[int] = None


class TPUpdate(BaseModel):
    number: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.post("/tech-processes", summary="Создать техпроцесс")
def create_tp(body: TPCreate,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    product = db.get(Product, body.product_id)
    if not product or product.is_deleted:
        raise HTTPException(404, "Product not found")

    from database.models import TechnologyType, TPType
    tp_type = getattr(TPType, body.tp_type, TPType.SINGLE)
    tech_type = getattr(TechnologyType, body.technology_type,
                        TechnologyType.MACHINING)

    tp = TechProcess(
        product_id=body.product_id,
        number=body.number,
        tp_type=tp_type,
        technology_type=tech_type,
        description=body.description,
        author_id=body.author_id,
        status=TPStatus.DRAFT,
    )
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return {"id": tp.id, "number": tp.number, "product_id": tp.product_id}


@router.put("/tech-processes/{tp_id}", summary="Обновить техпроцесс")
def update_tp(tp_id: int, body: TPUpdate,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    tp = db.get(TechProcess, tp_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(tp, k, v)
    db.commit()
    return {"id": tp.id}


@router.delete("/tech-processes/{tp_id}", summary="Удалить техпроцесс (soft)")
def delete_tp(tp_id: int,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    tp = db.get(TechProcess, tp_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")
    tp.is_deleted = True
    db.commit()
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════════
# Operations CRUD
# ═══════════════════════════════════════════════════════════════════

class OpCreate(BaseModel):
    tech_process_id: int
    number: str
    name: str
    equipment_id: Optional[int] = None
    profession_id: Optional[int] = None
    grade: Optional[int] = None
    shop: Optional[str] = None
    t_setup: float = 0.0
    t_piece: float = 0.0
    t_main: Optional[float] = None
    t_auxiliary: Optional[float] = None
    sort_order: int = 0


class OpUpdate(BaseModel):
    number: Optional[str] = None
    name: Optional[str] = None
    equipment_id: Optional[int] = None
    profession_id: Optional[int] = None
    grade: Optional[int] = None
    shop: Optional[str] = None
    t_setup: Optional[float] = None
    t_piece: Optional[float] = None
    t_main: Optional[float] = None
    t_auxiliary: Optional[float] = None
    sort_order: Optional[int] = None


@router.post("/operations", summary="Добавить операцию в ТП")
def create_operation(body: OpCreate,
                     db: Session = Depends(get_db),
                     _=Depends(get_current_user)):
    tp = db.get(TechProcess, body.tech_process_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")
    op = Operation(**body.model_dump())
    db.add(op)
    db.commit()
    db.refresh(op)
    return {"id": op.id, "number": op.number, "name": op.name}


@router.put("/operations/{op_id}", summary="Обновить операцию")
def update_operation(op_id: int, body: OpUpdate,
                     db: Session = Depends(get_db),
                     _=Depends(get_current_user)):
    op = db.get(Operation, op_id)
    if not op or op.is_deleted:
        raise HTTPException(404, "Operation not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(op, k, v)
    db.commit()
    return {"id": op.id}


@router.delete("/operations/{op_id}", summary="Удалить операцию (soft)")
def delete_operation(op_id: int,
                     db: Session = Depends(get_db),
                     _=Depends(get_current_user)):
    op = db.get(Operation, op_id)
    if not op or op.is_deleted:
        raise HTTPException(404, "Operation not found")
    op.is_deleted = True
    db.commit()
    return {"deleted": True}


@router.put("/operations/reorder/{tp_id}", summary="Переупорядочить операции ТП")
def reorder_operations(tp_id: int, order: List[int],
                       db: Session = Depends(get_db),
                       _=Depends(get_current_user)):
    """Принимает список operation_id в новом порядке."""
    for i, op_id in enumerate(order):
        op = db.get(Operation, op_id)
        if op and op.tech_process_id == tp_id:
            op.sort_order = i
            op.number = f'{i * 5 + 5:03d}'
    db.commit()
    return {"reordered": len(order)}


# ═══════════════════════════════════════════════════════════════════
# Work Orders CRUD
# ═══════════════════════════════════════════════════════════════════

class WOCreate(BaseModel):
    product_id: int
    tech_process_id: int
    number: Optional[str] = None
    qty_total: int = 1
    priority: int = 3
    due_date: Optional[str] = None


class WOUpdate(BaseModel):
    qty_total: Optional[int] = None
    priority: Optional[int] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


@router.post("/work-orders", summary="Создать наряд")
def create_wo(body: WOCreate,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    tp = db.get(TechProcess, body.tech_process_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")

    number = body.number or f'WO-{datetime.now().strftime("%Y%m%d%H%M")}'
    from datetime import date as d
    due_date = d.fromisoformat(body.due_date) if body.due_date else None

    wo = WorkOrder(
        product_id=body.product_id,
        tech_process_id=body.tech_process_id,
        number=number,
        qty_total=body.qty_total,
        priority=body.priority,
        due_date=due_date,
        status=WorkOrderStatus.RELEASED,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return {"id": wo.id, "number": wo.number, "status": wo.status.value}


@router.put("/work-orders/{wo_id}", summary="Обновить наряд")
def update_wo(wo_id: int, body: WOUpdate,
              db: Session = Depends(get_db),
              _=Depends(get_current_user)):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(404, "WorkOrder not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            if k == 'due_date':
                from datetime import date as d
                v = d.fromisoformat(v)
            if k == 'status':
                v = getattr(WorkOrderStatus, v, wo.status)
            setattr(wo, k, v)
    db.commit()
    return {"id": wo.id, "status": wo.status.value if wo.status else None}


# ═══════════════════════════════════════════════════════════════════
# Documents export
# ═══════════════════════════════════════════════════════════════════

class DocExportRequest(BaseModel):
    tech_process_id: int
    doc_type: str = "MK"  # MK, title, OK, pack, VO, VM, KK
    output_format: str = "xlsx"  # xlsx, docx, pdf


@router.post("/documents/generate", summary="Сгенерировать ГОСТ-документ")
def generate_document(body: DocExportRequest,
                      db: Session = Depends(get_db),
                      _=Depends(get_current_user)):
    """Generate and return path(s) to GOST document(s)."""
    tp = db.get(TechProcess, body.tech_process_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")

    from modules.doc_generator import DocumentGenerator
    gen = DocumentGenerator(db)

    doc_type = body.doc_type.upper()
    fmt = body.output_format

    if doc_type == 'MK':
        result = gen.generate_route_card(tp.id, fmt)
    elif doc_type == 'TITLE':
        result = gen.generate_title_page(tp.id, fmt)
    elif doc_type == 'OK':
        result = gen.generate_all_operation_cards(tp.id, fmt)
    elif doc_type == 'PACK':
        result = gen.generate_document_pack(tp.id)
    elif doc_type == 'VO':
        result = gen.generate_tooling_list(tp.id, fmt)
    elif doc_type == 'VM':
        result = gen.generate_material_specification(tp.id, fmt)
    elif doc_type == 'KK':
        result = gen.generate_control_card(tp.id, fmt)
    else:
        raise HTTPException(400, f"Unsupported doc_type: {body.doc_type}")

    if isinstance(result, list):
        return {"generated": True, "doc_type": body.doc_type,
                "files": [str(p) for p in result]}
    return {"generated": True, "doc_type": body.doc_type,
            "file_path": str(result)}


# ═══════════════════════════════════════════════════════════════════
# Time norm calculation
# ═══════════════════════════════════════════════════════════════════

class NormCalcRequest(BaseModel):
    tech_process_id: int
    production_type: str = "batch"  # single, small_batch, batch, mass


@router.post("/calculate-norms", summary="Автоматический расчёт норм времени")
def calculate_norms(body: NormCalcRequest,
                    db: Session = Depends(get_db),
                    _=Depends(get_current_user)):
    """Calculate Tшт/Тпз for all operations in a TP."""
    tp = db.get(TechProcess, body.tech_process_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")

    from modules.time_norms import TimeNormCalculator
    calc = TimeNormCalculator(body.production_type)
    results = calc.calculate_for_tp(tp)

    return {"tech_process_id": tp.id, "operations": results}
