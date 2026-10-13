#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import process from "node:process";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";

const args = process.argv.slice(2);
function arg(name, fallback) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; }
function fail(message) { console.error(message); process.exit(2); }
const htmlArg = arg("--html"), outArg = arg("--out");
if (!htmlArg || !outArg) fail("Usage: node scripts/render.mjs --html <index.html> --out <final.mp4> [--audio narration.wav] [--fps 30] [--duration seconds]");
const htmlPath = path.resolve(process.cwd(), htmlArg);
const outPath = path.resolve(process.cwd(), outArg);
const audioPath = arg("--audio") ? path.resolve(process.cwd(), arg("--audio")) : null;
const fps = Number(arg("--fps", "30"));
const forcedDuration = arg("--duration") ? Number(arg("--duration")) : null;
if (!Number.isFinite(fps) || fps < 1 || fps > 60) fail("--fps must be between 1 and 60.");
if (forcedDuration !== null && (!Number.isFinite(forcedDuration) || forcedDuration <= 0 || forcedDuration > 600)) fail("--duration must be > 0 and <= 600 seconds.");
await fs.access(htmlPath);
if (audioPath) await fs.access(audioPath);
let audioDuration = 0;
if (audioPath) {
  const probe = spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audioPath], { encoding: "utf8" });
  if (probe.error || probe.status !== 0 || !Number.isFinite(Number(probe.stdout.trim())) || Number(probe.stdout.trim()) <= 0) {
    fail(`Could not read narration duration with ffprobe. Check that FFmpeg is installed and the audio is valid. ${probe.stderr || probe.error?.message || ""}`);
  }
  audioDuration = Number(probe.stdout.trim());
  if (forcedDuration !== null && forcedDuration + 0.02 < audioDuration) {
    fail(`--duration (${forcedDuration}s) is shorter than narration (${audioDuration.toFixed(2)}s); refusing to cut off voice.`);
  }
}
const outDir = path.dirname(outPath), frameDir = path.join(outDir, "frames");
await fs.mkdir(frameDir, { recursive: true });
let duration, frameCount;
const browserErrors = [];
const externalRequests = [];
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2, reducedMotion: "reduce" });
  page.on("console", message => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", error => browserErrors.push(`page: ${error.message}`));
  page.on("request", request => {
    if (/^https?:/i.test(request.url())) externalRequests.push(request.url());
  });
  const sceneUrl = pathToFileURL(htmlPath);
  sceneUrl.searchParams.set("render", "1");
  await page.goto(sceneUrl.href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  const contract = await page.evaluate(() => ({
    renderAt: typeof window.renderAt,
    getDuration: typeof window.getDuration,
    duration: typeof window.getDuration === "function" ? window.getDuration() : null
  }));
  if (contract.renderAt !== "function" || contract.getDuration !== "function" || !Number.isFinite(contract.duration) || contract.duration <= 0) {
    fail("HTML must define window.renderAt(seconds) and window.getDuration() returning a positive duration.");
  }
  if (contract.duration > 600) fail("Scene duration must not exceed 600 seconds.");
  duration = forcedDuration ?? Math.max(contract.duration, audioDuration);
  if (duration > 600) fail("Final duration must not exceed 600 seconds.");
  frameCount = Math.ceil(duration * fps);

  await page.evaluate(() => window.renderAt(0));
  const first = await page.screenshot({ type: "png", animations: "disabled" });
  await page.evaluate(time => window.renderAt(time), Math.min(contract.duration * 0.63, contract.duration - 0.001));
  await page.evaluate(() => window.renderAt(0));
  const hash = buffer => crypto.createHash("sha256").update(buffer).digest("hex");
  if (hash(first) !== hash(await page.screenshot({ type: "png", animations: "disabled" }))) {
    fail("Determinism check failed: renderAt(0) produced different pixels after seeking. Derive all scene state from absolute time.");
  }
  console.log("Determinism check passed (same timestamp → identical screenshot).");
  if (audioDuration > contract.duration) console.log(`Narration (${audioDuration.toFixed(2)}s) is longer than the scene (${contract.duration.toFixed(2)}s); holding the final scene while audio finishes.`);
  console.log(`Rendering ${frameCount} frames at ${fps} fps (1080×1920), ${duration.toFixed(2)} seconds`);

  for (let i = 0; i < frameCount; i++) {
    await page.evaluate(time => window.renderAt(time), i / fps);
    await page.screenshot({ path: path.join(frameDir, `frame-${String(i).padStart(6, "0")}.png`), type: "png", animations: "disabled" });
    if (i % Math.max(1, Math.floor(fps * 5)) === 0 || i === frameCount - 1) process.stdout.write(`\rFrames: ${i + 1}/${frameCount}`);
  }
  process.stdout.write("\n");
  if (externalRequests.length) throw new Error(`Offline policy failed; external network requests detected: ${[...new Set(externalRequests)].join(", ")}`);
  if (browserErrors.length) throw new Error(`Browser errors detected:\n- ${[...new Set(browserErrors)].join("\n- ")}`);
} finally {
  await browser.close();
}

const ffmpegArgs = ["-y", "-hide_banner", "-loglevel", "warning", "-framerate", String(fps), "-i", path.join(frameDir, "frame-%06d.png")];
if (audioPath) ffmpegArgs.push("-i", audioPath);
// Output options must follow every input; placing -frames:v before the audio input
// makes FFmpeg incorrectly treat it as an input option.
ffmpegArgs.push("-frames:v", String(frameCount), "-t", String(duration));
if (audioPath) ffmpegArgs.push("-af", "apad");
ffmpegArgs.push("-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart");
if (audioPath) ffmpegArgs.push("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2");
ffmpegArgs.push(outPath);
const result = spawnSync("ffmpeg", ffmpegArgs, { stdio: "inherit" });
if (result.error) { console.error("Could not run ffmpeg. Install it with: brew install ffmpeg"); process.exit(1); }
if (result.status !== 0) process.exit(result.status ?? 1);
console.log(`Exported: ${outPath}`);
