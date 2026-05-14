"""Tooling API — issue/return, history, inventory."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from web.deps import get_db, get_current_user
from database.models import ToolingItem, ToolingIssue

router = APIRouter(tags=["tooling"])


@router.get("/tooling/items")
def list_tooling_items(search: str = Query(""),
                       db: Session = Depends(get_db),
                       _=Depends(get_current_user)):
    q = db.query(ToolingItem)
    if search:
        q = q.filter(
            (ToolingItem.name.ilike(f"%{search}%")) |
            (ToolingItem.inventory_no.ilike(f"%{search}%"))
        )
    items = q.order_by(ToolingItem.inventory_no).limit(200).all()
    return [{
        "id": ti.id, "inventory_no": ti.inventory_no,
        "name": ti.name, "location": ti.location or "",
        "status": ti.status.value if hasattr(ti.status, 'value') else str(ti.status),
        "wear_percent": ti.wear_percent or 0,
    } for ti in items]


@router.get("/tooling/issues")
def list_tooling_issues(tooling_item_id: Optional[int] = Query(None),
                        active_only: bool = Query(False),
                        db: Session = Depends(get_db),
                        _=Depends(get_current_user)):
    q = db.query(ToolingIssue)
    if tooling_item_id:
        q = q.filter(ToolingIssue.tooling_item_id == tooling_item_id)
    if active_only:
        q = q.filter(ToolingIssue.returned_at.is_(None))
    issues = q.order_by(ToolingIssue.issued_at.desc()).limit(200).all()
    return [{
        "id": i.id, "tooling_item_id": i.tooling_item_id,
        "work_order_id": i.work_order_id,
        "issued_at": str(i.issued_at) if i.issued_at else None,
        "returned_at": str(i.returned_at) if i.returned_at else None,
        "issued_to": i.issued_to or "",
        "notes": i.notes or "",
    } for i in issues]


@router.get("/tooling/history/{tooling_item_id}")
def get_tooling_history(tooling_item_id: int,
                        db: Session = Depends(get_db),
                        _=Depends(get_current_user)):
    ti = db.query(ToolingItem).get(tooling_item_id)
    if not ti:
        raise HTTPException(404, "Tooling item not found")
    issues = db.query(ToolingIssue).filter(
        ToolingIssue.tooling_item_id == tooling_item_id
    ).order_by(ToolingIssue.issued_at.desc()).all()
    return {
        "item": {
            "id": ti.id, "inventory_no": ti.inventory_no,
            "name": ti.name,
            "status": ti.status.value if hasattr(ti.status, 'value') else str(ti.status),
        },
        "issues": [{
            "id": i.id, "work_order_id": i.work_order_id,
            "issued_at": str(i.issued_at) if i.issued_at else None,
            "returned_at": str(i.returned_at) if i.returned_at else None,
            "issued_to": i.issued_to or "",
        } for i in issues],
    }
