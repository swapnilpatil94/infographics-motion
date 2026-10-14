import assert from "node:assert/strict";
import { applySceneCompatibility } from "./scene-compat.mjs";
import { validateSceneSource, assertSceneCandidate } from "./scene-contract.mjs";

const source = `<!doctype html><html><head><meta charset="utf-8"></head><body>
<canvas id="scene" width="540" height="960"></canvas>
<script>
const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
window.getDuration = () => 4;
window.renderAt = function (seconds) {
  ctx.clearRect(0, 0, 540, 960);
  ctx.fillStyle = "#050607"; ctx.fillRect(0, 0, 540, 960);
  ctx.fillStyle = "#f5f7f8";
  ctx.beginPath(); ctx.arc(270 + window.__tdcRandom() * 80, 480, 28, 0, Math.PI * 2); ctx.fill();
};
window.renderAt(0);
</script></body></html>`;
const result = applySceneCompatibility(source);
assert.ok(result.changes.some(change => change.includes("timestamp-deterministic")));
assert.ok(result.changes.some(change => change.includes("render-only")));
assert.deepEqual(validateSceneSource(result.html), []);
await assertSceneCandidate(result.html);
console.log("Scene compatibility passed: random is deterministic, render-only mode is present, and browser seeking reproduces identical frames.");
