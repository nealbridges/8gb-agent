# 07 — Speculative decoding (DFlash)

Goal: generation from ~85 tok/s to ~135 tok/s with no change in output quality.

Done when `python3 scripts/client/spec_bench.py dflash-n3 http://YOUR-BOX:8080` reports ~130+ tok/s overall.

## What it is

A small drafter model guesses the next few tokens; the main model checks them in one pass and keeps the ones it
agrees with. At temperature 0 the output is the same as without speculation, just faster. We use NVIDIA's
DFlash drafter for Nemotron-3.5-Bolt-E4B (a BF16 GGUF) with llama.cpp's `--spec-type draft-dflash`.

The drafter works with the bartowski Q4_K_M target, not just NVIDIA's own build: 132 tok/s at n7 and 135 at n3.

## Flags

```
--spec-draft-model C:\llm\models\Nemotron-3.5-Bolt-E4B-DFlash-BF16.gguf
--spec-type draft-dflash
--spec-draft-n-max 3
--spec-draft-ngl 999
-c 32768
```

## Result

| | Generation tok/s | VRAM | Quality |
|---|---|---|---|
| No speculation | 85 | 4.7 GB (at 64K) | 27/27 evals, 9/9 needle, 5/5 loop |
| DFlash n3 | 136 (`spec_bench.py`, 4 prompts) | 7.1 GB (at 32K) | Identical eval and needle results, temp 0 |

That is +58% generation. Full table: [results/dflash.md](../results/dflash.md).

## Hurdle: it OOMs at 64K context

**Symptom.** With `-c 65536`, the server starts, then dies on the first request. It looked like the whole box
hung: SSH timed out and ping failed.

**Cause.** Target plus drafter reach 7.6 GB at 64K. The first request needs a cuBLAS workspace allocation
(`cudaMalloc`), which fails, and llama-server exits. The box itself was fine: ping fails because Windows blocks it
by default, and the SSH timeouts were an unrelated network hiccup. Last boot time was unchanged and there were no
crash events.

**Fix.** `-c 32768`. Stable at 7.1 GB.

**How we proved it.** The `.err` log shows the cudaMalloc failure and the `EXIT` line; the box's last boot time
didn't change. Check uptime and the server log before concluding the machine hung.

If you need 64K, use the ingest profile (no drafter). See [config/profiles.md](../config/profiles.md).

## Hurdle: draft length

**Symptom.** NVIDIA's recipe uses a draft length of 7. Raising it to 10 or 15 changed nothing, and n7 was slower
than no speculation on some prose.

**Cause.** The drafter's block size is 8, so any `n-max` ≥ 8 behaves like 7. And acceptance drops as drafts get
longer: long drafts pay off only when the output is predictable (copying a scan into a table or JSON), and cost
time on free prose.

| Config | Overall | Prose finding | Scan → table | Prose checklist | Scan → JSON | Acceptance |
|---|---|---|---|---|---|---|
| no speculation | 85 | 87 | 83 | 87 | 85 | — |
| n7 (NVIDIA recipe) | 129 | 91 | 226 | 78 | 229 | 46% |
| n5 | 135 | 101 | 206 | 87 | 213 | 53% |
| **n3** | **136** | **114** | 171 | **101** | 177 | 67% |

**Fix.** `--spec-draft-n-max 3`. Prose +16–30%, structured output about 2×, no regressions against no
speculation. n7 only wins on pure transcription.

Vendor sampling (temp 1.0, top_p 0.95) keeps it at 133 tok/s, so it is not only a temp-0 result.

## Hurdle: prefill is slower

**Symptom.** The first turn of a session with a large prompt takes longer than without DFlash.

**Cause.** The drafter also processes the prompt. Cold prefill of 24K tokens: 14.2 s with DFlash vs 8.5 s
without, about 1.7× slower.

**Why it usually doesn't matter.** Agent loops reuse the prompt cache, so later turns only prefill the new tokens.
Cached turns: 0.44 s with DFlash vs 0.58 s without.

**When it does matter.** Workloads that send a big fresh dump every turn. For those, run the **ingest** profile:
no drafter, 64K context, prefill about 2.9K tok/s at 24K, generation ~85–90 tok/s.

## Checklist

1. Server up on the agent profile ([06](06-serving.md)).
2. `spec_bench.py` reports overall ~130+ tok/s and an acceptance rate (if it prints no acceptance, speculation
   isn't on).
3. Re-run `evals.py` and `evals_hard.py` with it on. Results should match the no-speculation run item for item at
   temp 0. See [08](08-measuring.md).
