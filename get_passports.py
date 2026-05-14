import subprocess, sys, re

sys.stdout.reconfigure(encoding='utf-8')

ps_script = r'''
$target = (New-Object -ComObject WScript.Shell).CreateShortcut('C:\Users\InjTeh\Desktop\инженерный центр.lnk').TargetPath
Get-ChildItem $target -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^53-74\.80\.\d+\.\d+' } | ForEach-Object {
    if ($_.Name -match '^(53-74\.80\.\d+\.\d+)') {
        Write-Output $Matches[1]
    }
}
'''

result = subprocess.run(
    ['powershell', '-NoProfile', '-Command', ps_script],
    capture_output=True, text=True, timeout=120
)

lines = result.stdout.strip().split('\n')
unique = sorted(set(line.strip() for line in lines if line.strip().startswith('53-74.80.')))
print(f'TOTAL_UNIQUE: {len(unique)}')
for n in unique:
    print(n)
