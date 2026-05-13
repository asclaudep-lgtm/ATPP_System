# Общие функции: чтение server_config.ini и поиск pg_dump/pg_restore.
# Подключается остальными скриптами через  . .\_lib_config.ps1

function Read-IniFile {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Файл конфигурации не найден: $Path"
    }
    $ini = @{}
    $section = ''
    foreach ($raw in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line)              { continue }
        if ($line.StartsWith(';'))   { continue }
        if ($line.StartsWith('#'))   { continue }
        if ($line -match '^\[(.+)\]$') {
            $section = $matches[1].Trim()
            if (-not $ini.ContainsKey($section)) { $ini[$section] = @{} }
            continue
        }
        if ($line -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($section) { $ini[$section][$key] = $val } else { $ini[$key] = $val }
        }
    }
    return $ini
}

function Find-PgTool {
    param([Parameter(Mandatory)][string]$Name)
    $cmd = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($base in @('C:\Program Files\PostgreSQL', 'C:\Program Files (x86)\PostgreSQL')) {
        if (Test-Path -LiteralPath $base) {
            $vers = Get-ChildItem -LiteralPath $base -Directory | Sort-Object Name -Descending
            foreach ($v in $vers) {
                $cand = Join-Path $v.FullName "bin\$Name.exe"
                if (Test-Path -LiteralPath $cand) { return $cand }
            }
        }
    }
    return $null
}

function Get-AtppRoot {
    # scripts/deploy/_lib_config.ps1 → корень проекта
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Get-DefaultConfigPath {
    return (Join-Path $PSScriptRoot 'server_config.ini')
}
