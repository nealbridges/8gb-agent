# Operating profiles

Two frozen operating points for NVIDIA-Nemotron-3.5-Bolt-E4B Q4_K_M (bartowski) on an RTX 2080 SUPER 8 GB,
llama.cpp CUDA 12.4 build. Both use f16 KV (the default) and flash attention on.

| Profile | VRAM | Generation tok/s | Context | Use |
|---|---|---|---|---|
| **agent** (default) | 7.1 GB | ~135 | 32K | Agent loops with short per-turn input |
| **ingest** | 4.7 GB | ~85–90 | 64K | Big fresh tool dumps each turn; prefill about 2.9K tok/s at 24K |

The agent profile scores 27/27 on `evals.py`, 9/9 needle and 5/5 loop on `evals_hard.py`.

Pick **agent** unless each turn brings a large new input (a whole scan, a long log) that won't hit the prompt
cache. Speculative decoding makes cold prefill about 1.7× slower, and the drafter doesn't fit at 64K.

## Base args (set by `serve.ps1` for every profile)

```
-m "C:\llm\models\<model file>" --host <tailnet IP> --port 8080 --jinja -ngl 99 -fa on --metrics
```

## agent

`-Extra` for `serve-task.ps1`:

```
-c 32768 -ub 1024 -np 1 --alias nemotron-bolt-e4b --spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf --spec-type draft-dflash --spec-draft-n-max 3 --spec-draft-ngl 999
```

Register it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\serve-task.ps1 `
  -Model NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf `
  -Extra "-c 32768 -ub 1024 -np 1 --alias nemotron-bolt-e4b --spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf --spec-type draft-dflash --spec-draft-n-max 3 --spec-draft-ngl 999"
```

Full command, for running `llama-server` by hand:

```
C:\llm\llama\<build>\llama-server.exe -m "C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf" --host <tailnet IP> --port 8080 --jinja -ngl 99 -fa on --metrics -c 32768 -ub 1024 -np 1 --alias nemotron-bolt-e4b --spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf --spec-type draft-dflash --spec-draft-n-max 3 --spec-draft-ngl 999
```

Do not raise `-c` above 32768 on this profile: at 65536 it OOMs on the first request.

## ingest

`-Extra` for `serve-task.ps1`:

```
-c 65536 -ub 1024 -np 1 --alias nemotron-bolt-e4b
```

Register it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\serve-task.ps1 `
  -Model NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf `
  -Extra "-c 65536 -ub 1024 -np 1 --alias nemotron-bolt-e4b"
```

Full command:

```
C:\llm\llama\<build>\llama-server.exe -m "C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf" --host <tailnet IP> --port 8080 --jinja -ngl 99 -fa on --metrics -c 65536 -ub 1024 -np 1 --alias nemotron-bolt-e4b
```

65536 is the model's trained context, and the server caps `-c` there.

`--alias` was set on the agent profile in our runs; we add it to ingest too so harnesses see the same model id
whichever profile is running.

## Not in either profile, on purpose

| Arg | Why not |
|---|---|
| `-ctk q8_0 -ctv q8_0` | f16 KV is 17% faster at 8K and 27% at 32K on this card |
| `-ub 2048` | ~4% better prefill at 32K, worse generation |
| `--swa-full` | +2.6 GB VRAM and slower |
| `--mmproj` | Vision projector, ~0.9 GB; not needed |
| `--spec-draft-n-max 7` | Vendor recipe; only wins on transcription-style output |
