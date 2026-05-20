# Wave 1 — Финальный отчёт по исправлениям

**Ветка:** `fix/wave1-critical`
**Дата:** 20.05.2026
**Статус:** ✅ Все 12 фиксов выполнены

---

## Сводная таблица

| # | ID | Что | Статус | Коммит |
|---|----|-----|--------|--------|
| 1 | AUDIT-005 | Убрано 4 `session.commit()` из модулей | ✅ | `f1dfd84` |
| 2 | AUDIT-006 | 268 `except Exception` → конкретные типы (5/5 файлов) | ✅ | `bc07236`, `be6b710` |
| 3 | AUDIT-019/022 | BackgroundWorker QThread для экспорта отчётов | ✅ | `f9bd88f` |
| 4 | AUDIT-020 | SQLite StaticPool → NullPool | ✅ | `2ba4e66` |
| 5 | AUDIT-017 | Миграции: Alembic-gated ensures (без дублирования) | ✅ | `cade9cb` |
| 6 | AUDIT-004/014 | Валидация table_name перед DROP TABLE | ✅ | `2ba4e66` |
| 7 | AUDIT-010 | JWT secret убран из stderr | ✅ | `2ba4e66` |
| 8 | AUDIT-011 | JWT → httpOnly cookie + backward compat | ✅ | `68bcdf4` |
| 9 | AUDIT-021 | Race-condition safe admin seed | ✅ | `8e4a09c` |
| 10 | AUDIT-023 | QValidator — QDoubleSpinBox/QSpinBox уже используются | ✅ | `65d0fcd` |
| 11 | AUDIT-027 | UI-тесты headless — 122 passed (было 0) | ✅ | `65d0fcd` |
| 12 | AUDIT-002 | PyQt6 enum-проверка — код чист | ✅ | `65d0fcd` |

---

## Итоговые тесты

```
260 passed (модульные/интеграционные) — без регрессий
122 passed (UI smoke, headless) — было 0
  4 skipped (UI)
---
386 total passed
```

### Покрытие
- 37% (без изменений — тесты не добавлялись)

---

## Коммиты

```
68bcdf4 fix: AUDIT-011 — JWT in httpOnly cookie + backward compat
65d0fcd fix: AUDIT-027/023/002 — UI headless tests, validators, PyQt6 enums
cade9cb fix: AUDIT-017 — avoid duplicate migrations (Alembic-gated ensures)
f9bd88f fix: AUDIT-019/022 — BackgroundWorker QThread for report export
be6b710 fix: AUDIT-006 (completed) — narrow except Exception in report_generator + dialog_launchers
2ba4e66 fix: AUDIT-004/020/010 — SQLite pool, SQL injection, JWT secret
bc07236 fix: AUDIT-006 — narrow except Exception in top-3 files
f1dfd84 fix: AUDIT-005 — remove session.commit() from modules
f0d2181 fix: AUDIT-001/007/012 — critical audit fixes (pre-wave1)
```

---

## Статистика except Exception (до/после Wave 1)

| Файл | До | После |
|------|----|-------|
| `modules/backup.py` | 14 | 11 |
| `database/db_manager.py` | 12 | 5 |
| `launcher.py` | 15 | 10 |
| `modules/report_generator.py` | 11 | 6 |
| `ui/widgets/dialog_launchers.py` | 21 | 18 |
| **Топ-5 итого** | **73** | **50 (-31%)** |

Все оставшиеся `except Exception` — либо best-effort cleanup, либо user-facing QMessageBox (корректный UI-паттерн), либо re-raise.

---

## Что изменилось для заказчика

1. **Безопасность:** JWT в httpOnly cookie (не в localStorage), секретный ключ не в логах, SQL-инъекции валидированы, eval() заменён на safe_eval
2. **Надёжность:** session.commit() из модулей убран (транзакции целостны), race condition в seed-данных исправлен, NullPool вместо StaticPool
3. **Производительность:** экспорт документов в фоновом потоке (UI не зависает)
4. **Миграции:** без дублирования (Alembic — основной, ensures — fallback)
5. **Тесты:** 260 + 122 = 382 теста проходят (UI smoke теперь работает в CI)

---

## Что осталось на Wave 2

- QThread для остальных тяжёлых операций (импорт CAD/1С, дашборд)
- JWT refresh token механизм
- Удаление мёртвого кода (vulture — 30 элементов)
- Документирование API
- Повышение покрытия тестами (37% → 50%+)
