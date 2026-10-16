import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = await fs.readFile(path.join(here, "ui.html"), "utf8");
const server = await fs.readFile(path.join(here, "ui-server.mjs"), "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/gi)];
assert.ok(scripts.length >= 1, "UI must include its client script");
for (const [index, match] of scripts.entries()) {
  assert.doesNotThrow(() => new Function(match[1]), "UI script " + index + " must parse");
}
for (const id of ["analyze", "planEditor", "savePlan", "stages", "run", "exportName", "audioOffset"]) {
  assert.ok(html.includes('id="' + id + '"'), "missing UI control: " + id);
}
for (const stage of ["analysis", "scene", "validation", "audio", "render"]) {
  assert.ok(html.includes('data-stage="' + stage + '"'), "missing progress stage: " + stage);
}
assert.ok(html.includes("/api/plan"), "editable plan must save through the validation endpoint");
assert.ok(html.includes("#050607") && html.includes("#e64b36"), "UI must preserve Yantralok near-black and red-orange brand colors");
assert.ok(server.includes("--audio-offset") && html.includes("audioOffset"), "render UI must expose adjustable audio/video sync offset");
assert.ok(html.includes("Yantralok") && html.includes("rgba(245,247,248,.12)"), "UI should use a dark dotted technical visual background");
assert.ok(html.includes("updateStages(j.stages,j.status)"), "UI must consume actual server stage statuses");
assert.ok(html.includes('pendingPhase==="all"?"all":(analysisReady?(sceneReady?"render":"scene"):"analysis")'), "UI must preserve staged workflow and allow one-click all-in-one production");
assert.ok(html.includes('id="runAll"') && html.includes('phase="all"'), "UI must expose one-click full production");
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
