# 02. Windows prep

**Done when:** `nvidia-smi` runs clean, the box never sleeps, and Defender exclusions are set.

Tested on 2026-11-12: Windows 11 Pro 26H2 (build 26300.9974), NVIDIA Studio driver 621.14.

Start from a fresh Windows 11 install with Windows Update applied. Some steps below need the GUI (marked
**[GUI]**); do those at the console or over RDP before you go headless. The rest is in
`scripts/windows/box-config.ps1`.

## Summary

| Setting | Value | How |
|---|---|---|
| Smart App Control | Off | **[GUI]** Windows Security → App & browser control |
| NVIDIA driver | Current Studio branch, clean install, no NVIDIA App / overlay | **[GUI]** installer |
| CUDA sysmem fallback | Prefer No Sysmem Fallback (global) | **[GUI]** NVIDIA Control Panel |
| Power | High performance plan, PCIe ASPM off, no standby, hibernate off | `box-config.ps1` |
| Defender | Exclude `C:\llm\models`, `C:\llm\llama`, `llama-server.exe`, `llama-bench.exe` | `box-config.ps1` |
| CUDA JIT cache | `CUDA_CACHE_PATH` + `CUDA_CACHE_MAXSIZE=4294967296` (machine level) | `box-config.ps1`, see [04](04-llama-cpp.md) |
| Windows Update | No auto-reboot with users signed in; active hours 08–02; updates via a SYSTEM task | `box-config.ps1`, `wu.ps1` |

Power commands, for reference:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /hibernate off
```

PCIe Link State Power Management goes off in the active plan's advanced settings. We ran the High performance
plan. Duplicating the hidden Ultimate Performance scheme
(`powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61`) is an option; we did not compare the two.

Defender exclusions:

```powershell
Add-MpPreference -ExclusionPath C:\llm\models,C:\llm\llama -ExclusionProcess llama-server.exe,llama-bench.exe
```

Defender otherwise scans multi-GB model files on every load. We did not measure the cost; the exclusion is cheap.

## Hurdle 4: Smart App Control blocks llama.cpp

- **Symptom:** unsigned binaries such as `llama-server.exe` are blocked from running on a clean install.
- **Cause:** Smart App Control (SAC) blocks unsigned code and has no per-app exception list.
- **Fix:** turn SAC **Off** in Windows Security → App & browser control → Smart App Control. It's a GUI-only
  switch.
- **How we proved it:** our fresh install had SAC in "evaluation" mode (value 2), which doesn't block yet, so
  llama.cpp ran. Evaluation mode can switch itself to On later, so we turned it Off rather than rely on that.
  We did not reproduce a block with SAC fully On. Since April 2026 (Windows 11 25H2 with a current Security app), SAC can be turned back on later without
  reinstalling Windows.

## Hurdle 5: sysmem fallback hides an out-of-memory

- **Symptom:** a model that's too big for VRAM loads and runs, just 5–10× slower than it should, and nothing
  tells you why.
- **Cause:** by default the NVIDIA driver on Windows lets CUDA allocations spill into system RAM ("shared GPU
  memory"). The model *looks* like it fit.
- **Fix:** NVIDIA Control Panel → Manage 3D settings → **CUDA – Sysmem Fallback Policy → Prefer No Sysmem
  Fallback** (global). Now an oversized model fails with an honest out-of-memory error.
- **How we proved it:** not tested in isolation; the 5–10× figure comes from published reports, not our
  measurement. To check your own box, watch Task Manager's "Shared GPU memory", or
  `Get-Counter '\GPU Adapter Memory(*)\Shared Usage'`, during a run; it should stay near zero.

## Hurdle 6: driver choice

- **Symptom:** none, if you get it right. If you install the default package, you get the NVIDIA App and its
  overlay running in the background.
- **Cause:** the default install adds software that uses VRAM and adds background noise to measurements.
- **Fix:** install the current **Studio** driver (R620 or newer), choose the clean-install option, and skip the
  NVIDIA App / GeForce Experience overlay.
- **How we proved it:** Studio 621.14 ran every build and model in this repo. With a clean install and nobody
  signed in, idle VRAM use was 96 MiB. We did not measure the overlay's cost separately.

## Hurdle 7: a signed-in desktop costs VRAM

- **Symptom:** less free VRAM than you expect.
- **Cause:** the 2080 SUPER drives the display, and the Ryzen 9 3950X has no integrated GPU, so the desktop
  compositor uses the card's VRAM. A signed-in session costs more; RDP costs more again.
- **Fix:** run the server from a scheduled task as SYSTEM (`serve-task.ps1`) and leave the console **signed
  out**. Sign out of RDP sessions; don't just disconnect or minimize.
- **How we proved it:** `nvidia-smi` showed **96 MiB** used with nobody signed in after a reboot, against
  **514 MiB** with a signed-in desktop. About 400 MiB back, on an 8 GB card. Serving with nobody signed in is
  covered in [03](03-remote-access.md).

## Hurdle 8: Windows Hello-only sign-in blocks RDP

- **Symptom:** RDP rejects the account password.
- **Cause:** the account was set to sign in with Windows Hello only, which disables password sign-in.
- **Fix:** turn off the Windows Hello-only requirement in Settings → Accounts → Sign-in options. It's a GUI
  setting.
- **How we proved it:** RDP password sign-in worked after the change. We didn't record more detail than that.

## Hurdle 9: PowerShell gotchas

Three separate traps, all hit while running scripts over SSH.

| Symptom | Cause | Fix |
|---|---|---|
| `.ps1` refuses to run over SSH | Execution policy | Run each script with `powershell -NoProfile -ExecutionPolicy Bypass -File script.ps1`. Don't change the machine policy |
| Script fails to parse, or strings come out garbled | Windows PowerShell 5.1 mishandles non-ASCII characters (smart quotes, dashes, arrows) in script files | Keep scripts pure ASCII. Every script in `scripts/windows/` is |
| An array parameter arrives as one string | Arguments passed via `-File` are not parsed as PowerShell arrays | Pass one comma-separated string and split it inside the script, or use `-Command` |

How we proved it: we hit each one while writing the scripts; with these fixes they run over SSH and from the
scheduled task.

## Hurdle 10: Windows blocks ping

- **Symptom:** the box stops answering ping and looks dead.
- **Cause:** Windows Firewall blocks inbound ICMP echo by default. Ping never worked; you just didn't notice
  until you needed it.
- **Fix:** check health with SSH or the server's HTTP port (`http://YOUR-BOX:8080/health`), not ping.
- **How we proved it:** during the 64K out-of-memory (see `07-speculative-decoding.md`) we first thought the box
  had hung. It hadn't: ping was never going to answer, the SSH timeouts were a network hiccup on the client side,
  the last boot time was unchanged, and there were no crash events. Only llama-server had exited.

## Hurdle 11: updates rebooting mid-run

- **Symptom:** a long benchmark or serving session ends with the box rebooted for updates.
- **Cause:** Windows Update's default restart behaviour.
- **Fix:**
  - Set `NoAutoRebootWithLoggedOnUsers=1` (Windows Update policy, Pro edition) and set active hours (we used
    08–02).
  - Install updates on your schedule with `wu.ps1`, which runs Windows Update through its COM API as a SYSTEM
    scheduled task, software updates only (no drivers, so it won't replace your Studio driver).
  - Pause updates before long runs.
- **How we proved it:** not tested. These settings were in place for our runs; we did not try to force an
  update reboot to confirm them.

## Verify

```powershell
nvidia-smi                          # driver loads, card listed, low idle VRAM
powercfg /getactivescheme           # High performance (or Ultimate)
Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess
[Environment]::GetEnvironmentVariable('CUDA_CACHE_MAXSIZE','Machine')
```
