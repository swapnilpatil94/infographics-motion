# Hindi/Hinglish Storytelling TTS

## What changed

The Script → Audio screen exposes three delivery presets and a Hindi-first pronunciation option. For this standalone export path, up to three adjacent narration lines (at most 28 whitespace tokens) are generated as one connected take to reduce the sentence-by-sentence reset effect. Presets are starting points for listening tests, not a guarantee that every reference voice will sound natural.

| Preset | exaggeration | cfg_weight | temperature | tempo | pause pad |
|---|---:|---:|---:|---:|---:|
| Storytelling (default) | 0.68 | 0.30 | 0.65 | 0.84 | 0.16 s |
| Conversational | 0.52 | 0.38 | 0.68 | 0.88 | 0.14 s |
| Dramatic | 0.78 | 0.25 | 0.60 | 0.80 | 0.22 s |

The values are passed to the companion mythic-video-studio/tools/chatterbox_tts.py through per-job JSON. The existing production environment remains the source of truth for the model, Python interpreter, and reference audio.

## Why these defaults

Resemble AI's official Chatterbox guidance says the standard settings are a useful baseline; for expressive/dynamic delivery, try exaggeration around 0.7 or higher and cfg_weight around 0.3. It also notes that higher exaggeration tends to speed up speech, so a lower cfg_weight can help pacing. This project adds a finishing tempo of 0.84 as a starting point for a calmer Reel narration pace. Listen and adjust per reference voice.

Official reference: https://github.com/resemble-ai/chatterbox

## Reference audio matters

Use a clean 5–10 second reference with one adult Hindi speaker, close-mic, little room echo, no music, no clipping, and a delivery close to the intended narrator. The reference should contain Hindi if Hindi is the target language. A calm, confident documentary read is a better clone prompt than shouting, acting, or heavily processed audio. Use only a voice you have permission to clone.

## Hindi/Hinglish pronunciation

The Hindi-first option applies a small one-token-to-one-token pronunciation dictionary to common English/technical words in the TTS input (for example, AI → एआई, OpenAI → ओपनएआई). The user's original script remains the displayed/caption text. Unknown English terms remain unchanged. Select “Keep exact script pronunciation” if a specific term sounds worse after conversion.

This is deliberately conservative. A complete automatic transliteration system could damage brand names, acronyms, numbers, and code-mixed phrases; extend the dictionary only after listening to the output.

## Test procedure

1. Use the same reference audio and the opening 10–15 seconds of a real Hindi/Hinglish script.
2. Generate the three presets; do not compare different scripts or references at the same time.
3. Listen on headphones and a phone speaker. Rate naturalness, pronunciation, pacing, pauses, and voice similarity.
4. Check that numbers and English terms are spoken correctly before generating a full script.
5. Inspect the timing JSON. When WhisperX misses words, estimated timings are explicitly flagged; don't use those estimated word timings for karaoke-style captions without reviewing them.
6. If all presets still sound synthetic, change the reference clip or benchmark a Hindi-specialized engine rather than trying extreme parameter values.

## Known limitations

- Chatterbox cannot be made “perfect” by settings alone; model checkpoint, reference quality, language mixing, text normalization, and sentence boundaries all matter.
- This patch has not yet been acoustically validated on the user's Mac. Run a short local A/B test before using the result in a published Reel.
- The companion production TTS adapter repository has a branch: feat/hindi-storytelling-chatterbox.
