#!/usr/bin/env node
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const outputRoot = path.join(root, "output");
const repoRoot = path.resolve(root, "../..");
const studioUrl = (process.env.CHATTERBOX_STUDIO_URL || "http://127.0.0.1:8765").replace(/\/$/, "");
let managedStudio = null;
const host = process.env.TDC_UI_HOST || "127.0.0.1";
const port = Number(process.env.TDC_UI_PORT || 4177);
const jobs = new Map();
let activeJob = null;

function json(res, status, data) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  res.end(JSON.stringify(data));
}
function safeSlug(value) {
  return String(value || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
      if (body.length > 500_000) { reject(new Error("Request too large (max 500 KB).")); req.destroy(); }
    });
    req.on("end", () => {
      try { resolve(JSON.parse(body || "{}")); } catch { reject(new Error("Invalid JSON request.")); }
    });
    req.on("error", reject);
  });
}
function log(job, message) {
  job.logs.push(`[${new Date().toLocaleTimeString()}] ${message}`);
  if (job.logs.length > 1000) job.logs.splice(0, job.logs.length - 1000);
}
function run(command, args, cwd, job, label) {
  return new Promise((resolve, reject) => {
    log(job, `Starting: ${label}`);
    const child = spawn(command, args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    job.child = child;
    let tail = "";
    const consume = chunk => {
      const text = chunk.toString("utf8");
      tail += text;
      const lines = tail.split(/\r?\n/);
      tail = lines.pop() || "";
      for (const line of lines) if (line.trim()) log(job, line.trim());
    };
    child.stdout.on("data", consume);
    child.stderr.on("data", consume);
    child.on("error", error => reject(new Error(`${label}: ${error.message}`)));
    child.on("close", code => {
      if (tail.trim()) log(job, tail.trim());
      job.child = null;
      if (code === 0) { log(job, `Finished: ${label}`); resolve(); }
      else reject(new Error(`${label} exited with code ${code}.`));
    });
  });
}

async function runSceneRepair(node, generateArgs, repairNote, cwd, job, label) {
  const repairArgs = [...generateArgs, "--repair-note", repairNote];
  try {
    await run(node, repairArgs, cwd, job, label);
    return;
  } catch (error) {
    const recent = job.logs.slice(-80).join("\n");
    const modelOutputInvalid = /Generated HTML failed export validation|Model output did not start with|Ollama returned no message content|Generated HTML uses Math\.random/i.test(recent);
    if (!modelOutputInvalid) throw error;

    const fallbackModel = "qwen2.5-coder:7b";
    const availableModels = await getModels();
    if (!availableModels.some(name => name === fallbackModel || name.startsWith(fallbackModel + ":"))) {
      throw new Error(`${label} failed because the model returned an invalid scene contract, and fallback model ${fallbackModel} is not installed. Install it with: ollama pull ${fallbackModel}`);
    }

    const fallbackArgs = [...repairArgs];
    const modelIndex = fallbackArgs.indexOf("--model");
    if (modelIndex < 0 || !fallbackArgs[modelIndex + 1]) throw error;
    fallbackArgs[modelIndex + 1] = fallbackModel;
    log(job, `Primary repair model returned invalid HTML; retrying once with fallback model ${fallbackModel}. Narration WAV remains unchanged.`);
    try {
      await run(node, fallbackArgs, cwd, job, `${label} (fallback ${fallbackModel})`);
    } catch (fallbackError) {
      const fallbackLogs = job.logs.slice(-80).join("\n");
      const reason = /Generated HTML uses Math\.random/i.test(fallbackLogs)
        ? "the fallback model still emitted Math.random(), which is not allowed in deterministic renders"
        : /Generated HTML failed export validation|Model output did not start with|Ollama returned no message content/i.test(fallbackLogs)
          ? "the fallback model still failed the required HTML/export contract"
          : fallbackError.message;
      throw new Error(`${label} could not produce a valid scene after the primary and fallback attempts: ${reason}. The existing narration WAV was not regenerated. Review the archived scene/logs, or try a stronger installed coding model; QA was not bypassed.`);
    }
  }
}

async function retryExportWithEndingRepair(node, generateArgs, htmlPath, mp4Path, finalWavPath, fps, dir, root, job) {
  const exportArgs = [ "scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", finalWavPath, "--fps", String(fps) ];
  try {
    await run(node, exportArgs, root, job, "Retry render with preserved narration WAV");
    return;
  } catch (error) {
    const endingFailure = job.logs.slice(-100).some(line => line.includes("Visual ending check failed"));
    if (!endingFailure) throw error;
    const archivedScene = path.join(dir, `index.failed-ending-${Date.now()}.html`);
    await fs.rename(htmlPath, archivedScene);
    const repairNote = [
      "SECOND, MORE STRICT VISUAL-ENDING REPAIR. The previous repaired scene still failed QA because its final frames are pixel-identical for more than 2.5 seconds.",
      "Keep the same story and visual explanation, but redesign the ending timeline. The final explanatory action must continue changing through the last narration beat. Only in the final 1.5 to 2.5 seconds may the scene resolve to the takeaway.",
      "Do not use a static card, static text, a long fade, or a frozen final composition. Add timestamp-driven motion or a visible causal resolution that changes at multiple timestamps during the final 3 seconds.",
      "The full scene must remain deterministic: renderAt(t) sets every visible property from absolute t and resets the complete drawing state. Preserve the exact export contract: define positive DURATION and global window.getDuration = function () { return DURATION; } and window.renderAt = function (seconds) { const t = Math.max(0, Math.min(DURATION, Number(seconds) || 0)); draw(t); }; adapt draw only if the renderer function has another name.",
      "Include render-only mode using new URLSearchParams(window.location.search).get('render') === '1'. Return a complete valid HTML document, not a fragment. No Math.random(), timers for scene state, or CSS transitions."
    ].join("\n");
    log(job, `The first repaired scene still failed ending QA; archived it as ${path.basename(archivedScene)} and making one stricter ending-only repair. Narration WAV remains unchanged.`);
    await runSceneRepair(node, generateArgs, repairNote, root, job, "Strict visual-ending repair");
    await run(node, exportArgs, root, job, "Final render after strict ending repair");
  }
}

async function ensureStudio(job) {
  const ready = async () => {
    try {
      const r = await fetch(`${studioUrl}/api/options`, { signal: AbortSignal.timeout(1200) });
      return r.ok;
    } catch { return false; }
  };
  if (await ready()) {
    log(job, `Reusing the existing Chatterbox API at ${studioUrl}.`);
    return;
  }
  if (!managedStudio || managedStudio.exitCode !== null) {
    log(job, "Chatterbox API is not responding; starting it headlessly in the background with the dedicated Hindi variant…");
    let python = process.env.STUDIO_PYTHON;
    if (!python) {
      const venvPython = path.join(repoRoot, ".venv", "bin", "python");
      try { await fs.access(venvPython); python = venvPython; }
      catch { python = "python3"; }
    }
    managedStudio = spawn(python, ["-u", "-m", "engine.studio.server", "--api-only", "--host", "127.0.0.1", "--port", String(new URL(studioUrl).port || 8765)], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONPATH: repoRoot, PYTHONUNBUFFERED: "1", CHATTERBOX_MODEL_VARIANT: process.env.CHATTERBOX_MODEL_VARIANT || "dedicated_hindi" },
      stdio: ["ignore", "pipe", "pipe"]
    });
    const consume = chunk => {
      for (const line of chunk.toString("utf8").split(/\r?\n/)) if (line.trim()) log(job, `[Studio] ${line.trim()}`);
    };
    managedStudio.stdout.on("data", consume);
    managedStudio.stderr.on("data", consume);
    managedStudio.on("exit", code => log(job, `[Studio] process exited with code ${code}`));
  }
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    if (await ready()) {
      log(job, `Background Chatterbox API is ready at ${studioUrl}.`);
      return;
    }
    if (managedStudio?.exitCode !== null && managedStudio?.exitCode !== undefined) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error(`Background Chatterbox API did not become ready at ${studioUrl}. Check that Python dependencies and the dedicated Hindi checkpoint/reference are installed. Set STUDIO_PYTHON if your working Python is not the system python3.`);
}

async function getModels() {
  const base = (process.env.OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/tags`, { signal: AbortSignal.timeout(1500) });
    if (!response.ok) throw new Error("Ollama not ready");
    const data = await response.json();
    return (data.models || []).map(m => m.name).filter(Boolean).sort();
  } catch { return []; }
}
async function serveFile(res, filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const types = { ".html": "text/html; charset=utf-8", ".mp4": "video/mp4", ".wav": "audio/wav", ".json": "application/json", ".md": "text/markdown; charset=utf-8" };
  try {
    const data = await fs.readFile(filePath);
    res.writeHead(200, { "content-type": types[ext] || "application/octet-stream", "cache-control": "no-store" });
    res.end(data);
  } catch { json(res, 404, { error: "File not found." }); }
}
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${host}:${port}`);
    if (req.method === "GET" && url.pathname === "/") return await serveFile(res, path.join(here, "ui.html"));
    if (req.method === "GET" && url.pathname === "/api/models") return json(res, 200, { models: await getModels(), active: Boolean(activeJob) });
    if (req.method === "GET" && url.pathname.startsWith("/api/jobs/")) {
      const job = jobs.get(url.pathname.split("/").pop());
      if (!job) return json(res, 404, { error: "Job not found." });
      return json(res, 200, { id: job.id, status: job.status, logs: job.logs, error: job.error || null, files: job.files || {} });
    }
    if (req.method === "POST" && url.pathname === "/api/run") {
      if (activeJob) return json(res, 409, { error: "A job is already running. Wait for it to finish before starting another model." });
      const body = await readBody(req);
      const title = String(body.title || "").trim();
      const story = String(body.story || "").trim();
      const voiceMode = String(body.voiceMode || "generate");
      const voiceScript = String(body.voiceScript || "").trim();
      const wavPath = String(body.wavPath || "").trim();
      const model = String(body.model || "").trim();
      const slug = safeSlug(body.slug || title);
      const fps = Number(body.fps || 30);
      if (!title || !story) return json(res, 400, { error: "Add a title and story brief." });
      if (!slug) return json(res, 400, { error: "The output name must contain letters or numbers." });
      if (!model) return json(res, 400, { error: "Choose an installed Ollama model." });
      if (!["generate", "wav", "silent"].includes(voiceMode)) return json(res, 400, { error: "Choose a valid voice mode." });
      if (voiceMode === "generate" && !voiceScript) return json(res, 400, { error: "Add the narration script for Chatterbox." });
      if (voiceMode === "wav" && !wavPath) return json(res, 400, { error: "Enter the absolute path to an existing WAV file." });
      if (!Number.isFinite(fps) || fps < 10 || fps > 60) return json(res, 400, { error: "FPS must be between 10 and 60." });
      const id = crypto.randomBytes(6).toString("hex");
      const job = { id, status: "queued", logs: [], files: {}, error: null, child: null };
      jobs.set(id, job);
      activeJob = id;
      log(job, "Queued. Heavy stages will run sequentially to reduce memory pressure.");
      (async () => {
        try {
          job.status = "running";
          const dir = path.join(outputRoot, slug);
          await fs.mkdir(dir, { recursive: true });
          const storyPath = path.join(dir, "story.md");
          const htmlPath = path.join(dir, "index.html");
          const narrationPath = path.join(dir, "narration.md");
          const mp4Path = path.join(dir, voiceMode === "silent" ? "final-silent.mp4" : "final.mp4");
          const storyContent = `# ${title}\n\n${story}\n`;

          // Never overwrite a completed video. Reuse a narration WAV only when its source
          // script matches exactly; this avoids rerunning Chatterbox after a render failure.
          for (const name of ["final.mp4", "final-silent.mp4"]) {
            try {
              await fs.access(path.join(dir, name));
              throw new Error(`Output already exists: ${path.join(dir, name)}. Choose a new output folder to preserve the previous production.`);
            } catch (error) {
              if (error.code !== "ENOENT") throw error;
            }
          }

          const narrationContent = voiceScript ? voiceScript + "\n" : "";
          const finalWavPath = path.join(dir, "final.narration.wav");
          let reuseNarration = false;
          try {
            await fs.access(finalWavPath);
            if (voiceMode !== "generate") throw new Error(`Narration WAV already exists: ${finalWavPath}. Choose a new output folder to avoid overwriting it.`);
            let savedNarration;
            try { savedNarration = await fs.readFile(narrationPath, "utf8"); }
            catch { throw new Error(`Narration WAV exists at ${finalWavPath}, but its source script is missing. Preserve it and choose a new output folder.`); }
            if (savedNarration !== narrationContent) throw new Error("Narration WAV exists, but narration.md does not match the submitted script. Choose a new output folder to preserve the existing voice.");
            reuseNarration = true;
            log(job, "Reusing the existing narration WAV; Chatterbox will not run again.");
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
          }

          let reuseScene = false;
          try {
            await fs.access(htmlPath);
            const savedStory = await fs.readFile(storyPath, "utf8");
            if (savedStory !== storyContent) throw new Error(`A scene already exists in ${dir}, but its saved story does not match this brief. Choose a new output folder to avoid mixing productions.`);
            reuseScene = true;
            log(job, "Reusing the existing scene because story.md matches; skipping Ollama generation.");
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
          }

          await fs.writeFile(storyPath, storyContent, "utf8");
          if (voiceMode === "generate") await fs.writeFile(narrationPath, narrationContent, "utf8");
          const node = process.execPath;
          const generateArgs = ["scripts/ollama-session.mjs", "--", "node", "scripts/generate.mjs", "--story", storyPath, "--model", model, "--out", htmlPath];
          if (!reuseScene) {
            try {
              await run(node, generateArgs, root, job, "Ollama scene generation (model unload happens before narration)");
            } catch (error) {
              const validationFailure = /Generated HTML uses Math\.random|Generated HTML failed export validation|Model output did not start with|Ollama returned no message content/i.test(job.logs.slice(-100).join("\n"));
              if (!validationFailure) throw error;
              const archivedScene = path.join(dir, `index.invalid-${Date.now()}.log.html`);
              // generate.mjs validates before writing, but preserve any unexpected partial artifact safely.
              try { await fs.rename(htmlPath, archivedScene); log(job, `Archived invalid generated scene as ${path.basename(archivedScene)}.`); }
              catch (archiveError) { if (archiveError.code !== "ENOENT") throw archiveError; }
              const repairNote = [
                "AUTOMATIC FIRST-PASS VALIDATION REPAIR. The previous model output was rejected by deterministic scene validation.",
                "Do not use Math.random() anywhere, including initialization. Do not use timers or CSS transitions for scene state.",
                "Every visible value must be a pure function of absolute timestamp; renderAt(seconds) must reset the full scene state and reproduce identical pixels when called repeatedly for the same timestamp.",
                "Return a complete HTML document beginning with <!doctype html>, include window.renderAt, window.getDuration, and render-only mode via new URLSearchParams(window.location.search).get('render').",
                "Keep the original story and narration meaning. Do not weaken or bypass any validation."
              ].join("\n");
              log(job, "Initial scene failed HTML/determinism validation; starting one targeted repair, then a single fallback-model attempt if needed. Narration is preserved.");
              await runSceneRepair(node, generateArgs, repairNote, root, job, "Repair invalid initial scene");
            }
          }
          if (voiceMode === "generate") {
            if (reuseNarration) {
              try {
                await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", finalWavPath, "--fps", String(fps)], root, job, "Render with reused narration WAV");
              } catch (error) {
                const recentLogs = job.logs.slice(-100);
                const deterministicFailure = recentLogs.some(line => line.includes("Determinism check failed"));
                const endingFailure = recentLogs.some(line => line.includes("Visual ending check failed"));
                if (!deterministicFailure && !endingFailure) throw error;
                const archivedScene = path.join(dir, `index.failed-${Date.now()}.html`);
                await fs.rename(htmlPath, archivedScene);
                const repairNote = endingFailure
                  ? "The previous export failed visual-ending QA: its final frames were pixel-identical for more than 2.5 seconds. Redesign the final 5 seconds: keep meaningful narration-synchronized motion through the last explanatory beat, then resolve into a takeaway only in the final 1.5–2.5 seconds. Do not stretch or freeze an end card; keep deterministic renderAt(seconds) behavior."
                  : "The previous export failed determinism QA. Ensure every visual property is derived from absolute timestamp and renderAt(t) resets the full scene state.";
                log(job, `${endingFailure ? "Visual ending" : "Determinism"} QA failed; archived scene as ${path.basename(archivedScene)} and attempting one targeted scene repair while preserving narration.`);
                await runSceneRepair(node, generateArgs, repairNote, root, job, endingFailure ? "Repair frozen visual ending" : "Regenerate nondeterministic scene");
                await retryExportWithEndingRepair(node, generateArgs, htmlPath, mp4Path, finalWavPath, fps, dir, root, job);
              }
            } else {
              await ensureStudio(job);
              try {
                await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--voice-script", narrationPath, "--fps", String(fps), "--style", String(body.style || "storytelling"), "--performance", String(body.performance || "directed"), "--expression-intensity", String(body.intensity ?? 65)], root, job, "Chatterbox narration, then video render");
              } catch (error) {
                const endingFailure = job.logs.slice(-100).some(line => line.includes("Visual ending check failed"));
                if (!endingFailure) throw error;
                const archivedScene = path.join(dir, `index.failed-${Date.now()}.html`);
                await fs.rename(htmlPath, archivedScene);
                const repairNote = "The previous export failed visual-ending QA: its final frames were pixel-identical for more than 2.5 seconds. Redesign the final 5 seconds: keep meaningful narration-synchronized motion through the last explanatory beat, then resolve into a takeaway only in the final 1.5–2.5 seconds. Do not stretch or freeze an end card; keep deterministic renderAt(seconds) behavior.";
                log(job, `Visual ending QA failed; archived scene as ${path.basename(archivedScene)} and attempting one targeted scene repair while preserving the generated narration WAV.`);
                await runSceneRepair(node, generateArgs, repairNote, root, job, "Repair frozen visual ending");
                await retryExportWithEndingRepair(node, generateArgs, htmlPath, mp4Path, finalWavPath, fps, dir, root, job);
              }
            }
          } else if (voiceMode === "wav") {
            await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", path.resolve(wavPath), "--fps", String(fps)], root, job, "Render with existing WAV narration");
          } else {
            await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--fps", String(fps)], root, job, "Silent video render");
          }
          job.files = {
            scene: `/files/${encodeURIComponent(slug)}/index.html`,
            video: `/files/${encodeURIComponent(slug)}/${path.basename(mp4Path)}`,
            audio: voiceMode === "generate" ? `/files/${encodeURIComponent(slug)}/final.narration.wav` : voiceMode === "wav" ? `/files/${encodeURIComponent(slug)}/${path.basename(wavPath)}` : null
          };
          if (voiceMode === "wav") {
            // The source WAV can live anywhere on disk; the UI intentionally offers the final video only.
            job.files.audio = null;
          }
          job.status = "completed";
          log(job, "All stages completed.");
        } catch (error) {
          job.status = "failed";
          job.error = error.message;
          log(job, `FAILED: ${error.message}`);
          if (job.child) { try { job.child.kill("SIGTERM"); } catch {} }
        } finally {
          activeJob = null;
          job.child = null;
        }
      })();
      return json(res, 202, { id });
    }
    if (req.method === "GET" && url.pathname.startsWith("/files/")) {
      const parts = url.pathname.split("/").filter(Boolean).slice(1).map(decodeURIComponent);
      if (parts.length !== 2 || parts.some(p => p.includes("/") || p === "." || p === "..")) return json(res, 400, { error: "Invalid file path." });
      return await serveFile(res, path.join(outputRoot, parts[0], parts[1]));
    }
    json(res, 404, { error: "Not found." });
  } catch (error) {
    json(res, 500, { error: error.message || "Unexpected local UI server error." });
  }
});
server.listen(port, host, () => {
  console.log(`Technical Data Cinema UI: http://${host}:${port}`);
  console.log("Local-only server. Keep this port bound to 127.0.0.1.");
});
