# Настройка клиентского ПК для подключения к серверу ATPP.
#
# Запуск (от обычного пользователя или Администратора):
#   powershell -ExecutionPolicy Bypass -File .\setup_client.ps1 `
#       -ServerHost 192.168.1.10 -AppUser atpp -AppPassword '...' [-AppDb atpp] `
#       [-ShareName ATPP_Backups]
#
# Что делает:
#   1) Пишет data/db.cfg со строкой подключения к PostgreSQL.
#   2) Пишет data/backup.cfg с UNC-путём \\SERVER\ATPP_Backups (для зеркала).
#   3) Проверяет, что pg_dump доступен (для локальных бэкапов клиента).
#      Если не доступен — даёт ссылку на установку PostgreSQL Client Tools.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ServerHost,
    [Parameter(Mandatory)][string]$AppPassword,
    [string]$AppUser   = 'atpp',
    [string]$AppDb     = 'atpp',
    [string]$ShareName = 'ATPP_Backups'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib_config.ps1')

$root = Get-AtppRoot
$dataDir = Join-Path $root 'data'
if (-not (Test-Path -LiteralPath $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}

$dbCfg = Join-Path $dataDir 'db.cfg'
$bkCfg = Join-Path $dataDir 'backup.cfg'

$dbUrl = "postgresql+psycopg2://${AppUser}:${AppPassword}@${ServerHost}:5432/${AppDb}"
Set-Content -LiteralPath $dbCfg -Value $dbUrl -Encoding UTF8 -NoNewline
Write-Host "✓ Записан $dbCfg" -ForegroundColor Green

$mirror = "\\$ServerHost\$ShareName"
Set-Content -LiteralPath $bkCfg -Value $mirror -Encoding UTF8 -NoNewline
Write-Host "✓ Записан $bkCfg  ($mirror)" -ForegroundColor Green

# Проверка pg_dump (нужен для клиентских локальных бэкапов)
$pg_dump = Find-PgTool -Name 'pg_dump'
if ($pg_dump) {
    Write-Host "✓ pg_dump найден: $pg_dump" -ForegroundColor Green
} else {
    Write-Warning "pg_dump НЕ найден на этом ПК."
    Write-Host "   Чтобы клиент мог делать локальные бэкапы, поставьте PostgreSQL Client Tools:"
    Write-Host "   https://www.postgresql.org/download/windows/  (можно установить только клиент-часть)"
    Write-Host "   После установки убедитесь, что C:\Program Files\PostgreSQL\<ver>\bin есть в PATH."
}

# Проверка доступности сервера
Write-Host "`nПроверяю доступ к ${ServerHost}:5432 ..." -ForegroundColor Cyan
$ok = Test-NetConnection -ComputerName $ServerHost -Port 5432 -InformationLevel Quiet
if ($ok) {
    Write-Host "✓ TCP 5432 доступен — сервер ATPP виден из этой машины." -ForegroundColor Green
} else {
    Write-Warning "TCP 5432 НЕ отвечает. Проверьте: сервер запущен, брандмауэр разрешает LAN, IP правильный."
}

Write-Host "`nГотово. Запускайте приложение:  python main.py" -ForegroundColor Yellow
