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
