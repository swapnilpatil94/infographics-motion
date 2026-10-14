import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = await fs.readFile(path.join(here, "ui.html"), "utf8");
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
console.log("Staged UI syntax and workflow contract tests passed.");
