# ATPP_System — Claude Code Instructions

## Project
Система автоматизации технологической подготовки производства (УЗГА-Инжиниринг).
Python 3.11+ / PyQt6 / SQLAlchemy 2.x / SQLite & PostgreSQL.

## Key paths
- Entry: `main.py` → `launcher.py`
- DB: `database/models.py` (30+ моделей), `database/db_manager.py`
- Modules: `modules/*.py` (25+ модулей бизнес-логики)
- UI: `ui/main_window.py`, `ui/widgets/*.py`, `ui/dialogs/*.py`
- Web: `web/server.py` (FastAPI), `web/static/index.html` (Vue.js 3 SPA)
- Tests: `tests/` (154 теста, pytest)
- Config: `config.py`

## Architecture patterns
- Modules: free functions, `session` as first positional arg, keyword-only after `*`
- Modules NEVER call `session.commit()` — caller manages transactions
- Modules raise `ValueError` for business errors
- UI widgets: `__init__(self, db_manager, ...)`, open via `self._add_or_focus_tab(w, 'Title')`
- DB sessions: `with db_manager.get_session() as s:` (auto commit/rollback/close)
- Migrations: lightweight ALTER TABLE in `db_manager._run_lightweight_migrations()`
- Seed data: `if session.query(Model).count() == 0:` guard

## Running
- Desktop: `python main.py`
- Web server: `python -m web.server` (port 8000)
- Tests: `pytest tests/ -v`
- Default login: `admin / admin`

## Current state (v10, May 2026)
- 152/154 tests pass (2 pre-existing test isolation issues)
- 21 features implemented across v10 strategic + 14 enhancements
- See `RELEASE_v9.md` for previous release notes
