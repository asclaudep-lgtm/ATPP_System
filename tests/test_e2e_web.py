"""E2E tests — FastAPI TestClient + Playwright browser smoke test."""

import sys
import time
from pathlib import Path

import pytest

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope='module')
def client():
    """FastAPI test client — no need to start a real server."""
    from web.server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get('/api/health')
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'ok'
        assert 'version' in data

    def test_metrics_endpoint(self, client):
        r = client.get('/metrics')
        assert r.status_code == 200
        assert 'atpp_requests_total' in r.text

    def test_login_invalid_credentials(self, client):
        r = client.post('/api/auth/login',
                        json={'username': 'nonexistent',
                              'password': 'wrong'})
        assert r.status_code == 401

    def test_static_served_or_redirect(self, client):
        r = client.get('/', follow_redirects=False)
        assert r.status_code in (200, 307, 302)


class TestDashboardAPI:
    def test_dashboard_stats_requires_auth(self, client):
        r = client.get('/api/dashboard/stats')
        assert r.status_code in (401, 403)

    def test_products_list_requires_auth(self, client):
        r = client.get('/api/products')
        assert r.status_code in (401, 403)

    def test_tech_processes_requires_auth(self, client):
        r = client.get('/api/tech-processes')
        assert r.status_code in (401, 403)

    def test_work_orders_requires_auth(self, client):
        r = client.get('/api/work-orders')
        assert r.status_code in (401, 403)

    def test_tooling_requires_auth(self, client):
        r = client.get('/api/tooling/items')
        assert r.status_code in (401, 403)

    def test_production_qa_requires_auth(self, client):
        r = client.get('/api/production/qa/pending')
        assert r.status_code in (401, 403)

    def test_barcode_lookup_requires_auth(self, client):
        r = client.get('/api/production/barcode/TEST')
        assert r.status_code in (401, 403)

    def test_equipment_load_requires_auth(self, client):
        r = client.get('/api/production/equipment-load')
        assert r.status_code in (401, 403)


class TestPlaywrightSmoke:
    """Playwright browser smoke test — verifies SPA loads and login works."""

    @pytest.fixture(scope='class')
    def playwright_page(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(15000)
            yield page
            page.close()
            browser.close()

    def test_spa_login_flow(self, playwright_page, client):
        """Open SPA in browser, attempt login, verify error message."""
        # We need a running server for Playwright.
        # Use TestClient's WSGI/ASGI bridge or start uvicorn in thread.
        import threading
        import uvicorn
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()

        from web.server import app
        t = threading.Thread(target=uvicorn.run,
                             args=(app,),
                             kwargs={'host': '127.0.0.1', 'port': port,
                                     'log_level': 'error'},
                             daemon=True)
        t.start()
        time.sleep(2)

        url = f'http://127.0.0.1:{port}'
        playwright_page.goto(url)
        assert 'ATPP' in playwright_page.title()

        playwright_page.fill('input[placeholder="Логин"]', 'wrong_user')
        playwright_page.fill('input[placeholder="Пароль"]', 'wrong_pass')
        playwright_page.click('button:has-text("Войти")')
        time.sleep(1)

        error_el = playwright_page.locator('.error')
        assert error_el.is_visible()
        assert 'Неверный' in error_el.text_content()
