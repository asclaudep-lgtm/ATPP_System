# Миграции БД (Alembic)

ATPP использует Alembic для управления схемой БД начиная с v10.

## Как создать миграцию

```bash
# Создать автогенерированную миграцию (сравнивает модели с текущей БД):
cd ATPP_System
alembic revision --autogenerate -m "описание изменений"

# Создать пустую миграцию (для ручного написания DDL):
alembic revision -m "описание изменений"
```

## Как применить миграции

```bash
# Применить все неприменённые миграции:
alembic upgrade head

# Применить до конкретной версии:
alembic upgrade <revision_id>

# Применить одну миграцию вперёд:
alembic upgrade +1
```

## Как откатить миграцию

```bash
# Откатить последнюю миграцию:
alembic downgrade -1

# Откатить до конкретной версии:
alembic downgrade <revision_id>

# Откатить все миграции (вернуться к пустой БД):
alembic downgrade base
```

## Текущее состояние

- **Базовая миграция:** `c974f71b6305_baseline.py` — начальная схема v10.
- **target_metadata:** `Base.metadata` (все 46 моделей из `database/models.py`).
- **Автогенерация:** включена (`alembic/env.py` использует `target_metadata`).

## Легковесные миграции (legacy)

Метод `DatabaseManager._run_lightweight_migrations()` в `database/db_manager.py`
выполняет ALTER TABLE для баз, созданных до внедрения Alembic (v5–v9).
Для новых установок (v10+) используйте Alembic. Легковесный механизм
сохранён для обратной совместимости и может быть удалён в v12.

## Проверка

```bash
# Применить все миграции на тестовой БД и сравнить с моделями:
python -m pytest tests/test_migrations.py -v
```
