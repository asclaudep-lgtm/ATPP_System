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

## Running
- Desktop: `python main.py`
- Web server: `python -m web.server` (port 8000)
- Tests: `pytest tests/ -v`
- Default login: `admin / admin`

## Current state (v10, May 2026)
- 156/156 tests pass
- 21 features implemented across v10 strategic + 14 enhancements
- See `RELEASE_v9.md` for previous release notes

## UI / Design system (orange Fluent)
Дизайн — оранжевый web-style как в SPA (Vue+Tailwind), сверху — Fluent-виджеты
из `qfluentwidgets`. Один источник правды: `ui/theme.py`.

### Палитра и токены
- Акцент: **`#f97316`** (orange-500), hover `#ea580c`, текст на акценте `#ffffff`.
  В `ui/theme.py` это `ACCENT_DEFAULT`, `ACCENT_HOVER`, `ACCENT_FG`.
- Светлая тема: фон workspace `#f1f5f9`, диалогов `#ffffff`, граница `#e5e7eb`,
  текст `#334155`, mute-текст `#64748b`.
- Тёмная тема: фон workspace `#0f172a`, sidebar/диалоги `#1e293b`, граница `#334155`,
  текст `#e2e8f0`.
- Радиусы: 6 px (кнопки/инпуты), 8 px (карточки/таблицы).
- Сетка отступов: кратная 4 px (4/6/8/12/16/24).
- Шрифт: системный по умолчанию (`app.setFont(QFont(...).setPointSize(font_size))`).

### Правила
- **Стили централизованы в `ui/theme.py`**. Не добавляй `setStyleSheet(...)` в виджетах,
  кроме случаев одноразовой раскраски (например, бейджи статуса).
- **Primary-кнопка ставится через property**:
  `btn.setProperty("primary", "true")` — QSS подхватит `QPushButton[primary="true"]`.
  Не пиши инлайн `background: #f97316` в код виджета.
- **Fluent-импорты идут через `ui/fluent_compat.py`**. Это drop-in, с graceful
  fallback на стандартные PyQt6, если `qfluentwidgets` недоступен:
  ```python
  from ui.fluent_compat import (
      BodyLabel, FluentIcon, LineEdit, PasswordLineEdit,
      PrimaryPushButton, PushButton, SubtitleLabel, TitleLabel,
  )
  ```
- При миграции виджетов следуй маппингу из `docs/ui_migration_ru.md`:
  - `QPushButton` (главное действие) → `PrimaryPushButton`
  - `QPushButton` (вторичное) → `PushButton`
  - `QLineEdit` → `LineEdit`
  - `QLineEdit` (пароль) → `PasswordLineEdit`
  - `QLabel` (заголовок) → `TitleLabel` / `SubtitleLabel` / `BodyLabel`
  - `QMessageBox.warning(...)` → `InfoBar.warning(...)`
  - иконки → `FluentIcon.*`
- **Не меняй сигнатуры публичных методов и сигналы** при миграции виджета —
  только внутреннюю реализацию (импорты, типы, layout-токены).
- **Не правь автогенерированные файлы.**
- При смене темы в рантайме вызывай `apply_theme(app, theme=...,  accent_color=...)`
  и затем `unpolish/polish` на всех виджетах (паттерн уже реализован в `launcher.py`).

### Примеры
- Эталонный мигрированный диалог: `ui/auth_dialog.py`.
- Чек-лист для следующих виджетов: `docs/ui_migration_ru.md`.
