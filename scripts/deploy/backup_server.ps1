# Серверный бэкап БД ATPP. Запускается Task Scheduler-ом ежедневно.
#
# Делает pg_dump в формате custom, кладёт в <BackupDir>\server\,
# ротирует по правилу: оставляем последние KeepDaily дней + по понедельникам за год.
#
# Запуск вручную (для проверки):
#   powershell -ExecutionPolicy Bypass -File .\backup_server.ps1

[CmdletBinding()]
param(
    [string]$ConfigPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib_config.ps1')

if (-not $ConfigPath) { $ConfigPath = Get-DefaultConfigPath }
$cfg = Read-IniFile -Path $ConfigPath

$AppDb     = $cfg['postgresql']['AppDb']
$AppUser   = $cfg['postgresql']['AppUser']
$AppPwd    = $cfg['postgresql']['AppPassword']
$BackupDir = $cfg['backup']['BackupDir']
$KeepDaily = [int]$cfg['backup']['KeepDaily']

$serverDir = Join-Path $BackupDir 'server'
if (-not (Test-Path -LiteralPath $serverDir)) {
    New-Item -ItemType Directory -Path $serverDir -Force | Out-Null
}

$pg_dump = Find-PgTool -Name 'pg_dump'
if (-not $pg_dump) { throw "pg_dump не найден (PostgreSQL не установлен?)" }

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$dst = Join-Path $serverDir "atpp_server_$ts.dump"

$env:PGPASSWORD = $AppPwd
try {
    & $pg_dump -h 127.0.0.1 -p 5432 -U $AppUser -d $AppDb `
        --format=custom --no-owner --no-privileges -f $dst
    if ($LASTEXITCODE -ne 0) { throw "pg_dump RC=$LASTEXITCODE" }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "Backup OK: $dst  ($([math]::Round((Get-Item $dst).Length/1KB)) KB)"

# ── Ротация ──
$today = (Get-Date).Date
$weeklyThreshold = $today.AddDays(-365)
$dailyThreshold = $today.AddDays(-$KeepDaily)

$all = Get-ChildItem -LiteralPath $serverDir -Filter 'atpp_*.dump' | Sort-Object Name
$keep = New-Object System.Collections.Generic.HashSet[string]

# Последние KeepDaily файлов — храним
foreach ($f in ($all | Select-Object -Last $KeepDaily)) { [void]$keep.Add($f.FullName) }

foreach ($f in $all) {
    if ($f.BaseName -match '_(\d{8})_\d{6}$') {
        try {
            $d = [datetime]::ParseExact($matches[1], 'yyyyMMdd', $null).Date
            if ($d -ge $dailyThreshold) { [void]$keep.Add($f.FullName) }
            if ($d -ge $weeklyThreshold -and $d.DayOfWeek -eq [System.DayOfWeek]::Monday) {
                [void]$keep.Add($f.FullName)
            }
        } catch {}
    } else {
        [void]$keep.Add($f.FullName)
    }
}

foreach ($f in $all) {
    if (-not $keep.Contains($f.FullName)) {
        try { Remove-Item -LiteralPath $f.FullName -Force; Write-Host "rotated: $($f.Name)" } catch {}
    }
}
