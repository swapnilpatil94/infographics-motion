# Technical Data Cinema

A local-first, story-specific mode for animation-led technical explainers. It reuses the repository's existing Chatterbox Studio narration adapter and does not add a second TTS implementation.

## Workflow
1. Approve the story brief and spoken narration script.
2. Generate one self-contained HTML scene with one local Ollama coding model.
3. Preview and revise the story-specific animation.
4. Export silently, add an approved WAV, or generate narration through the existing Chatterbox Studio API.
5. Inspect the final MP4 and audio before publishing.

This is **not a fixed scene template**. Visual language, motion, pacing and composition should change according to the causal story being explained.

## Requirements
- macOS on Apple Silicon
- Node.js 22+ and npm
- Ollama with a downloaded coding model
- FFmpeg available as `ffmpeg` and `ffprobe`
- Existing Chatterbox environment and reference WAV for voice generation
- Playwright Chromium; Chatterbox dependencies and the dedicated Hindi checkpoint/reference when generating voice

## Setup
From repository root:
```bash
cd modes/technical-data-cinema
npm install
npx playwright install chromium
npm run doctor
```

## UI workflow

Start the local production UI:
```bash
npm run ui
```
Open `http://127.0.0.1:4177`. Paste or edit the story brief and narration, select an installed Ollama model, then choose Chatterbox narration, an existing WAV, or silent export. The UI runs generation first, waits for the Ollama wrapper to unload the model, and only then starts narration/rendering. It prevents concurrent production jobs and shows live logs plus output links. For Chatterbox voice, the UI checks for an existing Studio and starts it with `CHATTERBOX_MODEL_VARIANT=dedicated_hindi` if needed. If your Chatterbox dependencies use a custom Python environment, set `STUDIO_PYTHON` to that interpreter path before `npm run ui`. The UI server binds to localhost by default and should not be exposed to your network.

## Generate a scene
```bash
npm run generate -- --story examples/viral-traffic.md --model qwen3-coder:30b
```
The default context is 8192 tokens for the 24 GB Mac. Generation runs one Ollama model, then unloads it before exiting. Use `--model qwen2.5-coder:7b` for quick revisions. Models are never pulled automatically.

Generated scenes must expose `window.renderAt(seconds)` and `window.getDuration()`, and must hide preview UI for `?render=1`. Invalid output is rejected before writing the HTML. Each generation writes a new file and never overwrites prior output.

## Export options

**Generate narration using the exact existing Chatterbox Studio adapter and then export video + voice:**

First start the Studio with the already configured dedicated Hindi branch settings (run from repository root):
```bash
CHATTERBOX_MODEL_VARIANT=dedicated_hindi python3 studio.py --ui
```
Make sure the Hindi checkpoint and voice reference are installed as documented in the repository's Chatterbox setup. If Studio is already running, restart it with the environment above if you need to change its model variant. Do not run Ollama generation and Chatterbox generation concurrently.

Then, from this folder:
```bash
npm run export -- --html output/<story>/index.html --out output/<story>/final.mp4 --voice-script examples/viral-traffic-narration.md
```
Use a narration-only file with spoken lines (no visual directions); you can use `--style storytelling|conversational|dramatic`, `--pronunciation hindi_mixed|original`, `--performance directed|uniform`, and `--expression-intensity 0..100`. Defaults match the current Studio audio tab: storytelling, Hindi-first pronunciation, directed performance, intensity 65. Existing performance cues such as `[HOOK]`, `[SUSPENSE]`, `[REVEAL]`, and `[EXPLAIN]` are preserved.

**Use an already approved WAV:**
```bash
npm run export -- --html output/<story>/index.html --out output/<story>/final.mp4 --audio /absolute/path/to/narration.wav
```

**Export silently:**
```bash
npm run export -- --html output/<story>/index.html --out output/<story>/silent.mp4
```

The renderer tests deterministic seeking, rejects browser errors and external requests, samples the narrated ending to reject a pixel-identical frozen frame lasting more than 2.5 seconds, and encodes 1080×1920 H.264/AAC. The UI makes one targeted scene-repair attempt after a frozen-ending failure while preserving the narration WAV; it does not rerun Chatterbox for this visual-only repair. When narration is longer than the scene, the scene timeline is time-scaled to span the narration rather than freezing on the final frame. A manually supplied `--duration` shorter than the voice is rejected to avoid cutting off speech. Rendered frames can use several GB; ensure enough disk space before full exports.

## Memory policy
- Heavy models run sequentially: Ollama generation completes and unloads its selected model before narration is generated.
- Start at 8192 context tokens. Do not keep the 30B coding model loaded while using Chatterbox.
- Use `ollama ps` and Activity Monitor to verify actual memory use.
- The export script calls the existing Studio endpoint; it does not start another TTS runtime or alter your tuned presets.

## Creative quality
- Every particle/object has a semantic role; motion demonstrates cause and effect.
- Graphs build progressively; sourced and illustrative values are clearly distinguished.
- Visual technique changes when the explanatory job changes; avoid repeating one layout.
- No CDN, remote assets, external fonts, or network dependency in generated HTML.
- Preview the entire scene and inspect the exported MP4 before publishing.

## Current validation status
The renderer smoke fixture passed CI previously. The new UI and auto-start behavior still need a fresh CI run and a local end-to-end test; generated scene quality, Chatterbox runtime compatibility, and final audio/video sync have not yet been validated on the Mac.
