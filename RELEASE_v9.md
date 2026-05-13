# ATPP_System v9 — «Средний горизонт»

Релиз закрывает все 10 пунктов из раздела «🟡 Средний горизонт» roadmap'а
(см. `ATPP_System_v8_roadmap.pdf`, стр. 2). Это не «маленькие фичи поверх
существующего» — добавлены 12 новых сущностей в БД, 9 новых модулей бизнес-логики,
10 новых виджетов UI и 12 новых тестов поверх 102 ранее.

## Итоги тестов

```
$ pytest tests/ -v
============== 114 passed, 184 warnings in 49.24s ==============
```

102 «зелёных» теста из v8 и более ранних релизов + 12 новых для v9.
Полный список новых тестов — `tests/test_v9_features.py`.

## Что появилось (по пунктам пользовательского запроса)

| № | Фича | Где смотреть | Скриншот |
|---|------|--------------|----------|
| 1 | **Gantt-доска планировщик** — APS-lite, FIFO по due_date, рисует операции на оси времени с группировкой по оборудованию, выделяет конфликты, экспорт PNG | `modules/scheduler.py`, `ui/widgets/gantt_widget.py` | `screenshots/v9/v9_09_gantt.png` |
| 2 | **Загрузка оборудования %** — два режима (Факт по RouteStep / План по открытым нарядам), цветовая шкала, средняя загрузка и счётчики «перегружено / простаивает» | `modules/equipment_load.py`, `ui/widgets/equipment_load_widget.py` | `screenshots/v9/v9_02_equipment_load.png` |
| 3 | **Терминал ОТК** — отдельный фокус-режим: список ожидающих нарядов слева, крупные цветные кнопки решений справа («Принять» / «На доработку» / «В брак») с диалогом фотофиксации | `ui/widgets/qa_terminal_widget.py` | `screenshots/v9/v9_03_qa_terminal.png` |
| 4 | **Учёт оснастки** — CRUD, статусы (Доступна/Выдана/В ремонте/Списана/Утеряна), выдача оператору с фиксацией возвратного износа, история выдач | `modules/tooling.py`, `ui/widgets/tooling_widget.py` | `screenshots/v9/v9_04_tooling.png` |
| 5 | **Учёт материала и трассируемость** — поступление партии (lot_no + сертификат PDF), резервирование под наряд, списание; контроль остатка | `modules/material_trace.py`, `ui/widgets/materials_widget.py` | `screenshots/v9/v9_05_materials.png` |
| 6 | **Дашборд руководителя** — KPI-карточки (% плана, нарядов в работе, просрочено, % брака), топ-5 узких мест по операциям и оборудованию, PDF-отчёт за период одной кнопкой (DejaVuSans) | `modules/manager_dashboard.py`, `ui/widgets/manager_dashboard_widget.py` | `screenshots/v9/v9_01_manager_dashboard.png` |
| 7 | **Версионирование ТП** — снимки в `TPVersion`, утилиты `list_versions/load_snapshot/diff_snapshots`, side-by-side diff с подсветкой (зелёный — добавлено, красный — удалено, жёлтый — изменено) | `modules/tp_versioning.py`, `ui/widgets/tp_history_widget.py` | (вызывается из контекстного меню ТП) |
| 8 | **ECN (извещения об изменениях)** — workflow «изменить ТП по причине Y» с маршрутом согласования (Гл. технолог → ОТК → Утверждающий), статусы DRAFT → UNDER_REVIEW → APPROVED/REJECTED → APPLIED, журнал подписей | `modules/ecn.py`, `ui/widgets/ecn_widget.py` | `screenshots/v9/v9_08_ecn.png` |
| 9 | **Брак-журнал с фотофиксацией** — отдельная сущность ScrapRecord, привязка к WO/операции, фото в `data/scrap/<id>/`, аналитика по причинам и операциям за период | `modules/scrap_journal.py`, `ui/widgets/scrap_journal_widget.py` | `screenshots/v9/v9_07_scrap_journal.png` |
| 10 | **Метрологическая поверка** — учёт СИ (инв.№, тип, диапазон, точность), регистрация поверки (организация + сертификат), автоматическое продление `next_cal_date`, алерты «истекает 30 дней» (жёлтым) и «просрочено» (красным), сводка внизу панели | `modules/metrology.py`, `ui/widgets/metrology_widget.py` | `screenshots/v9/v9_06_metrology.png` |

## Структура изменений

### Новые модели БД (`database/models.py`)

12 новых таблиц + 6 enum-ов:

- `scrap_records` (+ enum `ScrapReason`, `ScrapDecision`)
- `scrap_photos`
- `tooling_items` (+ enum `ToolingStatus`)
- `operation_tooling` — связь оснастка ↔ операция
- `tooling_issues` — журнал выдач/возвратов
- `material_batches` — партии материала с сертификатом
- `material_reservations` — резерв под наряд
- `material_issues` — списания
- `ecns` (+ enum `ECNStatus`, `SignerRole`)
- `ecn_approvals` — журнал подписей
- `instruments` (+ enum `InstrumentStatus`)
- `calibrations` — журнал поверок

Все таблицы создаются автоматически на старте через `Base.metadata.create_all()`.
Существующие данные v7/v8 (211 деталей, ТП, наряды, фото, аудит) не трогаются.

### Новые модули (`modules/*.py`)

- `scrap_journal.py` (180 строк) — create/photo/decide + аналитика
- `equipment_load.py` (150 строк) — расчёт факт/план занятости
- `metrology.py` (110 строк) — add_calibration / instruments_due_soon / refresh_statuses
- `tooling.py` (100 строк) — issue_to_user / return_from_user / attach_to_operation
- `material_trace.py` (130 строк) — add_batch / reserve / issue / trace_work_order
- `ecn.py` (140 строк) — create / submit / approve / reject / mark_applied
- `tp_versioning.py` (100 строк) — list_versions / load_snapshot / diff_snapshots / diff_human
- `scheduler.py` (170 строк) — schedule_open_orders / detect_conflicts (APS-lite)
- `manager_dashboard.py` (220 строк) — kpi_snapshot / export_pdf

### Новые UI-виджеты (`ui/widgets/*.py`)

- `gantt_widget.py` (~240 строк) — QGraphicsScene с операциями на тайм-линии
- `equipment_load_widget.py` (~120) — таблица с цветными прогресс-барами
- `qa_terminal_widget.py` (~260) — большие кнопки решений, фотофиксация
- `tooling_widget.py` (~330) — каталог + журнал выдач
- `materials_widget.py` (~240) — партии материала, резерв/списание
- `manager_dashboard_widget.py` (~140) — KPI-карточки + топы + PDF-кнопка
- `tp_history_widget.py` (~130) — список версий + diff-таблица
- `ecn_widget.py` (~200) — таблица ECN + действия (подача / подпись / отклонение)
- `scrap_journal_widget.py` (~280) — таблица записей + аналитика-сводка
- `metrology_widget.py` (~280) — каталог СИ с цветовыми алертами

### Меню

Все 9 новых разделов добавлены в меню «Производство»
(см. `ui/main_window.py:1100+`). Иконки в Unicode, никаких внешних
картинок не требуется.

## Совместимость с предыдущими версиями

- БД v7/v8 → v9 мигрируется автоматически на первом запуске
  (`DatabaseManager.init_database()` создаёт недостающие таблицы).
- Все ранее работавшие сценарии не затронуты: меню «Файл/Справочники/
  Документы», вкладка «Производство», корзина v8, шаблоны переходов
  v8, тёмная тема v8 — всё на месте.
- 102 теста из v8 проходят без изменений.

## Известные ограничения

- **Gantt drag-drop пока не интерактивен**: операции рисуются жадным
  алгоритмом и пересчитываются по кнопке «Перепланировать». Drag-drop
  редактирование — следующий шаг.
- **APS-lite scheduler** учитывает: рабочую смену 08:00–17:00, обед
  12:00–13:00, выходные. Не учитывает: переналадки между нарядами,
  параллельные станки одного типа, ручные приоритеты.
- **ECN-маршрут** жёстко зашит (Гл. технолог → ОТК → Утверждающий).
  Гибкий маршрут — отдельная фича.
- **TP versioning UI** вызывается из контекстного меню ТП («История версий…»)
  — отдельная вкладка, скриншота нет (UI ровно как у diff'а версий ТП v7,
  только с новой логикой `diff_snapshots`).

## Архивы

- `ATPP_System_v9_src.zip` — только исходники + БД (~10 MB).
- `ATPP_System_v9_linux.zip` — с готовым `.venv` под Ubuntu 24.04 / Python 3.12 (~360 MB).
- `ATPP_System_v9_windows.zip` — со всеми wheel-ами под Windows x64 / Python 3.12 (~125 MB) и `install_windows.bat`.

## Краткий roadmap дальше

После v9 остался раздел «🟠 Стратегические» (1–2 месяца на пункт):
веб-клиент, интеграция с 1С, AI-помощник технолога, IoT-сбор,
многоуровневые БОМ, CAD-интеграция. Сообщите, что важно — соберу v10.
