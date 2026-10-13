#!/usr/bin/env node
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { bundleSceneHtml } from "./bundle-scene.mjs";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const source = `<!doctype html>
<html><head><meta charset="utf-8"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#080b10}canvas{display:block;width:100vw;height:100vh}</style></head>
<body><script type="module">
import * as THREE from "three";
const scene = new THREE.Scene();
scene.background = new THREE.Color("#080b10");
const camera = new THREE.PerspectiveCamera(45, 540/960, 0.1, 100);
camera.position.set(0,0,6);
const renderer = new THREE.WebGLRenderer({antialias:false, alpha:false});
renderer.setPixelRatio(1);
renderer.setSize(540,960,false);
document.body.appendChild(renderer.domElement);
const geometry = new THREE.BoxGeometry(1.8,2.4,0.8);
const material = new THREE.MeshStandardMaterial({color:"#2fd3e6", roughness:0.45, metalness:0.15});
const object = new THREE.Mesh(geometry,material);
scene.add(object);
scene.add(new THREE.HemisphereLight(0xffffff,0x203040,2));
const light = new THREE.DirectionalLight(0xffffff,2);
light.position.set(3,4,5); scene.add(light);
window.getDuration = () => 2;
window.renderAt = seconds => { const t=Math.max(0,Math.min(2,Number(seconds)||0)); object.rotation.set(t*0.4,t*0.7,0); renderer.render(scene,camera); };
if (new URLSearchParams(window.location.search).get("render") === "1") document.body.style.margin="0";
window.renderAt(0);
</script></body></html>`;
const bundled = await bundleSceneHtml(source, root);
assert.doesNotMatch(bundled, /<script[^>]*type=["']module["']/i, "module script should be bundled");
assert.match(bundled, /window\.renderAt\s*=/, "renderAt export should survive bundling");
assert.match(bundled, /window\.getDuration\s*=/, "getDuration export should survive bundling");
assert.doesNotMatch(bundled, /https?:\/\//i, "bundled HTML must not require remote resources");

const tempPath = path.join(os.tmpdir(), `technical-data-three-smoke-${process.pid}.html`);
await fs.writeFile(tempPath, bundled);
const browser = await chromium.launch({headless:true,args:["--enable-webgl","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"]});
try {
  const page = await browser.newPage({viewport:{width:540,height:960},deviceScaleFactor:1});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => { if (/^https?:/i.test(request.url())) errors.push(`unexpected network request: ${request.url()}`); });
  await page.goto(pathToFileURL(tempPath).href+"?render=1", {waitUntil:"load"});
  const contract = await page.evaluate(() => ({renderAt:typeof window.renderAt,getDuration:typeof window.getDuration,duration:window.getDuration?.(),webgl:!!document.querySelector("canvas")}));
  assert.equal(contract.renderAt,"function");
  assert.equal(contract.getDuration,"function");
  assert.equal(contract.duration,2);
  assert.equal(contract.webgl,true);
  await page.evaluate(() => window.renderAt(0.75));
  const first = await page.screenshot({type:"png"});
  await page.evaluate(() => window.renderAt(1.4));
  await page.evaluate(() => window.renderAt(0.75));
  const second = await page.screenshot({type:"png"});
  assert.equal(crypto.createHash("sha256").update(first).digest("hex"),crypto.createHash("sha256").update(second).digest("hex"),"same timestamp must render identical pixels");
  assert.deepEqual(errors,[]);
  console.log("Three.js bundle smoke test passed: offline bundle, WebGL render, export contract, deterministic seek.");
} finally {
  await browser.close();
  await fs.rm(tempPath,{force:true});
}
