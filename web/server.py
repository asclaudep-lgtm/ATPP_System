"""FastAPI web server for ATPP.

Запуск:  python -m web.server  или  python web/server.py
Не зависит от desktop-режима — использует ту же БД.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
                          approval, bom, dashboard)

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
    return {"status": "ok", "version": "10.0.0"}


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
                pass


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


# Serve static SPA if built, otherwise redirect to API docs
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True),
              name="static")
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
