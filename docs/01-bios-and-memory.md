# 01. BIOS and memory

**Done when:** a multi-GB file hashes clean 6 times in a row and its full SHA-256 matches the published one.

Tested on 2026-11-12. Board: ASUS ROG Crosshair VIII Hero (WI-FI), X570. RAM: 4 × 8 GB G.Skill
F4-3600C18-8GTRS (DDR4-3600, single-rank).

This is the least "AI" part of the project and it cost the most time. Do it first, because a bad memory
setting doesn't crash anything. It just quietly corrupts every model you download.

## Why touch the BIOS at all

The used board came with BIOS 1302 (January 2020), the launch-era AGESA. That AGESA has the known fTPM stutter
bug, and Windows 11 needs fTPM on. We flashed to **5601 (AGESA ComboV2 PI 1.2.0.12)**.

The memory was running at the JEDEC default of DDR4-2133 (DOCP off). That leaves bandwidth on the table, which
matters if you ever run a model with layers in system RAM ([00](00-expectations.md)).

## Hurdle 1: the wrong BIOS file for the board variant

- **Symptom:** EZ Flash (in the BIOS) and USB BIOS FlashBack both refused the update file. Neither said why.
  About an hour gone.
- **Cause:** "Crosshair VIII Hero" and "Crosshair VIII Hero (WI-FI)" are different boards with different BIOS
  files: `C8H.CAP` vs `C8HW.CAP`. We had the non-Wi-Fi file.
- **Fix:** read the exact SKU off the board or the box, not the family name, and download the file for that
  SKU. `C8HW.CAP` flashed.
- **How we proved it:** the BIOS reported 5601 after the flash.

Lesson for any board: if a flash tool rejects a file silently, check the SKU before anything else.

## Turn on DOCP / XMP, then prove it

DOCP (ASUS's name for XMP on AMD) loads the kit's rated speed and timings. We set the kit's profile:
DDR4-3600 18-22-22-42 with FCLK 1800 (1:1). It booted clean.

It was not stable. Read on.

## Hurdle 2: silent RAM bit flips at the kit's rated speed

This is the most important section in the repo.

- **Symptom:** three model downloads finished at full size but failed their SHA-256 check. Re-hashing one
  of those files twice on the box gave **different chunk hashes each pass** (9 of 72 chunks differed between
  passes). No crash, no blue screen, nothing in the event log.
- **Cause:** memory errors. We compared one bad 64 MB chunk byte by byte against a known-good copy of the same
  file downloaded on another machine: **one byte differed, by one bit.** That pattern is RAM. A network problem
  would be caught by TLS, and a failing NVMe drive fails whole blocks or reports errors. Consumer DDR4 has no ECC,
  so Windows logs no WHEA events. The likely culprit is the memory controller / Infinity Fabric at 3600 / FCLK
  1800 with four single-rank DIMMs. Voltage was fine (see hurdle 3).
- **Fix:** keep DOCP (its timings), but set Memory Frequency to **DDR4-3200**. FCLK follows to 1600, still 1:1.
  If that still fails, the fallback is DOCP off.
- **How we proved it:** copied a known-good 4.8 GB file to the box and chunk-hashed it 6 times, about 30 GB of
  reads. All 6 passes were identical and the full SHA-256 matched. Then we re-verified **every** model file on
  disk against its Hugging Face SHA-256: two (a Q5_K_M and a 2B model) were corrupt and were re-downloaded or
  dropped. Finally we re-ran the model evals on the stable RAM; they reproduced item for item.

Why this matters: without SHA checks we would have run corrupted weights and blamed the model. A flipped bit in
a weight file doesn't stop the model from loading. It just makes it a little worse, in a way no one would ever
trace back to RAM.

### The hash test

`scripts/windows/hash-check.ps1` re-reads a large file N times in chunks and reports any chunk whose hash
changes between passes. Run it on a multi-GB file whose SHA-256 you already know (a model GGUF from Hugging Face
works; its SHA-256 is on the file page).

Pass criteria:

| Check | Pass |
|---|---|
| Chunk hashes across 6 passes | Identical on every pass |
| Full-file SHA-256 | Matches the published value |

A single differing chunk is a fail. Lower the memory speed and run it again. Run it after any BIOS or memory
change, and before you trust any download.

## Hurdle 3: don't trust software voltage readings

- **Symptom:** while chasing the bit flips, WMI on Windows reported DRAM at 1.20 V, which would mean DOCP's
  voltage wasn't applied.
- **Cause:** the WMI value is wrong on this board.
- **Fix:** check voltages in the BIOS hardware monitor, not from Windows.
- **How we proved it:** the BIOS showed DRAM at 1.35 V set / 1.344 V actual, and SoC on Auto at 1.072–1.080 V.
  Voltage was not the problem; frequency was.

## Checklist

- [ ] Exact board SKU read off the board or box
- [ ] BIOS flashed with the file for that SKU
- [ ] DOCP/XMP on; note the speed and FCLK you chose
- [ ] Voltages checked in the BIOS, not in Windows
- [ ] `hash-check.ps1`: 6 clean passes on a multi-GB file, full SHA-256 matches
