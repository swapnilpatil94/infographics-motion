#!/usr/bin/env node
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";
import { normalizeVisualPlan } from "./visual-plan.mjs";
import { normalizeNarrationForTTS } from "./narration-text.mjs";

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
function freshStages() {
  return Object.fromEntries(["input","analysis","planValidation","scene","sceneValidation","audio","render","videoQc","export"].map(key => [key, { status: "pending", detail: null, updatedAt: new Date().toISOString() }]));
}
function setStage(job, key, status, detail = null) {
  if (!job.stages) job.stages = freshStages();
  job.stages[key] = { status, detail, updatedAt: new Date().toISOString() };
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
  const logStart = job.logs.length;
  try {
    await run(node, repairArgs, cwd, job, label);
    return;
  } catch (error) {
    const primaryLogs = job.logs.slice(logStart).join("\n");
    const modelOutputInvalid = /Generated scene failed browser render-only validation|Generated HTML failed export validation|Model output did not start with|Ollama returned no message content|Math\.random\(\), forbidden|missing native \?render=1 render-only mode/i.test(primaryLogs);
    if (!modelOutputInvalid) throw error;

    const installedModels = await getModels();
    const candidates = ["qwen2.5-coder:7b", "qwen3:14b"];
    const availableCandidates = candidates.filter(candidate =>
      candidate !== generateArgs[generateArgs.indexOf("--model") + 1] &&
      installedModels.some(name => name === candidate || name.startsWith(candidate + ":"))
    ).slice(0, 3);
    if (!availableCandidates.length) {
      throw new Error(`${label} failed validation and no alternate repair model is installed. Install one of: ${candidates.join(", ")}. Original failure: ${summarizeSceneFailure(primaryLogs)}. Narration WAV remains unchanged; QA was not bypassed.`);
    }

    let lastFailure = error;
    let lastReason = summarizeSceneFailure(primaryLogs) || error.message;
    for (const fallbackModel of availableCandidates) {
      const fallbackArgs = [...repairArgs];
      const modelIndex = fallbackArgs.indexOf("--model");
      if (modelIndex < 0 || !fallbackArgs[modelIndex + 1]) throw error;
      fallbackArgs[modelIndex + 1] = fallbackModel;
      const attemptStart = job.logs.length;
      log(job, `Repair output from the primary model was invalid; trying alternate model ${fallbackModel}. Narration WAV remains unchanged.`);
      try {
        await run(node, fallbackArgs, cwd, job, `${label} (fallback ${fallbackModel})`);
        return;
      } catch (fallbackError) {
        lastFailure = fallbackError;
        const attemptLogs = job.logs.slice(attemptStart).join("\n");
        const reason = summarizeSceneFailure(attemptLogs) || fallbackError.message;
        lastReason = reason;
        log(job, `Fallback ${fallbackModel} did not produce a valid scene: ${reason}.`);
      }
    }

    throw new Error(`${label} could not produce a valid scene after ${availableCandidates.length} alternate model attempt(s). Last failure: ${lastReason || lastFailure.message}. Existing narration WAV was not regenerated. Try another installed coding model or revise the scene prompt; QA was not bypassed.`);
  }
}

function summarizeSceneFailure(logText) {
  if (/Ollama returned no (?:message )?content/i.test(logText)) return "Ollama returned an empty response";
  if (/Math\.random\(\), forbidden/i.test(logText)) return "generated HTML uses Math.random(), forbidden for deterministic rendering";
  const browserFailure = logText.match(/Generated scene failed browser render-only validation: ([^\n]+)/i);
  if (browserFailure) return browserFailure[1];
  const missing = logText.match(/Generated HTML failed export validation: missing ([^\n.]+)/i);
  if (missing) return `export contract is missing ${missing[1]}`;
  if (/Model output did not start with <!doctype html>/i.test(logText)) return "model output is not a complete HTML document";
  if (/Could not reach Ollama|Ollama returned HTTP|timed out|AbortError/i.test(logText)) return "Ollama request failed or timed out";
  return "";
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
async function serveFile(res, filePath, download = false) {
  const ext = path.extname(filePath).toLowerCase();
  const types = { ".html": "text/html; charset=utf-8", ".mp4": "video/mp4", ".wav": "audio/wav", ".json": "application/json", ".md": "text/markdown; charset=utf-8" };
  try {
    const data = await fs.readFile(filePath);
    res.writeHead(200, { "content-type": types[ext] || "application/octet-stream", "cache-control": "no-store", ...(download ? { "content-disposition": `attachment; filename="${path.basename(filePath).replace(/["\\\\]/g, "")}"` } : {}) });
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
      return json(res, 200, { id: job.id, status: job.status, stage: job.stage || null, stages: job.stages || {}, logs: job.logs, error: job.error || null, files: job.files || {} });
    }
    if (req.method === "POST" && url.pathname === "/api/plan") {
      if (activeJob) return json(res, 409, { error: "Wait for the active production stage to finish before editing its plan." });
      const body = await readBody(req);
      const slug = safeSlug(body.slug || "");
      if (!slug) return json(res, 400, { error: "Enter a valid output folder name." });
      let inputPlan;
      try { inputPlan = typeof body.plan === "string" ? JSON.parse(body.plan) : body.plan; }
      catch { return json(res, 400, { error: "Visual plan is not valid JSON." }); }
      let plan;
      try { plan = normalizeVisualPlan(inputPlan); }
      catch (error) { return json(res, 400, { error: error.message }); }
      let previousEnd = -Infinity;
      for (let i = 0; i < plan.beats.length; i++) {
        const beat = plan.beats[i];
        const start = Number(beat.start), end = Number(beat.end);
        if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || start < previousEnd - 0.05) {
          return json(res, 400, { error: `Beat ${i + 1} has invalid or overlapping start/end times.` });
        }
        previousEnd = end;
      }
      const dir = path.join(outputRoot, slug);
      try { await fs.access(path.join(dir, "story.md")); }
      catch { return json(res, 404, { error: "Analyze this story first; no matching project folder exists." }); }
      for (const videoName of ["final.mp4", "final-silent.mp4"]) {
        try { await fs.access(path.join(dir, videoName)); return json(res, 409, { error: "This project already has a final video. Use a new output folder for a new render." }); }
        catch (error) { if (error.code !== "ENOENT") throw error; }
      }
      await fs.writeFile(path.join(dir, "visual-plan.json"), JSON.stringify(plan, null, 2) + "\n", "utf8");
      let archivedScene = null;
      try {
        const scenePath = path.join(dir, "index.html");
        archivedScene = path.join(dir, `index.stale-plan-${Date.now()}.html`);
        await fs.rename(scenePath, archivedScene);
        archivedScene = path.basename(archivedScene);
      } catch (error) { if (error.code === "ENOENT") archivedScene = null; else throw error; }
      return json(res, 200, { ok: true, beats: plan.beats.length, plan, archivedScene });
    }
    if (req.method === "POST" && url.pathname === "/api/audio") {
      if (activeJob) return json(res, 409, { error: "A production job is already running. Wait for it to finish before starting another heavy stage." });
      const body = await readBody(req);
      const script = String(body.script || "").trim();
      const spokenScript = normalizeNarrationForTTS(script);
      const slug = safeSlug(body.slug || "narration");
      const style = String(body.style || "storytelling");
      const performance = String(body.performance || "directed");
      const intensity = Number(body.intensity ?? 65);
      const pace = Number(body.pace ?? 1);
      if (!script || !spokenScript) return json(res, 400, { error: "Add spoken narration text. Control markers alone cannot be sent to Chatterbox." });
      if (script.length > 25000) return json(res, 400, { error: "Narration is limited to 25,000 characters per take." });
      if (!slug) return json(res, 400, { error: "Enter a valid audio output folder name." });
      if (!["storytelling", "conversational", "dramatic"].includes(style)) return json(res, 400, { error: "Choose a supported voice delivery style." });
      if (!["directed", "uniform"].includes(performance)) return json(res, 400, { error: "Choose directed or uniform cue handling." });
      if (!Number.isFinite(intensity) || intensity < 0 || intensity > 100) return json(res, 400, { error: "Expression intensity must be between 0 and 100." });
      if (!Number.isFinite(pace) || pace < 0.8 || pace > 1.2) return json(res, 400, { error: "Overall pace must be between 0.8× and 1.2×." });
      const dir = path.join(outputRoot, slug);
      await fs.mkdir(dir, { recursive: true });
      const audioPath = path.join(dir, "narration.wav");
      const sourceAudioPath = path.join(dir, "narration-source.wav");
      const scriptPath = path.join(dir, "narration.md");
      try { await fs.access(audioPath); return json(res, 409, { error: `An audio take already exists at ${audioPath}. Change the output folder to preserve it.` }); }
      catch (error) { if (error.code !== "ENOENT") throw error; }
      const id = crypto.randomBytes(6).toString("hex");
      const job = { id, status: "queued", logs: [], files: {}, error: null, child: null };
      jobs.set(id, job); activeJob = id;
      log(job, "Queued audio-only job. Scene generation, Ollama and video rendering will not run.");
      (async () => {
        try {
          job.status = "running";
          await fs.writeFile(scriptPath, script + "\n", "utf8");
          await ensureStudio(job);
          log(job, "Narration format: pasted UTF-8 text (Hindi/Devanagari, Hinglish/Roman Hindi, English terms and punctuation).");
          if (spokenScript !== script) log(job, "Removed non-spoken [PAUSE]/[END] markers before Chatterbox; [PAUSE] becomes natural punctuation.");
          log(job, `Voice style=${style}; cue handling=${performance}; expression intensity=${intensity}; pace=${pace}×.`);
          const response = await fetch(`${studioUrl}/api/audio`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ text: spokenScript, style, hindi_pronunciation: true, performance_mode: performance, expression_intensity: intensity }),
            signal: AbortSignal.timeout(Number(process.env.CHATTERBOX_TIMEOUT_MS || 1800000))
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(`Chatterbox Studio returned HTTP ${response.status}: ${payload?.error?.message || payload?.message || JSON.stringify(payload)}`);
          if (!payload.id) throw new Error("Chatterbox Studio returned no audio job ID.");
          const wavResponse = await fetch(`${studioUrl}/api/audio/${encodeURIComponent(payload.id)}/wav`, { signal: AbortSignal.timeout(30000) });
          if (!wavResponse.ok) throw new Error(`Could not download generated WAV (HTTP ${wavResponse.status}).`);
          await fs.writeFile(sourceAudioPath, Buffer.from(await wavResponse.arrayBuffer()));
          if (Math.abs(pace - 1) < 0.001) await fs.copyFile(sourceAudioPath, audioPath);
          else await run("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-i", sourceAudioPath, "-filter:a", `atempo=${pace}`, "-c:a", "pcm_s16le", audioPath], dir, job, `Apply overall pace ${pace}× without pitch shifting`);
          log(job, `Generated WAV: ${audioPath}`);
          log(job, `Source audio duration: ${Number(payload.duration || 0).toFixed(2)}s; final pace: ${pace}×. Listen to the result before approving it.`);
          job.files = {
            audio: `/files/${encodeURIComponent(slug)}/narration.wav`,
            sourceAudio: `/files/${encodeURIComponent(slug)}/narration-source.wav`,
            script: `/files/${encodeURIComponent(slug)}/narration.md`
          };
          job.status = "completed";
          log(job, "Audio-only stage completed. No scene or video was generated.");
        } catch (error) {
          job.status = "failed"; job.error = error.message; log(job, `FAILED: ${error.message}`);
          try { await fs.unlink(audioPath); } catch {}
        } finally { activeJob = null; job.child = null; }
      })();
      return json(res, 202, { id });
    }
    if (req.method === "POST" && url.pathname === "/api/run") {
      if (activeJob) return json(res, 409, { error: "A job is already running. Wait for it to finish before starting another model." });
      const body = await readBody(req);
      const title = String(body.title || "").trim();
      const story = String(body.story || "").trim();
      const voiceMode = String(body.voiceMode || "generate");
      const phase = String(body.phase || "all");
      const voiceScript = String(body.voiceScript || "").trim();
      const wavPath = String(body.wavPath || "").trim();
      const model = String(body.model || "").trim();
      const plannerModel = String(body.plannerModel || process.env.OLLAMA_PLANNER_MODEL || "qwen3.5:9b").trim();
      const slug = safeSlug(body.slug || title);
      const fps = Number(body.fps || 30);
      const requestedAudioOffset = Number(body.audioOffset ?? 0);
      const audioOffset = voiceMode === "generate" ? 0 : requestedAudioOffset;
      const exportName = phase === "render" ? safeSlug(body.exportName || "") : "";
      if (!title || !story) return json(res, 400, { error: "Add a title and story brief." });
      if (!slug) return json(res, 400, { error: "The output name must contain letters or numbers." });
      if (!model) return json(res, 400, { error: "Choose an installed Ollama model." });
      if (!["generate", "wav", "silent"].includes(voiceMode)) return json(res, 400, { error: "Choose a valid voice mode." });
      if (!["all", "analysis", "scene", "render"].includes(phase)) return json(res, 400, { error: "Choose analysis, scene, render, or legacy all-in-one mode." });
      if (phase === "render" && voiceMode === "generate") return json(res, 400, { error: "Render is audio-preserving: select an existing approved WAV or silent video. Generate narration in the separate audio-only panel." });
      if (phase === "render" && !exportName) return json(res, 400, { error: "Enter a new export filename for a retry; existing MP4s are never overwritten." });
      if (phase !== "analysis" && voiceMode === "generate" && !voiceScript) return json(res, 400, { error: "Add the narration script for Chatterbox." });
      if (phase !== "analysis" && voiceMode === "wav" && !wavPath) return json(res, 400, { error: "Enter the absolute path to an existing WAV file." });
      if (!Number.isFinite(fps) || fps < 10 || fps > 60) return json(res, 400, { error: "FPS must be between 10 and 60." });
      if (!Number.isFinite(requestedAudioOffset) || requestedAudioOffset < -5 || requestedAudioOffset > 5) return json(res, 400, { error: "Audio sync offset must be between -5 and +5 seconds." });
      const id = crypto.randomBytes(6).toString("hex");
      const job = { id, status: "queued", logs: [], files: {}, error: null, child: null, stage: phase, stages: freshStages() };
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
          const mp4Path = path.join(dir, phase === "render" ? `${exportName}${voiceMode === "silent" ? "-silent" : ""}.mp4` : (voiceMode === "silent" ? "final-silent.mp4" : "final.mp4"));
          const storyContent = `# ${title}\n\n${story}\n`;

          // Never overwrite a completed video. Reuse a narration WAV only when its source
          // script matches exactly; this avoids rerunning Chatterbox after a render failure.
          for (const name of (phase === "render" ? [path.basename(mp4Path)] : ["final.mp4", "final-silent.mp4"])) {
            try {
              await fs.access(path.join(dir, name));
              throw new Error(`Output already exists: ${path.join(dir, name)}. Choose a new output folder to preserve the previous production.`);
            } catch (error) {
              if (error.code !== "ENOENT") throw error;
            }
          }

          if (phase === "analysis") {
            setStage(job, "input", "passed"); setStage(job, "analysis", "running");
            try { const existing = await fs.readFile(storyPath, "utf8"); if (existing !== storyContent) throw new Error("This output folder contains a different story.md. Choose a new folder to preserve existing artifacts."); }
            catch (e) { if (e.code === "ENOENT") await fs.writeFile(storyPath, storyContent, { flag: "wx" }); else throw e; }
            const planPath = path.join(dir, "visual-plan.json");
            try { await fs.access(planPath); const archive = path.join(dir, "visual-plan.previous-" + Date.now() + ".json"); await fs.rename(planPath, archive); log(job, "Archived the prior plan as " + path.basename(archive)); }
            catch (e) { if (e.code !== "ENOENT") throw e; }
            try { await fs.access(htmlPath); const archive = path.join(dir, "index.pre-analysis-" + Date.now() + ".html"); await fs.rename(htmlPath, archive); log(job, "Archived the prior scene as " + path.basename(archive)); }
            catch (e) { if (e.code !== "ENOENT") throw e; }
            const node = process.execPath;
            const args = ["scripts/ollama-session.mjs", "--", "node", "scripts/generate.mjs", "--story", storyPath, "--planner-model", plannerModel, "--model", model, "--out", htmlPath, "--plan-file", planPath, "--phase", "plan"];
            await run(node, args, root, job, "Visual analysis (plan only; model unload before next stage)");
            const plan = JSON.parse(await fs.readFile(planPath, "utf8"));
            setStage(job, "analysis", "passed"); setStage(job, "planValidation", "passed", `${plan.beats.length} beats ending at ${plan.beats.at(-1)?.end}s`);
            job.files = { plan: `/files/${encodeURIComponent(slug)}/visual-plan.json` };
            job.status = "completed";
            log(job, "ANALYSIS STAGE VALIDATED. Plan saved for review; scene generation, narration and rendering were not started.");
            return;
          }
          setStage(job, "input", "passed");
          const narrationContent = voiceScript ? voiceScript + "\n" : "";
          const finalWavPath = path.join(dir, "final.narration.wav");
          let reuseNarration = false;
          if (phase === "all" && voiceMode === "generate") try {
            await fs.access(finalWavPath);
            if (voiceMode !== "generate") throw new Error(`Narration WAV already exists: ${finalWavPath}. Choose a new output folder to avoid overwriting it.`);
            let savedNarration;
            try { savedNarration = await fs.readFile(narrationPath, "utf8"); }
            catch { throw new Error(`Narration WAV exists at ${finalWavPath}, but its source script is missing. Preserve it and choose a new output folder.`); }
            if (savedNarration !== narrationContent) throw new Error("Narration WAV exists, but narration.md does not match the submitted script. Choose a new output folder to preserve the existing voice.");
            reuseNarration = true;
            log(job, "Reusing the existing narration WAV; Chatterbox will not run again.");
          } catch (error) {
            if (phase !== "analysis" && error.code !== "ENOENT") throw error;
          }

          let reuseScene = false;
          if (phase !== "scene" && phase !== "render") try {
            await fs.access(htmlPath);
            const savedStory = await fs.readFile(storyPath, "utf8");
            if (savedStory !== storyContent) throw new Error(`A scene already exists in ${dir}, but its saved story does not match this brief. Choose a new output folder to avoid mixing productions.`);
            reuseScene = true;
            log(job, "Reusing the existing scene because story.md matches; skipping Ollama generation.");
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
          }

          try { const saved = await fs.readFile(storyPath, "utf8"); if (saved !== storyContent) throw new Error("Saved story.md differs from the submitted story. Choose a new output folder; existing files are preserved."); }
          catch (e) { if (e.code === "ENOENT") await fs.writeFile(storyPath, storyContent, { flag: "wx" }); else throw e; }
          if (phase === "all" && voiceMode === "generate") await fs.writeFile(narrationPath, narrationContent, "utf8");
          const node = process.execPath;
          const planPath = path.join(dir, "visual-plan.json");
          if (phase === "scene" || phase === "render") {
            const plan = JSON.parse(await fs.readFile(planPath, "utf8"));
            const storyFingerprint = crypto.createHash("sha256").update(storyContent).digest("hex");
            if (plan.story_fingerprint !== storyFingerprint) throw new Error("Saved visual plan is stale for this story. Run analysis again before scene generation.");
            if (phase === "render") {
              const source = await fs.readFile(htmlPath, "utf8");
              const planFingerprint = crypto.createHash("sha256").update(JSON.stringify(plan)).digest("hex");
              if (!source.includes(`name="tdc-story-fingerprint" content="${storyFingerprint}"`) || !source.includes(`name="tdc-plan-fingerprint" content="${planFingerprint}"`)) throw new Error("Saved scene does not match the current approved story/plan. Regenerate the scene first.");
              if (voiceMode === "wav") await fs.access(path.resolve(wavPath));
              setStage(job, "scene", "passed"); setStage(job, "sceneValidation", "passed"); setStage(job, "audio", voiceMode === "silent" ? "skipped" : "passed"); setStage(job, "render", "running");
            } else setStage(job, "scene", "running");
          } else if (phase === "all") setStage(job, "analysis", "running");
          const generateArgs = ["scripts/ollama-session.mjs", "--", "node", "scripts/generate.mjs", "--story", storyPath, "--planner-model", plannerModel, "--model", model, "--out", htmlPath, "--plan-file", planPath];
          if (phase === "analysis") generateArgs.push("--phase", "plan");
          else if (phase === "scene") generateArgs.push("--phase", "scene");
          if (phase === "render") { reuseScene = true; log(job, "Rendering the saved fingerprint-matched scene; Ollama and Chatterbox will not run."); }
          if (!reuseScene) {
            try {
              await run(node, generateArgs, root, job, "Ollama scene generation (model unload after scene generation)");
            } catch (error) {
              const recentOutput = job.logs.slice(-140).join("\n");
              const validationFailure = /Generated scene failed browser render-only validation|Generated HTML failed export validation|Model output did not start with|Ollama returned no message content|Math\.random\(\), forbidden|missing native \?render=1 render-only mode/i.test(recentOutput);
              const internalRepairExhausted = /Scene generation failed after one targeted repair|Scene generation stopped because Ollama connectivity failed|OLLAMA_UNAVAILABLE/i.test(recentOutput);
              if (!validationFailure || internalRepairExhausted) throw error;
              const archivedScene = path.join(dir, `index.invalid-${Date.now()}.log.html`);
              // generate.mjs validates before writing, but preserve any unexpected partial artifact safely.
              try { await fs.rename(htmlPath, archivedScene); log(job, `Archived invalid generated scene as ${path.basename(archivedScene)}.`); }
              catch (archiveError) { if (archiveError.code !== "ENOENT") throw archiveError; }
              const repairNote = [
                "AUTOMATIC FIRST-PASS REPAIR. Exact validation failure: " + (summarizeSceneFailure(job.logs.slice(-100).join("\n")) || "HTML failed validation") + ". Fix this specific failure first.",
                "If Math.random() was detected, remove every call completely. Use fixed coordinates, a seeded deterministic generator initialized once, or values derived directly from absolute time. Never use random values or accumulated state in renderAt().",
                "Every visible value must be a pure function of absolute timestamp; renderAt(seconds) must reset the full scene state and reproduce identical pixels when called repeatedly for the same timestamp.",
                "Return a complete HTML document beginning with <!doctype html>, include window.renderAt, window.getDuration, and render-only mode via new URLSearchParams(window.location.search).get('render').",
                "Keep the original story and narration meaning. Do not weaken or bypass any validation."
              ].join("\n");
              log(job, "Initial scene failed HTML/determinism validation; starting one targeted repair, then a single fallback-model attempt if needed. Narration is preserved.");
              await runSceneRepair(node, generateArgs, repairNote, root, job, "Repair invalid initial scene");
            }
          }
          if (phase === "all") {
            const completedPlan = JSON.parse(await fs.readFile(planPath, "utf8"));
            setStage(job, "analysis", "passed", "Story analysis completed");
            setStage(job, "planValidation", "passed", `${completedPlan.beats.length} validated beats`);
            setStage(job, "scene", "passed");
            setStage(job, "sceneValidation", "passed");
            setStage(job, "audio", voiceMode === "generate" ? "running" : "skipped", voiceMode === "generate" ? "Generating narration after scene validation" : "Narration not requested");
            setStage(job, "render", "running");
          }
          if (phase === "scene") {
            const plan = JSON.parse(await fs.readFile(planPath, "utf8"));
            const storyFingerprint = crypto.createHash("sha256").update(storyContent).digest("hex");
            const planFingerprint = crypto.createHash("sha256").update(JSON.stringify(plan)).digest("hex");
            const scene = await fs.readFile(htmlPath, "utf8");
            if (!scene.includes(`name="tdc-story-fingerprint" content="${storyFingerprint}"`) || !scene.includes(`name="tdc-plan-fingerprint" content="${planFingerprint}"`)) throw new Error("Generated scene fingerprint does not match the approved plan.");
            setStage(job, "scene", "passed"); setStage(job, "sceneValidation", "passed");
            job.files = { plan: `/files/${encodeURIComponent(slug)}/visual-plan.json`, scene: `/files/${encodeURIComponent(slug)}/index.html` };
            job.status = "completed"; log(job, "SCENE STAGE VALIDATED. Rendering and narration were not started."); return;
          }
          if (phase === "render") {
            if (voiceMode === "wav") await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", path.resolve(wavPath), "--fps", String(fps), "--audio-offset", String(audioOffset)], root, job, "Render and QC with approved existing WAV");
            else await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--fps", String(fps), "--audio-offset", String(audioOffset)], root, job, "Render and QC silent video");
            setStage(job, "render", "passed"); setStage(job, "videoQc", "passed"); setStage(job, "export", "passed");
          } else if (voiceMode === "generate") {
            if (reuseNarration) {
              try {
                await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", finalWavPath, "--fps", String(fps), "--audio-offset", String(audioOffset)], root, job, "Render with reused narration WAV");
              } catch (error) {
                const recentLogs = job.logs.slice(-100);
                const deterministicFailure = recentLogs.some(line => line.includes("Determinism check failed"));
                const endingFailure = recentLogs.some(line => line.includes("Visual ending check failed"));
                const densityFailure = recentLogs.some(line => line.includes("Visual density QA failed"));
                const offlineFailure = recentLogs.some(line => line.includes("Offline policy failed") || line.includes("Browser errors detected"));
                if (!deterministicFailure && !endingFailure && !densityFailure && !offlineFailure) throw error;
                const archivedScene = path.join(dir, `index.failed-${Date.now()}.html`);
                await fs.rename(htmlPath, archivedScene);
                const repairNote = densityFailure
                  ? "VISUAL DENSITY REPAIR: sampled frames are too sparse. Enlarge the dominant story-specific action; preserve deterministic seeking, offline behavior and the export contract."
                  : endingFailure
                    ? "The previous export failed visual-ending QA. Keep meaningful narration-synchronized motion through the last explanatory beat, then resolve into a takeaway only in the final 1.5–2.5 seconds. Do not freeze an end card."
                    : offlineFailure
                      ? "OFFLINE / RUNTIME REPAIR: fix browser errors or external requests without changing the story. Keep the scene self-contained and deterministic."
                      : "DETERMINISM REPAIR: derive every visual property from absolute time and reset the full scene state in renderAt(t).";
                log(job, `${endingFailure ? "Visual ending" : "Determinism"} QA failed; archived scene as ${path.basename(archivedScene)} and attempting one targeted scene repair while preserving narration.`);
                await runSceneRepair(node, generateArgs, repairNote, root, job, endingFailure ? "Repair frozen visual ending" : "Regenerate nondeterministic scene");
                await retryExportWithEndingRepair(node, generateArgs, htmlPath, mp4Path, finalWavPath, fps, dir, root, job);
              }
            } else {
              await ensureStudio(job);
              try {
                await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--voice-script", narrationPath, "--fps", String(fps), "--style", String(body.style || "storytelling"), "--performance", String(body.performance || "directed"), "--expression-intensity", String(body.intensity ?? 65)], root, job, "Chatterbox narration, then video render");
              } catch (error) {
                const recent = job.logs.slice(-120).join("\n");
                const endingFailure = recent.includes("Visual ending check failed");
                const densityFailure = recent.includes("Visual density QA failed");
                const deterministicFailure = recent.includes("Determinism check failed");
                const offlineFailure = recent.includes("Offline policy failed") || recent.includes("Browser errors detected");
                if (!endingFailure && !densityFailure && !deterministicFailure && !offlineFailure) throw error;
                try { await fs.access(finalWavPath); }
                catch { throw new Error("Visual export failed before narration was saved; Chatterbox will not be rerun by this visual repair."); }
                const archivedScene = path.join(dir, `index.failed-${Date.now()}.html`);
                await fs.rename(htmlPath, archivedScene);
                const repairNote = densityFailure
                  ? "VISUAL DENSITY REPAIR: sampled frames are too sparse. Enlarge the dominant story-specific action and use the vertical frame intentionally; preserve the story, deterministic export contract and offline policy."
                  : endingFailure
                    ? "VISUAL ENDING REPAIR: keep meaningful causal action through the last explanatory beat; resolve into the takeaway only in the final 1.5–2.5 seconds. No frozen end card."
                    : deterministicFailure
                      ? "DETERMINISM REPAIR: reset visible state in renderAt(t) and derive every property from absolute time."
                      : "OFFLINE / RUNTIME REPAIR: fix browser errors or external requests while preserving story-specific visuals and deterministic rendering."; 
                log(job, "Visual QA failed after narration was saved; repairing only the scene and reusing final.narration.wav unchanged.");
                await runSceneRepair(node, generateArgs, repairNote, root, job, "Repair scene with preserved Chatterbox narration");
                if (endingFailure) await retryExportWithEndingRepair(node, generateArgs, htmlPath, mp4Path, finalWavPath, fps, dir, root, job);
                else await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", finalWavPath, "--fps", String(fps), "--audio-offset", String(audioOffset)], root, job, "Render repaired scene with preserved narration WAV");
              }
            }
          } else if (voiceMode === "wav") {
            const wavExportArgs = ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--audio", path.resolve(wavPath), "--fps", String(fps), "--audio-offset", String(audioOffset)];
            try {
              await run(node, wavExportArgs, root, job, "Render with existing WAV narration");
            } catch (error) {
              const recent = job.logs.slice(-120).join("\n");
              const densityFailure = recent.includes("Visual density QA failed");
              const determinismFailure = recent.includes("Determinism check failed");
              const endingFailure = recent.includes("Visual ending check failed");
              const offlineFailure = recent.includes("Offline policy failed") || recent.includes("Browser errors detected");
              if (!densityFailure && !determinismFailure && !endingFailure && !offlineFailure) throw error;

              const archivedScene = path.join(dir, `index.failed-visual-qa-${Date.now()}.html`);
              await fs.rename(htmlPath, archivedScene);
              const repairNote = densityFailure
                ? "VISUAL DENSITY REPAIR: the renderer found that too many sampled frames are visually sparse. Recompose the dominant subject so it is recognisable and fills the vertical frame; enlarge the main mechanism and use the central visual area. Background texture and tiny labels do not count. Keep distinct story-specific beats, deterministic rendering, the offline policy, and the exact export contract."
                : endingFailure
                  ? "VISUAL ENDING REPAIR: the ending freezes for more than 2.5 seconds. Keep meaningful narration-synchronized action until the final 1.5–2.5 seconds, then resolve into a concise takeaway. Do not use a long static end card. Preserve the story, deterministic renderAt contract, and offline policy."
                  : determinismFailure
                    ? "DETERMINISM REPAIR: renderAt(t) must reset all visible state and derive every visual property from absolute timestamp t. The same timestamp must always reproduce identical pixels. Preserve the story and offline policy."
                    : "OFFLINE / RUNTIME REPAIR: remove external network requests and fix browser runtime errors. Bundle all required dependencies locally, preserve the story, use deterministic timestamp-driven rendering, and keep the required renderAt/getDuration export contract.";
              log(job, `Visual QA failed (${densityFailure ? "density" : endingFailure ? "ending" : determinismFailure ? "determinism" : "offline/runtime"}); archived scene as ${path.basename(archivedScene)} and attempting one targeted visual-only repair. Existing narration WAV will be reused unchanged.`);
              await runSceneRepair(node, generateArgs, repairNote, root, job, "Repair scene using existing narration WAV");
              await run(node, wavExportArgs, root, job, "Render repaired scene with the same WAV narration");
            }
          } else {
            await run(node, ["scripts/export.mjs", "--html", htmlPath, "--out", mp4Path, "--fps", String(fps), "--audio-offset", String(audioOffset)], root, job, "Silent video render");
          }
          if (phase === "all") { setStage(job, "scene", "passed"); setStage(job, "sceneValidation", "passed"); setStage(job, "audio", voiceMode === "generate" ? "passed" : "skipped"); setStage(job, "render", "passed"); setStage(job, "videoQc", "passed"); setStage(job, "export", "passed"); }
          job.files = {
            plan: `/files/${encodeURIComponent(slug)}/visual-plan.json`,
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
          const activeStage = ["analysis", "scene", "audio", "render"].find(key => job.stages?.[key]?.status === "running");
          if (activeStage) setStage(job, activeStage, "failed", error.message);
          else if (job.stage === "analysis") setStage(job, "analysis", "failed", error.message);
          else if (job.stage === "scene") setStage(job, "scene", "failed", error.message);
          else if (job.stage === "render") setStage(job, "render", "failed", error.message);
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
      return await serveFile(res, path.join(outputRoot, parts[0], parts[1]), url.searchParams.get("download") === "1");
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
