param([string]$Model, [string]$Extra = '')
Stop-ScheduledTask llm-server -ErrorAction SilentlyContinue; Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
$arg = "-NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\serve.ps1 -Model `"$Model`" -Extra `"$Extra`""
$a = New-ScheduledTaskAction -Execute powershell.exe -Argument $arg
$p = New-ScheduledTaskPrincipal -UserId SYSTEM -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 30) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName llm-server -Action $a -Principal $p -Settings $s -Force | Out-Null
Start-ScheduledTask llm-server
for ($i = 0; $i -lt 60; $i++) { Start-Sleep 2; try { $r = Invoke-RestMethod -Uri ("http://{0}:8080/health" -f (& 'C:\Program Files\Tailscale\tailscale.exe' ip -4)); if ($r.status -eq 'ok') { "server healthy after {0}s" -f (2 * ($i + 1)); break } } catch {} }
