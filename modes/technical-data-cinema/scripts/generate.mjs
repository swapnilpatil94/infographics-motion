#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

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
const plannerPrompt = await fs.readFile(path.join(root, "prompts", "visual-planner.md"), "utf8");
const timeoutMs = Number(process.env.OLLAMA_TIMEOUT_MS || 600000);
async function askOllama(messages, stage) {
  let response;
  try {
    response = await fetch(`${ollamaUrl}/api/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model, stream: false, messages,
        options: { temperature: 0.25, num_ctx: context }
      }),
      signal: AbortSignal.timeout(timeoutMs)
    });
  } catch (error) {
    console.error(`Could not reach Ollama during ${stage} at ${ollamaUrl}: ${error.message}`);
    process.exit(1);
  }
  if (!response.ok) {
    console.error(`Ollama ${stage} returned HTTP ${response.status}: ${await response.text()}`);
    process.exit(1);
  }
  const payload = await response.json();
  const content = payload?.message?.content?.trim();
  if (!content) {
    console.error(`Ollama returned no content during ${stage}.`);
    process.exit(1);
  }
  return content;
}

console.log("Visual Director: planning story-specific visual beats...");
const planText = await askOllama([
  { role: "system", content: plannerPrompt },
  { role: "user", content: `Create a concrete visual plan for this story. Adapt beat count and timing to the actual narration duration if provided.\n\n--- STORY BRIEF START ---\n${story}\n--- STORY BRIEF END ---` }
], "visual planning");
let visualPlan;
try {
  const cleanPlan = planText.replace(/^\uFEFF/, "").replace(/^```(?:json)?\s*/i, "").replace(/\s*```\s*$/, "");
  const jsonText = cleanPlan.slice(cleanPlan.indexOf("{"), cleanPlan.lastIndexOf("}") + 1);
  visualPlan = JSON.parse(jsonText);
  if (!Array.isArray(visualPlan.beats) || visualPlan.beats.length < 4) {
    throw new Error("plan must contain at least four visual beats");
  }
} catch (error) {
  console.error(`Visual Director returned an invalid plan: ${error.message}. No HTML was written. Retry or use a more capable local coding model.`);
  process.exit(1);
}
const planJson = JSON.stringify(visualPlan, null, 2);
console.log(`Visual Director planned ${visualPlan.beats.length} beats; generating the animated scene...`);
const payload = await askOllama([
  { role: "system", content: system },
  { role: "user", content: `Implement the supplied visual direction as one complete, deterministic, offline HTML scene. Treat the plan as mandatory creative direction; improve implementation details only when needed for clarity/performance.\n\n--- STORY BRIEF START ---\n${story}\n--- STORY BRIEF END ---\n\n--- VISUAL DIRECTOR PLAN JSON START ---\n${planJson}\n--- VISUAL DIRECTOR PLAN JSON END ---\n${repairNote ? `\nMANDATORY REPAIR REQUEST:\n${repairNote}\nPreserve the story, narration meaning, offline behavior, and export contract. Fix the specific QA failure; do not simply add a static end card.\n` : ""}\nReturn only complete HTML.\n` }
], "scene generation");
let html = payload;

if (!html) { console.error("Ollama returned no message content."); process.exit(1); }
html = html.replace(/^\uFEFF/, "").replace(/^\`\`\`(?:html)?\s*/i, "").replace(/\s*\`\`\`\s*$/, "");
if (!/^<!doctype html>/i.test(html)) {
  console.error("Model output did not start with <!doctype html>; refusing to save incomplete HTML.");
  process.exit(1);
}
if (/\bMath\s*\.\s*random\s*\(/.test(html)) {
  console.error("Generated HTML uses Math.random(), which makes exported frames nondeterministic. Remove Math.random() and derive every visual value from the render timestamp. No file was written; the pipeline can retry with a targeted repair.");
  process.exit(1);
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
// Bundle the optional module script so the final scene is self-contained and offline.
const moduleScripts = [...html.matchAll(/<script\b(?=[^>]*\btype\s*=\s*["']module["'])[^>]*>([\s\S]*?)<\/script\s*>/gi)];
if (moduleScripts.length > 1) {
  console.error("Generated HTML contains multiple module scripts. Use one module script so the scene can be bundled into a single offline HTML file.");
  process.exit(1);
}
if (moduleScripts.length === 1) {
  const match = moduleScripts[0];
  try {
    const result = await build({
      stdin: { contents: match[1], resolveDir: root, sourcefile: "generated-scene.js", loader: "js" },
      bundle: true, write: false, platform: "browser", format: "iife",
      target: "es2022", minify: true, legalComments: "none"
    });
    const bundled = result.outputFiles[0]?.text;
    if (!bundled) throw new Error("esbuild returned no bundled output");
    html = html.replace(match[0], `<script>\n${bundled}\n</script>`);
    console.log(`Bundled scene dependencies into offline HTML (${Buffer.byteLength(bundled)} JS bytes).`);
  } catch (error) {
    console.error(`Could not bundle the generated module scene: ${error.message}. Check imports and run npm install.`);
    process.exit(1);
  }
} else if (/from\s*["']three(?:\/|["'])|import\s*["']three(?:\/|["'])/.test(html)) {
  console.error('Generated HTML imports Three.js but has no <script type="module"> block. Put imports in one module script.');
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
