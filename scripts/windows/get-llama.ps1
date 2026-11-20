# get-llama.ps1 - download a pinned llama.cpp Windows CUDA 12.4 release (+ cudart), check SHA256, unzip.
# Use the CUDA 12.4 build: any current driver can JIT it for Turing.
# Don't 'winget install llama.cpp' - that gets a CPU/Vulkan build.
# Defaults are the SHA256 digests GitHub publishes for the b12318 assets. For another tag, pass that release's digests
# (gh api repos/ggml-org/llama.cpp/releases/tags/<tag> --jq '.assets[] | "\(.name) \(.digest)"').
param([string]$Tag = 'b12318',
  [string]$Sha = '20281408c618dcd13080bc0b3deed250c413bbe6541421a1c989acf5a376e684',
  [string]$CudartSha = '8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6',
  [string]$Root = 'C:\llm\llama')
$ProgressPreference = 'SilentlyContinue'
$dest = Join-Path $Root "$Tag-cuda124"; New-Item -ItemType Directory -Force $dest | Out-Null
$base = "https://github.com/ggml-org/llama.cpp/releases/download/$Tag"
$files = @(@("llama-$Tag-bin-win-cuda-12.4-x64.zip", $Sha), @('cudart-llama-bin-win-cuda-12.4-x64.zip', $CudartSha))
foreach ($f in $files) {
  $zip = Join-Path $env:TEMP $f[0]
  Invoke-WebRequest -UseBasicParsing -Uri "$base/$($f[0])" -OutFile $zip
  $got = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
  if ($f[1] -and $got -ne $f[1].ToLower()) { Write-Host "SHA MISMATCH $($f[0]): $got" -ForegroundColor Red; exit 1 }
  if (-not $f[1]) { Write-Host "no SHA given for $($f[0]); computed $got - compare it yourself" -ForegroundColor Yellow }
  Expand-Archive -Path $zip -DestinationPath $dest -Force
}
& (Join-Path $dest 'llama-server.exe') --version
