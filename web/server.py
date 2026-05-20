"""FastAPI web server for ATPP.

Запуск:  python -m web.server  (из корня проекта)
Не зависит от desktop-режима — использует ту же БД.
"""
# Ensure project root is importable when running as ``python web/server.py``.
# Running as ``python -m web.server`` from the project root needs no adjustment.
import logging
import sys
import threading
from pathlib import Path

_logger = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parent.parent
if _ROOT not in map(Path, sys.path):
    sys.path.insert(0, str(_ROOT))

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from config import APP_VERSION as _APP_VERSION
from web.config import CORS_ORIGINS, STATIC_DIR
from web.deps import _get_db_manager, get_current_user
from web.routers import (
    approval,
    audit,
    batch,
    bom,
    dashboard,
    editor,
    mobile,
    pdo,
    production,
    products,
    tech_processes,
    tooling,
    work_orders,
)
from web.schemas import LoginRequest

app = FastAPI(title="ATPP Web API", version=_APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(products.router, prefix="/api")
app.include_router(tech_processes.router, prefix="/api")
app.include_router(work_orders.router, prefix="/api")
app.include_router(approval.router, prefix="/api")
app.include_router(bom.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(production.router, prefix="/api")
app.include_router(tooling.router, prefix="/api")
app.include_router(mobile.router, prefix="/api")
app.include_router(pdo.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(batch.router, prefix="/api")
app.include_router(editor.router)

@app.post("/api/auth/login", tags=["auth"],
    summary="Вход в систему",
    description="Логин/пароль или API-ключ (поле api_key). JWT возвращается в httpOnly cookie.")
def login(body: LoginRequest, response: Response):
    from web.auth import login_user, login_user_by_api_key
    api_key = getattr(body, 'api_key', None)
    if api_key:
        user = login_user_by_api_key(_get_db_manager(), api_key)
    else:
        user = login_user(_get_db_manager(), body.username, body.password)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid credentials")
    # AUDIT-011: set httpOnly cookie instead of returning token in JSON body
    from web.config import JWT_EXPIRE
    response.set_cookie(
        key="atpp_token",
        value=user["access_token"],
        httponly=True,
        secure=False,  # False for localhost dev; set True in production with HTTPS
        samesite="lax",
        max_age=int(JWT_EXPIRE.total_seconds()),
    )
    return {
        "access_token": user["access_token"],  # backward compat (clients using JSON body)
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "role": user.get("role"),
        },
    }


@app.post("/api/auth/reset-password", tags=["auth"],
    summary="Сброс пароля (только admin)",
    description="Сбрасывает пароль пользователя. Доступно только администраторам.")
def reset_password(body: dict, user: dict = Depends(get_current_user)):
    # Только admin может сбрасывать пароли других пользователей
    if user.get("role") != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Only admin can reset passwords")
    from web.auth import reset_user_password
    pwd = reset_user_password(_get_db_manager(), body.get("login", ""))
    if pwd is None:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    # Возвращаем новый пароль только admin'у (не в открытый эндпоинт)
    return {"message": "Пароль сброшен.", "new_password": pwd}


@app.post("/api/auth/logout", tags=["auth"],
    summary="Выход из системы",
    description="Удаляет httpOnly cookie с JWT токеном")
def logout(response: Response):
    response.delete_cookie("atpp_token")
    return {"ok": True}


@app.get("/api/health", tags=["system"],
    summary="Проверка здоровья сервера",
    description="Возвращает статус сервера и БД")
def health():
    from sqlalchemy import text as sa_text
    db_status = "ok"
    try:
        db = _get_db_manager()
        with db.get_session() as s:
            s.execute(sa_text("SELECT 1"))
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": _APP_VERSION}


# ——— Rate limiting ————————————————————————

_rate_limit_store: dict = {}  # {ip: [timestamps]}
_rate_limit_lock = threading.Lock()
_RATE_LIMIT_RPM = 60  # requests per minute per IP
_RATE_LIMIT_CLEANUP_EVERY = 100  # cleanup stale IPs every N requests
_rate_limit_counter = 0


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Thread-safe rate limiter: 60 requests per minute per IP."""
    import time as _time

    from fastapi.responses import JSONResponse
    global _rate_limit_counter

    ip = request.client.host if request.client else 'unknown'
    now = _time.time()
    window = now - 60

    with _rate_limit_lock:
        if ip not in _rate_limit_store:
            _rate_limit_store[ip] = [now]
        else:
            _rate_limit_store[ip] = [
                t for t in _rate_limit_store[ip] if t > window]
            _rate_limit_store[ip].append(now)

        over_limit = len(_rate_limit_store[ip]) > _RATE_LIMIT_RPM

        # Periodic cleanup of stale IPs to prevent memory leak
        _rate_limit_counter += 1
        if _rate_limit_counter >= _RATE_LIMIT_CLEANUP_EVERY:
            _rate_limit_counter = 0
            stale = [k for k, v in _rate_limit_store.items()
                     if not v or v[-1] < window]
            for k in stale:
                del _rate_limit_store[k]

    if over_limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Wait."})

    return await call_next(request)


# ——— Prometheus metrics ————————————————————————

_metrics_lock = threading.Lock()
_request_count = 0
_request_errors = 0
_request_latency_sum = 0.0


@app.middleware("http")
async def metrics_middleware(request, call_next):
    import time
    global _request_count, _request_errors, _request_latency_sum
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception:
        with _metrics_lock:
            _request_count += 1
            _request_errors += 1
            _request_latency_sum += time.time() - t0
        raise
    with _metrics_lock:
        _request_count += 1
        _request_latency_sum += time.time() - t0
    return response


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus text format endpoint for scraping."""
    with _metrics_lock:
        count = _request_count
        errors = _request_errors
        latency = _request_latency_sum
    lines = [
        "# HELP atpp_requests_total Total HTTP requests.",
        "# TYPE atpp_requests_total counter",
        f"atpp_requests_total {count}",
        "# HELP atpp_requests_errors_total Total HTTP errors.",
        "# TYPE atpp_requests_errors_total counter",
        f"atpp_requests_errors_total {errors}",
        "# HELP atpp_request_latency_seconds_sum Total latency.",
        "# TYPE atpp_request_latency_seconds_sum counter",
        f"atpp_request_latency_seconds_sum {latency:.6f}",
    ]
    return "\n".join(lines) + "\n"


# ——— Push notification helper ———————————————————

def send_push_alert(alert_type: str, title: str, message: str):
    """Broadcast a push alert to all connected WebSocket clients."""
    import asyncio
    data = {
        'type': 'alert',
        'alert_type': alert_type,
        'title': title,
        'message': message,
        'ts': datetime.now().isoformat(),
    }
    try:
        asyncio.get_running_loop()
        asyncio.create_task(ws_manager.broadcast(data))
    except RuntimeError:
        pass  # Not in async context
    except Exception:
        _logger.exception("Unhandled error")


# ——— WebSocket: IoT live updates ———


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        try:
            self.active.remove(ws)
        except ValueError:
            pass  # already removed

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in list(self.active):  # iterate over copy
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


def _ws_verify_token(websocket: WebSocket) -> Optional[dict]:
    """Extract and verify JWT from WebSocket query param or cookie."""
    from web.auth import verify_token
    # Try query parameter first: ws://host/ws/iot?token=...
    token = websocket.query_params.get('token')
    if not token:
        # Try cookie
        token = websocket.cookies.get('atpp_token')
    if not token:
        return None
    return verify_token(token)


@app.websocket("/ws/iot")
async def ws_iot(websocket: WebSocket):
    # Auth: verify JWT before accepting connection
    payload = _ws_verify_token(websocket)
    if payload is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            # Отправляем статус станков каждые 3 секунды
            db = _get_db_manager()
            with db.get_session() as s:
                from modules.iot_collector import get_all_machine_statuses
                machines = get_all_machine_statuses(s)
            await websocket.send_text(json.dumps({
                'type': 'machine_status',
                'data': machines,
                'ts': datetime.now().isoformat(),
            }))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/kpi")
async def ws_kpi(websocket: WebSocket):
    """Live KPI dashboard — broadcast stats every 3 seconds."""
    # Auth: verify JWT before accepting connection
    payload = _ws_verify_token(websocket)
    if payload is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            db = _get_db_manager()
            with db.get_session() as s:
                from database.models import (
                    Product,
                    ScrapRecord,
                    TechProcess,
                    WorkOrder,
                )
                total_products = s.query(Product).filter(
                    not Product.is_deleted).count()
                total_tps = s.query(TechProcess).filter(
                    not TechProcess.is_deleted).count()
                active_wos = s.query(WorkOrder).filter(
                    not WorkOrder.is_deleted,
                    WorkOrder.status.in_([
                        'RELEASED', 'REGISTERED', 'IN_PROGRESS']),
                ).count()
                today = __import__('datetime').datetime.now().strftime(
                    '%Y-%m-%d')
                scrap_today = s.query(ScrapRecord).filter(
                    ScrapRecord.created_at >= today).count()

            await websocket.send_text(json.dumps({
                'type': 'kpi',
                'data': {
                    'products': total_products,
                    'tech_processes': total_tps,
                    'active_orders': active_wos,
                    'scrap_today': scrap_today,
                    'health': 'ok',
                },
                'ts': datetime.now().isoformat(),
            }))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# Serve SPA from dist/ if built, otherwise redirect to API docs
DIST_DIR = STATIC_DIR / "dist"
if (DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="spa")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    @app.get("/")
    def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/docs")


def main():
    import uvicorn
    _get_db_manager().init_database()
    uvicorn.run("web.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
