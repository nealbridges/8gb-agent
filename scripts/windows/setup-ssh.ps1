# setup-ssh.ps1 - OpenSSH server + admin key. Run from an ADMIN window.
# Idempotent: safe to run twice. Uses only cmdlets/exes (works under App Control constrained language).
$ErrorActionPreference = 'Stop'
function Step($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }

if (-not ((whoami /groups) -match 'S-1-16-12288')) {
    Write-Host "NOT ELEVATED: open Terminal (Admin) / Command Prompt (Admin) and rerun." -ForegroundColor Red
    exit 1
}

Step "1/5 OpenSSH Server feature"
$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
if ($cap.State -ne 'Installed') { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
(Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1).State

Step "2/5 sshd service: automatic + running"
Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd
Get-Service -Name sshd | Format-Table Name, Status, StartType -AutoSize

Step "3/5 Firewall: TCP 22 inbound, all profiles"
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True `
        -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -Profile Any | Out-Null
} else {
    Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Enabled True -Profile Any
}
Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' | Format-Table Name, Enabled, Profile, Direction, Action -AutoSize

Step "4/5 Admin key"
$key = (Get-Content -Path (Join-Path $PSScriptRoot 'admin.pub') -Raw).Trim()
if ($key -notmatch '^ssh-ed25519 ') { Write-Host "admin.pub missing or bad" -ForegroundColor Red; exit 1 }
# Admin accounts: sshd reads ONLY this file, and only if its ACL is Administrators + SYSTEM.
$adminKeys = 'C:\ProgramData\ssh\administrators_authorized_keys'
Set-Content -Path $adminKeys -Value $key -Encoding ascii
icacls.exe $adminKeys /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
icacls.exe $adminKeys
# Standard (non-admin) accounts read the per-user file instead; write it too so either case works.
$userSsh = Join-Path $env:USERPROFILE '.ssh'
New-Item -ItemType Directory -Path $userSsh -Force | Out-Null
Set-Content -Path (Join-Path $userSsh 'authorized_keys') -Value $key -Encoding ascii

Step "5/5 SSH default shell = PowerShell"
New-Item -Path 'HKLM:\SOFTWARE\OpenSSH' -Force | Out-Null
New-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell `
    -Value 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -PropertyType String -Force | Out-Null
Restart-Service -Name sshd

Step "Summary"
"User:  $env:USERNAME   Computer: $env:COMPUTERNAME"
try { "Local admins: " + ((Get-LocalGroupMember -SID 'S-1-5-32-544' | ForEach-Object { $_.Name }) -join ', ') } catch { "Local admins: (lookup failed)" }
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    Format-Table InterfaceAlias, IPAddress -AutoSize
$ts = 'C:\Program Files\Tailscale\tailscale.exe'
if (Test-Path $ts) { "Tailscale IPv4: " + (& $ts ip -4) } else { "Tailscale: not installed" }
Write-Host ""
Write-Host "DONE - send Claude a photo of this window" -ForegroundColor Green
