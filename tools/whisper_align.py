#!/usr/bin/env python3
"""Whisper (whisperx) forced-alignment + dead-air-tightening adapter for infographics-motion.

Contract: invoked as `whisper_align.py <narration.wav> <segments.json> <output.json>`.

`segments.json` is the `.segments.json` sidecar written by tools/chatterbox_tts.py:
{"segments": [{"beat_id","text","start_seconds","end_seconds"}, ...], "duration_seconds": N}.
Those start/end values are our own generation-time bookkeeping, not a real forced alignment —
this script uses them only as rough per-beat bounds, then runs whisperx's wav2vec2 CTC forced
alignment against the KNOWN script text (not ASR) to get precise word-level timestamps.

Chatterbox's own amplitude-threshold trim (in chatterbox_tts.py) does not catch every gap —
some sentence boundaries still carry 0.5-2s of near-silence (soft breath/room tone that reads as
"loud enough" to a naive threshold but is still dead air to a viewer). Real word-level alignment
finds these precisely, so this script also SPLICES the audio: any inter-word gap wider than a
natural pause (0.35s) is trimmed down to that cap, directly on the actual waveform (not a global
tempo change), and every word timestamp is remapped to match. This only ever removes silence
that isn't between two spoken words — it never touches speech.

Writes `<output.json>`:
{"beats": [{"beat_id", "words": [{"word","start","end","score"}, ...]}, ...]}
and (if any tightening happened) overwrites `<narration.wav>` and its `.segments.json` sidecar
in place with the tightened audio and remapped boundaries, so re-running this script against
already-tightened audio is a no-op (idempotent).

Requires whisperx (already installed in the pyenv 3.12.0 environment on this machine), with the
Hindi wav2vec2 alignment model (theainerd/Wav2Vec2-large-xlsr-hindi) already cached locally.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

GAP_CAP = 0.35   # max inter-word silence to keep, seconds — a natural sentence-boundary pause
LEAD_CAP = 0.15  # max silence to keep before the first word
TRAIL_CAP = 0.35  # max silence to keep after the last word


def log(message: str) -> None:
    print(f"[whisper_align] {message}", file=sys.stderr, flush=True)


def tighten(out_beats, duration: float):
    """Returns (removals, total_removed) where removals is a sorted list of
    (start, end) ranges in the ORIGINAL audio timeline to cut out."""
    flat = [w for beat in out_beats for w in beat["words"]]
    if not flat:
        return [], 0.0

    removals = []
    if flat[0]["start"] > LEAD_CAP:
        removals.append((0.0, flat[0]["start"] - LEAD_CAP))
    for i in range(1, len(flat)):
        gap = flat[i]["start"] - flat[i - 1]["end"]
        if gap > GAP_CAP:
            removals.append((flat[i - 1]["end"] + GAP_CAP, flat[i]["start"]))
    if duration - flat[-1]["end"] > TRAIL_CAP:
        removals.append((flat[-1]["end"] + TRAIL_CAP, duration))

    total_removed = sum(e - s for s, e in removals)
    return removals, total_removed


def remap(t: float, removals) -> float:
    removed_before = 0.0
    for (rs, re) in removals:
        if t <= rs:
            break
        removed_before += min(t, re) - rs
    return max(0.0, t - removed_before)


def main() -> int:
    if len(sys.argv) < 4:
        log("usage: whisper_align.py <narration.wav> <segments.json> <output.json>")
        return 2

    audio_path = Path(sys.argv[1])
    segments_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    if not audio_path.exists():
        log(f"audio not found: {audio_path}")
        return 1
    if not segments_path.exists():
        log(f"segments sidecar not found: {segments_path}")
        return 1

    sidecar = json.loads(segments_path.read_text(encoding="utf-8"))
    beats = sidecar.get("segments") or []
    if not beats:
        log("no segments to align")
        return 1

    import numpy as np
    import soundfile as sf
    import whisperx

    device = "cpu"  # whisperx alignment (wav2vec2 CTC) is fast enough on CPU for a ~80s clip
    log(f"loading Hindi alignment model (device={device})")
    model, metadata = whisperx.load_align_model(language_code="hi", device=device)

    audio = whisperx.load_audio(str(audio_path))
    duration = len(audio) / 16000.0

    transcript = []
    for beat in beats:
        start = max(0.0, float(beat["start_seconds"]))
        end = min(duration, float(beat["end_seconds"]))
        if end <= start:
            continue
        transcript.append({"start": start, "end": end, "text": beat["text"]})

    log(f"aligning {len(transcript)} beat segments against {duration:.2f}s of audio")
    result = whisperx.align(transcript, model, metadata, audio, device, return_char_alignments=False)

    aligned_segments = result.get("segments", [])
    out_beats = []
    for beat, aligned in zip(beats, aligned_segments):
        words = []
        for w in aligned.get("words", []):
            if "start" not in w or "end" not in w:
                continue  # whisperx drops timing for words it couldn't confidently place
            words.append({
                "word": w["word"],
                "start": round(float(w["start"]), 3),
                "end": round(float(w["end"]), 3),
                "score": round(float(w.get("score", 0.0)), 3),
            })
        out_beats.append({"beat_id": beat["beat_id"], "words": words})
        log(f"beat {beat['beat_id']}: {len(words)}/{len(beat['text'].split())} words placed")

    removals, total_removed = tighten(out_beats, duration)
    if total_removed > 0.05:
        log(f"tightening {len(removals)} dead-air gap(s), removing {total_removed:.2f}s total")
        native_audio, native_sr = sf.read(str(audio_path), dtype="float32", always_2d=False)
        kept = []
        cursor = 0.0
        for (rs, re) in removals:
            if rs > cursor:
                kept.append((cursor, rs))
            cursor = max(cursor, re)
        if cursor < duration:
            kept.append((cursor, duration))
        pieces = [native_audio[int(round(s * native_sr)):int(round(e * native_sr))] for s, e in kept]
        tightened_audio = np.concatenate(pieces) if pieces else native_audio
        sf.write(str(audio_path), tightened_audio, native_sr)

        for beat in out_beats:
            for w in beat["words"]:
                w["start"] = round(remap(w["start"], removals), 3)
                w["end"] = round(remap(w["end"], removals), 3)
        for beat in beats:
            beat["start_seconds"] = round(remap(float(beat["start_seconds"]), removals), 3)
            beat["end_seconds"] = round(remap(float(beat["end_seconds"]), removals), 3)
        sidecar["duration_seconds"] = round(remap(duration, removals), 3)
        segments_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"tightened audio written: {audio_path} ({len(tightened_audio) / native_sr:.2f}s, was {duration:.2f}s)")
    else:
        log("no dead-air gaps exceed the cap; audio unchanged")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"beats": out_beats}, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
