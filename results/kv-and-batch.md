# KV cache, micro-batch, context and prompt cache: Nemotron-3.5-Bolt-E4B Q4_K_M

RTX 2080 SUPER 8 GB, llama.cpp CUDA 12.4 build, flash attention on.

## KV cache type: f16 vs q8_0

| KV (K/V) | tg at 8K | tg at 32K |
|---|---|---|
| **f16 / f16** | **79.6** | **60.2** |
| q8_0 / q8_0 | 68.2 | 47.5 |
| f16 advantage | +17% | +27% |

Prefill gains about 2% with f16. On this card KV quantization costs speed; it isn't free. We serve f16 (the
default).

Related, from other models on the same box:

- **Mixed K/V types** (e.g. K q8_0 / V q4_0) silently fall back to F16 or CPU unless llama.cpp is built with
  `GGML_CUDA_FA_QUANTS`. Use matching pairs.
- **q8_0 V cache crashes `granitemoe`** models. K q8_0 / V f16 works. Qwen and granitehybrid were fine with
  q8/q8. Smoke-test the KV type for each model.
- **FA off with a q8_0 V cache** fails context creation, as expected. FA off with f16: not measured.

## Micro-batch (`-ub`)

| `-ub` | Result |
|---|---|
| **1024** | Best generation tok/s |
| 2048 | About 4% better prefill at 32K |

We use `-ub 1024`.

## Context and VRAM (f16 KV, no speculative decoding)

| `-c` | VRAM |
|---|---|
| 32768 | 4.15 GB |
| 65536 | 4.73 GB |

The model's trained context (n_ctx_train) is 64K and the server caps `-c` there. The per-layer embeddings (PLE)
stay on the CPU. That leaves about 3 GB of headroom, enough for a bigger quant or for the speculative-decoding
drafter, which changes the picture: see
[dflash.md](dflash.md).

Flash attention works on sm_75 for this model despite head_dim 512, with no crash.

## Prompt cache across agent turns

`scripts/client/evals_turns.py`, 10-turn agent loop at 24K context, default settings:

| Turn | Prefill | Wall per turn |
|---|---|---|
| 1 | full prompt | 8.5 s |
| 2–10 | 39 tokens in about 70 ms | 0.58 s |

It works by default.

| Option | Result |
|---|---|
| `--swa-full` | +2.6 GB VRAM and slower. Rejected |
| `-cms 0` | No difference for append-only loops |

With speculative decoding on, cached turns take 0.44 s (see [dflash.md](dflash.md)).
