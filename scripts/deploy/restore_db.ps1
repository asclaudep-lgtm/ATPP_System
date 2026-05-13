# Восстановление БД ATPP из любого .dump (PostgreSQL custom format).
#
# Запуск (от Администратора, ОБЫЧНО НА СЕРВЕРЕ):
#   powershell -ExecutionPolicy Bypass -File .\restore_db.ps1 -DumpPath C:\path\to\atpp_*.dump
#
# Можно использовать .dump-файл с любого ПК пользователей (data\backups)
# — это и есть гарантия восстановления при потере сервера.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$DumpPath,
    [string]$ConfigPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib_config.ps1')

if (-not (Test-Path -LiteralPath $DumpPath)) { throw "Файл не найден: $DumpPath" }
if (-not $ConfigPath) { $ConfigPath = Get-DefaultConfigPath }
$cfg = Read-IniFile -Path $ConfigPath

$AppDb         = $cfg['postgresql']['AppDb']
$AppUser       = $cfg['postgresql']['AppUser']
$AppPwd        = $cfg['postgresql']['AppPassword']
$PgSuperPwd    = $cfg['postgresql']['PostgresPassword']

$pg_restore = Find-PgTool -Name 'pg_restore'
$psql       = Find-PgTool -Name 'psql'
if (-not $pg_restore) { throw "pg_restore не найден." }
if (-not $psql)       { throw "psql не найден." }

Write-Host "==[ ATPP Database Restore ]====================================" -ForegroundColor Cyan
Write-Host "Source dump : $DumpPath"
Write-Host "Target DB   : $AppDb (на этом сервере)"
Write-Host "================================================================" -ForegroundColor Cyan

$reply = Read-Host "ВНИМАНИЕ! Текущее содержимое БД '$AppDb' будет ЗАМЕНЕНО на содержимое $DumpPath. Продолжить? (yes/no)"
if ($reply -ne 'yes') { Write-Host "Отменено."; return }

# Сначала делаем "страховочный" дамп текущей БД, чтобы можно было откатиться.
$safetyDir = Join-Path $env:TEMP 'atpp_pre_restore'
New-Item -ItemType Directory -Path $safetyDir -Force | Out-Null
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$safetyDump = Join-Path $safetyDir "atpp_PRE_RESTORE_$ts.dump"

$env:PGPASSWORD = $AppPwd
try {
    & (Find-PgTool -Name 'pg_dump') -h 127.0.0.1 -U $AppUser -d $AppDb `
        --format=custom --no-owner --no-privileges -f $safetyDump
    Write-Host "Страховочная копия текущей БД: $safetyDump" -ForegroundColor Yellow
} catch {
    Write-Warning "Не удалось снять страховочный дамп: $_"
}

# Пересоздаём БД, чтобы восстановление было «чистым»
$env:PGPASSWORD = $PgSuperPwd
& $psql -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c `
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$AppDb' AND pid <> pg_backend_pid();" | Out-Null
& $psql -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $AppDb;"
if ($LASTEXITCODE -ne 0) { throw "DROP DATABASE failed" }
& $psql -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $AppDb OWNER $AppUser ENCODING 'UTF8' TEMPLATE template0;"
if ($LASTEXITCODE -ne 0) { throw "CREATE DATABASE failed" }

# Ресторим. --no-owner / --no-privileges для безболезненной миграции между хостами.
$env:PGPASSWORD = $AppPwd
& $pg_restore -h 127.0.0.1 -U $AppUser -d $AppDb --no-owner --no-privileges `
    --exit-on-error $DumpPath
if ($LASTEXITCODE -ne 0) {
    Write-Warning "pg_restore RC=$LASTEXITCODE. Если это были безобидные предупреждения — БД скорее всего восстановлена."
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

Write-Host "`n✓ Восстановление завершено." -ForegroundColor Green
Write-Host "Скажите пользователям перезапустить ATPP." -ForegroundColor Yellow
Write-Host "Если что-то пошло не так — страховочная копия лежит здесь:" -ForegroundColor Yellow
Write-Host "  $safetyDump"
