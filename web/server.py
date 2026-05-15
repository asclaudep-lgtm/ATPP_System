"""FastAPI web server for ATPP.

Запуск:  python -m web.server  (из корня проекта)
Не зависит от desktop-режима — использует ту же БД.
"""
import sys
from pathlib import Path

# Ensure project root is importable when running as ``python web/server.py``.
# Running as ``python -m web.server`` from the project root needs no adjustment.
_ROOT = Path(__file__).resolve().parent.parent
if _ROOT not in map(Path, sys.path):
    sys.path.insert(0, str(_ROOT))

import asyncio
import json
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.config import CORS_ORIGINS, STATIC_DIR
from web.deps import _get_db_manager
from web.schemas import LoginRequest
from web.routers import (products, tech_processes, work_orders,
                          approval, bom, dashboard, production, tooling,
                          mobile, pdo)

app = FastAPI(title="ATPP Web API", version="10.0.0")

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


@app.post("/api/auth/login")
def login(body: LoginRequest):
    from web.auth import login_user
    user = login_user(_get_db_manager(), body.username, body.password)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid username or password")
    return {
        "access_token": user["access_token"],
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "role": user.get("role"),
        },
    }


@app.get("/api/health")
def health():
    db_status = "ok"
    try:
        db = _get_db_manager()
        with db.get_session() as s:
            s.execute("SELECT 1")
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": "11.0.0"}


# ——— Rate limiting ————————————————————————

_rate_limit_store = {}  # {ip: [timestamps]}


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Simple rate limiter: 60 requests per minute per IP."""
    from fastapi.responses import JSONResponse
    import time as _time

    ip = request.client.host if request.client else 'unknown'
    now = _time.time()
    window = now - 60

    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = [now]
    else:
        _rate_limit_store[ip] = [
            t for t in _rate_limit_store[ip] if t > window]
        _rate_limit_store[ip].append(now)

    if len(_rate_limit_store[ip]) > 60:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Wait."})

    return await call_next(request)


# ——— Prometheus metrics ————————————————————————

_request_count = 0
_request_errors = 0
_request_latency_sum = 0.0


@app.middleware("http")
async def metrics_middleware(request, call_next):
    import time
    global _request_count, _request_errors, _request_latency_sum
    _request_count += 1
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception:
        _request_errors += 1
        raise
    finally:
        _request_latency_sum += time.time() - t0
    return response


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus text format endpoint for scraping."""
    lines = [
        "# HELP atpp_requests_total Total HTTP requests.",
        "# TYPE atpp_requests_total counter",
        f"atpp_requests_total {_request_count}",
        "# HELP atpp_requests_errors_total Total HTTP errors.",
        "# TYPE atpp_requests_errors_total counter",
        f"atpp_requests_errors_total {_request_errors}",
        "# HELP atpp_request_latency_seconds_sum Total latency.",
        "# TYPE atpp_request_latency_seconds_sum counter",
        f"atpp_request_latency_seconds_sum {_request_latency_sum:.6f}",
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
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast(data))
    except Exception:
        pass


# ——— WebSocket: IoT live updates ———


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                self.disconnect(ws)


ws_manager = ConnectionManager()


@app.websocket("/ws/iot")
async def ws_iot(websocket: WebSocket):
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
    await ws_manager.connect(websocket)
    try:
        while True:
            db = _get_db_manager()
            with db.get_session() as s:
                from database.models import (
                    Product, TechProcess, WorkOrder,
                    ScrapRecord,
                )
                total_products = s.query(Product).filter(
                    Product.is_deleted == False).count()
                total_tps = s.query(TechProcess).filter(
                    TechProcess.is_deleted == False).count()
                active_wos = s.query(WorkOrder).filter(
                    WorkOrder.is_deleted == False,
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
