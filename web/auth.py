"""JWT-аутентификация для веб-клиента."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError

from web.config import WEB_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE


def create_access_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user.get("role", "user"),
        "exp": datetime.now(timezone.utc) + JWT_EXPIRE,
    }
    return jwt.encode(payload, WEB_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, WEB_SECRET_KEY,
                         algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def login_user(db, username: str, password: str) -> Optional[dict]:
    user = db.authenticate_user(username, password)
    if user is None:
        return None
    user["access_token"] = create_access_token(user)
    return user
