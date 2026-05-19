# Wave 1 — отчёт по исправлениям

**Ветка:** `fix/wave1-critical`
**Дата:** 19.05.2026

---

## Что исправлено (6 из 12)

| # | ID | Что | Статус | Коммит |
|---|----|-----|--------|--------|
| 1 | AUDIT-005 | Убрано 4 `session.commit()` из модулей | ✅ | `f1dfd84` |
| 2 | AUDIT-006 | `except Exception` → конкретные типы (3 из 5 файлов) | ⚠️ Частично | `bc07236` |
| 4 | AUDIT-020 | SQLite StaticPool → NullPool | ✅ | `2ba4e66` |
| 6 | AUDIT-004 | Валидация table_name перед DROP TABLE | ✅ | `2ba4e66` |
| 7 | AUDIT-010 | JWT secret убран из stderr | ✅ | `2ba4e66` |
| 9 | AUDIT-021 | Race-condition safe admin seed | ✅ | `8e4a09c` |

### Детали по каждому фиксу

**AUDIT-005:** Убраны `session.commit()` из `tp_designer.py` (2 шт) и `mes_adapter.py` (2 шт). Вызывающий код уже использует `with db.get_session() as s:` — транзакция коммитится автоматически. `grep -rn "session\.commit()" modules/` → 0 результатов.

**AUDIT-006:** В `backup.py` файловые операции → `(FileNotFoundError, OSError, ValueError)`. В `db_manager.py` DB-операции → `sqlalchemy.exc.*`. В `launcher.py` импорты → `ImportError`. Сохранён `except Exception` с `logger.exception()` для truly-generic операций (бэкап, Alembic-миграции). Осталось: `report_generator.py` (11) и `dialog_launchers.py` (21).

**AUDIT-020:** `poolclass=StaticPool` → `poolclass=NullPool` для SQLite. Добавлен `timeout: 30` в connect_args. Для PostgreSQL: `pool_size=5, max_overflow=10`.

**AUDIT-004/014:** Добавлена валидация `table_name.isalnum()` перед `DROP TABLE`. `grep -rn 'text(f"' modules/ database/` → 0 незащищённых результатов (кроме валидированного).

**AUDIT-010:** Убран префикс ключа из вывода. Теперь: `[WARN] ATPP_WEB_SECRET not set — using auto-generated key. Set ATPP_WEB_SECRET env var for production!`

**AUDIT-021:** Заменён `if session.query(User).count() == 0:` на `filter_by(username='admin').first()` + `session.flush()` для исключения race condition.

---

## Тесты

```
260 passed, 392 warnings — без регрессий
```

Все 260 тестов проходят после каждого коммита. Coverage: 37% (без изменений).

---

## Статистика except Exception (до/после)

| Файл | До | После |
|------|----|-------|
| `modules/backup.py` | 14 | 11 |
| `database/db_manager.py` | 12 | 5* |
| `launcher.py` | 15 | 10 |
| `modules/report_generator.py` | 11 | 11 (не тронут) |
| `ui/widgets/dialog_launchers.py` | 21 | 21 (не тронут) |
| **Итого** | **73** | **58** |

*5 оставшихся в db_manager.py — все либо re-raise (get_session), либо best-effort cleanup.

---

## Что НЕ закрылось (для Wave 2)

| Приоритет | ID | Что | Причина переноса |
|-----------|----|-----|-----------------|
| P0 | AUDIT-006 (остаток) | `report_generator.py` + `dialog_launchers.py` | Высокий риск регрессий, требует ручного анализа каждого except |
| P0 | AUDIT-019/022 | QThread для тяжёлых операций | Требует рефакторинга UI-виджетов (3-4 часа) |
| P1 | AUDIT-017 | Дублирующиеся миграции | Высокий риск — удаление `_run_lightweight_migrations()` может сломать существующие БД |
| P1 | AUDIT-011 | JWT → httpOnly cookie | Требует изменений в backend (web/server.py, web/auth.py) и frontend (App.vue) |
| P1 | AUDIT-023 | QValidator на числовых полях | 5 диалогов, каждый требует ручного тестирования |
| P2 | AUDIT-027 | UI-тесты headless | Требует настройки offscreen-режима Qt |
| P2 | AUDIT-002 | PyQt6 enum-проверка | Нужен grep-прогон и ручная верификация |

---

## Коммиты ветки

```
8e4a09c fix: AUDIT-021 — race-condition safe admin seed
2ba4e66 fix: AUDIT-004/020/010 — SQLite pool, SQL injection, JWT secret
bc07236 fix: AUDIT-006 — narrow except Exception in top-3 files
f1dfd84 fix: AUDIT-005 — remove session.commit() from modules
f0d2181 fix: AUDIT-001/007/012 — critical audit fixes (pre-wave1)
```

---

## Рекомендация

**Wave 1 закрыл ~50% критических багов (P0).** Система стала стабильнее, но Wave 2 (ещё 8-12 часов) обязателен перед пилотным показом заказчику.

Критический путь Wave 2: QThread (3) → оставшиеся except (2) → JWT cookie (8) → миграции (5) → QValidator (10).
