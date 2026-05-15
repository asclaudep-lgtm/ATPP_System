"""API состава изделия (BOM)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from database.models import Product
from modules.bom import get_bom_tree, get_bom_flat

router = APIRouter(tags=["bom"])


@router.get("/bom/{product_id}")
def get_product_bom(
    product_id: int,
    flat: bool = False,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    if flat:
        return {"product_id": product_id, "rows": get_bom_flat(
            db, product_id=product_id)}

    tree = get_bom_tree(db, product_id=product_id)

    def _serialize_node(node):
        return {
            "id": node.id,
            "product_id": node.product_id,
            "designation": node.product_designation,
            "name": node.product_name,
            "level": node.level,
            "quantity": node.quantity,
            "position": node.position,
            "has_tp": node.has_tp,
            "children": [_serialize_node(c) for c in node.children],
        }

    return {"product_id": product_id, "tree": [_serialize_node(n) for n in tree]}
