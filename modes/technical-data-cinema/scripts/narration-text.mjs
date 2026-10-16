/**
 * Remove non-spoken production control markers before sending narration to TTS.
 * PAUSE becomes natural punctuation; END is a control marker, not spoken text.
 * Other bracketed performance cues are preserved for the existing directed-cue adapter.
 */
export function normalizeNarrationForTTS(value) {
  return String(value ?? "")
    .replace(/\[\s*PAUSE\s*\]/gi, "…")
    .replace(/\[\s*END\s*\]/gi, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
