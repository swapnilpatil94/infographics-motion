import assert from "node:assert/strict";
import { normalizeNarrationForTTS } from "./narration-text.mjs";

assert.equal(
  normalizeNarrationForTTS("पहला वाक्य। [PAUSE]\nदूसरा वाक्य। [END]"),
  "पहला वाक्य। …\nदूसरा वाक्य।"
);
assert.equal(normalizeNarrationForTTS("[PAUSE] [END]"), "…");
assert.equal(
  normalizeNarrationForTTS("[HOOK] यह एक सवाल है। [REVEAL] जवाब सामने है।"),
  "[HOOK] यह एक सवाल है। [REVEAL] जवाब सामने है।"
);
assert.equal(normalizeNarrationForTTS("सिर्फ़ कहानी।"), "सिर्फ़ कहानी।");
console.log("Narration control-marker normalization tests passed.");
