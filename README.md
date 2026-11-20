# 8gb-agent: a local agent model on a used gaming PC

A 2019 gaming GPU with 8 GB of VRAM, serving a tool-calling model over your private network fast enough to
drive a real agent harness. No $10K rig. A careful setup and honest measurements.

## What you get

| | |
|---|---|
| **Hardware** | RTX 2080 SUPER 8 GB (Turing, 2019), Ryzen 9 3950X, 32 GB DDR4, Windows 11. Used-market gaming-PC tier |
| **Model** | Nemotron-3.5-Bolt-E4B, Q4_K_M, served by llama.cpp as an OpenAI-compatible endpoint |
| **Speed** | ~135 tok/s generation with DFlash speculative decoding, 32K context, 7.1 GB VRAM |
| **Quality checks** | 27/27 on our tool-call and knowledge evals, 9/9 needle-in-a-scan, 5/5 on a scripted agent loop |
| **Use it from** | any OpenAI-compatible agent harness on another machine |
| **Time** | a weekend. About half of it is hardware and Windows hurdles, not AI |

This is what we built on stream, written down so you can reproduce it. Different card? Same steps; your
numbers will differ.

## Start here

| Step | Read | Run | Done when |
|---|---|---|---|
| 0 | [00-expectations](docs/00-expectations.md) | | You know your expected tok/s range |
| 1 | [01-bios-and-memory](docs/01-bios-and-memory.md) | `hash-check.ps1` | 6 identical hash passes on a multi-GB file |
| 2 | [02-windows-prep](docs/02-windows-prep.md) | `box-config.ps1` | `nvidia-smi` clean, no sleep, exclusions set |
| 3 | [03-remote-access](docs/03-remote-access.md) | `setup-ssh.ps1`, `firewall-tailnet.ps1` | SSH works from another machine with the console signed out |
| 4 | [04-llama-cpp](docs/04-llama-cpp.md) | `get-llama.ps1` | `llama-server --version` over SSH |
| 5 | [05-choosing-a-model](docs/05-choosing-a-model.md) | `getmodels.ps1` | Every file "SHA OK" |
| 6 | [06-serving](docs/06-serving.md) | `serve-task.ps1` | `smoke.py` passes from another machine |
| 7 | [07-speculative-decoding](docs/07-speculative-decoding.md) | (flags in [profiles](config/profiles.md)) | `spec_bench.py` ~130+ tok/s |
| 8 | [08-measuring](docs/08-measuring.md) | `evals*.py` | Your numbers in a results table |
| 9 | [09-agent-harnesses](docs/09-agent-harnesses.md) | [config/harness](config/harness/) | A multi-turn tool-using session works |

Stuck? [10-troubleshooting](docs/10-troubleshooting.md) is every hurdle we hit, as symptom → cause → fix.

## The three hurdles that cost the most

1. **Silent RAM bit flips** at the kit's rated speed. Downloads finished full size and failed SHA; no crash,
   no log. Without checksums you'd run corrupted weights and blame the model.
2. **Turing ships as PTX-only** in the official llama.cpp zips: a ~50 s JIT on every cold start until you
   give CUDA a shared cache (48 s → 4 s).
3. **Agent harnesses assume big context.** Their system prompts and one noisy tool output can fill a 32K
   window on their own. Budget context like VRAM.

## Repo layout

```
docs/            the path, one doc per step, plus troubleshooting
scripts/windows/ run ON the GPU box (PowerShell 5.1, ASCII only)
scripts/client/  run from any machine that can reach the endpoint (Python 3, stdlib only; set LLM_URL)
config/          model list with SHA256s, the two serving profiles, harness snippets
results/         our measured tables
```

## Safety

- **llama-server has no authentication.** Bind it to a private-network address and scope the firewall
  (`firewall-tailnet.ps1`). Never `0.0.0.0` on a LAN, never port-forward it.

## License

Scripts and docs: MIT ([LICENSE](LICENSE)). No model weights are in this repo; the scripts download them from
Hugging Face under their own licenses (Nemotron-3.5-Bolt: OpenMDW-1.1). Check a model's license before you
use it.
