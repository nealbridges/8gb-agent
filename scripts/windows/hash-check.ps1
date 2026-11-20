# hash-check.ps1 - hash a big file in chunks, N passes. Every pass should give identical chunk hashes.
# If they differ, your RAM (or storage path) is flipping bits: lower the memory speed and run it again.
# This is how we caught silent bit flips at DDR4-3600 that no crash or log ever showed (docs/01-bios-and-memory.md).
param([Parameter(Mandatory)][string]$Path, [int]$Passes = 6, [int]$ChunkMB = 64)
$sha = [Security.Cryptography.SHA256]::Create(); $buf = New-Object byte[] ($ChunkMB * 1MB); $first = $null; $bad = 0
for ($p = 1; $p -le $Passes; $p++) {
  $fs = [IO.File]::OpenRead($Path); $hashes = New-Object Collections.Generic.List[string]
  while (($n = $fs.Read($buf, 0, $buf.Length)) -gt 0) { $hashes.Add([BitConverter]::ToString($sha.ComputeHash($buf, 0, $n))) }
  $fs.Close()
  if ($null -eq $first) { $first = $hashes; "pass 1: {0} chunks" -f $hashes.Count; continue }
  $diff = 0; for ($i = 0; $i -lt $first.Count; $i++) { if ($hashes[$i] -ne $first[$i]) { $diff++ } }
  "pass {0}: {1} of {2} chunks differ from pass 1" -f $p, $diff, $first.Count; $bad += $diff
}
if ($bad -eq 0) { "CLEAN: $Passes identical passes" } else { "UNSTABLE: chunk hashes changed between passes" }
