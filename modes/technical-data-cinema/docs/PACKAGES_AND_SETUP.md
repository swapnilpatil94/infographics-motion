# Packages, Setup and Runtime Policy

## Required tools

| Tool | Required? | Install / verify |
|---|---|---|
| Node.js | Yes | Install current supported LTS; `node --version` |
| npm | Yes | `npm --version` |
| Ollama | Yes for local generation | `ollama list`, `curl http://127.0.0.1:11434/api/tags` |
| Playwright package | Yes | `npm install` inside this folder |
| Playwright Chromium | Yes for rendering | `npx playwright install chromium` |
| FFmpeg | Yes for MP4 export | macOS: `brew install ffmpeg`; verify `ffmpeg -version` |
| Existing Chatterbox setup | For narration | Use the repository's existing Script → Audio flow |
| Three.js | Optional | Add only for scenes that need actual 3D; vendor locally and pin version |

No additional JavaScript animation package is required for the first version. Canvas, SVG and DOM are browser APIs.

## Fresh setup

From the repository root:

```bash
cd modes/technical-data-cinema
node --version
npm --version
npm install
npx playwright install chromium
npm run doctor
```

If Node is older than the supported version documented by the current Playwright release, upgrade Node before installing dependencies.

## Update packages safely

Playwright's browser binaries are tied to the Playwright package version. After upgrading Playwright, reinstall Chromium. Do not update package.json manually without refreshing the lockfile.

```bash
npm install playwright@latest
npx playwright install chromium
npm run doctor
npm run test:smoke
```

Commit both `package.json` and `package-lock.json` after a successful install. This repository branch may not contain a lockfile until installation has been performed on a network-enabled machine.

## Model memory management

- Generate a scene with one coding model at a time.
- Use the existing `qwen3-coder:30b` as the high-effort candidate; start with 8192 context tokens and raise only if needed.
- Use `qwen2.5-coder:7b` for rapid fixes.
- Use `deepseek-r1:14b` as an optional reviewer, not a permanently loaded companion.
- Before Chatterbox synthesis, run `ollama ps`; stop the large coding model if memory is tight.
- Don't kill unknown macOS system processes. Quit known apps you aren't using and inspect Activity Monitor.

## Disk and render cost

At 30 fps, a 50-second video is 1,500 frames. PNG frames can consume several gigabytes depending on scene detail. Render to a directory with free disk space. The initial workflow keeps frames under the output directory to support debugging; delete the frames folder only after validating the final MP4.

## Local-first policy

- No runtime CDN dependencies, remote fonts, remote images or telemetry.
- Pin third-party libraries and vendor local files if they are required for offline use.
- Keep all source story briefs and prompts version-controlled; generated output and large frames should remain ignored by Git.
- Re-run browser installation after Playwright updates.
