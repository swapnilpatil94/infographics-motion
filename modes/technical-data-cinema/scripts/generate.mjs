#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { normalizeVisualPlan, validateVisualPlan } from "./visual-plan.mjs";
import { validateSceneSource, assertSceneCandidate } from "./scene-contract.mjs";
import { applySceneCompatibility } from "./scene-compat.mjs";
import crypto from "node:crypto";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const args = process.argv.slice(2);
function arg(name, fallback) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; }
function slugify(value) { return value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64) || "story"; }
const storyArg = arg("--story");
if (!storyArg) {
  console.error("Usage: node scripts/generate.mjs --story <file.md> [--planner-model qwen3.5:9b] [--model qwen2.5-coder:7b] [--out output/<slug>/index.html]");
  process.exit(2);
}
const model = arg("--model", process.env.OLLAMA_MODEL || "qwen2.5-coder:7b");
const plannerModel = arg("--planner-model", process.env.OLLAMA_PLANNER_MODEL || "qwen3.5:9b");
const repairNote = arg("--repair-note", "");
const planFileArg = arg("--plan-file", "");
const phase = arg("--phase", "all");
if (!["all", "plan", "scene"].includes(phase)) { console.error("Unknown --phase. Use all, plan, or scene."); process.exit(2); }
const ollamaUrl = (process.env.OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
const storyPath = path.resolve(process.cwd(), storyArg);
const story = await fs.readFile(storyPath, "utf8");
const system = await fs.readFile(path.join(root, "prompts", "visual-director.md"), "utf8");
const title = story.match(/^#\s+(.+)$/m)?.[1] || path.basename(storyPath, path.extname(storyPath));
const defaultOut = path.join(root, "output", slugify(title), "index.html");
const outPath = path.resolve(process.cwd(), arg("--out", path.relative(process.cwd(), defaultOut)));
const planFile = path.resolve(process.cwd(), planFileArg || path.join(path.dirname(outPath), "visual-plan.json"));
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
const tagsResponse = await fetch(`${ollamaUrl}/api/tags`, { signal: AbortSignal.timeout(5000) });
if (!tagsResponse.ok) {
  console.error(`Could not list installed Ollama models (HTTP ${tagsResponse.status}).`);
  process.exit(1);
}
const installedModels = ((await tagsResponse.json()).models || []).map(item => item.name).filter(Boolean);
const hasModel = requested => installedModels.some(name => name === requested || name.startsWith(`${requested}:`) || requested.startsWith(`${name}:`));
if (!hasModel(plannerModel)) {
  console.error(`Visual planner model '${plannerModel}' is not downloaded. Run 'ollama pull ${plannerModel}' explicitly. Installed models: ${installedModels.join(", ") || "(none)"}`);
  process.exit(1);
}
console.log(`Visual planner: ${plannerModel}; scene coder: ${model}; context=${context} tokens`);
console.log(`Story: ${storyPath}\nOutput: ${outPath}`);
const plannerPrompt = await fs.readFile(path.join(root, "prompts", "visual-planner.md"), "utf8");
const timeoutMs = Number(process.env.OLLAMA_TIMEOUT_MS || 600000);
async function askOllama(messages, stage, selectedModel = model, responseFormat = null) {
  let response;
  try {
    response = await fetch(`${ollamaUrl}/api/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: selectedModel, stream: false, messages, keep_alive: 0,
        ...(responseFormat ? { format: responseFormat } : {}),
        options: { temperature: 0.25, num_ctx: context }
      }),
      signal: AbortSignal.timeout(timeoutMs)
    });
  } catch (error) {
    throw new Error("Could not reach Ollama during " + stage + " at " + ollamaUrl + ": " + error.message, { cause: error });
  }
  if (!response.ok) {
    throw new Error("Ollama " + stage + " returned HTTP " + response.status + ": " + await response.text());
  }
  const payload = await response.json();
  const content = payload?.message?.content?.trim();
  if (!content) throw new Error(`Ollama returned no content during ${stage}.`);
  return content;
}

const storyFingerprint = crypto.createHash("sha256").update(story).digest("hex");
let visualPlan;
try {
  const cached = await fs.readFile(planFile, "utf8");
  visualPlan = JSON.parse(cached);
  if (String(visualPlan.story_fingerprint || "") !== storyFingerprint) {
    if (phase !== "plan") throw new Error("cached visual plan belongs to different story inputs; rerun analysis before scene generation");
    const archivedPlan = planFile.replace(/\\.json$/i, ".stale-" + Date.now() + ".json");
    await fs.rename(planFile, archivedPlan); visualPlan = undefined;
    console.log(`Archived stale plan as ${archivedPlan}`);
  } else console.log(`Reusing validated visual plan: ${planFile}`);
} catch (error) {
  if (error.code !== "ENOENT" && visualPlan !== undefined) {
    console.error(`Cached visual plan is invalid at ${planFile}: ${error.message}. Review it or rerun analysis.`);
    process.exit(1);
  }
  if (phase === "scene") { console.error(`Scene-only phase requires an existing visual plan at ${planFile}. Run --phase plan first.`); process.exit(1); }
  console.log("Visual Director: planning story-specific visual beats...");
  const plannerMessages = [
    { role: "system", content: plannerPrompt },
    { role: "user", content: ["Create a concrete visual plan for this story. Adapt beat count and timing to the actual narration duration if provided. Return a single valid JSON object only; no markdown fences or commentary.", "", "--- STORY BRIEF START ---", story, "--- STORY BRIEF END ---"].join(String.fromCharCode(10)) }
  ];
  let planText;
  try {
    planText = await askOllama(plannerMessages, "visual planning", plannerModel, "json");
  } catch (firstError) {
    if (!/Ollama returned no content during visual planning/i.test(firstError.message)) throw firstError;
    console.warn(`Visual planner ${plannerModel} returned an empty response; retrying once before scene generation.`);
    try {
      planText = await askOllama(plannerMessages, "visual planning retry", plannerModel, "json");
    } catch (retryError) {
      if (!/Ollama returned no content during visual planning retry/i.test(retryError.message) || plannerModel === model) throw retryError;
      console.warn(`Visual planner stayed empty; falling back to the selected scene coder ${model} for planning.`);
      planText = await askOllama(plannerMessages, "visual planning fallback", model, "json");
    }
  }
  try {
    const cleanPlan = planText.replace(/^\uFEFF/, "").trim();
    const jsonText = cleanPlan.slice(cleanPlan.indexOf("{"), cleanPlan.lastIndexOf("}") + 1);
    visualPlan = JSON.parse(jsonText);
    visualPlan.story_fingerprint = storyFingerprint;
    visualPlan = normalizeVisualPlan(visualPlan);
    validateVisualPlan(visualPlan, { requireFingerprint: true });
    await fs.mkdir(path.dirname(planFile), { recursive: true });
    await fs.writeFile(planFile, JSON.stringify(visualPlan, null, 2) + String.fromCharCode(10), { flag: "wx" });
    console.log(`Saved validated visual plan: ${planFile}`);
  } catch (error) {
    console.error(`Visual Director returned an invalid plan: ${error.message}. No HTML was written. The planner now uses Ollama JSON mode; if this persists, remove any partial plan file and retry.`);
    process.exit(1);
  }
}
visualPlan = normalizeVisualPlan(visualPlan);
validateVisualPlan(visualPlan, { requireFingerprint: true });
if (phase === "plan") { console.log(`ANALYSIS VALIDATED: ${visualPlan.beats.length} beats saved to ${planFile}`); process.exit(0); }
const planJson = JSON.stringify(visualPlan, null, 2);
console.log(`Visual Director planned ${visualPlan.beats.length} beats; generating the animated scene...`);
let payload = "";
let sceneFailure = "";
try {
  payload = await askOllama([
    { role: "system", content: system },
    { role: "user", content: "Implement the supplied visual direction as one complete, deterministic, offline HTML scene. Treat the plan as mandatory creative direction. Never call Math.random, including in helper functions. Every frame must be fully derived from absolute render time. Implement window.renderAt(seconds), window.getDuration(), and render-only mode.\n\n--- STORY BRIEF START ---\n" + story + "\n--- STORY BRIEF END ---\n\n--- VISUAL DIRECTOR PLAN JSON START ---\n" + planJson + "\n--- VISUAL DIRECTOR PLAN JSON END ---\n" + (repairNote ? "\nMANDATORY REPAIR REQUEST:\n" + repairNote + "\nPreserve story meaning, offline behavior and export contract. Fix the specific QA failure; do not add a static end card.\n" : "") + "\nReturn only complete HTML.\n" }
  ], "scene generation");
} catch (error) {
  sceneFailure = error.message || "Ollama scene generation failed";
}
let html = (payload || "").replace(/^\uFEFF/, "").replace(/^\`\`\`(?:html)?\s*/i, "").replace(/\s*\`\`\`\s*$/, "");
let compatibility = applySceneCompatibility(html);
html = compatibility.html;
if (compatibility.changes.length) console.warn("Applied narrow scene compatibility: " + compatibility.changes.join("; ") + ". Visual QA and browser render checks still apply.");
const validationErrors = validateSceneSource(html);
if (!sceneFailure && validationErrors.length === 0) {
  try {
    const auditText = await askOllama([
      { role: "system", content:
        "You are a strict visual-storytelling QA reviewer. Inspect the generated HTML source against the story and visual plan. Return JSON only with keys pass (boolean) and issues (array of strings). Fail if it is mainly a repeated central icon/diagram, generic orbit/network animation, title cards with changing labels, decorative motion without causal proof, or if different narration beats do not produce meaningfully different subjects/compositions. Pass only if the code implements story-specific visible actions, state changes and distinct explanatory beats. Do not fail for style preference alone; mention concrete source evidence. Be strict and concise."
      },
      { role: "user", content:
        "STORY:\\n" + story + "\\nVISUAL PLAN:\\n" + planJson +
        "\\nGENERATED HTML (source excerpt):\\n" + html.slice(0, 14000)
      }
    ], "visual quality audit", plannerModel, "json");
    const cleanAudit = auditText.replace(/^\uFEFF/, "").trim();
    const auditJson = cleanAudit.slice(cleanAudit.indexOf("{"), cleanAudit.lastIndexOf("}") + 1);
    const audit = JSON.parse(auditJson);
    if (audit.pass !== true) {
      const issues = Array.isArray(audit.issues) ? audit.issues.map(String).slice(0, 5) : ["visual QA did not approve the scene"];
      validationErrors.push("visual quality audit rejected the scene: " + issues.join("; "));
      console.warn("Visual QA rejected the generated scene; a targeted repair will run before output.");
    } else {
      console.log("Visual QA passed: scene source appears story-specific with causal visual changes.");
    }
  } catch (error) {
    validationErrors.push("visual quality audit failed: " + error.message);
    console.warn("Visual QA could not verify the scene; a targeted repair will run rather than silently accepting unverified output.");
  }
}
if (validationErrors.length || sceneFailure) {
  const firstFailure = [sceneFailure, ...validationErrors].filter(Boolean).join("; ");
  console.warn("Scene generation failed its export-contract check: " + firstFailure + ". Attempting one targeted repair with the same coding model.");
  try {
    const repair = await askOllama([
      { role: "system", content: system },
      { role: "user", content:
        "REPAIR THE FAILED SCENE. Return a complete replacement HTML document, not a patch. The previous attempt failed this deterministic gate: " + firstFailure + ". " +
        "Do not simplify this into a generic infographic, repeated central icon, generic network/orbit diagram, or title-card sequence. Implement the supplied story and each beat as distinct, causally meaningful visual action. " +
        "Use different dominant silhouettes and compositions when the narration changes subject; animate actual state changes, not only decorative particles. " +
        "Preserve offline deterministic rendering, no Math.random(), window.renderAt(seconds), window.getDuration(), and URLSearchParams(location.search).get('render') === '1'. " +
        "Story brief:\\n" + story + "\\nVisual plan JSON:\\n" + planJson + "\\nReturn only complete HTML starting with <!doctype html>."
      }
    ], "scene repair");
    const repaired = repair.replace(/^\uFEFF/, "").replace(/^\`\`\`(?:html)?\s*/i, "").replace(/\s*\`\`\`\s*$/, "");
    const repairedCompatibility = applySceneCompatibility(repaired);
    const compatibleRepair = repairedCompatibility.html;
    const errors = validateSceneSource(compatibleRepair);
    if (errors.length) throw new Error(errors.join("; "));
    html = compatibleRepair;
    if (repairedCompatibility.changes.length) console.warn("Applied narrow scene compatibility to repaired output: " + repairedCompatibility.changes.join("; "));
    const repairedAuditText = await askOllama([
      { role: "system", content: "You are a strict visual-storytelling QA reviewer. Return JSON only with keys pass (boolean) and issues (array of strings). Fail if the scene is a repeated central icon/diagram, generic orbit/network animation, title cards with changing labels, decorative motion without causal proof, or if narration beats do not produce meaningfully different subjects/compositions. Pass only when story-specific visible actions and causal state changes are implemented. Be strict and concise." },
      { role: "user", content: ["STORY:", story, "VISUAL PLAN:", planJson, "REPAIRED HTML:", html.slice(0, 14000)].join("\n") }
    ], "repaired visual quality audit", plannerModel, "json");
    const cleanRepairedAudit = repairedAuditText.replace(/^\\uFEFF/, "").trim();
    const repairedAuditJson = cleanRepairedAudit.slice(cleanRepairedAudit.indexOf("{"), cleanRepairedAudit.lastIndexOf("}") + 1);
    const repairedAudit = JSON.parse(repairedAuditJson);
    if (repairedAudit.pass !== true) {
      const issues = Array.isArray(repairedAudit.issues) ? repairedAudit.issues.map(String).slice(0, 5) : ["visual QA did not approve the repaired scene"];
      throw new Error("repaired scene failed story-specific visual QA: " + issues.join("; "));
    }
    console.log("Repaired scene passed story-specific visual QA.");
    console.log("Scene repair passed deterministic export-contract validation.");
  } catch (repairError) {
    const reason = [firstFailure, "repair failed: " + repairError.message].join("; ");
    console.error("Scene generation failed after one targeted repair. Refusing to emit a generic substitute as a production scene. " + reason);
    console.error("Revise the plan or retry scene generation. Existing narration/audio artifacts remain untouched.");
    process.exit(1);
  }
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
const planFingerprint = crypto.createHash("sha256").update(JSON.stringify(visualPlan)).digest("hex");
html = html.replace(/<head([^>]*)>/i, match => match + `<meta name="tdc-story-fingerprint" content="${storyFingerprint}"><meta name="tdc-plan-fingerprint" content="${planFingerprint}">`);
try { await assertSceneCandidate(html); console.log("Browser render-only/seek/determinism validation passed."); }
catch (error) { console.error(`Generated scene failed browser render-only validation: ${error.message}`); process.exit(1); }
await fs.mkdir(path.dirname(outPath), { recursive: true });
try { await fs.writeFile(outPath, html + "\n", { flag: "wx" }); }
catch (error) {
  if (error.code === "EEXIST") console.error(`Output already exists: ${outPath}. Choose a new --out path; previous output was not overwritten.`);
  else console.error(error.message);
  process.exit(1);
}
console.log(`Saved ${Buffer.byteLength(html)} bytes to ${outPath}`);
console.log("Next: preview the HTML, then export with --voice-script to generate narration using the existing Chatterbox studio adapter.");
