# Quant A/B: Nemotron-3.5-Bolt-E4B

RTX 2080 SUPER 8 GB, llama.cpp CUDA 12.4 build, f16 KV, `-ub 1024`.

KLD is against Q6_K on wikitext-2 test, 16 chunks × 2048 tokens (`scripts/windows/kld.ps1`).

| Quant | GiB | tg d0 / 8K / 32K | pp2048 d0 | Mean KLD | 99% KLD | Same top |
|---|---|---|---|---|---|---|
| Q6_K (ref) | 6.0 | 75 / 67 / 53 | 4,850 | — | — | — |
| Q5_K_M | 5.56 | 80 / 74 / 56 | 4,910 | **0.038** | 0.47 | 92.5% |
| **Q4_K_M (bartowski)** | 4.79 | 90 / 79 / 60 | 5,017 | **0.098** | 1.09 | 88.4% |
| IQ4_XS | — | 89 / 80 / 61 | **5,437** | 0.164 | 1.89 | 84.9% |
| Q4_K_M (NVIDIA "4GB" build) | 5.74 | 91 / 76 / 59 | 4,982 | 0.173* | 1.88 | 84.7% |
| Q4_0 | — | 90 / 78 / 60 | 5,188 | 0.506 | 4.37 | 74.0% |

"—" in the GiB column: not recorded.

\*NVIDIA's "4GB" build is described as further post-trained, so it is likely a different checkpoint from the BF16
that bartowski quantized. Its KLD against the bartowski Q6_K partly measures that difference, not just quant
loss. Its task evals: 26/27 (Heartbleed answered as "memory leak"), needle 9/9, loop 5/5, 85 tok/s on long
generations.

## Pick: bartowski Q4_K_M

- Best 4-bit KLD at full 4-bit speed.
- Q5_K_M halves KLD for −11% generation at d0 and −7% at 32K. A reasonable choice if you value fidelity over
  speed.
- IQ4_XS has the fastest prefill but worse KLD.
- Q4_0 is no faster than Q4_K_M here and has 5× the KLD.

## File integrity

During this round, two files on disk (the Q5_K_M and another model's file) turned out corrupt from RAM bit flips.
Both were caught by re-checking against the Hugging Face SHA and re-pulled or dropped before these numbers were
taken. Verify every download.
