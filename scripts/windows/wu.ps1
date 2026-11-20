# wu.ps1 - Windows Update via COM API, run as SYSTEM task. Software only (no drivers).
$log = 'C:\llm\logs\wu.log'
function L($m) { $l = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Add-Content -Path $log -Value $l }
L "=== WU pass start"
try {
  $s = New-Object -ComObject Microsoft.Update.Session
  $r = $s.CreateUpdateSearcher().Search("IsInstalled=0 and IsHidden=0 and Type='Software'")
  L ("found " + $r.Updates.Count)
  if ($r.Updates.Count -gt 0) {
    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    foreach ($u in $r.Updates) { L ("  queued: " + $u.Title); if (-not $u.EulaAccepted) { $u.AcceptEula() }; [void]$coll.Add($u) }
    $d = $s.CreateUpdateDownloader(); $d.Updates = $coll; L ("download result " + $d.Download().ResultCode)
    $i = $s.CreateUpdateInstaller(); $i.Updates = $coll; $ir = $i.Install()
    L ("install result " + $ir.ResultCode + " rebootRequired=" + $ir.RebootRequired)
    for ($k = 0; $k -lt $coll.Count; $k++) { L ("  [" + $ir.GetUpdateResult($k).ResultCode + "] " + $coll.Item($k).Title) }
  }
} catch { L ("ERROR " + $_.Exception.Message) }
L "=== WU pass done"
