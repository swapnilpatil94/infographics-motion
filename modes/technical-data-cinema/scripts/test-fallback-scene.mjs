import assert from "node:assert/strict";
import { buildFallbackScene } from "./fallback-scene.mjs";

const plan = {
  beats: Array.from({ length: 6 }, (_, index) => ({
    start: index * 3,
    end: (index + 1) * 3,
    narration_idea: `Beat ${index + 1}: cause and effect`,
    viewer_takeaway: "A system changes under pressure",
    visual_grammar: index % 2 ? "particle_flow" : "three_d_mechanism",
    dominant_subject: index % 2 ? "Request queue" : "Network",
    action_and_causal_proof: "Requests accumulate, then move through the system",
    overlay_text: ["Input", "Bottleneck", "Outcome"]
  }))
};
const html = buildFallbackScene({ title: "Test story", story: "# Test story", plan });
assert.match(html, /^<!doctype html>/i);
assert.match(html, /window\.renderAt\s*=/);
assert.match(html, /window\.getDuration\s*=/);
assert.match(html, /URLSearchParams\(window\.location\.search\)/);
assert.doesNotMatch(html, /Math\s*\.\s*random\s*\(/);
assert.match(html, /BEAT 01/);
assert.match(html, /Requests accumulate/);
assert.match(html, /renderAt\(0\)/);
assert.match(html, /getDuration/);
assert.ok(html.length > 5000, "fallback should contain a substantial SVG scene");
assert.throws(() => buildFallbackScene({ title: "Bad", story: "", plan: { beats: [] } }), /at least four beats/);
console.log("Deterministic fallback scene tests passed.");
