# 08 — Measuring: how to know a change helped

Every tuning claim in this repo came from one of five instruments. Use the same ones before and after any change,
and change one thing at a time.

## The instruments

| Tool | Runs on | Measures | Use it when |
|---|---|---|---|
| `scripts/windows/bench.ps1` | the GPU box | `llama-bench` prefill (pp) and generation (tg) tok/s, as markdown rows | Comparing builds, quants, KV types, batch sizes, context depths |
| `scripts/windows/kld.ps1` | the GPU box | KL divergence of a quant vs a reference quant | Choosing a quant |
| `scripts/client/evals.py` | any machine | 12 tool calls + 3 two-step chains + 12 knowledge items (27) | Any change that could affect output |
| `scripts/client/evals_hard.py` | any machine | Needle in a 3K / 11K / 27K-token scan dump (9) + a scripted 5-step agent loop (5) | Long-context and multi-turn behaviour |
| `scripts/client/evals_turns.py` | any machine | Per-turn prefill tokens and time over a 10-turn agent loop | Prompt-cache behaviour, context settings |
| `scripts/client/spec_bench.py` | any machine | Generation tok/s and draft acceptance on 4 agent-shaped outputs | Speculative decoding settings |

The client scripts are Python 3 stdlib only. They hit the server's OpenAI-compatible API with temperature 0 and
thinking off, and read speed from llama-server's own `timings` field, not wall clock.

```bash
python3 scripts/client/evals.py       <label> http://YOUR-BOX:8080 [--think]
python3 scripts/client/evals_hard.py  <label> http://YOUR-BOX:8080
python3 scripts/client/evals_turns.py <label> http://YOUR-BOX:8080 [--hosts N]
python3 scripts/client/spec_bench.py  <label> http://YOUR-BOX:8080 [--temp T]
```

Each prints per-item lines and a summary row with your label. Keep the summary rows; they are your results table.

## Speed: `bench.ps1`

`bench.ps1` takes a list file, one config per line: `label|model path|extra args`. It runs `llama-bench` with a
common set of args plus each line's extras, and appends markdown rows to `C:\llm\logs\bench.md`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\bench.ps1 -ListFile C:\llm\scripts\kv.txt
```

```
# kv.txt
f16|C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf|-ctk f16 -ctv f16
q8|C:\llm\models\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf|-ctk q8_0 -ctv q8_0
```

Useful `llama-bench` args:

| Arg | Meaning |
|---|---|
| `-p 512` / `-p 2048` | Prefill test length |
| `-n 128` | Generation test length |
| `-d 0,8192,32768` | Run at these context depths. Generation slows as context fills; d0 alone flatters every config |
| `-r 3` | Repetitions |
| `-ub 512,1024,2048` | Sweep micro-batch |

**Gotcha: repeating a flag makes combinations, not overrides.** `llama-bench` treats every value of a repeated
flag as another arm. If the common args say `-ctk q8_0` and a line says `-ctk f16`, you get both arms, not f16.
Check the `-Common` default before you put the same flag in a line, and keep each flag in one place.

**Make the bench match what you serve.** Our first screening pass used q8_0 KV in the common args. The served
config uses f16 KV, which turned out 17–27% faster on this card. Numbers measured on a config you don't serve
don't transfer.

**First load is not a measurement.** On Turing the first load JIT-compiles kernels (~50 s), and some new kernel
shapes JIT once more on first use. Discard the first run after installing a new build.

## Quality of a quant: `kld.ps1`

KL divergence compares each quant's next-token distribution against a reference, over the same text. Lower is
closer to the reference. It catches quality loss that a 27-item eval is too small to see.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\llm\scripts\kld.ps1 `
  -Ref C:\llm\models\<model>-Q6_K.gguf `
  -Quants "C:\llm\models\<model>-Q5_K_M.gguf,C:\llm\models\<model>-Q4_K_M.gguf" -Chunks 16
```

Our setup: Q6_K as the reference, wikitext-2 test, 16 chunks × 2048 tokens. Read three numbers:

| Metric | What it tells you |
|---|---|
| Mean KLD | Average drift from the reference |
| 99% KLD | How bad the worst 1% of tokens get |
| Same top p | How often the quant picks the same top token as the reference |

Caveat: if two files come from different checkpoints (NVIDIA's "4GB" Nemotron build is described as further
post-trained), KLD measures the checkpoint difference too, not just quantization loss. Run the task evals as
well. Results: [results/quant-ab.md](../results/quant-ab.md).

## Behaviour: the evals

- **`evals.py`** is the broad pass. Tool-call items score parse success, the right tool, and argument fidelity.
  Knowledge items check a fact.
- **`evals_hard.py`** is the discriminator. The needle test hides one fact in a 3K, 11K and 27K-token scan dump,
  which is what real tool output looks like. The scripted loop checks that the model makes the expected call at
  each of 5 steps. In our shoot-out it separated models the basic evals didn't (see
  [results/s-tier.md](../results/s-tier.md)).
- **`evals_turns.py`** sends a large first turn, then 9 short follow-ups, and prints prefill tokens and time per
  turn. If turns 2–10 prefill only a few dozen tokens, the prompt cache is working. If every turn re-processes
  the whole prompt, something (a model architecture, a flag, a harness that rewrites history) is breaking it.

Run with temperature 0 and thinking off unless you're testing thinking. Same settings, same label scheme, every
time.

## Speculation: `spec_bench.py`

Four prompts shaped like agent output: a prose finding, a scan converted to a markdown table, a prose checklist,
a scan converted to JSON. It prints tok/s per prompt, overall generation tok/s, and the draft acceptance rate.
Report per-prompt numbers, not just the overall: draft length helps structured output and can hurt prose (see
[07](07-speculative-decoding.md)).

## How to decide a change helped

1. **Record the toolchain.** Driver version and llama.cpp build, together, every time. Re-run `bench.ps1` after
   changing either.
2. **One change per comparison.** Same model file, same prompts, same context depth.
3. **Speed at depth, not just d0.** Check 8K and 32K.
4. **Quality didn't move.** For anything claimed lossless (speculative decoding, a flag), the evals should match
   item for item at temp 0. For a quant change, look at KLD and the evals.
5. **VRAM still fits at the context you serve,** with an honest OOM (sysmem fallback off) rather than a silent
   spill into system RAM.
6. **Re-run after hardware fixes.** We found silent RAM bit flips mid-project (see
   [01](01-bios-and-memory.md)). After fixing them we re-verified every model file's SHA and re-ran the deciding
   evals. They reproduced item for item, so the ranking stood. If we hadn't checked, we couldn't have said that.

## What we did not test

- **Vulkan build A/B:** not tested. All numbers are the CUDA 12.4 build.
- **FA off with f16 KV:** not measured.
- **A second GPU:** every number here is from one RTX 2080 SUPER.
