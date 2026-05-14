# ATPP System — V11 Release Report

Дата: 2026-05-14

## Список веток и коммитов

| Фаза | Ветка | Коммит | Описание |
|---|---|---|---|
| 0 | v11/phase-0-docs | d485fdc | docs: FEATURES.md, ROADMAP.md, README.md |
| 1 | v11/phase-1-decompose-main-window | c3c192b | refactor: main_window.py 2537→548 строк |
| 2 | v11/phase-2-visual-editors | 0ce04e7 | feat: редакторы изделий, ТП, справочников |
| 3 | v11/phase-3-gost-docs | b84a156 | feat: ОК, КЭ, ВО, ВМ, комплект документов |
| 4 | v11/phase-4-web-client | 58cc027 | feat: веб-клиент — производство, ОТК, оснастка |
| 5 | v11/phase-5-tech-improvements | 59d26ef | feat: тесты, лог-ротация, health-check |

**Всего:** 6 веток, 6 коммитов, 0 PR (нет git remote / gh CLI).

## Статус тестов

- **179/184 pass** (5 skipped — нет данных в seeded test DB)
- 1 flaky test (`test_create_scrap_creates_entry`) — проблема порядка тестов в общем прогоне, passes alone
- Добавлено: test_editors.py (12), test_gost_docs.py (6), test_v9_uncovered.py (11) = +29 тестов

## Что сделано

### Фаза 0 — Документация
- FEATURES.md: актуализирован (8 пунктов перенесены в «Реализовано», добавлены секции v8/v9/v10)
- ROADMAP.md: создан с v11 (фазы 1–5) и v12 (задел)
- README.md: версия v5→v10, стек, ссылка на ROADMAP

### Фаза 1 — Декомпозиция main_window.py
- Вынесены 5 модулей из 2537-строчного main_window.py:
  - `ui/widgets/main_statusbar.py` (72 строки)
  - `ui/widgets/main_toolbar.py` (102 строки)
  - `ui/widgets/main_menu.py` (241 строка)
  - `ui/widgets/navigation_panel.py` (454 строки)
  - `ui/widgets/dialog_launchers.py` (1202 строки — mixin)
- main_window.py: 548 строк (координатор на Qt signals/slots)

### Фаза 2 — Визуальные редакторы
- `ui/editors/product_editor.py` — редактор изделия (общие, связанные ТП, документы)
- `ui/editors/tp_editor.py` — редактор ТП (шапка, операции, нормы, документы)
- `ui/editors/reference_editor.py` — универсальный CRUD для 4 справочников
- Открываются по двойному клику в дереве навигации

### Фаза 3 — Документы ГОСТ
- `generate_all_operation_cards()` — ОК для всех операций ТП
- `generate_sketch_card()` — КЭ (карта эскизов)
- `generate_tooling_list()` — ВО (ведомость оснастки)
- `generate_material_list()` — ВМ (ведомость материалов, алиас)
- `generate_document_pack()` — улучшен: МК + ОК + КЭ + ВО + ВМ + ZIP

### Фаза 4 — Веб-клиент
- Backend: `web/routers/production.py` + `web/routers/tooling.py`
- Frontend: Vue 3 SPA + ECharts (CDN, вариант A)
  - Производство: barcode-сканер + маршрутный лист
  - ОТК: ожидающие контроля + проблемы
  - Дашборд: график загрузки оборудования
  - Оснастка: список + история выдач/возвратов

### Фаза 5 — Технические улучшения
- 11 тестов для tooling, material_trace, metrology, scrap_journal, ecn
- Ротация логов: RotatingFileHandler (10 MB × 5) + JsonFormatter
- Health endpoint с проверкой БД: `{"status":"ok","db":"ok","version":"11.0.0"}`
- Документация по Alembic-миграциям: `docs/migrations.md`
- Prometheus отложен в v12

## Что не удалось сделать

1. **Создать PR** — отсутствует `gh` CLI и git remote. Все ветки — локальные. Нужно настроить GitHub remote и запушить ветки.
2. **Flaky-тест test_create_scrap_creates_entry** — падает в общем прогоне из-за порядка тестов (другой тест создаёт WorkOrder с некорректным состоянием). Проходит изолированно.
3. **Prometheus-метрики** — отложены в v12 согласно решению пользователя.

## Открытые вопросы

1. **GitHub remote:** настроить `git remote add origin <url>` и запушить все ветки `v11/phase-*`.
2. **Мерж-стратегия:** ветки фаз зависят друг от друга (каждая от предыдущей). Мержить нужно последовательно: phase-0 → phase-1 → ... → phase-5, либо сквошить в один merge-commit на master.
3. **Smoke-тест GUI:** визуальные редакторы не тестировались в реальном GUI (только unit-тесты). Нужен ручной прогон: открыть приложение, дважды кликнуть изделие — должен открыться ProductEditorWidget.

## Рекомендации для v12

1. Prometheus-метрики для веб-сервера
2. Визуализация раскроя заготовок (нестинг)
3. Редактор формул расчёта
4. E2E-тесты (Playwright)
5. Мобильное приложение (PWA)
6. Удаление `_run_lightweight_migrations()` (после полного перехода на Alembic)
7. Рефакторинг `database/models.py` (1400+ строк, 46 моделей — кандидат на splitting)
