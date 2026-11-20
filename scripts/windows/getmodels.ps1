# getmodels.ps1 - pull GGUFs listed as "repo|file|sha256"; verify SHA256; retry up to 3x; skip files already good.
# Public repos need no token. For gated repos, put a READ-ONLY token in %USERPROFILE%\.cache\huggingface\token (never log it).
param([string]$ListFile = 'C:\llm\scripts\models.txt')
$ProgressPreference = 'SilentlyContinue'
$tf = Join-Path $env:USERPROFILE '.cache\huggingface\token'
$h = @{}; if (Test-Path $tf) { $h.Authorization = 'Bearer ' + (Get-Content $tf -Raw).Trim() }
New-Item -ItemType Directory -Force C:\llm\models, C:\llm\logs | Out-Null
$log = 'C:\llm\logs\getmodels.log'
foreach ($line in Get-Content $ListFile) {
  if (-not $line.Trim() -or $line.StartsWith('#')) { continue }
  $repo, $file, $want = $line.Split('|')
  $out = Join-Path 'C:\llm\models' $file
  if ((Test-Path $out) -and ((Get-FileHash $out -Algorithm SHA256).Hash.ToLower() -eq $want)) { Add-Content $log "SKIP (have)  $file"; continue }
  for ($try = 1; $try -le 3; $try++) {
    $t = Measure-Command { try { Invoke-WebRequest -UseBasicParsing -Headers $h -Uri ("https://huggingface.co/{0}/resolve/main/{1}" -f $repo, $file) -OutFile $out } catch { Add-Content $log "ERROR  $file  try $try  $($_.Exception.Message)" } }
    $sha = if (Test-Path $out) { (Get-FileHash $out -Algorithm SHA256).Hash.ToLower() } else { '' }
    $len = if (Test-Path $out) { (Get-Item $out).Length / 1MB } else { 0 }
    Add-Content $log ("{0}  {1}  {2:N0} MB in {3:N0}s  (try {4})" -f $(if ($sha -eq $want) { 'SHA OK ' } else { 'SHA BAD' }), $file, $len, $t.TotalSeconds, $try)
    if ($sha -eq $want) { break }
    Remove-Item $out -ErrorAction SilentlyContinue
  }
}
Add-Content $log "ALL DONE"
