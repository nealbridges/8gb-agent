# 00. Expectations: what an 8 GB Turing card can do

**Done when:** you know the tok/s range to expect from your card and which model tier fits it.

Tested on 2026-11-12: RTX 2080 SUPER 8 GB, Ryzen 9 3950X, 32 GB DDR4, Windows 11 Pro.

## The one formula that matters

Generating a token means reading (roughly) every active weight once from VRAM. So decode speed is set by
memory bandwidth, not by compute:

```
tok/s  ≈  memory bandwidth (GB/s) × efficiency  ÷  GB read per token
```

For the 2080 SUPER we used **496 GB/s × ~0.73 efficiency**. "GB read per token" is roughly the size of the
weights that are active for each token (for a dense model, about the file size of the quant).

| Model | Our estimate before testing | Measured on the GPU box |
|---|---|---|
| Qwen3.5-4B Q4_K_M (2.74 GB file) | 110–130 tok/s | 106 tok/s at empty context (q8 KV cache) |
| Qwen3.5-9B Q4_K_M, all on GPU | 55–65 tok/s | not tested |
| Qwen3.6-35B-A3B UD-IQ4_XS, experts partly in system RAM | 15–25 tok/s | not tested |

On the one dense model we measured against it, the result landed just under the low end of the estimate. Use it to rule things
in or out, not to promise a number.

## What lowers the number in practice

- **Context depth.** The KV cache is read every token too. Nemotron-3.5-Bolt-E4B Q4_K_M (f16 KV) generated
  90 / 79 / 60 tok/s at 0 / 8K / 32K tokens of context.
- **Anything in system RAM.** System RAM is far slower than VRAM. Ours measured about 34 GB/s as found (DDR4 at
  the JEDEC 2133 default), and dual-channel DDR4 tops out around 40–50 GB/s. A small MoE (granite-3.1-1b-a400m)
  dropped from 294 to 93.7 tok/s when its experts were moved to the CPU. This is also why the NVIDIA
  "sysmem fallback" setting matters (see [02](02-windows-prep.md)).
- **The Windows desktop.** The card also drives the display. A signed-in desktop used 514 MiB of VRAM; with
  nobody signed in, 96 MiB. See [02](02-windows-prep.md) and [03](03-remote-access.md).

## What raises it

Speculative decoding. A small drafter model proposes tokens and the main model checks several at once, so
you get more than one token per weight read. With the DFlash drafter, Nemotron-Bolt went from about 85 to
about 135 tok/s on agent-style output, with identical results at temperature 0. That is the only reason the
headline number beats the formula. Details in `07-speculative-decoding.md`.

## What 8 GB rules out

The weights, KV cache, CUDA context, compute buffers and the Windows display all share the 8 GB.

| Rules out | Why |
|---|---|
| 8-bit quants of 4B-class models | The ggml-org Q8_0 of Nemotron-Bolt-E4B is ~8 GB on its own |
| 9B models with long context | A 9B Q4_K_M costs 32 KiB of KV per token; realistic ceiling is about 32K at f16 KV (estimate, not tested) |
| Large dense models | Anything that doesn't fit spills to system RAM at a fraction of the speed |
| Loading vision projectors | `--mmproj` costs about 0.9 GB; don't load it for text/tool work |
| Speculative decoding at 64K context | Model + drafter reached 7.6 GB at `-c 65536` and the server died on the first request. 32K fits at 7.1 GB |

Big MoE models (e.g. 35B-A3B) can run with experts in system RAM, but that path is bandwidth-capped by your
DDR4 and we did not measure it on this box.

## What Turing (sm_75) rules out

The 2080 SUPER is a TU104, compute capability 7.5 (sm_75).

| Rules out | Why |
|---|---|
| BF16 / FP8 / FP4 hardware paths | Turing has FP16 tensor cores only. Prefer plain K-quants (Q4_K_M, IQ4_XS, Q4_0) |
| Unsloth `_XL` quants | They carry BF16/F16 tensors. We avoided them; see [05](05-choosing-a-model.md) |
| vLLM | Not native on Windows. Under WSL, sm_75 is its minimum and it falls back to Triton attention; Gemma-4-style head_dim 512 fails on shared memory. No expert offload |
| SGLang, TensorRT-LLM, ExLlamaV3 | Linux-only, untested, or no Turing support statement |
| Built-in MTP speculative decoding for Qwen3.6 | Doesn't activate on sm_75 (llama.cpp #24670, "not planned") |
| Full-speed flash attention at long context | The FA Q-tile is capped at 32 on sm_75 (llama.cpp #28761): 3–14% slower prefill at 8–16K, up to 50% for head_dim 256 at long context (upstream figures, not measured here). FA still works and is still worth turning on |

One more honest line: Turing is the oldest architecture CUDA 13 supports. NVIDIA has announced no end-of-life
date for it, but this card will be dropped eventually. Our guess is CUDA 14; nothing is announced.

## Model tiers for this card

| Tier | Fits how | Examples we staged |
|---|---|---|
| S | Fully in VRAM, room for 32K+ context | Nemotron-3.5-Bolt-E4B, granite-4.0-h-tiny, Qwen3.5-4B |
| M | Fully in VRAM, tighter context | Qwen3.5-9B, granite-4.2-8B (not tested) |
| L | MoE with experts in system RAM | Qwen3.6-35B-A3B, gpt-oss-20b (not tested) |
| Floor | Tiny, fast, weak | Qwen3.5-2B |

Everything in this repo uses the S tier. Choosing within it is [05](05-choosing-a-model.md).
