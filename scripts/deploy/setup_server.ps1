# Развёртывание PostgreSQL-сервера ATPP на Windows-ПК.
#
# Запуск (от Администратора):
#   powershell -ExecutionPolicy Bypass -File .\setup_server.ps1
#
# Что делает:
#   1) Проверяет/устанавливает PostgreSQL (через Chocolatey, если он есть; иначе
#      просит скачать установщик вручную).
#   2) Создаёт БД и пользователя приложения по server_config.ini.
#   3) Настраивает postgresql.conf (listen_addresses) и pg_hba.conf (LAN-доступ).
#   4) Открывает порт 5432 в брандмауэре.
#   5) Создаёт каталог бэкапов и расшаривает его в сеть.
#   6) Регистрирует ежедневное задание ATPP_DailyBackup в Task Scheduler.
#
# При повторном запуске идемпотентен: пропускает уже выполненные шаги.

[CmdletBinding()]
param(
    [string]$ConfigPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib_config.ps1')

if (-not $ConfigPath) { $ConfigPath = Get-DefaultConfigPath }
$cfg = Read-IniFile -Path $ConfigPath

$ServerHost       = $cfg['server']['ServerHost']
$LanCIDR          = $cfg['server']['LanCIDR']
$PgVersion        = $cfg['postgresql']['Version']
$PgSuperPwd       = $cfg['postgresql']['PostgresPassword']
$AppDb            = $cfg['postgresql']['AppDb']
$AppUser          = $cfg['postgresql']['AppUser']
$AppPwd           = $cfg['postgresql']['AppPassword']
$BackupDir        = $cfg['backup']['BackupDir']
$ShareName        = $cfg['backup']['ShareName']
$DailyTime        = $cfg['backup']['DailyTime']

Write-Host "==[ ATPP Server Setup ]=========================================" -ForegroundColor Cyan
Write-Host "Server host : $ServerHost"
Write-Host "LAN CIDR    : $LanCIDR"
Write-Host "PostgreSQL  : $PgVersion"
Write-Host "AppDb/User  : $AppDb / $AppUser"
Write-Host "BackupDir   : $BackupDir  (\\$env:COMPUTERNAME\$ShareName)"
Write-Host "Daily time  : $DailyTime"
Write-Host "================================================================`n"

# Требуем админа
$wid = [Security.Principal.WindowsIdentity]::GetCurrent()
$prp = New-Object Security.Principal.WindowsPrincipal($wid)
if (-not $prp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Запустите PowerShell от имени Администратора."
}

# 1) PostgreSQL ───────────────────────────────────────────────────────────
$psql = Find-PgTool -Name 'psql'
if (-not $psql) {
    Write-Host "[1/6] PostgreSQL не найден, пробую установить..." -ForegroundColor Yellow
    $choco = Get-Command 'choco.exe' -ErrorAction SilentlyContinue
    if ($choco) {
        & $choco.Source install postgresql$PgVersion `
            --params "/Password:$PgSuperPwd" -y --no-progress
        $psql = Find-PgTool -Name 'psql'
    }
    if (-not $psql) {
        Write-Host "Chocolatey не доступен. Установите PostgreSQL $PgVersion вручную:" -ForegroundColor Yellow
        Write-Host "  https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
        Write-Host "  Пароль суперпользователя: значение PostgresPassword из server_config.ini"
        throw "После установки PostgreSQL запустите этот скрипт ещё раз."
    }
} else {
    Write-Host "[1/6] PostgreSQL найден: $psql" -ForegroundColor Green
}

# Подключаемся под суперпользователем postgres через PGPASSWORD
$env:PGPASSWORD = $PgSuperPwd

function Invoke-Psql {
    param([Parameter(Mandatory)][string]$Sql, [string]$Db = 'postgres')
    & $psql -h 127.0.0.1 -U postgres -d $Db -v ON_ERROR_STOP=1 -c $Sql 2>&1
    if ($LASTEXITCODE -ne 0) { throw ("psql вернул {0}: {1}" -f $LASTEXITCODE, $Sql) }
}

# 2) Роль и БД приложения ─────────────────────────────────────────────────
Write-Host "[2/6] Создаю роль и БД (если ещё нет)..." -ForegroundColor Cyan
$exists = & $psql -h 127.0.0.1 -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$AppUser'"
if (-not $exists) {
    Invoke-Psql "CREATE ROLE $AppUser LOGIN PASSWORD '$AppPwd';"
} else {
    Invoke-Psql "ALTER ROLE $AppUser WITH PASSWORD '$AppPwd';"
}
$db_exists = & $psql -h 127.0.0.1 -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$AppDb'"
if (-not $db_exists) {
    Invoke-Psql "CREATE DATABASE $AppDb OWNER $AppUser ENCODING 'UTF8' TEMPLATE template0;"
}
Invoke-Psql "GRANT ALL PRIVILEGES ON DATABASE $AppDb TO $AppUser;"

# 3) postgresql.conf + pg_hba.conf ────────────────────────────────────────
Write-Host "[3/6] Настраиваю listen_addresses и pg_hba.conf..." -ForegroundColor Cyan
$pgDataLine = & $psql -h 127.0.0.1 -U postgres -d postgres -tAc "SHOW data_directory"
$pgData = $pgDataLine.Trim()
if (-not (Test-Path -LiteralPath $pgData)) { throw "Не найден data_directory: $pgData" }

$conf = Join-Path $pgData 'postgresql.conf'
$hba  = Join-Path $pgData 'pg_hba.conf'

# postgresql.conf: слушаем все интерфейсы LAN
$confText = Get-Content -LiteralPath $conf -Raw
if ($confText -match "(?m)^\s*#?\s*listen_addresses\s*=") {
    $confText = [regex]::Replace($confText, "(?m)^\s*#?\s*listen_addresses\s*=.*$", "listen_addresses = '*'")
} else {
    $confText += "`r`nlisten_addresses = '*'`r`n"
}
Set-Content -LiteralPath $conf -Value $confText -Encoding UTF8

# pg_hba.conf: добавляем разрешение для LAN-подсети, если ещё нет
$hbaText = Get-Content -LiteralPath $hba -Raw
$rule = "host    $AppDb    $AppUser    $LanCIDR    scram-sha-256"
if ($hbaText -notmatch [regex]::Escape($rule)) {
    Add-Content -LiteralPath $hba -Value "`r`n# ATPP LAN access`r`n$rule" -Encoding UTF8
}

# Перезапуск службы PostgreSQL
$svc = Get-Service -Name 'postgresql*' | Select-Object -First 1
if ($svc) {
    Write-Host "  Перезапуск службы $($svc.Name)..."
    Restart-Service -Name $svc.Name -Force
}

# 4) Брандмауэр ───────────────────────────────────────────────────────────
Write-Host "[4/6] Открываю порт 5432 в брандмауэре..." -ForegroundColor Cyan
if (-not (Get-NetFirewallRule -DisplayName 'ATPP PostgreSQL 5432' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'ATPP PostgreSQL 5432' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5432 `
        -Profile Domain,Private | Out-Null
}

# 5) Папка и SMB-шара бэкапов ─────────────────────────────────────────────
Write-Host "[5/6] Создаю папку и SMB-шару для бэкапов..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}
if (-not (Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name $ShareName -Path $BackupDir -FullAccess 'Authenticated Users' | Out-Null
}
# NTFS-права: модификация для аутентифицированных пользователей
$acl = Get-Acl -LiteralPath $BackupDir
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    'NT AUTHORITY\Authenticated Users','Modify','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $BackupDir -AclObject $acl

# 6) Задача ежедневного бэкапа ────────────────────────────────────────────
Write-Host "[6/6] Регистрирую задачу Task Scheduler ATPP_DailyBackup..." -ForegroundColor Cyan
$repoRoot = Get-AtppRoot
$backupScript = Join-Path $PSScriptRoot 'backup_server.ps1'
if (-not (Test-Path -LiteralPath $backupScript)) {
    throw "Не найден backup_server.ps1: $backupScript"
}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$backupScript`" -ConfigPath `"$ConfigPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

if (Get-ScheduledTask -TaskName 'ATPP_DailyBackup' -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName 'ATPP_DailyBackup' -Confirm:$false
}
Register-ScheduledTask -TaskName 'ATPP_DailyBackup' `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description 'ATPP: ежедневный pg_dump в \\SERVER\ATPP_Backups\server' | Out-Null

# Делаем сразу первый бэкап (чтобы убедиться, что всё работает)
Write-Host "`nПервый бэкап для проверки..." -ForegroundColor Cyan
& powershell.exe -NonInteractive -ExecutionPolicy Bypass -File $backupScript -ConfigPath $ConfigPath
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Первый бэкап завершился с кодом $LASTEXITCODE — проверьте логи."
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

Write-Host "`n✓ Сервер настроен." -ForegroundColor Green
Write-Host "Строка подключения для клиентов (data/db.cfg):" -ForegroundColor Yellow
Write-Host "  postgresql+psycopg2://${AppUser}:${AppPwd}@${ServerHost}:5432/${AppDb}"
Write-Host "Сетевая папка для бэкапов:" -ForegroundColor Yellow
Write-Host "  \\$env:COMPUTERNAME\$ShareName"
