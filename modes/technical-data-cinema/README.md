# Technical Data Cinema

A local-first, story-specific mode for animation-led technical explainers. It reuses the repository's existing Chatterbox Studio narration adapter and does not add a second TTS implementation.

## Workflow
1. Approve the story brief and spoken narration script.
2. Plan the visual beats with a local reasoning model, then generate one self-contained HTML scene with a coding model; the two models run sequentially and unload after each stage to protect unified memory.
3. Preview and revise the story-specific animation.
4. Export silently, add an approved WAV, or generate narration through the existing Chatterbox Studio API.
5. Inspect the final MP4 and audio before publishing.

This is **not a fixed scene template**. Visual language, motion, pacing and composition should change according to the causal story being explained.

## Standalone narration workflow

The production UI also has a separate **Generate narration separately** panel. It calls the existing Chatterbox Studio audio API directly; it does not run the visual planner, Ollama scene coder, or video renderer. Paste a script, generate a WAV, preview it in the browser, and download the paced and original WAVs independently. This is useful for approving narration before any visual generation.

### Narration input

- Paste UTF-8 plain text directly into the script box. Devanagari Hindi, Roman Hindi, Hinglish, English technical terms, and normal punctuation are accepted as text input.
- Optional existing directed-performance cues such as `[HOOK]`, `[CURIOUS]`, `[SUSPENSE]`, `[EXPLAIN]`, and `[REVEAL]` may be placed before the passage they should influence. Use **Directed cues** to preserve cue-driven delivery or **Uniform delivery** to request a more consistent read.
- Voice delivery: **Storytelling**, **Conversational**, or **Dramatic**.
- Expression intensity: **0–100** (default 65).
- Overall pace: **0.8×–1.2×**. This is a post-generation FFmpeg tempo adjustment; it changes duration while aiming to preserve pitch. The original generated WAV is retained separately so you can compare. Use 1.0× when you want the untouched Studio output.
- Each audio take is saved to its own output folder as `narration.wav`, `narration-source.wav`, and `narration.md`. Existing final audio is not overwritten; choose a new folder for another take.

The pace control adjusts the whole take uniformly; it does not independently retime individual sentences or add pauses. For better natural rhythm, keep punctuation and paragraph breaks in the script and use the existing directed cues sparingly.

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
Open `http://127.0.0.1:4177`. Paste or edit the story brief and narration, select an installed Ollama scene-coding model, then choose Chatterbox narration, an existing WAV, or silent export. The visual planner defaults to `qwen3.5:9b` (`OLLAMA_PLANNER_MODEL` can override it). Use **Analyze story first** to create a separate `visual-plan.json`; inspect/edit the JSON in the UI and choose **Validate & save plan** before generating the scene. The main action then generates the scene, validates the export contract and visual quality, and continues into the existing audio/render pipeline. You can still use the main action directly for full automation. Heavy models run sequentially; narration is not involved in analysis or scene repair. The UI shows progress and validation state for analysis, scene generation, visual QA, narration and rendering, plus links to saved artifacts. It prevents concurrent production jobs and never regenerates approved narration during a visual-only repair. For Chatterbox voice, the UI checks for an existing Studio and starts it with `CHATTERBOX_MODEL_VARIANT=dedicated_hindi` if needed. If your Chatterbox dependencies use a custom Python environment, set `STUDIO_PYTHON` to that interpreter path before `npm run ui`. The UI server binds to localhost by default and should not be exposed to your network.

## Generate a scene
```bash
npm run generate -- --story examples/viral-traffic.md --planner-model qwen3.5:9b --model qwen2.5-coder:7b
```
Recommended defaults for the 24 GB Apple Silicon Mac: `qwen3.5:9b` for visual planning and `qwen2.5-coder:7b` for HTML/JS scene implementation. They run sequentially (`keep_alive: 0`), so both models are not kept resident together. The default context is 8192 tokens. The coding model is also the repair model unless the UI selects an installed alternative. Override with `--planner-model` / `--model`, or `OLLAMA_PLANNER_MODEL` / `OLLAMA_MODEL`. Models are never pulled automatically; the generator checks that the planner model is installed and reports available models if not.

The generator supports `--phase plan` (analyze and validate `visual-plan.json` only) and `--phase scene` (require an existing plan, then generate the HTML), in addition to the default full sequence. The UI exposes these as separate analysis and scene/export stages and lets you validate/edit the plan before rendering. If the model uses `Math.random()` or omits the render-only query contract, the generator installs a deterministic, timestamp-seeded compatibility layer and still runs the normal visual-quality and rendered-video checks; it does not mark a scene as publish-ready just because the export contract was repaired. Generated scenes must expose `window.renderAt(seconds)` and `window.getDuration()`, and must hide preview UI for `?render=1`. Invalid output is rejected before writing the HTML. Each generation writes a new file and never overwrites prior output. If the scene coder returns invalid HTML, uses `Math.random()`, omits the export contract, or becomes unreachable after a valid visual plan has been saved, the generator makes one automatic repair attempt with the same coding model and the exact validation failure. If repair still fails, generation stops instead of silently producing a generic-looking MP4. Set `ALLOW_GENERIC_FALLBACK=1` only when you explicitly want the diagnostic SVG fallback; it is not creative-quality approved. The fallback selects distinct scene grammars—network topology, directional flow/queue, before-after comparison, causal timeline, scale imbalance, layered causes, or transformation—rather than reusing one central icon. Headline text is wrapped into safe lines and the fallback is built from absolute render time, so seeking remains deterministic. The fallback is explicitly logged and is a recovery path, not automatic creative-quality approval. Review the preview before publishing. Run `npm run test:fallback` for the export contract and `npm run test:fallback:render` for browser rendering, seven distinct scene grammars, safe text bounds, browser errors and deterministic seeking.

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

The renderer tests deterministic seeking, rejects browser errors and external requests, samples the narrated ending to reject a pixel-identical frozen frame lasting more than 2.5 seconds, and encodes 1080×1920 H.264/AAC. The renderer also runs a canvas visual-density audit at six points in the timeline and rejects scenes where most samples contain only sparse artwork; `--allow-low-visual-density` is available for intentionally minimalist concepts, but should not be used to bypass poor composition. The UI makes one targeted scene-repair attempt after a frozen-ending failure while preserving the narration WAV; it does not rerun Chatterbox for this visual-only repair. When narration is longer than the scene, the scene timeline is time-scaled to span the narration rather than freezing on the final frame. A manually supplied `--duration` shorter than the voice is rejected to avoid cutting off speech. Rendered frames can use several GB; ensure enough disk space before full exports.

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


## Visual Director benchmark

The repository includes a deterministic Three.js benchmark scene demonstrating a dotted stadium/crowd, moving request particles, delivery nodes, an overload queue, camera reframing, and a resolution beat. It is a renderer/visual-language test—not proof that the local LLM will generate equally strong scenes for every story.

Build and render the silent benchmark without calling Ollama or Chatterbox:
```bash
npm run test:visual-benchmark
```
Output:
- `output/visual-director-benchmark/index.html` — offline, bundled scene
- `output/visual-director-benchmark.mp4` — 16-second vertical benchmark

To test the Visual Director with a real episode while preserving approved narration, generate the episode scene first, then export with the existing WAV:
```bash
npm run generate -- --story <story-brief.md> --model qwen3-coder:30b
npm run export -- --html output/<story-slug>/index.html --out output/<story-slug>/final.mp4 --audio /absolute/path/to/approved-narration.wav
```
Do not run a new TTS pass just to test visuals. Review the MP4 for recognisable silhouettes, meaningful motion, continuity between visual metaphors, mobile readability, and narration sync; passing automated tests alone is not a creative-quality sign-off.
