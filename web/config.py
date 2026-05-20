"""Настройки веб-сервера ATPP."""
import os
import secrets
from datetime import timedelta
from pathlib import Path

_WEB_SECRET_ENV = os.getenv("ATPP_WEB_SECRET")
_ENV_MODE = os.getenv("ATPP_ENV", "development").lower()

if _WEB_SECRET_ENV:
    WEB_SECRET_KEY = _WEB_SECRET_ENV
elif _ENV_MODE == "production":
    raise RuntimeError(
        "ATPP_WEB_SECRET environment variable MUST be set in production! "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )
else:
    WEB_SECRET_KEY = secrets.token_urlsafe(48)
    import sys
    print(
        "[WARN] ATPP_WEB_SECRET not set — using auto-generated key. "
        "Tokens will be invalidated on restart. "
        "Set ATPP_WEB_SECRET env var for production!",
        file=sys.stderr,
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE = timedelta(hours=8)
CORS_ORIGINS = os.getenv(
    "ATPP_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8000",
).split(",")
STATIC_DIR = Path(__file__).parent / "static"
