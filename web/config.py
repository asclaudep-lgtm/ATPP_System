"""Настройки веб-сервера ATPP."""
import os
from pathlib import Path
from datetime import timedelta

WEB_SECRET_KEY = os.getenv("ATPP_WEB_SECRET", "change-me-in-production-atpp-v10")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE = timedelta(hours=8)
CORS_ORIGINS = os.getenv(
    "ATPP_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8000",
).split(",")
STATIC_DIR = Path(__file__).parent / "static"
