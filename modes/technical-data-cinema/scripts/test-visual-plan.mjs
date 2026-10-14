import assert from "node:assert/strict";
import { normalizeVisualPlan } from "./visual-plan.mjs";

const legacy = normalizeVisualPlan({
  visual_thesis: "The same system changes over time",
  beats: Array.from({ length: 7 }, (_, i) => ({
    start: i * 4, end: (i + 1) * 4,
    visual_grammar: i % 2 ? "three_d_mechanism" : "dot_silhouette",
    narration_idea: "Beat " + i,
    dominant_subject: "System"
  }))
});
assert.equal(legacy.beats[0].visual_grammar, "network");
assert.equal(legacy.beats[1].visual_grammar, "transformation");
assert.ok(new Set(legacy.beats.map(beat => beat.visual_grammar)).size >= 3);
for (let i = 1; i < legacy.beats.length; i++) {
  assert.notEqual(legacy.beats[i].visual_grammar, legacy.beats[i - 1].visual_grammar, "adjacent beats must not reuse the same visual grammar");
}
const supported = normalizeVisualPlan({
  beats: [
    { visual_grammar: "particle_flow" },
    { visual_grammar: "particle_flow", dominant_subject: "Before after comparison" },
    { visual_grammar: "particle_flow", dominant_subject: "Timeline escalation" },
    { visual_grammar: "particle_flow", dominant_subject: "Scale imbalance" },
    { visual_grammar: "particle_flow", dominant_subject: "Layered hidden incentive" }
  ]
});
assert.ok(new Set(supported.beats.map(beat => beat.visual_grammar)).size >= 3);
assert.throws(() => normalizeVisualPlan({ beats: [] }), /at least four beats/);
console.log("Visual plan grammar normalization tests passed.");
