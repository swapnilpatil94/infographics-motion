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
for (const id of ["analyze", "planEditor", "savePlan", "stages", "run"]) {
  assert.ok(html.includes('id="' + id + '"'), "missing UI control: " + id);
}
for (const stage of ["analysis", "scene", "validation", "audio", "render"]) {
  assert.ok(html.includes('data-stage="' + stage + '"'), "missing progress stage: " + stage);
}
assert.ok(html.includes("/api/plan"), "editable plan must save through the validation endpoint");
assert.ok(html.includes('phase:pendingPhase!=="all"?pendingPhase:(analysisReady?"scene":"all")'), "UI must separate analysis from scene/export");
for (const id of ["audioForm", "audioScript", "audioStyle", "audioPerformance", "audioIntensity", "audioPace", "audioRun", "audioLogs", "audioLinks"]) {
  assert.ok(html.includes('id="' + id + '"'), "missing audio-only UI control: " + id);
}
assert.ok(html.includes('fetch("/api/audio"'), "audio-only UI must use its separate endpoint");
assert.ok(html.includes('value="0.8"') && html.includes('value="1.2"'), "audio UI must expose overall pace range");
assert.ok(server.includes('url.pathname === "/api/audio"'), "server must expose separate audio-only endpoint");
assert.ok(server.includes('atempo=') && server.includes('narration-source.wav'), "server must preserve original audio and apply pace as a separate post-process");
assert.ok(server.includes("content-disposition") && html.includes('?download=1'), "audio downloads must be served as attachments");
console.log("Staged UI syntax, audio-only workflow, and pace controls tests passed.");
