# Technical Data Cinema

A second production mode for story-specific, animation-led technical explainers. It is isolated from the existing shorts pipeline and reuses the repository's existing Chatterbox workflow instead of implementing a second TTS system.

## Workflow
1. Approve a story brief and narration.
2. Generate one self-contained HTML scene with a local Ollama coding model.
3. Preview and revise the story-specific animation.
4. Generate/approve narration using the existing Chatterbox workflow.
5. Render deterministic frames and mux the approved WAV with FFmpeg.
6. Inspect the exported video before publishing.

This is **not a fixed scene template**. The visual plan must decide what each entity represents, how it moves, what causes a state change, and how the viewer infers the mechanism.

## Requirements
- macOS on Apple Silicon
- Node.js 22+ and npm (Playwright current releases track supported Node LTS versions)
- Ollama with a downloaded coding model
- FFmpeg available as `ffmpeg`
- Existing Chatterbox environment for narration
- Chromium for Playwright rendering

## Setup
From repository root:
```bash
cd modes/technical-data-cinema
npm install
npx playwright install chromium
```
Check local services:
```bash
ollama list
curl http://127.0.0.1:11434/api/tags
ffmpeg -version
```

## Generate a story-specific HTML page
```bash
npm run generate -- --story examples/viral-traffic.md --model qwen3-coder:30b
```
Output is written under `output/`. The generator writes only a new generated HTML file and never modifies application source. Use `--model qwen2.5-coder:7b` for faster iterations.

## Automatic Ollama lifecycle

Use `npm run generate` (rather than invoking `scripts/generate.mjs` directly) for managed lifecycle handling. The wrapper checks the Ollama API, starts `ollama serve` only if no server is already responding, verifies the selected model is already downloaded, runs generation, unloads that model if it is resident, and stops the server only when this command started it. An existing Ollama server is left running. It never silently downloads models; if one is missing, the error tells you to run `ollama pull <model>` yourself.

The model is unloaded after the generation command, including failed runs, so memory is available for Chatterbox. The service is not stopped if it was already running before generation.

## Render a deterministic timeline
Generated HTML must expose `window.renderAt(seconds)` and `window.getDuration()`. Render with:
```bash
node scripts/render.mjs --html output/pilot-why-a-viral-moment-can-break-a-backend/index.html --out output/pilot-why-a-viral-moment-can-break-a-backend/final.mp4 --fps 30 --audio /absolute/path/to/approved-narration.wav
```
Chromium captures 1080×1920 frames, checks that seeking is deterministic, and rejects browser errors or HTTP(S) requests; FFmpeg encodes H.264/AAC. Start with `npm run test:smoke` before a story render. Full 1080×1920 rendering can take time and disk space.\n\n## Reference docs\n- [Animation Playbook](docs/ANIMATION_PLAYBOOK.md)\n- [Research Report](docs/RESEARCH_REPORT.md)\n- [Packages and Setup](docs/PACKAGES_AND_SETUP.md)\n- [Scene QA Checklist](docs/SCENE_QA_CHECKLIST.md)\n\nThe included `examples/render-smoke-test.html` is only a renderer test fixture, not a creative template.

## Model/memory policy for a 24 GB Mac
- Run one heavy model at a time; do not keep Qwen3-Coder, Chatterbox and other large models active together.
- Start with 8192 context tokens; increase only after checking memory. Longer context increases memory use.
- Use Qwen3-Coder 30B for high-effort scene generation, then unload it before narration/rendering if memory pressure appears.
- Use Qwen2.5-Coder 7B for quick revisions and syntax fixes.
- Use DeepSeek-R1 14B only as an optional reasoning reviewer.
- Check actual allocation using `ollama ps` and Activity Monitor. Do not close unknown system processes; quit known heavy apps you are not using.

## Quality rules
- Every particle/object has a semantic role; no decorative particle wallpaper.
- Motion demonstrates a causal relationship or state change.
- Graphs build progressively; values are sourced or labelled illustrative.
- Composition and technique change when the explanatory job changes.
- Camera motion supports comprehension and never obscures the mechanism.
- Seeking is deterministic and repeatable.
- No CDN, remote assets, external fonts, or network dependency in generated HTML.
- Run browser/console checks and inspect representative frames and full playback before publishing.

## Status
Initial scaffold only. It has not been run on the user's Mac; Ollama generation quality, Chatterbox alignment, render speed, and final video quality remain to be validated locally.
