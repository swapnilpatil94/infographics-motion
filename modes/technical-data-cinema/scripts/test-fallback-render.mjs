import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { buildFallbackScene } from "./fallback-scene.mjs";

const grammars = [
  ["network", "Network topology"],
  ["particle_flow", "Request queue"],
  ["split_comparison", "Before after"],
  ["timeline", "Causal sequence"],
  ["scale", "Leverage"],
  ["layered_system", "Incentive layers"],
  ["transformation", "System state"]
];
const plan = { beats: grammars.map(([visual_grammar, dominant_subject], i) => ({
  start: i * 3, end: (i + 1) * 3,
  narration_idea: i === 0
    ? "Why a hidden system can move a surprisingly large amount of money through hundreds of separate accounts"
    : "Beat " + (i + 1) + " explains the next causal step",
  viewer_takeaway: "The system changes under pressure",
  visual_grammar, dominant_subject,
  action_and_causal_proof: "Watch the mechanism change and see the consequence",
  overlay_text: ["Input", "Bottleneck", "Outcome"]
})) };
const html = buildFallbackScene({ title: "Fallback browser test", story: "# Fallback browser test", plan });
const dir = await fs.mkdtemp(path.join(os.tmpdir(), "fallback-render-"));
const file = path.join(dir, "scene.html");
await fs.writeFile(file, html);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(pathToFileURL(file).href + "?render=1", { waitUntil: "load" });
  const contract = await page.evaluate(() => ({
    renderAt: typeof window.renderAt,
    getDuration: typeof window.getDuration,
    duration: window.getDuration()
  }));
  assert.equal(contract.renderAt, "function");
  assert.equal(contract.getDuration, "function");
  assert.equal(contract.duration, 21);
  const artHashes = new Set();
  const sceneTypes = new Set();
  for (let i = 0; i < grammars.length; i++) {
    await page.evaluate(t => window.renderAt(t), i * 3 + 1.25);
    const state = await page.evaluate(() => {
      const ids = ["headline", "action", "description"];
      const bounds = ids.map(id => {
        const box = document.getElementById(id).getBBox();
        return { id, x: box.x, y: box.y, right: box.x + box.width, bottom: box.y + box.height };
      });
      return {
        art: document.getElementById("sceneArt").innerHTML,
        sceneType: document.getElementById("sceneArt").getAttribute("data-scene"),
        bounds,
        text: document.getElementById("headline").textContent
      };
    });
    artHashes.add(crypto.createHash("sha256").update(state.art).digest("hex"));
    sceneTypes.add(state.sceneType);
    for (const b of state.bounds) {
      assert.ok(b.x >= 0 && b.y >= 0, b.id + " starts outside the frame: " + JSON.stringify(b));
      assert.ok(b.right <= 1005, b.id + " overflows the right safe area: " + JSON.stringify(b));
      assert.ok(b.bottom <= 1730, b.id + " overflows the bottom safe area: " + JSON.stringify(b));
    }
    assert.ok(state.text.length > 0, "headline must not be empty");
  }
  assert.equal(artHashes.size, grammars.length, "each planned grammar must compile to different artwork");
  assert.equal(sceneTypes.size, grammars.length, "each planned grammar must select a distinct semantic scene component");
  assert.deepEqual(errors, [], "fallback must not throw browser errors");
  await page.evaluate(() => window.renderAt(0));
  const first = await page.screenshot({ type: "png" });
  await page.evaluate(() => window.renderAt(12));
  await page.evaluate(() => window.renderAt(0));
  const repeated = await page.screenshot({ type: "png" });
  assert.equal(crypto.createHash("sha256").update(first).digest("hex"), crypto.createHash("sha256").update(repeated).digest("hex"), "renderAt must be deterministic after seeking");
  console.log("Fallback browser render tests passed: 7 distinct grammars, export contract, safe text bounds, no browser errors, deterministic seeking.");
} finally {
  await browser.close();
  await fs.rm(dir, { recursive: true, force: true });
}
