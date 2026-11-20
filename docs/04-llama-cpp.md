# 04. llama.cpp: which build and why

**Done when:** `llama-server --version` works over SSH, and a second cold start takes about 4 s.

Tested on 2026-11-12 with llama.cpp release **b12318**, `win-cuda-12.4-x64`, on Studio driver 621.14.

## The pick

Mainline llama.cpp, the official prebuilt **Windows CUDA 12.4** zip, plus the matching **cudart** zip, unpacked
into one folder: `C:\llm\llama\<build>` (e.g. `C:\llm\llama\b12318-cuda124`).

`scripts/windows/get-llama.ps1` downloads a pinned release, checks its SHA-256, and unzips it. Pin a build and
record it next to your driver version. After changing either one, re-run `bench.ps1` before trusting old numbers.

Why this build:

- **Native Windows CUDA** is the path most people with a gaming PC will actually take, and it works on Turing:
  flash attention runs through the MMA_F16 kernel, the quantized KV cache works (with matching K/V types), and
  `--n-cpu-moe` works.
- **CUDA 12.4, not the newest toolkit.** The official zips ship Turing as PTX only (hurdle 15). The driver has to
  be at least as new as the toolkit to JIT that PTX. An old toolkit means any current driver can do it.
- **Prebuilt, SHA-verified.** No compiler toolchain on the box.

## Engines we didn't use

| Engine | Verdict | Why |
|---|---|---|
| llama.cpp CUDA zip, native Windows | **Used** | See above |
| llama.cpp Vulkan zip | Fallback, **not tested** | Downloaded but the A/B was never run. Avoids CUDA coupling; may lack some kernels for newer hybrid architectures |
| llama.cpp built from source in WSL2 (native `75-real` SASS) | Not tested | Would remove the PTX JIT. Not needed once the JIT cache was fixed |
| ik_llama.cpp (WSL2) | Not tested | Claims Turing support, but its big reported speedups are Ampere-only, and it rejects quants with BF16 tensors |
| Ollama | Rejected (not measured here) | Works on the 2080, but reported much slower than llama.cpp on Qwen3.5 (ollama #14579) |
| LM Studio | Rejected (not measured here) | Little Turing-specific evidence |
| vLLM | No | Not native on Windows. In WSL, sm_75 is its minimum and it uses a Triton attention fallback; head_dim 512 models fail on shared memory; no expert offload |
| SGLang, TensorRT-LLM, ExLlamaV3 | No | Linux-only, untested on Turing, or no Turing support statement |

## Hurdle 15: Turing is PTX-only in the official zips (slow first load)

- **Symptom:** the first model load takes about 50 s before anything happens. Then it happens again when a
  different Windows account (e.g. the SYSTEM scheduled task) runs the server.
- **Cause:** release builds compile sm_75 as `75-virtual`: PTX, not native code. The driver JIT-compiles it on
  first use and caches the result **per Windows account**, in a default cache that's small. Your user and
  SYSTEM each pay the 50 s.
- **Fix:** one shared, large cache, set machine-wide (`box-config.ps1` does this):

  ```powershell
  [Environment]::SetEnvironmentVariable('CUDA_CACHE_PATH', 'C:\llm\cudacache', 'Machine')
  [Environment]::SetEnvironmentVariable('CUDA_CACHE_MAXSIZE', '4294967296', 'Machine')   # 4 GB
  ```

  New services and scheduled tasks pick up machine variables after a restart of that process (a reboot is the
  simplest way to be sure). Use the CUDA 12.4 build so any current driver can JIT it.
- **How we proved it:** cold server start went from **48 s to 4 s** with the shared cache in place.
  New kernel shapes still JIT once: the first request to a hybrid-architecture model took about 30 s, then it
  was cached too.

## Hurdle 16: don't `winget install` llama.cpp

- **Symptom:** llama.cpp installs fine, but the GPU path isn't CUDA.
- **Cause:** the winget package is a CPU/Vulkan build.
- **Fix:** use the official CUDA zip (above).
- **How we proved it:** we didn't install it; the package contents are why we skipped it.

## Hurdle 17: no BF16 on Turing

Turing has no BF16 hardware. Prefer quants built from plain K-quant tensors (Q4_K_M, IQ4_XS, Q4_0) and avoid
Unsloth's `_XL` quants, which carry BF16/F16 tensors. This is why we use bartowski's Q4_K_M of Nemotron-Bolt.
Full reasoning in [05](05-choosing-a-model.md).

## Hurdle 19: `llama-bench` turns repeated flags into combinations

- **Symptom:** a benchmark run takes far longer than expected and reports more rows than configs you asked for.
- **Cause:** `llama-bench` treats every value of a repeated flag as one axis of a sweep. If a flag appears both
  in your "common" args and in a per-run arg string, you get every combination of the two values, not an
  override.
- **Fix:** put each flag in exactly one place. `bench.ps1` takes a list of configs; keep shared flags out of the
  per-config strings (or vice versa).
- **How we proved it:** we hit it in our own sweeps; we didn't keep a before/after record.

The same sweep behaviour is useful on purpose: `-d 0,8192,32768` measures generation speed at three context
depths in one run.

## Hurdle 20: the model id is the Windows file path

- **Symptom:** your agent harness lists the model as `C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf`,
  and any config that names the model breaks the moment you move or swap the file.
- **Cause:** llama-server reports the `-m` path as the model id unless told otherwise.
- **Fix:** always pass `--alias`, e.g. `--alias nemotron-bolt-e4b`. Clients then use that name.
- **How we proved it:** harnesses showed the Windows path until we added `--alias nemotron-bolt-e4b`; the
  frozen serving profile includes it.

## Verify

Over SSH, with nobody signed in:

```powershell
C:\llm\llama\b12318-cuda124\llama-server.exe --version
C:\llm\llama\b12318-cuda124\llama-cli.exe --list-devices     # should list the RTX 2080 SUPER
```

Then start the server twice (stop it in between) and time the second cold start. About 4 s means the JIT cache
is working; about 50 s means it isn't.
