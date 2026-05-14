"""FastAPI-зависимости (DI): БД и текущий пользователь."""
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import threading

from database.db_manager import DatabaseManager
from web.auth import verify_token

security = HTTPBearer()

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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
) -> dict:
    """Извлечь и проверить JWT, вернуть данные пользователя."""
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = int(payload.get("sub", 0))
    from database.models import User
    user = db.query(User).get(user_id)
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
