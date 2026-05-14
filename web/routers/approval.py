"""API workflow утверждения ТП."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.deps import get_db, get_current_user
from web.schemas import ApprovalAction
from database.models import TechProcess, TPStatus
from modules.audit import log_change_session

router = APIRouter(tags=["approval"])


@router.post("/approval/action")
def approval_action(
    body: ApprovalAction,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    tp = db.query(TechProcess).get(body.tp_id)
    if not tp or tp.is_deleted:
        raise HTTPException(404, "TechProcess not found")

    if user["role"] not in ("admin", "technologist"):
        raise HTTPException(403, "Only admin/technologist can approve")

    action = body.action.lower()
    if action == "approve":
        tp.status = TPStatus.APPROVED
    elif action == "reject":
        tp.status = TPStatus.REVIEW
    elif action == "send_for_rework":
        tp.status = TPStatus.REWORK
    else:
        raise HTTPException(400, f"Unknown action: {body.action}")

    db.flush()
    log_change_session(db, user_id=user.get('id'), entity_type='TechProcess',
                       entity_id=tp.id, action=action,
                       description=f'Web: TP {tp.number} → {body.action}')
    return {
        "ok": True,
        "tp_id": tp.id,
        "new_status": tp.status.value
        if hasattr(tp.status, 'value') else str(tp.status),
    }
