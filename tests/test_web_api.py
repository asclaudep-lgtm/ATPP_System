"""Тесты FastAPI веб-клиента (синхронные, через TestClient)."""
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(db_manager):
    """FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from web.server import app
    return TestClient(app)


class TestWebAPI:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_login_success(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "WRONG"})
        assert r.status_code == 401

    def test_products_list_unauthorized(self, client):
        r = client.get("/api/products")
        assert r.status_code in (401, 403)  # unauthorized: no auth header

    def test_products_list(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/products", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_dashboard_stats(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/api/dashboard/stats", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_products" in data
        assert "total_users" in data

    def test_approval_action(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/approval/action", json={
            "tp_id": 99999, "action": "approve"}, headers=headers)
        assert r.status_code == 404
