# Local Chatterbox performance generation (Script → Audio)

This first iteration adds **performance-directed takes** to the existing local Chatterbox + WhisperX Script → Audio flow. It does not call a cloud API and does not fine-tune the model.

## Try it

1. Start the Studio UI with `python3 studio.py --ui`.
2. Open **Script → Audio**.
3. Select **Performance generation → Directed**.
4. Click **Load emotional example**.
5. Keep the initial **Storytelling** style and start around **65% expression intensity**.
6. Generate and listen for changes in hook urgency, suspense, reveal emphasis, explanatory calm, and transitions.

The sample uses these optional line-prefix cues (not spoken aloud):

- `[HOOK]` — attention-grabbing opening
- `[CURIOUS]` — question-led, interested delivery
- `[SUSPENSE]` — restrained tension
- `[REVEAL]` — stronger emphasis on a discovery
- `[EXPLAIN]` — clear, controlled explanation
- `[URGENT]` — time-sensitive warning; use sparingly
- `[CALM]` — reassuring or reflective close
- `[DEFAULT]` — return to the base storytelling preset

Lines with the same cue are generated together where possible. A change of cue starts a new take so Chatterbox settings can change between thought groups. **Uniform** mode ignores the cues and uses one delivery throughout.

## What the adapter changes

The performance adapter blends the selected cue's target values with the existing Chatterbox settings using the expression-intensity slider. It only changes supported generation parameters: `exaggeration`, `cfg_weight`, and `temperature`. The existing reference voice, Hindi language selection, timing/alignment, WAV export and production pipeline remain in place.

These targets are experimental starting points, not guaranteed emotion controls. Chatterbox does not necessarily interpret cue labels as semantic acting instructions; the cues select different supported parameter combinations. Reference-audio quality and the script itself still matter. If settings sound exaggerated or inconsistent, reduce intensity or use Uniform mode.

## What success should sound like

- The hook feels more immediate without shouting.
- Suspense lines feel more controlled.
- The reveal has more vocal emphasis than the explanation.
- The closing returns to a calmer, conversational tone.
- Hindi/Hinglish pronunciation remains intelligible.
- Joins between takes do not sound like unrelated clips.

Compare the same script with **Uniform** and **Directed** at the same style and voice reference. Do not judge only by loudness or pitch; listen for useful variation, naturalness, continuity, and pronunciation. The output remains fully local.

## Current limits

- Cue assignment is explicit/manual in this first test; it is not yet an automatic local-LLM performance director.
- Parameter changes cannot guarantee specific emotions, and every new take may vary.
- No new model is downloaded and no cloud service is required.
- This is an experiment branch; validate locally before merging into the main production path.


## Cue design decisions

This intentionally stays a small, script-writer-friendly vocabulary. Use one cue per thought group, not one emotion label per sentence. The cue is stripped before synthesis and is never spoken. Keep adjacent lines under the same cue together to protect continuity; a cue change may start a new take.

We do not add generic `[ANGER]`, `[SAD]`, `[FEAR]`, or `[WHISPER]` cues in this iteration. The supported generation controls do not guarantee those specific acting behaviors, and a larger label vocabulary would imply more control than we have validated. If a future use case needs them, evaluate dedicated model capabilities and reference recordings first.

## Hindi model status (research, not yet switched)

The current adapter uses the **Chatterbox Multilingual V3 family** with `language_id="hi"` when the installed package supports the V3 selector. Its generated `model_info.json` explicitly records `dedicated_hindi_checkpoint: false`. It is not currently loading the dedicated Hindi single-language checkpoint.

Resemble AI publishes `ResembleAI/Chatterbox-Multilingual-hi`, a Hindi-specific fine-tune in its V3 single-language pack. This is the strongest next candidate to A/B test for Hindi quality. Do not assume it is a drop-in model-name change: its Hindi T3 weights and shared V3 speech decoder need to be loaded using a compatible loader. Keep the existing multilingual path as the known baseline until the dedicated checkpoint is loaded and tested locally.

Suggested evaluation: render the same 20–30 second Hindi/Hinglish script with the same reference voice, text, seed where supported, and comparable settings. Score Devanagari pronunciation, English technical terms, continuity across sentences, natural pacing, speaker similarity, and emotional variation. Keep whichever version wins listening tests; the Hindi-only fine-tune may not necessarily win on English code-switching.
