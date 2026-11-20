# 10 — Troubleshooting

Symptom → cause → fix for every hurdle we hit. The number in the first column matches the hurdle numbering used
across the docs; the last column points at the doc with the full story.

## Hardware and firmware

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 1 | BIOS flash rejected by EZ Flash and by FlashBack, with no reason given | BIOS file for the wrong board variant (e.g. Crosshair VIII Hero `C8H.CAP` vs Hero (Wi-Fi) `C8HW.CAP`) | Read the exact SKU off the board or box, not the family name, and download that file | [01](01-bios-and-memory.md) |
| 2 | Model downloads finish at full size but fail SHA; re-hashing the same file gives different results each pass. No crash, no WHEA log | Silent RAM bit flips at the kit's rated speed (we saw it at DDR4-3600, 4×8 GB single-rank, FCLK 1800). No ECC, so nothing is logged | Drop memory frequency (DDR4-3200 with DOCP timings fixed ours). Prove it: chunk-hash a known-good multi-GB file 6× with `hash-check.ps1`, all clean. Then re-verify every model file and re-run your evals | [01](01-bios-and-memory.md) |
| 3 | Software reports DRAM voltage that doesn't match what you set | Software readings are wrong (WMI said 1.20 V; BIOS showed 1.35 V set, 1.344 V actual) | Check voltages in the BIOS | [01](01-bios-and-memory.md) |

## Windows

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 4 | llama.cpp binaries blocked from running | Smart App Control blocks unsigned binaries, with no per-app exception. It can flip itself from evaluation mode to On | Turn Smart App Control Off in Windows Security (GUI) | [02](02-windows-prep.md) |
| 5 | A model that shouldn't fit "loads fine" but runs 5–10× slower | NVIDIA sysmem fallback spills it into system RAM silently | NVIDIA Control Panel → Manage 3D settings → CUDA – Sysmem Fallback Policy → Prefer No Sysmem Fallback. You want an honest OOM | [02](02-windows-prep.md) |
| 6 | Extra VRAM use and background noise from the driver stack | NVIDIA App / overlay | Studio driver, clean install, skip the NVIDIA App and overlay | [02](02-windows-prep.md) |
| 7 | Less VRAM free than expected | A signed-in desktop holds VRAM: 514 MiB vs 96 MiB headless; RDP more | Serve from the SYSTEM task, sign out of the console, disconnect RDP (don't just minimize) | [06](06-serving.md) |
| 8 | Password logins over RDP refused | Windows Hello-only sign-in is enabled | Change the sign-in setting in the GUI | [02](02-windows-prep.md) |
| 9a | `.ps1` won't run over SSH | Execution policy | `powershell -ExecutionPolicy Bypass -File ...` per call | [06](06-serving.md) |
| 9b | A script fails to parse, or behaves strangely, in PowerShell 5.1 | Non-ASCII characters in the script | Keep scripts ASCII only | [02](02-windows-prep.md) |
| 9c | An array argument arrives as one string | Array args passed through `-File` arrive as a single string | Pass extra args as one quoted string (`-Extra "..."`) | [06](06-serving.md) |
| 10 | "The box is down" (ping fails) | Windows blocks ping by default | Check SSH or `curl http://YOUR-BOX:8080/health` instead | [06](06-serving.md) |
| 11 | Box reboots in the middle of a run | Windows Update | No auto-reboot with users signed in; run updates as a scheduled SYSTEM task (`wu.ps1`) at a time you choose | [02](02-windows-prep.md) |

## Remote access

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 12 | SSH key login fails for an admin account | Admin keys must be in `C:\ProgramData\ssh\administrators_authorized_keys`, not `~\.ssh`; sshd silently ignores the file if its ACL is loose | Put the key there and lock the ACL (`setup-ssh.ps1` does both) | [03](03-remote-access.md) |
| 13 | Worry: CUDA won't work from SSH / a SYSTEM task (session 0) | Old reports | Not a problem on current drivers, even with nobody signed in. Test with `nvidia-smi` over SSH | [03](03-remote-access.md) |
| 14 | Server reachable from the LAN | Bound to `0.0.0.0`; the server has no auth | Bind to the tailnet IP and scope the firewall to the Tailscale range (`serve.ps1`, `firewall-tailnet.ps1`) | [06](06-serving.md) |

## llama.cpp on Turing (sm_75)

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 15 | First load takes ~50 s; it happens again under SYSTEM after you warmed it as your user | Official CUDA zips ship Turing as PTX only; JIT result is cached per Windows account | Shared `CUDA_CACHE_PATH` + `CUDA_CACHE_MAXSIZE` 4 GB (`box-config.ps1`): cold start 48 s → 4 s. Use the CUDA 12.4 build so any current driver can JIT it | [04](04-llama-cpp.md) |
| 16 | Very slow inference after `winget install` | winget gives a CPU/Vulkan build | Download the pinned CUDA 12.4 release zip (`get-llama.ps1`) | [04](04-llama-cpp.md) |
| 17 | Quant fails or misbehaves on this card | Turing has no BF16; some quants (Unsloth `_XL`) carry BF16 tensors | Use quants without BF16 tensors (we use bartowski Q4_K_M) | [05](05-choosing-a-model.md) |
| 18a | Quantized KV cache slower than expected | KV quantization costs speed on this card: f16 beat q8_0 by 17% at 8K and 27% at 32K | Leave KV at f16 unless you need the context | [results/kv-and-batch](../results/kv-and-batch.md) |
| 18b | Mixed K/V types (e.g. K q8_0, V q4_0) silently slow | Mixed pairs fall back to F16 or CPU unless built with `GGML_CUDA_FA_QUANTS` | Use matching pairs | [results/kv-and-batch](../results/kv-and-batch.md) |
| 18c | Crash with q8_0 V cache on a `granitemoe` model | Model-family bug (K q8_0 / V f16 works) | Smoke-test the KV type for each model | [results/kv-and-batch](../results/kv-and-batch.md) |
| 19 | `llama-bench` runs more arms than you asked for | Repeating a flag in common + per-run args makes combinations, not overrides | Keep each flag in one place | [08](08-measuring.md) |
| 20 | Harness shows the model as `C:\llm\models\...` | Model id defaults to the file path | `--alias nemotron-bolt-e4b` | [06](06-serving.md) |

## Speculative decoding

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 21 | With DFlash at `-c 65536`, server exits on the first request; box looks hung | Target + drafter reach 7.6 GB; cuBLAS workspace `cudaMalloc` fails | `-c 32768` (7.1 GB). Check the `.err` log and last boot time before assuming a hang | [07](07-speculative-decoding.md) |
| 22 | Raising draft length past 7 changes nothing; n7 slower on prose | Drafter block size is 8 (n ≥ 8 behaves like 7); long drafts get rejected on prose | `--spec-draft-n-max 3` | [07](07-speculative-decoding.md) |
| 23 | First turn with a big prompt is slower with DFlash | Drafter also processes the prompt: cold prefill ~1.7× slower | Fine for cached agent loops; use the ingest profile for big fresh dumps every turn | [07](07-speculative-decoding.md) |

## Agent harnesses

| # | Symptom | Cause | Fix | Doc |
|---|---|---|---|---|
| 24 | Model can't start in a harness, or compacts at once | Harness base prompt (system + tool schemas) eats the window: ~7.6K in one harness, ~39K in another | Measure the base prompt; drop unneeded MCP servers/tools; or use the 64K ingest profile | [09](09-agent-harnesses.md) |
| — | Session stalls after one tool call; compaction fails (`exceed_context_size_error`) | One tool output larger than the window (ours: ~380 KB of progress lines, next request 40,650 tokens vs 32,768) | Filter noisy output at the source (`grep -v`), cap tool output in the harness | [09](09-agent-harnesses.md) |
| 25 | Model follows instructions you didn't give, or reads unrelated files | Harness loads every instruction file up the tree; model reads its working folder | Run from a clean, dedicated folder | [09](09-agent-harnesses.md) |
| 26 | Main request waits with nothing visible running | One server slot; harness side calls (titles etc.) queue ahead of it | Turn titles off or route side calls elsewhere | [09](09-agent-harnesses.md) |
| 27 | Slow turns, context fills fast | Thinking on: 300–2,600 chars per turn | Thinking off for agent loops | [09](09-agent-harnesses.md) |
| 28 | Non-interactive harness run never finishes | Waiting on stdin | `</dev/null` | [09](09-agent-harnesses.md) |
| 29 | Multi-step stateful tasks fail; write-up claims steps that didn't happen | Small models chain poorly across shells and state | One obvious tool per step; human owns stateful steps; verify write-ups | [09](09-agent-harnesses.md) |

## First checks when something is wrong

1. `curl http://YOUR-BOX:8080/health` (not ping).
2. `C:\llm\logs\llama-server-8080.log`: last `START`/`EXIT` lines, then the matching `.err`.
3. `nvidia-smi` over SSH: is the memory used what you expect for the profile (7.1 GB agent, 4.7 GB ingest)?
4. Did anything change: driver, llama.cpp build, Windows Update, BIOS? Re-run `bench.ps1` and `smoke.py`.
5. Garbage output after a hardware change: run `hash-check.ps1` before blaming the model.
