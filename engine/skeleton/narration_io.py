"""NARRATION I/O: the narration SEGMENTS JSON is the factory's audio contract.

    {"segments": [{"id","text","start","end","words":[{"word","start","end"}]}], "audio": "path/to/paced.wav", "tts": "chatterbox", "tempo": 1.08}

`load(path)` validates and returns it; `synthesize(beats, out_dir)` produces one from script lines (Chatterbox Hindi TTS, content-hash cached, paced into the 45-60 s window) - the same file a user could supply
from any other voice as long as every segment carries start/end (and ideally word timings) and the audio file exists.
"""
import hashlib
import json
import os
import subprocess

from engine.shorts.raster import ROOT


class NarrationInvalid(Exception):
    pass


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    segs = d["segments"] if isinstance(d, dict) else d
    audio = d.get("audio") if isinstance(d, dict) else None
    errs = []
    prev = -1.0
    for i, s in enumerate(segs):
        for k in ("id", "text", "start", "end"):
            if k not in s:
                errs.append(f"segment {i} lacks '{k}'")
        if "start" in s and "end" in s:
            if s["end"] <= s["start"]:
                errs.append(f"segment {s.get('id', i)}: end <= start")
            if s["start"] < prev - 1e-6:
                errs.append(f"segment {s.get('id', i)} starts before the previous one ended")
            prev = s["end"]
    if audio:
        ap = audio if os.path.isabs(audio) else os.path.join(ROOT, audio)
        if not os.path.exists(ap):
            errs.append(f"audio file missing: {audio}")
    if errs:
        raise NarrationInvalid("; ".join(errs[:6]))
    return dict(segments=segs, audio=audio, tts=(d.get("tts") if isinstance(d, dict) else "provided") or "provided", tempo=(d.get("tempo") if isinstance(d, dict) else 1.0) or 1.0)


def synthesize(beats, out_dir, tempo=1.08, lo=44.0, hi=60.0, log=print):
    """beats: [(id, text)] -> path of the segments JSON (written to out_dir/segments.json)"""
    from engine.skeleton import pace
    h = hashlib.sha1(json.dumps(beats, ensure_ascii=False).encode()).hexdigest()[:12]
    d = os.path.join(ROOT, "narration/production", h)
    os.makedirs(d, exist_ok=True)
    bj = os.path.join(d, "beats.json")
    json.dump([dict(id=i, text=t) for i, t in beats], open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    raw, seg = os.path.join(d, "raw.wav"), os.path.join(d, "raw.wav.segments.json")
    if not (os.path.exists(raw) and os.path.exists(seg)):
        log(f"[tts] Chatterbox Hindi for {len(beats)} lines (cache {h}) ...")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), os.path.join(ROOT, "tools/tts_beats.py"), bj, os.path.join(d, "raw")], check=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT))
    os.makedirs(out_dir, exist_ok=True)
    pw, pj = os.path.join(out_dir, "paced.wav"), os.path.join(out_dir, "paced.json")
    for _ in range(8):                                                       # re-tempo (pitch-preserving) until the film lands in the duration window; no new TTS
        p = pace.build(raw, seg, beats, pw, pj, tempo=tempo)
        dur = p["segments"][-1]["end_seconds"] + 3.0
        if lo <= dur <= hi:
            break
        new = round(min(1.3, max(0.9, tempo * (dur / (0.5 * (lo + hi))) ** 0.8)), 3)
        if new == tempo:
            break
        tempo = new
    out = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in p["segments"]], audio=os.path.relpath(pw, ROOT), tts="chatterbox", tempo=tempo,
               pacing={k: p[k] for k in ("raw_duration", "raw_words_per_s", "paced_words_per_s", "gap_cap", "beat_gap", "tempo")})
    path = os.path.join(out_dir, "segments.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path
