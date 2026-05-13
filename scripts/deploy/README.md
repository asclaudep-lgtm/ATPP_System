# Папка `scripts/deploy/` — развёртывание ATPP в сети

| Файл                  | Где запускается        | Что делает                                                                                  |
|-----------------------|------------------------|---------------------------------------------------------------------------------------------|
| `server_config.ini`   | конфиг (правят оба)    | IP сервера, имя/пароль БД, путь к бэкапам, время ежедневного бэкапа                         |
| `setup_server.ps1`    | один раз на **сервере** (от Администратора) | Ставит PostgreSQL, создаёт БД и пользователя, настраивает сеть, открывает порт, расшаривает папку бэкапов, регистрирует ежедневную задачу |
| `setup_client.ps1`    | на каждом **клиенте**  | Пишет `data\db.cfg` и `data\backup.cfg`, проверяет связь с сервером                         |
| `backup_server.ps1`   | сервер (Task Scheduler)| `pg_dump` БД ATPP с ротацией                                                                |
| `restore_db.ps1`      | сервер (Администратор) | Восстанавливает БД из любого `*.dump` (со страховочным дампом текущего состояния)            |
| `_lib_config.ps1`     | библиотека             | Общие функции чтения INI и поиска `pg_dump`/`pg_restore`                                    |

Полная пошаговая инструкция: [`docs/network_setup_ru.md`](../../docs/network_setup_ru.md).
Восстановление при потере сервера: [`docs/backup_recovery_ru.md`](../../docs/backup_recovery_ru.md).

## Быстрая шпаргалка

**Сервер (один раз):**

```powershell
# 1) Заполнить server_config.ini под свою сеть
# 2) От Администратора:
cd C:\ATPP_System\scripts\deploy
powershell -ExecutionPolicy Bypass -File .\setup_server.ps1
```

**Клиент (на каждом ПК):**

```powershell
cd C:\ATPP_System\scripts\deploy
powershell -ExecutionPolicy Bypass -File .\setup_client.ps1 `
    -ServerHost 192.168.1.10 -AppPassword 'ПарольПриложения!'
```

**Сделать бэкап вручную (на сервере):**

```powershell
powershell -ExecutionPolicy Bypass -File .\backup_server.ps1
```

**Восстановить БД из бэкапа:**

```powershell
powershell -ExecutionPolicy Bypass -File .\restore_db.ps1 `
    -DumpPath D:\ATPP_Backups\server\atpp_server_20260506_230015.dump
```
