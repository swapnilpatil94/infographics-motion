#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import process from "node:process";

let ok = true;
function check(command, args, label) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.error || result.status !== 0) {
    console.log(`MISSING/FAILED  ${label}`);
    ok = false;
  } else {
    console.log(`OK             ${label}`);
  }
}
check("node", ["--version"], "Node.js");
check("npm", ["--version"], "npm");
check("ffmpeg", ["-version"], "FFmpeg");
check("ollama", ["list"], "Ollama CLI");
const base = (process.env.OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
try {
  const response = await fetch(`${base}/api/tags`, { signal: AbortSignal.timeout(2500) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  console.log(`OK             Ollama API (${(data.models || []).length} models visible)`);
} catch (error) {
  console.log(`MISSING/FAILED  Ollama API (${error.message})`);
  ok = false;
}
try {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  await browser.close();
  console.log("OK             Playwright Chromium");
} catch (error) {
  console.log(`MISSING/FAILED  Playwright Chromium (${error.message})`);
  ok = false;
}
console.log(ok ? "\nPreflight passed." : "\nPreflight incomplete. Follow README.md setup steps.");
process.exit(ok ? 0 : 1);
