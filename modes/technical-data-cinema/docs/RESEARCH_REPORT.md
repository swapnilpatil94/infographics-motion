# Research Report: Building a Local Technical Data Cinema Engine

**Research date:** 2026-10-13  
**Purpose:** Establish a practical, maintainable toolkit for making animation-led technical explainers as story-specific HTML pages on Apple Silicon.

## Executive recommendation

Use a **browser-first, deterministic HTML scene as the primary production unit**. Each story gets a new authored composition and causal animation, while the rendering contract and quality checks remain reusable. Start with Canvas 2D + SVG + DOM. Add WebGL/Three.js only when a story benefits from true 3D or GPU-scale effects. Use Playwright/Chromium to render exact timeline frames and FFmpeg to encode the final video.

The key capability is not a larger library of visual effects. It is the ability to select the right animation model for the explanation, make its state change visible, and synchronize those changes to narration.

## Findings

### 1. Browser rendering is practical for a local-first engine

A self-contained HTML page can combine Canvas, SVG and DOM, work offline, and be inspected directly in a browser. Playwright can launch its bundled Chromium and capture frames. Its official documentation notes that browser binaries are version-specific; update the Playwright package and reinstall the matching browser binaries when upgrading.

### 2. Deterministic time is a non-negotiable requirement

The offline renderer asks for a particular timestamp, so animation must be a function of absolute time. A page that relies on a live animation loop, accumulated frame deltas, random state or CSS keyframes may look correct in a live preview but produce incorrect frames when seeking or rendering. Keep a single `renderAt(seconds)` entry point for preview, screenshot capture, and regression tests.

### 3. Use different visual techniques for different causal explanations

The playbook catalogs particles, graph/network flows, branching requests, queues, capacity charts, feedback loops, heat maps, state machines, before/after experiments, camera tracking, parallax, cutaways and progressive reveals. A technique is selected because it makes a causal relationship visible, not because it looks impressive.

### 4. Keep the dependency set small

| Dependency | Role | Recommendation |
|---|---|---|
| Node.js | CLI scripts and orchestration | Use a current supported LTS; verify version with `node --version` |
| Ollama | Local model inference | Use existing installation and already-downloaded models |
| Playwright | Chromium automation and frame capture | Required for renderer |
| Chromium installed by Playwright | Consistent headless browser rendering | Install after changing Playwright version |
| FFmpeg | H.264/AAC output and audio muxing | Required for MP4 export |
| Chatterbox | Narration | Reuse existing repository workflow; don't create a duplicate TTS stack |
| Canvas 2D / SVG / DOM | Primary animation tools | Built into the browser; no extra package |
| Three.js | Optional 3D/WebGL | Add only when a scene needs 3D; vendor/pin locally to preserve offline execution |
| Playwright Test | Automated browser assertions | Optional next step; initial renderer can use Playwright library directly |

Avoid adding GSAP, anime.js, D3, PixiJS, p5.js and Three.js simultaneously. Each adds another dependency and animation lifecycle to control. Add a library only when it enables a clearly defined class of scenes and can satisfy deterministic seeking.

### 5. Model workflow should be staged

1. Use `qwen3-coder:30b` for high-effort scene generation, with conservative context on a 24 GB unified-memory Mac.
2. Use `qwen2.5-coder:7b` for quick edits and syntax fixes.
3. Use `deepseek-r1:14b` only for a separate reasoning review when needed.
4. Avoid running multiple large models alongside Chatterbox. Generate HTML, stop/unload the coding model if memory is tight, then generate narration and render.
5. Measure real quality, latency, memory pressure and failure rate on the actual Mac before downloading more models.

## Recommended architecture

```text
Story brief + approved narration
             |
             v
Visual Director prompt + animation playbook
             |
             v
Story-specific index.html
             |
             v
Static checks + deterministic contract checks
             |
             v
Chromium / Playwright frame capture
             |
             v
Frame inspection + repairs
             |
             v
FFmpeg MP4 + approved Chatterbox narration
             |
             v
Final playback + release checklist
```

The scene-specific HTML is not a fixed template. Shared code should define the renderer contract, reusable math helpers, local generation workflow and QC. The visual composition, metaphor, camera language, timing and animation system should be authored for each story.

## What to benchmark

Run the same story brief through each model under similar context settings and compare:
- whether the animation explains the mechanism without narration;
- meaningful state changes vs decorative motion;
- originality of composition and camera language;
- timing coherence and caption readability;
- determinism under random timestamp seeking;
- console errors, clipping and frame stability;
- first-pass success rate and number of repair rounds;
- total generation time and memory use.

Use a human review rubric, not a single “looks good” score. Do not select a model based only on parameter count.

## Known risks and controls

| Risk | Control |
|---|---|
| Model returns incomplete HTML or code fences | Validate doctype and required renderer functions before saving |
| Page depends on a CDN or remote font | Static scan and offline browser test |
| Frame differs after seeking | Render the same timestamps twice and compare pixel hashes |
| Console exceptions hidden in logs | Collect browser console/page errors and fail the render |
| Long frame renders exhaust disk | Estimate frames and disk use; offer a short preview render |
| Audio duration differs from visual duration | Measure WAV duration and explicitly trim/pad only after user approval |
| Demo values look factual | Require source metadata or visible “illustrative example” labels |
| Model overwrites prior output | Unique output paths and refuse overwrite by default |
| Overloaded Mac | One heavy model at a time; monitor `ollama ps` and Activity Monitor |

## Research sources

1. Playwright, browser installation and version management: https://playwright.dev/docs/browsers
2. Playwright release notes (latest documented release at research time includes v1.63): https://playwright.dev/docs/release-notes
3. Ollama chat API, model/options and non-streaming responses: https://github.com/ollama/ollama/blob/main/docs/api.md
4. MDN requestAnimationFrame: https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame
5. MDN Canvas filter (compatibility caveat): https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/filter
6. Three.js WebGLRenderer: https://threejs.org/docs/pages/WebGLRenderer.html

## Research limitations

This report is an engineering synthesis of official tool documentation and established browser-rendering patterns. It is not a benchmark of the user's local models and does not claim that generated scenes have been rendered successfully on the user's Mac. The first local pilot is required to validate visual quality, performance and Chatterbox synchronization.
