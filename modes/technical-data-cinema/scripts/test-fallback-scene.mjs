import assert from "node:assert/strict";
import { buildFallbackScene } from "./fallback-scene.mjs";

const grammars = ["network", "particle_flow", "comparison", "timeline", "scale", "layered_system", "transformation"];
const plan = {
  beats: grammars.map((grammar, index) => ({
    start: index * 3,
    end: (index + 1) * 3,
    narration_idea: index === 0
      ? "A very long headline explaining how an invisible system can move a surprising amount of money between hundreds of separate accounts without being noticed"
      : `Beat ${index + 1}: cause and effect`,
    viewer_takeaway: "A system changes under pressure",
    visual_grammar: grammar,
    dominant_subject: ["Network", "Request queue", "Before and after", "Timeline", "Scale", "Incentive layers", "Transformation"][index],
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
assert.match(html, /tspan/);
assert.match(html, /function network\(/);
assert.match(html, /function flow\(/);
assert.match(html, /function compare\(/);
assert.match(html, /function timeline\(/);
assert.match(html, /function scale\(/);
assert.match(html, /function stack\(/);
assert.match(html, /function transform\(/);
assert.match(html, /very long headline explaining how an invisible system/i);
assert.match(html, /Requests accumulate/);
assert.match(html, /renderAt\(0\)/);
assert.match(html, /SAFE FALLBACK/);
assert.ok(html.length > 10000, "fallback should contain multiple substantial scene grammars");
assert.throws(() => buildFallbackScene({ title: "Bad", story: "", plan: { beats: [] } }), /at least four beats/);
console.log("Story-grammar fallback scene tests passed.");
