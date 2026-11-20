# firewall-tailnet.ps1 - allow the llama-server ports ONLY from the Tailscale address range. Run from an ADMIN window.
# llama-server has no authentication: never expose it to the LAN or the internet.
param([string]$Ports = '8080-8089', [string]$Range = '100.64.0.0/10')
$name = 'llm-server-tailnet'
Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $name -DisplayName 'llm-server (tailnet only)' -Direction Inbound -Protocol TCP `
  -LocalPort $Ports -RemoteAddress $Range -Action Allow -Profile Any | Out-Null
Get-NetFirewallRule -Name $name | Get-NetFirewallAddressFilter | Format-Table RemoteAddress -AutoSize
