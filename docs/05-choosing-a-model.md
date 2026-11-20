# 05. Choosing a model

**Done when:** every file you downloaded reports "SHA OK".

Tested on 2026-11-12. All numbers on the GPU box with llama.cpp b12318 (CUDA 12.4), temperature 0, thinking off.

## The short answer

**NVIDIA Nemotron-3.5-Bolt-E4B, bartowski's Q4_K_M** (`NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf`, 4.79 GiB),
plus NVIDIA's DFlash drafter (`Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf`) for speculative decoding. Both are
listed with their SHA-256 in `config/models.txt`.

The rest of this page is how we got there, so you can redo the choice when better models ship.

## Tiers for 8 GB

| Tier | What fits | Candidates we considered |
|---|---|---|
| **S**: all in VRAM, 32K+ context | ~4B dense, or small MoE (~1B active) | Nemotron-3.5-Bolt-E4B, granite-4.0-h-tiny (7B total / 1B active), Qwen3.5-4B |
| M: all in VRAM, tighter context | 8–9B dense at 4 bits | Qwen3.5-9B, granite-4.2-8B (not tested) |
| L: MoE with experts in system RAM | 20–35B MoE | Qwen3.6-35B-A3B, gpt-oss-20b (not tested) |
| Floor | ~2B | Qwen3.5-2B |

We tested only the S tier end to end. It's the tier where the whole model and a useful context stay in VRAM.

We also dropped a reasoning-heavy 9B early: it thought for 3–16K tokens per step, which at roughly 55 tok/s is
minutes per step and eats the context this card can afford. For agent loops on 8 GB, long thinking is the wrong
trade.

## The S-tier shoot-out

Three models, same instruments (all in `scripts/client/`):

- `evals.py`: 12 tool calls, 3 two-step chains, 12 security-knowledge questions (27 items).
- `evals_hard.py`: find a needle in a 3K / 11K / 27K-token scan dump (9 items), plus a scripted 5-step agent
  loop.

| Model (Q4_K_M) | evals (27) | Needle (9) | Loop (5) | Gen tok/s at 0 / 8K / 32K context* | Prefill tok/s (pp512) |
|---|---|---|---|---|---|
| **Nemotron-3.5-Bolt-E4B** | **27** | **9** | **5** | 85 / 71 / 48 | 4,375 |
| granite-4.0-h-tiny | 24 | 8 | 1 (skipped a probe step) | 154 / 159 / 143 | 5,020 |
| Qwen3.5-4B | 20 | 9 | 3 | 106 / 101 / 81 | 3,279 |

\*Measured with a q8_0 KV cache. Nemotron is faster with f16 KV (hurdle 18): 90 / 79 / 60.

How to read it:

- **granite-4.0-h-tiny is the fastest by far** and holds its speed at 32K, but it was weakest at multi-step
  work: 1 of 5 on the scripted loop.
- **Qwen3.5-4B's** loop misses included one arguably smarter move than the script expected (an extra
  confirmation scan). With thinking on it took 41 s per knowledge item and ran past a 4K-token budget on 7 of 12,
  so it's not viable for agent loops with thinking.
- **Nemotron-Bolt** was the only perfect score. It's slower raw, but speculative decoding (`07`) more than
  closes the gap.

After fixing the RAM problem ([01](01-bios-and-memory.md)) we re-ran these evals: they reproduced item for item.

## Check the license before you download

| Model | License |
|---|---|
| Nemotron-3.5-Bolt-E4B | OpenMDW-1.1 |
| Qwen3.5 family, granite family | Apache-2.0 |
| LFM2.5-8B-A1B | LFM 1.0 (custom); read its commercial terms |
| xLAM-2 | CC-BY-NC; excluded |

Read the license on the model card yourself. This repo ships no weights; the scripts download them from
Hugging Face.

## Hurdle 17: no BF16 on Turing, so pick the quant source carefully

- **Symptom:** none we chose to find out. The risk is quants that carry BF16 tensors on a card with no BF16
  hardware.
- **Cause:** Unsloth's Nemotron-Bolt uploads were only `_XL` quants, which keep some tensors in BF16/F16. The
  ggml-org upload was only a ~8 GB Q8_0, which doesn't fit.
- **Fix:** use **bartowski's Q4_K_M**, built from plain K-quant tensors.
- **How we proved it:** bartowski's Q4_K_M ran at the speeds above with flash attention on (despite the model's
  head_dim of 512) and no errors. We did not benchmark an `_XL` quant. Note that the DFlash drafter is itself a
  BF16 GGUF and runs fine in mainline llama.cpp, so treat "avoid `_XL`" as a cautious default, not a measured
  failure.

## Quant choice: measure quality loss with KLD

Smaller quants are faster but lose quality. Rather than guess, measure **KL divergence** (KLD): how far the quant's
next-token probabilities drift from a higher-precision reference. `scripts/windows/kld.ps1` does this with
llama.cpp's perplexity tool.

Our setup: reference = Q6_K, text = wikitext-2 test, 16 chunks of 2,048 tokens, f16 KV, `-ub 1024`.

| Quant | Size (GiB) | Gen tok/s 0 / 8K / 32K | Prefill (pp2048) | Mean KLD | 99th pct KLD | Same top token |
|---|---|---|---|---|---|---|
| Q6_K (reference) | 6.0 | 75 / 67 / 53 | 4,850 | — | — | — |
| Q5_K_M | 5.56 | 80 / 74 / 56 | 4,910 | **0.038** | 0.47 | 92.5% |
| **Q4_K_M (bartowski)** | 4.79 | 90 / 79 / 60 | 5,017 | **0.098** | 1.09 | 88.4% |
| IQ4_XS | not recorded | 89 / 80 / 61 | **5,437** | 0.164 | 1.89 | 84.9% |
| Q4_K_M (NVIDIA "4GB" build) | 5.74 | 91 / 76 / 59 | 4,982 | 0.173* | 1.88 | 84.7% |
| Q4_0 | not recorded | 90 / 78 / 60 | 5,188 | 0.506 | 4.37 | 74.0% |

\*NVIDIA describes its "4GB" build as further post-trained, so it's probably a different checkpoint. Its KLD
against bartowski's Q6_K partly measures that difference, not just quantization loss. On the task evals it
scored 26/27, 9/9 needle, 5/5 loop.

Reading it:

- **All the 4-bit quants generate at about the same speed.** Decode is bandwidth-bound and they're similar sizes.
  So pick the 4-bit quant with the lowest KLD: bartowski's Q4_K_M.
- **Q4_0 is a trap here:** same speed, five times the KLD.
- **Q5_K_M** halves the KLD for 11% less generation speed at empty context (7% at 32K). We did not test it with
  the drafter loaded.

## Hurdle 18: KV cache quantization isn't free on this card

- **Symptom:** a q8_0 KV cache, usually recommended to save VRAM, made generation slower.
- **Cause:** measured, not root-caused. On this card and model the quantized-KV attention path is slower than
  the bandwidth it saves.
- **Fix:** keep the default f16 KV cache for Nemotron-Bolt. At 32K context it uses 4.15 GB of VRAM with f16 KV
  (4.73 GB at 64K), so there's room.
- **How we proved it:** f16/f16 vs q8/q8 on Nemotron-Bolt Q4_K_M: generation +17% at 8K (79.6 vs 68.2 tok/s) and
  +27% at 32K (60.2 vs 47.5). Prefill gained about 2%.

Two related traps if you do quantize KV:

- **Use matching K and V types** (`-ctk q8_0 -ctv q8_0`). Mixed types (e.g. K q8_0 / V q4_0) can silently fall
  back to F16 or the CPU unless llama.cpp was built with `GGML_CUDA_FA_QUANTS`.
- **Smoke-test the KV type for each model.** A q8_0 V cache crashed one model family (`granitemoe`); K q8_0 /
  V f16 worked. Qwen and `granitehybrid` were fine with q8/q8. Flash attention off with a q8 V cache fails at
  context creation.

## Verify every download

Hurdle 2 in [01](01-bios-and-memory.md) is why this isn't optional. Three of our downloads came back full size
with the wrong SHA-256, and later two files already on disk turned out corrupt.

`scripts/windows/getmodels.ps1` reads a list of `repo|file|sha256` lines (`config/models.txt`), downloads each
file from Hugging Face into `C:\llm\models`, hashes it, retries up to 3 times on a mismatch, and skips files
already present with the right hash. It logs one line per file:

```
SHA OK   NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf ...
SHA BAD  ...
```

To add a model, take the SHA-256 from the file's page on Hugging Face and add a line to the list.

**Hugging Face token:** most model repos are public. If you need a token, use a **read-only, fine-grained**
token, store it only on the GPU box, and never paste it into logs or scripts.

**Re-verify after any memory change.** A hash that was right yesterday proves nothing about a file read through
unstable RAM today. Re-run `getmodels.ps1` (it re-hashes what's on disk) or `hash-check.ps1`.

## Things we skipped

- **Vision projectors** (`--mmproj`): about 0.9 GB for features an agent server doesn't use.
- **M and L tiers** (9B dense, 35B MoE offload): staged, not tested. No numbers for them here.
