import assert from "node:assert/strict";
import { buildFallbackScene } from "./fallback-scene.mjs";
import { validateSceneSource } from "./scene-contract.mjs";

const plan = {
  visual_thesis: "A single decision triggers a visible chain of consequences.",
  visual_signature: ["ink edges", "red causal path", "layered paper"],
  ending_image: "The scattered causes converge into one clear insight.",
  beats: [
    { start: 0, end: 4, narration_idea: "Draupadi asks a question no one can answer", viewer_takeaway: "The assembly freezes when the question exposes a contradiction", dominant_subject: "Draupadi in the royal assembly", action_and_causal_proof: "A single raised hand stops the room and all gazes turn toward the throne", composition: "Low angle on a foreground silhouette with a deep assembly behind", camera: "Slow push toward the raised hand", transition: "The raised hand becomes the pivot for the next comparison", implementation_notes: "Layered SVG silhouettes and deterministic opacity changes", visual_grammar: "transformation", overlay_text: ["THE QUESTION"] },
    { start: 4, end: 8, narration_idea: "The dice game changes the balance of power", viewer_takeaway: "The result is driven by a sequence of decisions", dominant_subject: "Dice crossing a marked game board", action_and_causal_proof: "Dice roll to a fixed result and the balance shifts toward one side", composition: "Top-down board with large asymmetric pieces", camera: "Short top-down track", transition: "Board line becomes a timeline", implementation_notes: "SVG paths and time-derived dice positions", visual_grammar: "split_comparison", overlay_text: ["THE DICE GAME"] },
    { start: 8, end: 12, narration_idea: "The elders remain silent", viewer_takeaway: "Silence becomes a visible collective choice", dominant_subject: "Silent elders along the court", action_and_causal_proof: "Separate figures dim one by one while the empty center expands", composition: "Wide symmetrical court with a strong empty center", camera: "Slow pullback", transition: "The empty center resolves into a layered cause map", implementation_notes: "Fixed SVG silhouettes with absolute-time opacity", visual_grammar: "timeline", overlay_text: ["SILENCE"] },
    { start: 12, end: 16, narration_idea: "The deeper conflict is between authority and justice", viewer_takeaway: "The visible dispute rests on competing principles", dominant_subject: "Authority and justice represented as opposing forces", action_and_causal_proof: "Two opposing sides pull the central line until it snaps into a clear divide", composition: "Split composition with a bright central seam", camera: "Locked split-screen", transition: "The divide closes into the final insight", implementation_notes: "SVG lines and deterministic split geometry", visual_grammar: "layered_system", overlay_text: ["AUTHORITY / JUSTICE"] }
  ]
};
const html = buildFallbackScene({ title: "Draupadi's Question", story: "Draupadi asks whether the rules of the game can justify the injustice.", plan });
assert.deepEqual(validateSceneSource(html), [], "compiled HTML must satisfy the static export contract");
assert.match(html, /window\.renderAt=renderAt/);
assert.match(html, /window\.getDuration=\(\)=>DURATION/);
assert.match(html, /new URLSearchParams\(window\.location\.search\)/);
assert.doesNotMatch(html, /Math\.random\s*\(/);
assert.match(html, /Draupadi in the royal assembly/, "scene should expose the story-specific dominant subject");
assert.match(html, /data-theme="parchment"/, "mythology scenes should use the parchment art direction");
assert.match(html, /function drawDraupadiConstruction\(/, "Draupadi beats should have a real deterministic silhouette renderer");
assert.match(html, /function drawDiceGame\(/, "dice-game beats should have a dedicated visual renderer");
assert.match(html, /function drawAssembly\(/, "assembly beats should have a dedicated visual renderer");
assert.match(html, /function drawBalance\(/, "authority-versus-justice beats should have a dedicated visual renderer");
assert.match(html, /THE QUESTION/, "scene should preserve authored labels");
assert.match(html, /data-scene/, "renderer should tag the current visual grammar for diagnostics");
console.log("Deterministic plan compiler contract and story-specific labels passed.");
