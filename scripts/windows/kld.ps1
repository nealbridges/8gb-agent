# kld.ps1 - KL divergence of each quant vs a reference quant on wikitext-2 test
param([string]$Ref, [string]$Quants, [int]$Chunks = 16)
$exe = 'C:\llm\llama\b12318-cuda124\llama-perplexity.exe'; $base = 'C:\llm\dl\kld-base.bin'; $txt = 'C:\llm\dl\wiki.test.raw'
$common = @('-f', $txt, '-c', '2048', '--chunks', "$Chunks", '-ngl', '99', '-fa', 'on', '-ub', '1024')
& $exe -m $Ref @common --kl-divergence-base $base 2>&1 | Select-String 'Final estimate' | % { "REF  $(Split-Path $Ref -Leaf)  $($_.Line.Trim())" }
foreach ($q in $Quants.Split(',')) {
  $o = & $exe -m $q @common --kl-divergence-base $base --kl-divergence 2>&1 | % { "$_" }
  "== " + (Split-Path $q -Leaf)
  $o | Select-String 'Mean PPL\(Q\)|Mean\s+KLD|99\.0%\s+KLD|Maximum KLD|Same top p|RMS .p|error|failed' | % { "   " + ($_.Line -replace '^\S+ [IWE] ', '').Trim() }
}
Remove-Item $base -ErrorAction SilentlyContinue
