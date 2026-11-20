# serve.ps1 - run llama-server bound to the tailnet IP; invoked by the llm-server SYSTEM task.
param([string]$Model, [int]$Port = 8080, [string]$Extra = '', [string]$Build = 'b12318-cuda124')
$ts = & 'C:\Program Files\Tailscale\tailscale.exe' ip -4
$log = "C:\llm\logs\llama-server-$Port.log"
$exe = "C:\llm\llama\$Build\llama-server.exe"
$argList = "-m `"$Model`" --host $ts --port $Port --jinja -ngl 99 -fa on --metrics $Extra"
# one stderr log per run (llama-server logs to stderr), so restarts never overwrite a test session; prune after 14 days
$err = "C:\llm\logs\llama-server-$Port-{0}.err" -f (Get-Date -Format yyyyMMdd-HHmmss)
Get-ChildItem "C:\llm\logs\llama-server-$Port-*.err" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -ErrorAction SilentlyContinue
Add-Content $log ("{0}  START {1} {2}  -> {3}" -f (Get-Date -Format s), $exe, $argList, $err)
$p = Start-Process -FilePath $exe -ArgumentList $argList -NoNewWindow -PassThru -Wait -RedirectStandardError $err -RedirectStandardOutput "$log.out"
Add-Content $log ("{0}  EXIT {1}" -f (Get-Date -Format s), $p.ExitCode)
