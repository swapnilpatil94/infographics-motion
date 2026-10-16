# Script → Audio (Chatterbox) tab

Adds an audio-only utility to Kathaaya Studio. It reuses `engine.shorts.voice.synthesize()`, the same narration adapter called by production. It does not introduce another TTS implementation or trigger a film render.

## Run locally

```bash
git checkout feat/script-to-chatterbox-audio
.venv/bin/python studio.py --ui
```

Open http://127.0.0.1:8765 and select **Script → Audio**.

Uses the same production settings: `MYTHIC_STUDIO_DIR`, `TTS_PYTHON`, and `TTS_REFERENCE_AUDIO`. The existing adapter caches synthesis, runs Chatterbox multilingual Hindi and aligns words with WhisperX. The new API rejects the flagged macOS `say` fallback, so placeholder speech is never mislabeled as Chatterbox.

Output: `output/audio/<job-id>/narration.wav` (PCM 16-bit) and `narration.segments.json` (segment and word timestamps). The UI previews the WAV and offers both downloads. Generated files stay under git-ignored `output/`.

Paste Hindi in Devanagari, one beat per line. Blank lines/headings are ignored; mostly Latin English is rejected, so write acronyms phonetically (`OTP` → `ओटीपी`). Maximum request size: 30,000 characters.

Run mocked API tests with `.venv/bin/python -m pytest tests/test_script_audio.py -q`. The actual Chatterbox stack still needs a local smoke test because model files, the sibling project and reference voice are machine-local.


## Delivery cues

In Directed mode, place one cue on its own line. It remains active until the next cue; `[DEFAULT]` resets to the base delivery. Supported cues: `[HOOK]`, `[CURIOUS]`, `[SUSPENSE]`, `[REVEAL]`, `[EXPLAIN]`, `[URGENT]`, `[CALM]`, `[EMPHASIS]`, `[CONFIDENT]`, `[WARM]`, `[CONCERNED]`, `[SHOCKED]`, `[REFLECTIVE]`, `[PLAYFUL]`, and `[DEFAULT]`.

These are application-level delivery profiles that map to supported Chatterbox generation parameters; they are **not** native emotion tokens. The dedicated Hindi path uses the multilingual tokenizer, so do not insert Turbo-only non-speech tags such as `[laugh]`, `[sigh]`, or `[gasp]` into the script. Those are unsupported for multilingual models and can be spoken literally. The UI strips recognized cue lines before synthesis. Prefer a handful of longer cue blocks over changing delivery every sentence.

## Voice Setup

Open **Voice Setup** in Studio to upload audio or record through the browser microphone. FFmpeg removes low-frequency rumble, applies conservative noise reduction, filters the speech band and normalizes loudness. The cleaned output is mono 24 kHz PCM WAV under `output/voice/references/<id>/cleaned.wav`; the original file is retained for comparison. Preview each cleaned profile and click **Use for narration** to activate it. The active profile is used by the production Chatterbox adapter and changes the synthesis cache key. The default `TTS_REFERENCE_AUDIO` remains in effect until a profile is activated. Audio stays local and git-ignored; only clone voices you own or have permission to use.
