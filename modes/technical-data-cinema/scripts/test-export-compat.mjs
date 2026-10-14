import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { installDeterministicCompatibility } from "./export-compat.mjs";

const source = \`<!doctype html><html><head><style>body{margin:20px}</style></head><body><button id="preview">Preview UI</button><main id="scene">scene</main><script>window.renderAt=function(t){document.querySelector("#scene").textContent=String(Math.random())+":"+t};window.getDuration=function(){return 3};renderAt(0);</script></body></html>\`;
const transformed = installDeterministicCompatibility(source);
assert.ok(transformed.includes("TDC deterministic compatibility layer"));
assert.ok(transformed.includes("TDC export compatibility"));
const dir = await fs.mkdtemp(path.join(os.tmpdir(), "tdc-export-compat-"));
const file = path.join(dir, "scene.html");
await fs.writeFile(file, transformed, "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
  const url = pathToFileURL(file);
  url.searchParams.set("render", "1");
  await page.goto(url.href, { waitUntil: "load" });
  const contract = await page.evaluate(() => ({
    renderAt: typeof window.renderAt,
    getDuration: typeof window.getDuration,
    renderOnly: document.body.dataset.tdcRenderOnly,
    buttonDisplay: getComputedStyle(document.querySelector("#preview")).display,
    bodyMargin: getComputedStyle(document.body).margin
  }));
  assert.equal(contract.renderAt, "function");
  assert.equal(contract.getDuration, "function");
  assert.equal(contract.renderOnly, "1");
  assert.equal(contract.buttonDisplay, "none");
  assert.equal(contract.bodyMargin, "0px");
  await page.evaluate(() => window.renderAt(1));
  const first = await page.locator("#scene").textContent();
  await page.evaluate(() => window.renderAt(2));
  await page.evaluate(() => window.renderAt(1));
  const repeated = await page.locator("#scene").textContent();
  assert.equal(repeated, first, "same timestamp must reproduce the same random-driven frame");
} finally {
  await browser.close();
  await fs.rm(dir, { recursive: true, force: true });
}
console.log("Deterministic export compatibility tests passed.");
