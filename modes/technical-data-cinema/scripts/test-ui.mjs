import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = await fs.readFile(path.join(here, "ui.html"), "utf8");
const server = await fs.readFile(path.join(here, "ui-server.mjs"), "utf8");
const generator = await fs.readFile(path.join(here, "generate.mjs"), "utf8");
const director = await fs.readFile(path.join(here, "../prompts/visual-director.md"), "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/gi)];
assert.ok(scripts.length >= 1, "UI must include its client script");
for (const [index, match] of scripts.entries()) {
  assert.doesNotThrow(() => new Function(match[1]), "UI script " + index + " must parse");
}
for (const id of ["analyze", "planEditor", "savePlan", "stages", "run", "exportName", "audioOffset"]) {
  assert.ok(html.includes('id="' + id + '"'), "missing UI control: " + id);
}
for (const stage of ["analysis", "planValidation", "scene", "validation", "audio", "render"]) {
  assert.ok(html.includes('data-stage="' + stage + '"'), "missing progress stage: " + stage);
}
assert.ok(html.includes("/api/plan"), "editable plan must save through the validation endpoint");
assert.ok(html.includes("#050607") && html.includes("#e64b36"), "UI must preserve Yantralok near-black and red-orange brand colors");
assert.ok(server.includes("--audio-offset") && html.includes("audioOffset"), "render UI must expose adjustable audio/video sync offset");
assert.ok(html.includes("Yantralok") && html.includes("rgba(245,247,248,.12)"), "UI should use a dark dotted technical visual background");
assert.ok(html.includes("updateStages(j.stages,j.status)"), "UI must consume actual server stage statuses");
assert.ok(html.includes("<b>2. Plan validation</b>") && html.includes("<b>3. Scene compilation</b>"), "UI must show plan validation and scene compilation as separate stages");
assert.ok(html.includes('pendingPhase==="all"?"all":(analysisReady?(sceneReady?"render":"scene"):"analysis")'), "UI must preserve staged workflow and allow one-click all-in-one production");
assert.ok(html.includes('id="runAll"') && html.includes('pendingPhase="all"') && html.includes('pendingPhase==="all"?"all"'), "UI must expose one-click full production");
assert.ok(generator.includes("OLLAMA_UNAVAILABLE") && generator.includes("attempt <= 3"), "generator must retry transient Ollama connection failures and stop cleanly when unavailable");
assert.ok(generator.includes("num_ctx: context, num_predict:"), "scene generation must set an explicit context and output-token budget");
assert.ok(generator.includes("buildFallbackScene") && generator.includes("TDC_EXPERIMENTAL_LLM_SCENE"), "production scene generation must compile the validated plan without depending on LLM-authored renderer code");
assert.ok(server.includes("deterministic renderer"), "scene stage logs must distinguish plan compilation from analysis");
assert.ok(server.includes('TDC_EXPERIMENTAL_LLM_SCENE: "0"'), "UI production jobs must disable experimental LLM-authored scene code");
assert.ok(server.includes('url.pathname === "/api/projects"'), "UI must list existing projects for reuse");
assert.ok(!server.includes("visual-plan.previous-"), "reopening analysis must not archive and regenerate an existing visual plan");
assert.ok(html.includes('id="existingProject"') && html.includes('id="loadProject"') && html.includes("loadProjects();"), "UI must support loading and continuing an existing project folder");
assert.ok(server.includes('[...generateArgs, "--phase", "plan"]') && server.includes('[...generateArgs, "--phase", "scene"]'), "one-click production must run analysis and scene compilation as separately reported stages");
assert.ok(server.includes('setStage(job, "planValidation", "passed"'), "analysis plan validation must be reported before scene compilation starts");
assert.ok(server.includes("internalRepairExhausted"), "UI must not launch a second repair after the generator has already exhausted its repair");
assert.ok(director.includes("Do NOT force the dark Yantralok palette onto mythology/history stories"), "mythology/history scenes must use their story-appropriate parchment palette in infographic mode");
assert.ok(director.includes("a real balance/scale with two labelled pans") && director.includes("recognisable spatial environment"), "mythology scenes must contain concrete story-specific visuals, not generic dots");
assert.ok(server.includes("stages: job.stages"), "job API must expose explicit stage statuses");
assert.ok(server.includes('SCENE STAGE VALIDATED. Rendering and narration were not started.'), "scene phase must stop before audio/render");
assert.ok(server.includes('phase === "render"') && server.includes("Rendering the saved fingerprint-matched scene"), "render phase must reuse saved scene without model generation");
assert.ok(server.includes("setStage(job") && server.includes("stages: job.stages"), "server must report explicit stage status");
for (const id of ["audioForm", "audioScript", "audioStyle", "audioPerformance", "audioIntensity", "audioPace", "audioRun", "audioLogs", "audioLinks"]) {
  assert.ok(html.includes('id="' + id + '"'), "missing audio-only UI control: " + id);
}
assert.ok(html.includes('fetch("/api/audio"'), "audio-only UI must use its separate endpoint");
assert.ok(html.includes('value="0.8"') && html.includes('value="1.2"'), "audio UI must expose overall pace range");
assert.ok(server.includes('url.pathname === "/api/audio"'), "server must expose separate audio-only endpoint");
assert.ok(server.includes('atempo=') && server.includes('narration-source.wav'), "server must preserve original audio and apply pace as a separate post-process");
assert.ok(server.includes("content-disposition") && html.includes('?download=1'), "audio downloads must be served as attachments");
console.log("Staged UI syntax, brand palette, audio-only workflow, audio sync offset, and pace controls tests passed.");

const voiceCache = await fs.readFile(path.resolve(here, "../../../engine/shorts/voice.py"), "utf8");
const exporter = await fs.readFile(path.join(here, "export.mjs"), "utf8");
assert.ok(voiceCache.includes("CACHE HIT: narration WAV already exists; skipping Chatterbox synthesis"), "partial TTS cache must not trigger expensive re-synthesis");
assert.ok(voiceCache.includes("CACHE HIT: reusing existing word alignment"), "existing alignment must be reused independently");
assert.ok(exporter.includes("isolated local synthesis also failed") && exporter.includes("from engine.studio.server import script_to_audio"), "export must fall back to the local production voice adapter if Studio disappears");
assert.ok(exporter.includes("copyFile(cachedAudio, audioPath)"), "fallback narration must be copied to the project output without regenerating visuals");


assert.ok(html.includes('id="sceneHtml"') && html.includes('id="saveSceneHtml"'), "UI must expose a paste-and-save custom scene HTML editor");
assert.ok(html.includes('id="previewSceneHtml"') && html.includes('id="renderSceneHtml"'), "custom scene UI must support preview and render actions");
assert.ok(server.includes('url.pathname === "/api/scene/save"') && server.includes('index.user-backup-'), "custom scene saves must be server-backed and preserve the previous scene");
assert.ok(server.includes("tdc-story-fingerprint") && server.includes("tdc-plan-fingerprint"), "custom HTML saves must be bound to the selected story and plan so render-only validation can reuse them");
