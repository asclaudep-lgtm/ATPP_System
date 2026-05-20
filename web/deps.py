"""FastAPI-зависимости (DI): БД и текущий пользователь."""
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import threading

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.db_manager import DatabaseManager
from web.auth import verify_token

security = HTTPBearer(auto_error=False)

_db_manager = None
_db_lock = threading.Lock()


def _get_db_manager():
    global _db_manager
    if _db_manager is None:
        with _db_lock:
            if _db_manager is None:
                from config import DATABASE_URL
                _db_manager = DatabaseManager(database_url=DATABASE_URL)
    return _db_manager


def get_db():
    """Yield SQLAlchemy session (commit on success, rollback on error)."""
    with _get_db_manager().get_session() as s:
        yield s



async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db=Depends(get_db),
) -> dict:
    """Extract JWT from httpOnly cookie (preferred) or Authorization header (backward compat)."""
    token = None
    # AUDIT-011: read from httpOnly cookie first
    token = request.cookies.get("atpp_token")
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = int(payload.get("sub", 0))
    from database.models import User
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
    }


def require_role(*allowed_roles: str):
    """FastAPI dependency factory: restrict endpoint to specific roles.

    Usage::

        @router.post("/products")
        def create(user=Depends(require_role("admin", "technologist"))):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}",
            )
        return user
    return _check


# Pre-built role dependencies for convenience
require_admin = require_role("admin")
require_editor = require_role("admin", "technologist", "engineer")
require_viewer = require_role("admin", "technologist", "engineer", "foreman", "user")
