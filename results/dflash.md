# DFlash speculative decoding: Nemotron-3.5-Bolt-E4B

RTX 2080 SUPER 8 GB, llama.cpp CUDA 12.4 build. Target: NVIDIA-Nemotron-3.5-Bolt-E4B Q4_K_M. Drafter: NVIDIA's
DFlash drafter (BF16 GGUF), `--spec-type draft-dflash`, f16 KV, FA on.

## Generation speed by draft length

`scripts/client/spec_bench.py`, 4 prompts, temp 0. tok/s.

| Config | Overall | Prose finding | Scan → table | Prose checklist | Scan → JSON | Acceptance |
|---|---|---|---|---|---|---|
| no speculation | 85 | 87 | 83 | 87 | 85 | — |
| n7 (NVIDIA recipe) | 129 | 91 | 226 | 78 | 229 | 46% |
| n5 | 135 | 101 | 206 | 87 | 213 | 53% |
| **n3** | **136** | **114** | 171 | **101** | 177 | 67% |

- The drafter's block size is 8, so `--spec-draft-n-max` 10 or 15 behaves like 7.
- **n3 is the all-rounder:** prose +16–30%, structured output about 2×, no regressions vs no speculation.
- n7 only wins on pure transcription (scan → table / JSON) and loses on the prose checklist.

## Other checks

| Check | Result |
|---|---|
| Drafter on the bartowski Q4_K_M target | 132 tok/s at n7, 135 at n3 |
| Vendor sampling (temp 1.0, top_p 0.95) | 133 tok/s |
| Quality, on vs off, temp 0 | Identical `evals.py` and needle results (27/27, 9/9, loop 5/5) |

## VRAM and context

| `-c` | VRAM (target + drafter) | Result |
|---|---|---|
| 32768 | 7.1 GB | Stable |
| 65536 | 7.6 GB | First request fails in the cuBLAS workspace `cudaMalloc`; llama-server exits |

## Prefill cost

| | No speculation | DFlash |
|---|---|---|
| Cold prefill, 24K tokens | 8.5 s | 14.2 s (about 1.7× slower) |
| Cached agent turn | 0.58 s | 0.44 s |

The drafter processes the prompt too, so cold prefill is slower. Agent loops with cached turns come out ahead;
workloads that send a big fresh dump every turn should use the ingest profile (no drafter, 64K, prefill about
2.9K tok/s at 24K). See `config/profiles.md`.
