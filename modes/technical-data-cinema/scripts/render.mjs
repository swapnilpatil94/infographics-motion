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
const audioOffset = Number(arg("--audio-offset", "0"));
if (!Number.isFinite(audioOffset) || audioOffset < -5 || audioOffset > 5) fail("--audio-offset must be between -5 and 5 seconds.");
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
  if (audioOffset < 0 && Math.abs(audioOffset) >= audioDuration) fail("Negative --audio-offset must be smaller than the narration duration.");
  const effectiveAudioDuration = audioDuration + audioOffset;
  if (forcedDuration !== null && forcedDuration + 0.02 < effectiveAudioDuration) {
    fail(`--duration (${forcedDuration}s) is shorter than adjusted narration (${effectiveAudioDuration.toFixed(2)}s); refusing to cut off voice.`);
  }
}
const outDir = path.dirname(outPath), frameDir = path.join(outDir, "frames");
await fs.mkdir(frameDir, { recursive: true });
let duration, frameCount;
const browserErrors = [];
const externalRequests = [];
const browser = await chromium.launch({ headless: true, args: ["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
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
  duration = forcedDuration ?? Math.max(contract.duration, audioDuration + audioOffset);
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

  // Audit the actual canvas content at representative points. This catches a
  // technically valid but visually empty scene (tiny labels/lines on a blank
  // frame), which syntax and determinism checks cannot detect.
  if (!args.includes("--allow-low-visual-density")) {
    const auditTimes = [0.03, 0.2, 0.4, 0.6, 0.8, 0.95].map(f => Math.min(contract.duration - 0.001, contract.duration * f));
    const audit = await page.evaluate(times => {
      const canvas = [...document.querySelectorAll("canvas")].sort((a, b) => (b.width * b.height) - (a.width * a.height))[0];
      if (!canvas || !canvas.width || !canvas.height) return { supported: false, reason: "no canvas found" };
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return { supported: false, reason: "canvas 2D pixels unavailable" };
      const frames = [];
      for (const time of times) {
        window.renderAt(time);
        let pixels;
        try { pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data; }
        catch { return { supported: false, reason: "canvas pixels are not readable" }; }
        // Estimate the dominant background colour from a coarse sample so a
        // flat light or dark background does not count as visual content.
        const histogram = new Map();
        const quantize = (r, g, b, a) => [r >> 4, g >> 4, b >> 4, a >> 6].join(",");
        for (let i = 0; i < pixels.length; i += 32) {
          const key = quantize(pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]);
          histogram.set(key, (histogram.get(key) || 0) + 1);
        }
        let background = "0,0,0,0", best = -1;
        for (const [key, count] of histogram) if (count > best) { background = key; best = count; }
        const bg = background.split(",").map(Number);
        let foreground = 0, minX = canvas.width, minY = canvas.height, maxX = -1, maxY = -1;
        const stride = 8; // every second pixel in each dimension
        for (let y = 0; y < canvas.height; y += 2) {
          for (let x = 0; x < canvas.width; x += 2) {
            const i = (y * canvas.width + x) * 4;
            const different = Math.max(
              Math.abs((pixels[i] >> 4) - bg[0]) * 16,
              Math.abs((pixels[i + 1] >> 4) - bg[1]) * 16,
              Math.abs((pixels[i + 2] >> 4) - bg[2]) * 16,
              Math.abs((pixels[i + 3] >> 6) - bg[3]) * 64
            ) >= 24;
            if (!different) continue;
            foreground++;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
        const sampleCount = Math.ceil(canvas.width / 2) * Math.ceil(canvas.height / 2);
        frames.push({
          time: Number(time.toFixed(2)),
          coverage: foreground / sampleCount,
          width: maxX >= minX ? (maxX - minX + 1) / canvas.width : 0,
          height: maxY >= minY ? (maxY - minY + 1) / canvas.height : 0
        });
      }
      return { supported: true, frames };
    }, auditTimes);
    await page.evaluate(() => window.renderAt(0));
    if (!audit.supported) {
      console.warn(`Visual density audit skipped: ${audit.reason}. Use sampled-frame review for SVG/DOM-only scenes.`);
    } else {
      const weak = audit.frames.filter(frame => frame.coverage < 0.0025 || frame.width < 0.3 || frame.height < 0.18);
      console.log(`Visual density audit: ${audit.frames.length - weak.length}/${audit.frames.length} sampled frames meet minimum content coverage.`);
      if (weak.length >= 4) {
        const details = weak.map(frame => `${frame.time}s (coverage ${(frame.coverage * 100).toFixed(2)}%, bounds ${(frame.width * 100).toFixed(0)}%×${(frame.height * 100).toFixed(0)}%)`).join("; ");
        fail(`Visual density QA failed: ${weak.length}/${audit.frames.length} sampled frames are too sparse. Main artwork must be phone-readable and occupy the frame, not consist of tiny labels/lines on empty space. Weak frames: ${details}. Improve the scene or use --allow-low-visual-density only for an intentionally minimalist concept.`);
      }
    }
  } else {
    console.warn("Visual density QA explicitly bypassed with --allow-low-visual-density.");
  }

  // With narration, reject a dead visual ending instead of exporting a long frozen
  // takeaway card. Sample the final 3.5 seconds at half-second intervals.
  if (audioPath && duration >= 3.5) {
    const tailHashes = [];
    for (let sample = 0; sample <= 7; sample++) {
      const t = duration - 3.5 + sample * 0.5;
      await page.evaluate(time => window.renderAt(time), Math.min(contract.duration, t * (contract.duration / duration)));
      tailHashes.push(hash(await page.screenshot({ type: "png", animations: "disabled" })));
    }
    let unchangedSeconds = 0;
    for (let i = 1; i < tailHashes.length; i++) {
      unchangedSeconds = tailHashes[i] === tailHashes[i - 1] ? unchangedSeconds + 0.5 : 0;
      if (unchangedSeconds > 2.5) {
        fail("Visual ending check failed: the final scene stays pixel-identical for more than 2.5 seconds. Animate the final insight or shorten the scene ending before exporting.");
      }
    }
    await page.evaluate(() => window.renderAt(0));
    console.log("Narrated ending check passed (no frozen final frame longer than 2.5 seconds).");
  }

  const sceneTimeScale = contract.duration / duration;
  if (duration > contract.duration + 0.05) {
    console.log(`Scene (${contract.duration.toFixed(2)}s) is shorter than final duration (${duration.toFixed(2)}s); time-scaling the full scene to avoid a frozen end card.`);
  }
  console.log(`Rendering ${frameCount} frames at ${fps} fps (1080×1920), ${duration.toFixed(2)} seconds`);

  for (let i = 0; i < frameCount; i++) {
    const sceneTime = Math.min(contract.duration, (i / fps) * sceneTimeScale);
    await page.evaluate(time => window.renderAt(time), sceneTime);
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
if (audioPath) {
  const audioFilters = [];
  if (audioOffset > 0) audioFilters.push(`adelay=${Math.round(audioOffset * 1000)}:all=1`);
  else if (audioOffset < 0) audioFilters.push(`atrim=start=${Math.abs(audioOffset).toFixed(3)}`, "asetpts=PTS-STARTPTS");
  audioFilters.push("apad", "loudnorm=I=-16:TP=-1.5:LRA=7");
  ffmpegArgs.push("-af", audioFilters.join(","));
}
ffmpegArgs.push("-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart");
if (audioPath) ffmpegArgs.push("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2");
ffmpegArgs.push(outPath);
const result = spawnSync("ffmpeg", ffmpegArgs, { stdio: "inherit" });
if (result.error) { console.error("Could not run ffmpeg. Install it with: brew install ffmpeg"); process.exit(1); }
if (result.status !== 0) process.exit(result.status ?? 1);
console.log(`Exported: ${outPath}`);
