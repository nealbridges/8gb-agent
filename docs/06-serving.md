# 06 — Serving the model

Goal: `llama-server` running as a SYSTEM scheduled task, bound to the box's Tailscale IP, logging every run,
reachable from another machine at `http://YOUR-BOX:8080`.

Done when `python3 scripts/client/smoke.py http://YOUR-BOX:8080` passes from another machine.

## Why a SYSTEM task, not a console window

- **A signed-in desktop costs VRAM.** We measured 96 MiB of VRAM in use headless (nobody signed in) against
  514 MiB with a signed-in desktop. RDP costs more. On an 8 GB card that is real headroom.
- **CUDA works with nobody signed in.** A task running as SYSTEM (session 0) sees the GPU on current drivers.
  Old forum posts say otherwise; we tested it after a reboot with no one logged on and it worked.
- **It survives you logging out.** Start it, sign out of the console, leave it.

## The pieces

| Script | Runs | Does |
|---|---|---|
| `scripts/windows/serve.ps1` | inside the task | Looks up the tailnet IP, launches `llama-server`, writes a start/exit line and a per-run log |
| `scripts/windows/serve-task.ps1` | by you, over SSH | Stops any running server, registers (or replaces) the `llm-server` task as SYSTEM, starts it, polls `/health` |
| `scripts/windows/firewall-tailnet.ps1` | once | Inbound rule for the server port, scoped to the Tailscale range |

Run PowerShell scripts over SSH with `-ExecutionPolicy Bypass` per call (the default policy blocks `.ps1`):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\serve-task.ps1 `
  -Model NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf `
  -Extra "-c 32768 -ub 1024 -np 1 --alias nemotron-bolt-e4b --spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf --spec-type draft-dflash --spec-draft-n-max 3 --spec-draft-ngl 999"
```

`-Extra` is one quoted string on purpose: PowerShell 5.1 passes array arguments through `-File` as a single
string, so the scripts take extra args as a string and split nothing.

Those `-Extra` values are the **agent profile**. The other frozen profile (ingest) and when to use each are in
[`config/profiles.md`](../config/profiles.md). Speculative decoding is explained in
[07](07-speculative-decoding.md); if you want to bring the server up without it first, use the ingest profile.

## The full command

What `serve.ps1` ends up running for the agent profile:

```
C:\llm\llama\<build>\llama-server.exe
  -m "C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf"
  --host <tailnet IP> --port 8080
  --jinja -ngl 99 -fa on --metrics
  -c 32768 -ub 1024 -np 1
  --alias nemotron-bolt-e4b
  --spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf
  --spec-type draft-dflash --spec-draft-n-max 3 --spec-draft-ngl 999
```

### Every flag

**Fixed in `serve.ps1` (every profile):**

| Flag | What it does | Why this value |
|---|---|---|
| `-m <path>` | Model file | bartowski Q4_K_M: best 4-bit KLD at full 4-bit speed (see [results/quant-ab.md](../results/quant-ab.md)) |
| `--host <tailnet IP>` | Interface to listen on | The server has **no auth**. Bind to the Tailscale IP only, never `0.0.0.0` on a LAN |
| `--port 8080` | Listen port | The firewall rule opens the server port to the tailnet only |
| `--jinja` | Use the model's own chat template | Required for tool calls to be parsed into `tool_calls` |
| `-ngl 99` | Offload all layers to the GPU | The whole model fits in 8 GB |
| `-fa on` | Flash attention | Works on sm_75 for this model (head_dim 512) with no crash; required for quantized KV if you ever use it |
| `--metrics` | Exposes a Prometheus `/metrics` endpoint | Cheap visibility into load and throughput |

**Profile args (passed in `-Extra`):**

| Flag | What it does | Why this value |
|---|---|---|
| `-c 32768` | Context window (tokens) | DFlash OOMs at 65536 on this card; 32K fits at 7.1 GB. Ingest profile uses 65536 (the model's trained max) |
| `-ub 1024` | Physical micro-batch size | Best generation speed in our sweep; 2048 is ~4% better for prefill at 32K only |
| `-np 1` | One parallel slot | All the context goes to one conversation. Side effect: background calls from a harness queue behind the main one (see [09](09-agent-harnesses.md)) |
| `--alias nemotron-bolt-e4b` | Model id reported by `/v1/models` | Without it the id is the Windows file path, and harnesses display `C:\llm\models\...` |
| `--spec-draft-model <path>` | The DFlash drafter | +58% generation, lossless at temp 0 |
| `--spec-type draft-dflash` | Speculation method | Required for the DFlash drafter |
| `--spec-draft-n-max 3` | Max draft tokens per step | Best all-rounder; see [07](07-speculative-decoding.md) |
| `--spec-draft-ngl 999` | Put the drafter fully on the GPU | It fits alongside the target at 32K |

**Left at default, on purpose:**

| Setting | Default | Why we kept it |
|---|---|---|
| KV cache type (`-ctk`/`-ctv`) | f16 | f16 beat q8_0 by 17% at 8K and 27% at 32K on this card. KV quantization is not free on Turing |
| Prompt cache across turns | on | Turns 2–10 of an agent loop prefill only the new tokens (~70 ms). Nothing to set |
| `--swa-full` | off | Costs +2.6 GB VRAM and was slower |
| `--mmproj` | not loaded | The vision projector costs ~0.9 GB; this is a text agent |

## Logging

`serve.ps1` writes to `C:\llm\logs`:

| File | Contents |
|---|---|
| `llama-server-8080.log` | One `START` line (timestamp, exe, full args, which `.err` file) and one `EXIT` line (exit code) per run |
| `llama-server-8080-<yyyyMMdd-HHmmss>.err` | That run's server output. llama-server logs to stderr, so this is the real log |
| `llama-server-8080.log.out` | stdout (mostly empty) |

One `.err` per run means a restart never overwrites the log of the run you were debugging. Files older than
14 days are pruned at each start.

When the server dies, read the `EXIT` line first, then the tail of the matching `.err`. The DFlash 64K OOM, for
example, shows up as a failed cudaMalloc in the cuBLAS workspace on the first request, then an exit.

## Task behaviour

- Task name `llm-server`, principal SYSTEM, run level Highest, execution time limit 30 days.
- `serve-task.ps1` stops the task, kills any stray `llama-server`, re-registers with `-Force`, starts it, then
  polls `http://<tailnet IP>:8080/health` every 2 s for up to 120 s and prints `server healthy after Ns`.
- Switching profiles or models = run `serve-task.ps1` again with different args.
- As written, the task has no boot trigger. After a reboot, `Start-ScheduledTask llm-server` (or rerun
  `serve-task.ps1`).

## Cold start

The official CUDA zips ship Turing as PTX only, so the first load JIT-compiles kernels (~50 s), and the cache is
**per Windows account**: SYSTEM and your user each pay it. `box-config.ps1` sets a shared `CUDA_CACHE_PATH` and
a 4 GB `CUDA_CACHE_MAXSIZE`. With that, cold server start went from 48 s to about 4 s. Details in
[04](04-llama-cpp.md).

## Checking it from another machine

Windows blocks ping by default, so a failed ping means nothing. Check the HTTP port:

```bash
curl http://YOUR-BOX:8080/health          # {"status":"ok"}
curl http://YOUR-BOX:8080/v1/models       # id should be nemotron-bolt-e4b
python3 scripts/client/smoke.py http://YOUR-BOX:8080
```

`smoke.py` does one chat round-trip and one tool call (an nmap-shaped schema) and prints `PASS`, `PARTIAL`, or
`NO TOOL CALL`, plus prompt and generation tok/s from the server's timings.

## Security notes

- llama-server has no authentication. Anyone who can reach the port can use it.
- Bind to the tailnet IP **and** scope the firewall rule to the Tailscale range. Either alone is one mistake away
  from exposing it on your LAN.
- Don't put it behind a public tunnel.
