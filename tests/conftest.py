"""
Общая фикстура: in-memory SQLite БД с инициализированной схемой.
"""
import os
import sys
from pathlib import Path

import pytest

# AUDIT-027: Qt headless mode — тесты не требуют дисплея
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ATPP_TEST_MODE", "1")

# Гарантируем доступ к корню проекта
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def db_manager(tmp_path, monkeypatch):
    """Свежий DatabaseManager с временной SQLite-базой."""
    db_path = tmp_path / 'atpp_test.db'
    url = f'sqlite:///{db_path}'
    monkeypatch.setenv('DATABASE_URL', url)
    # Импортируем после установки env, чтобы config подхватил новый URL
    from database.db_manager import DatabaseManager
    db = DatabaseManager(database_url=url)
    db.init_database()
    yield db
    db.engine.dispose()
