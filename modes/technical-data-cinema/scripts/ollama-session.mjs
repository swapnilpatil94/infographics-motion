#!/usr/bin/env node
/**
 * Owns the Ollama lifecycle for one generation command.
 * - Reuses an existing server without shutting it down.
 * - Starts a local server only when needed.
 * - Requires the model to be already downloaded (never pulls silently).
 * - Unloads the selected model after the command.
 */
import { spawn, spawnSync } from "node:child_process";
import process from "node:process";

const argv = process.argv.slice(2);
const separator = argv.indexOf("--");
if (separator < 0 || !argv[separator + 1]) {
  console.error("Usage: node scripts/ollama-session.mjs -- <command> [args...]");
  process.exit(2);
}
const command = argv[separator + 1];
const commandArgs = argv.slice(separator + 2);
const modelIndex = commandArgs.indexOf("--model");
const model = modelIndex >= 0
  ? commandArgs[modelIndex + 1]
  : (process.env.OLLAMA_MODEL || "qwen3-coder:30b");
const base = (process.env.OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
const startupTimeoutMs = Number(process.env.OLLAMA_STARTUP_TIMEOUT_MS || 30000);
let serverProcess = null;
let startedHere = false;
let child = null;

async function apiReady() {
  try {
    const response = await fetch(`${base}/api/tags`, { signal: AbortSignal.timeout(1000) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForApi() {
  const deadline = Date.now() + startupTimeoutMs;
  while (Date.now() < deadline) {
    if (await apiReady()) return true;
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  return false;
}

async function unloadModel() {
  try {
    const response = await fetch(`${base}/api/generate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model, prompt: "", stream: false, keep_alive: 0 }),
      signal: AbortSignal.timeout(15000)
    });
    if (response.ok) console.log(`Unloaded Ollama model: ${model}`);
    else console.warn(`Warning: model unload returned HTTP ${response.status}.`);
  } catch (error) {
    console.warn(`Warning: could not explicitly unload ${model}: ${error.message}`);
  }
}

async function cleanup() {
  await unloadModel();
  if (startedHere && serverProcess && serverProcess.exitCode === null) {
    console.log("Stopping Ollama server started by this command...");
    serverProcess.kill("SIGTERM");
    await Promise.race([
      new Promise(resolve => serverProcess.once("exit", resolve)),
      new Promise(resolve => setTimeout(resolve, 3000))
    ]);
    if (serverProcess.exitCode === null) serverProcess.kill("SIGKILL");
  } else if (!startedHere) {
    console.log("Leaving the pre-existing Ollama server running.");
  }
}

try {
  if (!(await apiReady())) {
    const probe = spawnSync("ollama", ["--version"], { encoding: "utf8" });
    if (probe.error || probe.status !== 0) {
      throw new Error("Ollama is not running and the 'ollama' CLI is unavailable. Install/start Ollama, then retry.");
    }
    console.log("Ollama API is not responding; starting 'ollama serve'...");
    serverProcess = spawn("ollama", ["serve"], { stdio: "ignore", detached: false });
    serverProcess.once("error", error => console.error(`Could not start Ollama: ${error.message}`));
    startedHere = true;
    if (!(await waitForApi())) {
      throw new Error(`Ollama did not become ready at ${base} within ${startupTimeoutMs}ms.`);
    }
    console.log("Ollama server is ready.");
  } else {
    console.log("Reusing the already-running Ollama server.");
  }

  const tagsResponse = await fetch(`${base}/api/tags`);
  const tags = await tagsResponse.json();
  const models = (tags.models || []).map(item => item.name);
  const installed = models.some(name => name === model || name.startsWith(`${model}:`) || model.startsWith(`${name}:`));
  if (!installed) {
    throw new Error(`Model '${model}' is not downloaded. Run 'ollama pull ${model}' explicitly, then retry. Available models: ${models.join(", ") || "(none)"}`);
  }

  child = spawn(command, commandArgs, {
    stdio: "inherit",
    env: { ...process.env, OLLAMA_URL: base, OLLAMA_MODEL: model }
  });
  const exitCode = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => resolve(code ?? (signal ? 1 : 0)));
  });
  process.exitCode = exitCode;
} catch (error) {
  console.error(`Ollama session failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  await cleanup();
}
