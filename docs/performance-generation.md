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

- `[HOOK]` — more energetic opening
- `[SUSPENSE]` — controlled, tense delivery
- `[REVEAL]` — stronger emphasis
- `[EXPLAIN]` — clearer, less dramatic explanation
- `[CALM]` — calmer closing
- `[DEFAULT]` — use the base storytelling preset

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
