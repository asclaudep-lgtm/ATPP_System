"""Настройки веб-сервера ATPP."""
import os
import secrets
from pathlib import Path
from datetime import timedelta

_WEB_SECRET_ENV = os.getenv("ATPP_WEB_SECRET")
if _WEB_SECRET_ENV:
    WEB_SECRET_KEY = _WEB_SECRET_ENV
else:
    WEB_SECRET_KEY = secrets.token_urlsafe(48)
    import sys
    print(
        f"[WARN] ATPP_WEB_SECRET not set — generated random key: {WEB_SECRET_KEY[:12]}...",
        file=sys.stderr,
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE = timedelta(hours=8)
CORS_ORIGINS = os.getenv(
    "ATPP_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8000",
).split(",")
STATIC_DIR = Path(__file__).parent / "static"
