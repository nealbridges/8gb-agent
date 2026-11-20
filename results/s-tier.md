# S-tier shoot-out: three small models that fit entirely in 8 GB

RTX 2080 SUPER 8 GB, llama.cpp CUDA 12.4 build. All three models Q4_K_M, fully in VRAM.

Instruments (`scripts/client/`): `evals.py` (12 tool calls + 3 two-step chains + 12 knowledge items),
`evals_hard.py` (needle in a 3K / 11K / 27K-token nmap dump, plus a scripted 5-step agent loop). Temperature 0,
thinking off. Speed from `llama-bench` with q8_0 KV (the screening config; the served config later moved to f16
KV, see [kv-and-batch.md](kv-and-batch.md)).

| Model | evals (27) | Needle (9) | Loop (5) | tg tok/s at d0 / 8K / 32K (q8 KV) | pp512 at d0 |
|---|---|---|---|---|---|
| **Nemotron-3.5-Bolt-E4B Q4_K_M** | **27** | **9** | **5** | 85 / 71 / 48 | 4,375 |
| granite-4.0-h-tiny Q4_K_M | 24 | 8 | 1 (skipped the probe) | 154 / 159 / 143 | 5,020 |
| Qwen3.5-4B Q4_K_M | 20 | 9 | 3* | 106 / 101 / 81 | 3,279 |

\*Qwen's loop miss was a scan of AJP port 8009 to confirm Ghostcat. That is arguably better tradecraft; the
scripted loop is rigid. With thinking on, Qwen took 41 s per knowledge item and exceeded the 4K-token budget on 7
of 12, so thinking mode is not viable for the loop.

**Winner: Nemotron-3.5-Bolt-E4B (bartowski Q4_K_M).** It is the slowest of the three at long context, and the
only one with a perfect score. Tuning (f16 KV, then speculative decoding) more than closed the speed gap: see
[dflash.md](dflash.md).

## Stability check

Midway through, we found silent RAM bit flips on the box (see `docs/01-bios-and-memory.md`). After fixing the
memory and re-verifying every model file's SHA, the S-tier evals reproduced item for item. The ranking stands.

## Notes on the models

- **Nemotron-3.5-Bolt-E4B**: license OpenMDW-1.1. Gemma 4 architecture, tuned for multi-turn tool use. We use the
  bartowski Q4_K_M because Unsloth publishes only `_XL` quants (which carry BF16 tensors, unsupported on Turing)
  and ggml-org publishes only an 8 GB Q8_0.
- **granite-4.0-h-tiny**: 7B total / 1B active MoE + Mamba2, Apache-2.0. Fastest by far; lost on the loop.
- **Qwen3.5-4B**: Apache-2.0.
