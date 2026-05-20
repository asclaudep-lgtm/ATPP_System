"""Тесты FastAPI веб-клиента (синхронные, через TestClient)."""
import pytest
from pathlib import Path
import sys
import time as _time
from random import randint as _rand

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_UID = str(int(_time.time()))[-6:] + str(_rand(100, 999))


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

    # ── V12 Editor API tests ──

    def _auth(self, client):
        r = client.post("/api/auth/login",
                       json={"username": "admin", "password": "admin"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_editor_create_product(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-1", "name": "Тестовое изделие",
            "mass": 5.0, "accuracy_class": "IT7",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["designation"] == f"API-{_UID}-1"

    def test_editor_update_product(self, client):
        headers = self._auth(client)
        # Create first
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-2", "name": "Обновляемое",
        }, headers=headers)
        pid = r.json()["id"]
        # Update
        r = client.put(f"/api/editor/products/{pid}", json={
            "name": "Обновлённое изделие",
        }, headers=headers)
        assert r.status_code == 200

    def test_editor_delete_product(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-3", "name": "Удаляемое",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.delete(f"/api/editor/products/{pid}", headers=headers)
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_editor_create_tp(self, client):
        headers = self._auth(client)
        # Need product first
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-4", "name": "Изделие для ТП",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-API-{_UID}-001",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["number"] == f"TP-API-{_UID}-001"

    def test_editor_create_operation(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": "API-CREATEOP-005", "name": "Изделие с операцией",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-CREATEOP-{_UID}-002",
        }, headers=headers)
        tpid = r.json()["id"]
        r = client.post("/api/editor/operations", json={
            "tech_process_id": tpid, "number": "005",
            "name": "Токарная", "t_setup": 10.0, "t_piece": 15.0,
        }, headers=headers)
        assert r.status_code == 200

    def test_editor_update_operation(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-6", "name": "Обновление операции",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-API-{_UID}-003",
        }, headers=headers)
        tpid = r.json()["id"]
        r = client.post("/api/editor/operations", json={
            "tech_process_id": tpid, "number": "005",
            "name": "Фрезерная", "t_piece": 12.0,
        }, headers=headers)
        opid = r.json()["id"]
        r = client.put(f"/api/editor/operations/{opid}", json={
            "t_piece": 14.0,
        }, headers=headers)
        assert r.status_code == 200

    def test_editor_create_wo(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-7", "name": "Изделие для наряда",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-API-{_UID}-004",
        }, headers=headers)
        tpid = r.json()["id"]
        r = client.post("/api/editor/work-orders", json={
            "product_id": pid, "tech_process_id": tpid,
            "qty_total": 10, "priority": 5,
            "number": f"WO-CREATE-{_UID}",
        }, headers=headers)
        assert r.status_code == 200
        assert "производство" in r.json()["status"].lower()

    def test_editor_update_wo(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-8", "name": "Наряд обновление",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-API-{_UID}-005",
        }, headers=headers)
        tpid = r.json()["id"]
        r = client.post("/api/editor/work-orders", json={
            "product_id": pid, "tech_process_id": tpid,
            "qty_total": 5,
            "number": f"WO-UPDATE-{_UID}",
        }, headers=headers)
        woid = r.json()["id"]
        r = client.put(f"/api/editor/work-orders/{woid}", json={
            "qty_total": 15,
        }, headers=headers)
        assert r.status_code == 200

    def test_editor_reorder_operations(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": f"API-{_UID}-9", "name": "Reorder test",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/tech-processes", json={
            "product_id": pid, "number": f"TP-API-{_UID}-006",
        }, headers=headers)
        tpid = r.json()["id"]
        r1 = client.post("/api/editor/operations", json={
            "tech_process_id": tpid, "number": "005",
            "name": "Первая", "sort_order": 0,
        }, headers=headers)
        r2 = client.post("/api/editor/operations", json={
            "tech_process_id": tpid, "number": "010",
            "name": "Вторая", "sort_order": 1,
        }, headers=headers)
        r = client.put(f"/api/editor/operations/reorder/{tpid}",
                      json=[r2.json()["id"], r1.json()["id"]],
                      headers=headers)
        assert r.status_code == 200

    def test_editor_document_generate(self, client):
        headers = self._auth(client)
        r = client.post("/api/editor/products", json={
            "designation": "API-010", "name": "Документ тест",
        }, headers=headers)
        pid = r.json()["id"]
        r = client.post("/api/editor/documents/generate", json={
            "product_id": pid, "doc_type": "MK",
        }, headers=headers)
        # May fail if no approved TP — that's expected
        assert r.status_code in (200, 400)
