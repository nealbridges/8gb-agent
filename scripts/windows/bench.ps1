# bench.ps1 - llama-bench a list of "label|model|extra args" lines; md rows to stdout + C:\llm\logs\bench.md
param([string]$ListFile, [string]$Build = 'b12318-cuda124', [string]$Common = '-ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 -p 512 -n 128 -r 3')
$exe = "C:\llm\llama\$Build\llama-bench.exe"
foreach ($line in Get-Content $ListFile) {
  if (-not $line.Trim() -or $line.StartsWith('#')) { continue }
  $label, $model, $extra = $line.Split('|')
  $argv = @('-m', $model) + $Common.Split(' ', [StringSplitOptions]::RemoveEmptyEntries) + ("$extra").Split(' ', [StringSplitOptions]::RemoveEmptyEntries) + @('-o', 'md')
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $out = & $exe @argv 2>&1 | ForEach-Object { "$_" }
  $sw.Stop()
  $hdr = "== {0}  [{1}]  wall {2:N1}s" -f $label, $extra, $sw.Elapsed.TotalSeconds
  $rows = $out | Where-Object { $_ -match '^\| ' -and $_ -match '(pp|tg)\d' }
  $errs = $out | Where-Object { $_ -match 'error|failed|illegal' } | Select-Object -First 3
  ($hdr, $rows, $errs) | ForEach-Object { $_ } | Tee-Object -FilePath C:\llm\logs\bench.md -Append
}
