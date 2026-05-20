"""JWT-аутентификация для веб-клиента."""
from datetime import datetime, timezone
from typing import Optional

from jose import JWTError, jwt

from web.config import JWT_ALGORITHM, JWT_EXPIRE, WEB_SECRET_KEY


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


def login_user_by_api_key(db, api_key: str) -> Optional[dict]:
    """Вход через API-ключ (Bearer token или atpp_ префикс)."""
    with db.get_session() as s:
        from database.models import User
        user = s.query(User).filter(
            User.api_key == api_key,
            User.is_active,
        ).first()
        if user is None:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "access_token": create_access_token({
                "id": user.id,
                "username": user.username,
                "role": user.role,
            }),
        }


def reset_user_password(db, login: str) -> Optional[str]:
    """Сброс пароля: возвращает новый пароль или None."""
    import secrets
    with db.get_session() as s:
        from database.models import User
        user = s.query(User).filter(
            (User.username == login) | (User.email == login),
            User.is_active,
        ).first()
        if user is None:
            return None
        new_pw = secrets.token_urlsafe(8)
        user.password_hash = db._hash_password(new_pw)
        # Note: no explicit commit — get_session() auto-commits on exit
        return new_pw
