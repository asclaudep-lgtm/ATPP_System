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
- Tests: `tests/` (156 тестов, pytest)
- Config: `config.py`

## Architecture patterns
- Modules: free functions, `session` as first positional arg, keyword-only after `*`
- Modules NEVER call `session.commit()` — caller manages transactions
- Modules raise `ValueError` for business errors
- UI widgets: `__init__(self, db_manager, ...)`, open via `self._add_or_focus_tab(w, 'Title')`
- DB sessions: `with db_manager.get_session() as s:` (auto commit/rollback/close)
- Migrations: lightweight ALTER TABLE in `db_manager._run_lightweight_migrations()`
- Seed data: `if session.query(Model).count() == 0:` guard

## UI: Fluent Design (v11, May 2026)
- **Style library**: PyQt-Fluent-Widgets + centralized QSS in `ui/theme.py`
- **Accent**: orange `#f97316` (hover `#ea580c`, disabled `#fdba74`)
- **Background**: light `#F3F3F3` / dark `#1F1F1F`; surface `#FFFFFF` / `#2B2B2B`
- **Sidebar**: always dark `#0F172A` (web-style)
- **Font**: Segoe UI Variable (system fallback), base 9pt
- **Spacing grid**: 4px base → 4, 8, 12, 16, 20, 24, 32
- **Border radius**: 4px (small), 6px (default), 8px (card)
- **Widget compatibility**: `ui/fluent_compat.py` — drop-in Fluent imports with PyQt6 fallback

**Critical rule — NO inline setStyleSheet**:
All styling lives in `ui/theme.py`. If a widget needs custom styling, use `setProperty("key", True)` and add a QSS selector `QClass[key="true"]` to the theme. Never write `widget.setStyleSheet("color: #xxx")` — it overrides the global theme and breaks dark/light switching.

**Widget mapping** (standard → Fluent):
- `QPushButton` (primary action) → `PrimaryPushButton` from `ui.fluent_compat`
- `QPushButton` (secondary) → `PushButton` from `ui.fluent_compat`
- `QLineEdit` → `LineEdit` from `ui.fluent_compat`
- `QLabel` (title) → `TitleLabel`, `SubtitleLabel` from `ui.fluent_compat`
- `QLabel` (body) → `BodyLabel` from `ui.fluent_compat`
- Password fields → `PasswordLineEdit` from `ui.fluent_compat` (has built-in eye toggle)
- Tables → standard `QTableWidget` / `QTreeWidget` (styled by global QSS)

**What NOT to touch without explicit request**:
- `database/`, `modules/` — business logic
- `ui/theme.py` — already rewritten, single source of truth
- `tests/` — test suite
- Public method signatures of any widget/dialog

## Running
- Desktop: `python main.py`
- Web server: `python -m web.server` (port 8000)
- Tests: `pytest tests/ -v`
- Default login: `admin / admin`

## Current state (v11, May 2026)
- Fluent Design migration in progress
- Branch: `devin/wip-fluent-base`
- 182/210 tests pass (28 pre-existing web/e2e failures, not UI-related)
- See `docs/ui_migration_ru.md` for migration checklist
