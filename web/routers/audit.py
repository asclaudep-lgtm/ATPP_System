"""GET /api/audit — журнал изменений с диффами полей."""
from fastapi import APIRouter, Query

from web.deps import _get_db_manager
from modules.audit import list_audit_enriched

router = APIRouter(tags=["audit"])


@router.get("/audit")
def get_audit(entity_type: str = Query(None),
              action: str = Query(None),
              limit: int = Query(500, ge=1, le=2000)):
    db = _get_db_manager()
    return list_audit_enriched(db, limit=limit, entity_type=entity_type, action=action)
