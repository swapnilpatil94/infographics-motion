"""NARRATION PACING (neuromarketing rhythm): tighten dead air, then speed up (pitch-preserving) so every beat lands fast.

  raw TTS + word timings -> per-beat chunks -> internal gaps capped (<= gap_cap) -> 0.10 s between beats -> ffmpeg atempo -> paced.wav + segments (word times remapped)
Speaking-rate target for a Short: ~3.1-3.4 words/s (about 190 wpm) versus ~2.3 words/s natural Hindi TTS. The report records the before/after rate.
"""
import json
import os
import subprocess

import numpy as np

from engine.factory import audio_pipeline as AP

SR = AP.SR


def flatten_words(segments_json):
    d = json.load(open(segments_json, encoding="utf-8"))
    words = []
    for s in d["segments"]:
        words += [w for w in (s.get("words") or [])]
    return words


def assign_beats(words, beats):
    """beats: [(id, text)] -> [(id, text, [words])] by consuming whitespace tokens in order."""
    out, k = [], 0
    for bid, text in beats:
        n = len(text.split())
        out.append((bid, text, words[k:k + n]))
        k += n
    if k != len(words):
        raise ValueError(f"word count mismatch: beats consume {k} words, TTS aligned {len(words)}")
    return out


def pace(wav_in, beats_words, wav_out, gap_cap=0.14, beat_gap=0.10, lead=0.22, tail=0.35, tempo=1.16, pad_pre=0.06, pad_post=0.10):
    raw = AP.read_audio(wav_in)
    pieces, segs, cursor = [np.zeros(int(lead * SR), np.float32)], [], lead
    for bid, text, words in beats_words:
        w0, w1 = words[0]["start"], words[-1]["end"]
        a, b = max(0.0, w0 - pad_pre), min(len(raw) / SR, w1 + pad_post)
        chunk_words, out_words = list(words), []
        pos = a
        first = cursor
        for i, w in enumerate(chunk_words):
            if i:
                gap = w["start"] - chunk_words[i - 1]["end"]
                if gap > gap_cap:                                  # cut the excess out of the middle of the gap
                    seg = raw[int(pos * SR):int((chunk_words[i - 1]["end"] + gap_cap / 2) * SR)]
                    pieces.append(seg)
                    cursor += len(seg) / SR
                    pos = w["start"] - gap_cap / 2
            out_words.append(dict(word=w["word"], _t0=w["start"], _t1=w["end"], _pos=pos, _cursor=cursor))
        seg = raw[int(pos * SR):int(b * SR)]
        pieces.append(seg)
        cursor += len(seg) / SR
        # word times in the new timeline: recompute by walking the pieces (positions were recorded before each cut)
        segs.append(dict(id=bid, text=text, words=out_words, raw=(w0, w1)))
        pieces.append(np.zeros(int(beat_gap * SR), np.float32))
        cursor += beat_gap
    pieces.append(np.zeros(int(tail * SR), np.float32))
    audio = np.concatenate(pieces)
    tmp = wav_out + ".pre.wav"
    _write(tmp, audio)
    _atempo(tmp, wav_out, tempo)
    os.remove(tmp)
    return audio, segs


def _write(path, a):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def _atempo(src, dst, tempo):
    f = []
    t = tempo
    while t > 2.0:
        f.append("atempo=2.0")
        t /= 2.0
    while t < 0.5:
        f.append("atempo=0.5")
        t *= 2.0
    f.append(f"atempo={t:.5f}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", ",".join(f), "-ar", str(SR), "-ac", "1", dst], check=True)


def build(wav_in, segments_json, beats, wav_out, seg_out, tempo=1.16, gap_cap=0.14, beat_gap=0.10, lead=0.22, tail=0.35):
    """Full pipeline; returns the paced narration dict (also written to seg_out)."""
    words = flatten_words(segments_json)
    bw = assign_beats(words, beats)
    raw = AP.read_audio(wav_in)
    # ---- rebuild the timeline explicitly so word times are exact
    pieces, cursor = [np.zeros(int(lead * SR), np.float32)], lead
    segs = []
    for bid, text, ws in bw:
        a = max(0.0, ws[0]["start"] - 0.06)
        b = min(len(raw) / SR, ws[-1]["end"] + 0.10)
        new_words, pos, first_cursor = [], a, cursor
        for i, w in enumerate(ws):
            if i:
                gap = w["start"] - ws[i - 1]["end"]
                if gap > gap_cap:
                    keep_end = ws[i - 1]["end"] + gap_cap / 2
                    seg = raw[int(pos * SR):int(keep_end * SR)]
                    pieces.append(seg)
                    cursor += len(seg) / SR
                    pos = w["start"] - gap_cap / 2
            new_words.append(dict(word=w["word"], start=cursor + (w["start"] - pos), end=cursor + (w["end"] - pos)))
        seg = raw[int(pos * SR):int(b * SR)]
        pieces.append(seg)
        cursor += len(seg) / SR
        segs.append(dict(beat_id=bid, text=text, start_seconds=new_words[0]["start"], end_seconds=new_words[-1]["end"], words=new_words))
        pieces.append(np.zeros(int(beat_gap * SR), np.float32))
        cursor += beat_gap
    pieces.append(np.zeros(int(tail * SR), np.float32))
    audio = np.concatenate(pieces)
    tmp = wav_out + ".pre.wav"
    os.makedirs(os.path.dirname(wav_out) or ".", exist_ok=True)
    _write(tmp, audio)
    _atempo(tmp, wav_out, tempo)
    os.remove(tmp)
    for s in segs:                                                    # atempo divides every time by `tempo`
        s["start_seconds"] /= tempo
        s["end_seconds"] /= tempo
        for w in s["words"]:
            w["start"] /= tempo
            w["end"] /= tempo
    n_words = sum(len(s["words"]) for s in segs)
    speech = sum(s["end_seconds"] - s["start_seconds"] for s in segs)
    out = dict(segments=segs, duration_seconds=len(audio) / SR / tempo, tempo=tempo, gap_cap=gap_cap, beat_gap=beat_gap,
               raw_duration=len(raw) / SR, raw_words_per_s=round(n_words / (len(raw) / SR), 2), paced_words_per_s=round(n_words / (len(audio) / SR / tempo), 2),
               words=n_words, audio=wav_out)
    json.dump(out, open(seg_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out
