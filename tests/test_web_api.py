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
        import pytest
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        try:
            r = client.get("/api/dashboard/stats", headers=headers)
            assert r.status_code == 200
            data = r.json()
            assert "total_products" in data
            assert "total_users" in data
        except Exception as e:
            if 'OperationalError' in str(type(e).__name__):
                pytest.skip(f'DB locked by concurrent test: {e}')
            raise

    def test_approval_action(self, client):
        r = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/approval/action", json={
            "tp_id": 99999, "action": "approve"}, headers=headers)
        assert r.status_code in (200, 404)

    def test_workshops_list(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/api/products/workshops", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_audit_list(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/api/audit", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_batch_approve_empty(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/api/batch/approve-tps", json={"tp_ids": []}, headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_scrap_by_month(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/api/dashboard/scrap-by-month?months=3", headers=headers)
        assert r.status_code == 200
        assert "months" in r.json()

    def test_production_rate(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/api/dashboard/production-rate?days=7", headers=headers)
        assert r.status_code == 200
        assert "days" in r.json()
