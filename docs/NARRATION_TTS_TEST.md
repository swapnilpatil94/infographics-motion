# Narration pacing + VibeVoice test (mythic-video-studio tools)

User feedback: narration too slow. Target: "neuromarketing" rhythm = short punchy sentences, hook first, no dead air, faster speaking rate.

## Pacing (engine/skeleton/pace.py)
Chatterbox natural rate on the 109-word script: **2.34 words/s** (46.5 s). Pipeline: per-beat chunks -> every in-beat gap capped at 0.14 s -> 0.10 s between beats ->
pitch-preserving `atempo` 1.16 -> **2.97 words/s** (36.7 s, +27 % faster). Word times are remapped exactly, so captions and cuts stay in sync. `--tempo` changes it.

## VibeVoice Hindi 7B (`~/mythic-video-studio/tools/vibevoice_tts.py`), run on this machine
It did NOT run out of the box. Two fixes were needed, both isolated from the shared environment:
1. `vibevoice-venv` is broken (`libtorch_cpu.dylib` missing) -> ran with the pyenv 3.12 interpreter (torch 2.6, MPS) + `PYTHONPATH=vibevoice-repo`.
2. The repo needs `transformers==4.51.3` (4.57 raises `_prepare_cache_for_generation() takes 6 positional arguments but 7 were given`) -> installed into `.vendor_tf/` (git-ignored), plus the vendored scipy in `.vendor_py/`.
Then it generated Hindi on MPS (7B) - one 109-word pass: 41 s, ~159 wpm, ~3 min wall.

Measured intelligibility (Whisper large-v3 transcript vs. script; similarity 0-1, same metric for both):

| | Chatterbox (per beat) | VibeVoice, one long pass | VibeVoice, 4 short batches (raw) | VibeVoice, batches after dead-air trimming |
|---|---|---|---|---|
| beats 1-4 | **0.94** | 0.52 (whole script) | 0.25 | 0.49 |
| beats 5-8 | **0.95** | | 0.80 | 0.68 |
| beats 9-11 | **0.89** | | 0.83 | 0.70 |
| beats 12-13 | **0.90** | | 0.94 | 0.44 |

Findings: VibeVoice inserts long dead-air stretches (10.8 s of 41 s in the long pass), degrades in long-form (the second half of the long pass was unintelligible; word alignment failed on the last beat),
is inconsistent batch to batch (0.25 - 0.94), and is ~10x slower to generate than Chatterbox. **Chatterbox is used for the film**; `--tts vibevoice` runs the batch path and is kept as an option.
Not measured: subjective voice quality (no listening test was possible here).
