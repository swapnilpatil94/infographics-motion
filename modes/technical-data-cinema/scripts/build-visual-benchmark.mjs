#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const sourcePath = path.join(root, "examples", "visual-director-benchmark.html");
const outputDir = path.join(root, "output", "visual-director-benchmark");
const htmlPath = path.join(outputDir, "index.html");
const videoPath = path.join(root, "output", "visual-director-benchmark.mp4");
await fs.mkdir(outputDir, { recursive: true });
let html = await fs.readFile(sourcePath, "utf8");
const scripts = [...html.matchAll(/<script\b(?=[^>]*\btype\s*=\s*["']module["'])[^>]*>([\s\S]*?)<\/script\s*>/gi)];
if (scripts.length !== 1) throw new Error(`Expected exactly one module script, found ${scripts.length}`);
const bundled = await build({
  stdin: { contents: scripts[0][1], resolveDir: root, sourcefile: "visual-director-benchmark.js", loader: "js" },
  bundle: true, write: false, platform: "browser", format: "iife", target: "es2022", minify: true, legalComments: "none"
});
html = html.replace(scripts[0][0], `<script>\n${bundled.outputFiles[0].text}\n</script>`);
if (/<(?:script|link|img|video|audio)[^>]+(?:src|href)=["']https?:\/\//i.test(html)) throw new Error("Benchmark HTML references a remote asset");
await fs.writeFile(htmlPath, html);
console.log(`Bundled offline benchmark: ${htmlPath}`);
const render = spawnSync(process.execPath, [
  path.join(here, "render.mjs"), "--html", htmlPath, "--out", videoPath, "--fps", "12", "--duration", "16"
], { stdio: "inherit", env: process.env });
if (render.error) throw render.error;
if (render.status !== 0) process.exit(render.status ?? 1);
console.log(`Benchmark MP4 created: ${videoPath}`);
