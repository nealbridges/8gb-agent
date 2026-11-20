# box-config.ps1 - one-time Windows tuning for a headless llama.cpp box. Run from an ADMIN window.
# The commands we ran by hand on the reference box (2026-11-12), collected here; the box state matches what it sets.
# GUI-only steps it can't do: Smart App Control off, NVIDIA "Prefer No Sysmem Fallback" (see docs/02-windows-prep.md).
param([string]$Root = 'C:\llm')
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force "$Root\models", "$Root\llama", "$Root\logs", "$Root\scripts", "$Root\cudacache" | Out-Null

# Power: High performance, PCIe link-state power management (ASPM) off, never sleep or hibernate.
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
powercfg /setacvalueindex SCHEME_CURRENT SUB_PCIEXPRESS ASPM 0
powercfg /setactive SCHEME_CURRENT
powercfg /change standby-timeout-ac 0
powercfg /hibernate off

# Defender: don't scan multi-GB model files on every load.
Add-MpPreference -ExclusionPath "$Root\models", "$Root\llama" -ExclusionProcess 'llama-server.exe', 'llama-bench.exe'

# CUDA JIT cache shared by every account (SYSTEM task + your user), big enough for Turing PTX kernels.
[Environment]::SetEnvironmentVariable('CUDA_CACHE_PATH', "$Root\cudacache", 'Machine')
[Environment]::SetEnvironmentVariable('CUDA_CACHE_MAXSIZE', '4294967296', 'Machine')

# Windows Update: no automatic reboot while someone is signed in; active hours 08-02.
$au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
New-Item -Path $au -Force | Out-Null
Set-ItemProperty -Path $au -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
$ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
Set-ItemProperty -Path $ux -Name ActiveHoursStart -Value 8 -Type DWord
Set-ItemProperty -Path $ux -Name ActiveHoursEnd -Value 2 -Type DWord

Write-Host "Done. Reboot once so the CUDA cache variables reach services and scheduled tasks."
