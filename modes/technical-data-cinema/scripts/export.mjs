#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { normalizeNarrationForTTS } from "./narration-text.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const args = process.argv.slice(2);
function arg(name, fallback) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; }
function has(name) { return args.includes(name); }
function fail(message) { console.error(message); process.exit(2); }

const htmlArg = arg("--html"), outArg = arg("--out");
const audioArg = arg("--audio"), scriptArg = arg("--voice-script");
const audioOffset = Number(arg("--audio-offset", "0"));
if (!Number.isFinite(audioOffset) || audioOffset < -5 || audioOffset > 5) fail("--audio-offset must be between -5 and 5 seconds.");
if (has("--help")) {
  console.log("Usage: npm run export -- --html <scene.html> --out <final.mp4> [--audio narration.wav | --voice-script narration.md] [--studio-url http://127.0.0.1:8765] [--fps 30]");
  console.log("Use --audio to mux approved narration, or --voice-script to generate it with the existing Chatterbox Studio API.");
  process.exit(0);
}
if (!htmlArg || !outArg) fail("Usage: node scripts/export.mjs --html output/<story>/index.html --out output/<story>/final.mp4 [--audio narration.wav | --voice-script narration.md] [--studio-url http://127.0.0.1:8765] [--fps 30]");
if (audioArg && scriptArg) fail("Choose only one of --audio or --voice-script.");
const htmlPath = path.resolve(process.cwd(), htmlArg);
const outPath = path.resolve(process.cwd(), outArg);
await fs.access(htmlPath);
await fs.mkdir(path.dirname(outPath), { recursive: true });
let audioPath = audioArg ? path.resolve(process.cwd(), audioArg) : null;
if (audioPath) await fs.access(audioPath);

if (scriptArg) {
  const scriptPath = path.resolve(process.cwd(), scriptArg);
  const sourceScript = (await fs.readFile(scriptPath, "utf8")).trim();
  const script = normalizeNarrationForTTS(sourceScript);
  if (!script) fail("Narration script contains no spoken text after removing control markers.");
  if (script !== sourceScript) console.log("Removed non-spoken [PAUSE]/[END] markers before sending narration to Chatterbox.");
  const studioUrl = (arg("--studio-url", process.env.CHATTERBOX_STUDIO_URL || "http://127.0.0.1:8765")).replace(/\/$/, "");
  const body = { text: script, style: arg("--style", "storytelling"), hindi_pronunciation: arg("--pronunciation", "hindi_mixed") !== "original", performance_mode: arg("--performance", "directed"), expression_intensity: Number(arg("--expression-intensity", "65")) };
  audioPath = path.join(path.dirname(outPath), path.basename(outPath, path.extname(outPath)) + ".narration.wav");
  let apiFailure = null;
  try {
    const response = await fetch(studioUrl + "/api/audio", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(Number(process.env.CHATTERBOX_TIMEOUT_MS || 1800000)) });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) { const message = result?.error?.message || result?.message || JSON.stringify(result); fail("Chatterbox narration failed (HTTP " + response.status + "): " + message); }
    if (!result.id) fail("Chatterbox Studio returned no audio job ID.");
    const audioResponse = await fetch(studioUrl + "/api/audio/" + encodeURIComponent(result.id) + "/wav", { signal: AbortSignal.timeout(30000) });
    if (!audioResponse.ok) throw new Error("audio download returned HTTP " + audioResponse.status);
    await fs.writeFile(audioPath, Buffer.from(await audioResponse.arrayBuffer()));
    console.log("Generated narration using existing Chatterbox Studio adapter: " + audioPath);
    console.log("Voice profile: " + (result.voice || "configured production reference") + "; duration: " + Number(result.duration || 0).toFixed(2) + "s; performance: " + (result.performance_mode || "directed"));
  } catch (error) {
    apiFailure = error;
    console.error("Chatterbox API became unavailable (" + error.message + "). Falling back to the same local production voice adapter in an isolated process; cached WAV/alignment will be reused if present.");
    const repoRoot = path.resolve(root, "../..");
    let python = process.env.STUDIO_PYTHON || "";
    const venvPython = path.join(repoRoot, ".venv", "bin", "python");
    if (!python) { try { await fs.access(venvPython); python = venvPython; } catch { python = process.env.PYTHON || "python3"; } }
    const code = ["import json, sys", "from engine.studio.server import script_to_audio", "result = script_to_audio(json.load(sys.stdin))", "print('TDC_AUDIO_RESULT=' + json.dumps(result, ensure_ascii=False))"].join("\n");
    const direct = spawnSync(python, ["-u", "-c", code], { cwd: repoRoot, env: { ...process.env, CHATTERBOX_MODEL_VARIANT: process.env.CHATTERBOX_MODEL_VARIANT || "dedicated_hindi", PYTHONPATH: repoRoot, PYTHONUNBUFFERED: "1" }, input: JSON.stringify(body), encoding: "utf8", timeout: Number(process.env.CHATTERBOX_TIMEOUT_MS || 1800000), maxBuffer: 20 * 1024 * 1024 });
    if (direct.stdout) for (const line of direct.stdout.split(/\r?\n/)) if (line && !line.startsWith("TDC_AUDIO_RESULT=")) console.log("[local voice adapter] " + line);
    if (direct.error || direct.status !== 0) { const detail = direct.error?.message || (direct.stderr || direct.stdout || "no diagnostic output").slice(-3000); fail("Chatterbox API failed (" + apiFailure.message + ") and isolated local synthesis also failed: " + detail); }
    const marker = (direct.stdout || "").split(/\r?\n/).find(line => line.startsWith("TDC_AUDIO_RESULT="));
    if (!marker) fail("Isolated local voice adapter finished without returning an audio job ID.");
    let result; try { result = JSON.parse(marker.slice("TDC_AUDIO_RESULT=".length)); } catch { fail("Isolated local voice adapter returned invalid job metadata."); }
    const cachedAudio = path.join(repoRoot, "output", "audio", result.id, "narration.wav");
    try { await fs.access(cachedAudio); } catch { fail("Local voice adapter reported success but narration WAV is missing: " + cachedAudio); }
    await fs.copyFile(cachedAudio, audioPath);
    console.log("Generated narration through isolated local adapter: " + audioPath + "; duration " + Number(result.duration || 0).toFixed(2) + "s");
  }
}
const renderArgs = ["scripts/render.mjs", "--html", htmlPath, "--out", outPath, "--fps", arg("--fps", "30")];
renderArgs.push("--audio-offset", String(audioOffset));
if (audioPath) renderArgs.push("--audio", audioPath);
if (arg("--duration")) renderArgs.push("--duration", arg("--duration"));
if (has("--allow-low-visual-density")) renderArgs.push("--allow-low-visual-density");
const result = spawnSync(process.execPath, renderArgs, { stdio: "inherit", cwd: root });
if (result.error) fail(`Could not start renderer: ${result.error.message}`);
process.exit(result.status ?? 1);
