#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const args = process.argv.slice(2);
function arg(name, fallback) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; }
function slugify(value) { return value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64) || "story"; }
const storyArg = arg("--story");
if (!storyArg) {
  console.error("Usage: node scripts/generate.mjs --story <file.md> [--model qwen3-coder:30b] [--out output/<slug>/index.html]");
  process.exit(2);
}
const model = arg("--model", process.env.OLLAMA_MODEL || "qwen3-coder:30b");
const repairNote = arg("--repair-note", "");
const ollamaUrl = (process.env.OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
const storyPath = path.resolve(process.cwd(), storyArg);
const story = await fs.readFile(storyPath, "utf8");
const system = await fs.readFile(path.join(root, "prompts", "visual-director.md"), "utf8");
const title = story.match(/^#\s+(.+)$/m)?.[1] || path.basename(storyPath, path.extname(storyPath));
const defaultOut = path.join(root, "output", slugify(title), "index.html");
const outPath = path.resolve(process.cwd(), arg("--out", path.relative(process.cwd(), defaultOut)));
const outputRoot = path.join(root, "output") + path.sep;
if (!outPath.startsWith(outputRoot)) {
  console.error("Refusing to write outside modes/technical-data-cinema/output/. Use --out under that directory.");
  process.exit(2);
}
const context = Number(process.env.OLLAMA_NUM_CTX || 8192);
if (!Number.isInteger(context) || context < 2048 || context > 32768) {
  console.error("OLLAMA_NUM_CTX must be an integer between 2048 and 32768.");
  process.exit(2);
}
console.log(`Generating with ${model}; context=${context} tokens`);
console.log(`Story: ${storyPath}\nOutput: ${outPath}`);
let response;
try {
  response = await fetch(`${ollamaUrl}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model, stream: false,
      messages: [
        { role: "system", content: system },
        { role: "user", content: `Create the visual explainer for this story brief.\n\n--- STORY BRIEF START ---\n${story}\n--- STORY BRIEF END ---\n${repairNote ? `\nMANDATORY REPAIR REQUEST:\n${repairNote}\nPreserve the story, narration meaning, offline behavior, and export contract. Fix the specific QA failure; do not simply add a static end card.\n` : ""}\nReturn only complete HTML.\n` }
      ],
      options: { temperature: 0.25, num_ctx: context }
    }),
    signal: AbortSignal.timeout(Number(process.env.OLLAMA_TIMEOUT_MS || 600000))
  });
} catch (error) {
  console.error(`Could not reach Ollama at ${ollamaUrl}: ${error.message}`);
  process.exit(1);
}
if (!response.ok) {
  console.error(`Ollama returned HTTP ${response.status}: ${await response.text()}`);
  process.exit(1);
}
const payload = await response.json();
let html = payload?.message?.content?.trim();
if (!html) { console.error("Ollama returned no message content."); process.exit(1); }
html = html.replace(/^\uFEFF/, "").replace(/^\`\`\`(?:html)?\s*/i, "").replace(/\s*\`\`\`\s*$/, "");
if (!/^<!doctype html>/i.test(html)) {
  console.error("Model output did not start with <!doctype html>; refusing to save incomplete HTML.");
  process.exit(1);
}
// Models sometimes ignore the no-randomness rule. Convert Math.random() calls to a
// local PRNG reset from renderAt(t), so the same timestamp reproduces the same sequence.
const randomCalls = /\bMath\s*\.\s*random\s*\(\s*\)/g;
if (randomCalls.test(html)) {
  const scriptTags = [...html.matchAll(/<script\b([^>]*)>/gi)];
  const inlineScript = scriptTags.find(match => !/\bsrc\s*=/.test(match[1]));
  if (!inlineScript) {
    console.error("Generated HTML uses Math.random() but has no inline script for a deterministic PRNG. No file was written.");
    process.exit(1);
  }
  const deterministicRandom = `
var __tdcSeed = 0x6d2b79f5;
function __tdcRandom() {
  __tdcSeed = (__tdcSeed + 0x6D2B79F5) | 0;
  var n = __tdcSeed;
  n = Math.imul(n ^ (n >>> 15), n | 1);
  n ^= n + Math.imul(n ^ (n >>> 7), n | 61);
  return ((n ^ (n >>> 14)) >>> 0) / 4294967296;
}
`;
  const insertion = inlineScript.index + inlineScript[0].length;
  html = html.slice(0, insertion) + deterministicRandom + html.slice(insertion);
  html = html.replace(/\bMath\s*\.\s*random\s*\(\s*\)/g, "__tdcRandom()");
  const renderAt = /window\.renderAt\s*=\s*function\s*\(\s*seconds\s*\)\s*\{\s*const\s+t\s*=\s*Math\.max\(0,\s*Math\.min\(DURATION,\s*Number\(seconds\)\s*\|\|\s*0\)\)\s*;/;
  if (!renderAt.test(html)) {
    console.error("Cannot seed generated randomness safely: window.renderAt does not match the expected export contract. No file was written.");
    process.exit(1);
  }
  html = html.replace(renderAt, match => match + "\n  __tdcSeed = ((Math.floor(t * 1000) ^ 0x6d2b79f5) >>> 0) || 1;");
  console.log("Replaced model-generated Math.random() calls with a timestamp-seeded PRNG; determinism QA remains enabled.");
}
const missing = [];
if (!/window\.renderAt\s*=/.test(html)) missing.push("window.renderAt(seconds)");
if (!/window\.getDuration\s*=/.test(html)) missing.push("window.getDuration()");
if (!/URLSearchParams\s*\(\s*(?:window\.)?location\.search\s*\)/.test(html) || !/get\s*\(\s*["']render["']\s*\)/.test(html)) {
  missing.push("?render=1 render-only mode");
}
if (missing.length) {
  console.error(`Generated HTML failed export validation: missing ${missing.join(", ")}.\nNo file was written. Try again with --model qwen2.5-coder:7b for a targeted repair, or revise the prompt.`);
  process.exit(1);
}
await fs.mkdir(path.dirname(outPath), { recursive: true });
try { await fs.writeFile(outPath, html + "\n", { flag: "wx" }); }
catch (error) {
  if (error.code === "EEXIST") console.error(`Output already exists: ${outPath}. Choose a new --out path; previous output was not overwritten.`);
  else console.error(error.message);
  process.exit(1);
}
console.log(`Saved ${Buffer.byteLength(html)} bytes to ${outPath}`);
console.log("Next: preview the HTML, then export with --voice-script to generate narration using the existing Chatterbox studio adapter.");
