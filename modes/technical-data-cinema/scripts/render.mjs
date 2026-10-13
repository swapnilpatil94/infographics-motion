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
  const sceneUrl = pathToFileURL(htmlPath);\n  sceneUrl.searchParams.set("render", "1");\n  await page.goto(sceneUrl.href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  const contract = await page.evaluate(() => ({
    renderAt: typeof window.renderAt,
    getDuration: typeof window.getDuration,
    duration: typeof window.getDuration === "function" ? window.getDuration() : null
  }));
  if (contract.renderAt !== "function" || contract.getDuration !== "function" || !Number.isFinite(contract.duration) || contract.duration <= 0) {
    fail("HTML must define window.renderAt(seconds) and window.getDuration() returning a positive duration.");
  }
  duration = forcedDuration ?? contract.duration;
  if (duration > 600) fail("Duration must not exceed 600 seconds.");
  frameCount = Math.ceil(duration * fps);

  // Determinism check: the same timestamp must yield byte-identical PNG output
  // after visiting a different timestamp. This catches state accumulated by frame loops.
  await page.evaluate(() => window.renderAt(0));
  const first = await page.screenshot({ type: "png", animations: "disabled" });
  await page.evaluate(time => window.renderAt(time), Math.min(duration * 0.63, duration - 0.001));
  await page.evaluate(() => window.renderAt(0));
  const second = await page.screenshot({ type: "png", animations: "disabled" });
  const hash = buffer => crypto.createHash("sha256").update(buffer).digest("hex");
  if (hash(first) !== hash(second)) {
    fail("Determinism check failed: renderAt(0) produced different pixels after seeking. Derive all scene state from absolute time.");
  }
  console.log("Determinism check passed (same timestamp → identical screenshot).");
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

const ffmpegArgs = ["-y", "-hide_banner", "-loglevel", "warning", "-framerate", String(fps), "-i", path.join(frameDir, "frame-%06d.png"), "-frames:v", String(frameCount)];
if (audioPath) ffmpegArgs.push("-i", audioPath, "-af", "apad");
ffmpegArgs.push("-t", String(duration), "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart");
if (audioPath) ffmpegArgs.push("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2");
ffmpegArgs.push(outPath);
const result = spawnSync("ffmpeg", ffmpegArgs, { stdio: "inherit" });
if (result.error) { console.error("Could not run ffmpeg. Install it with: brew install ffmpeg"); process.exit(1); }
if (result.status !== 0) process.exit(result.status ?? 1);
console.log(`Exported: ${outPath}`);
