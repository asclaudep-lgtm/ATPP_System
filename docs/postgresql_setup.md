# Переключение на PostgreSQL

ATPP_System по умолчанию использует SQLite (`data/atpp.db`) — этого достаточно для одного пользователя на одном ПК. Для **многопользовательской работы по сети** нужен PostgreSQL.

> Полную пошаговую инструкцию для развёртывания на нескольких ПК см. в [`network_setup_ru.md`](./network_setup_ru.md). Здесь — короткая выжимка.

## Шаг 1. Установите PostgreSQL и драйвер

```
.venv\Scripts\pip install psycopg2-binary
```

Сервер PostgreSQL ставится один раз на ПК-сервер (`scripts/deploy/setup_server.ps1` сделает всё автоматически).

## Шаг 2. Создайте БД и пользователя

```sql
CREATE USER atpp WITH PASSWORD 'СЛОЖНЫЙ_ПАРОЛЬ';
CREATE DATABASE atpp OWNER atpp ENCODING 'UTF8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE atpp TO atpp;
```

(`setup_server.ps1` делает это сам по `server_config.ini`.)

## Шаг 3. Укажите URL подключения

Создайте файл `data/db.cfg` с одной строкой:

```
postgresql+psycopg2://atpp:СЛОЖНЫЙ_ПАРОЛЬ@server:5432/atpp
```

Альтернатива: переменная окружения `DATABASE_URL` (имеет приоритет над `db.cfg`).

Скрипт `scripts/deploy/setup_client.ps1 -ServerHost ... -AppPassword ...` сделает это автоматически.

## Шаг 4. Перенос данных из SQLite (опционально)

Если у вас уже есть `data/atpp.db` с накопленными данными — нужно перенести их в PostgreSQL до переключения. Несколько вариантов:

- **`pgloader`** (рекомендуется) — однострочная команда из dockerized или нативного pgloader:

  ```
  pgloader sqlite:///абс_путь_к/atpp.db postgresql://atpp:ПАРОЛЬ@server/atpp
  ```

- **Через Python** — открыть SQLAlchemy `Session` к старой БД, читать строки, писать в новую. Под этот сценарий в репозитории отдельного скрипта не предусмотрено; делается ad-hoc.

## Шаг 5. Бэкап

В этой версии модуль `modules/backup.py` поддерживает оба движка:

- SQLite → `data/backups/atpp_<host>_*.db.gz`
- PostgreSQL → `data/backups/atpp_<host>_*.dump` (через `pg_dump --format=custom`)

После бэкапа файл копируется в зеркальную папку (если задана через `ATPP_BACKUP_MIRROR` или `data/backup.cfg`). Если зеркало недоступно — основной бэкап остаётся валидным, в лог пишется предупреждение.

Серверный ежедневный бэкап настраивается через `scripts/deploy/setup_server.ps1` — задача `ATPP_DailyBackup` в Task Scheduler.
