"""NARRATION TIMELINE: the temporal spine of a film. Builds the `NarrationTimeline` from whatever the user brings:

    timing JSON (+ audio)   -> used as given
    audio + text            -> segment times from the audio itself (speech region + silence gaps; NOT forced alignment - stated in `warnings`)
    text only               -> Chatterbox Hindi TTS (real audio, real word times) or, for a quick plan, an estimate
Segment durations are never configured: they are whatever the narration is.
"""
import json
import os
import re
import subprocess

from engine.shorts.raster import ROOT
from kathaya import schemas
from kathaya.story import hindi

END_MARKS = re.compile(r"(?<=[।?!])\s+|(?<=\.)\s+(?=\D)")
WPS = 2.7


def segment_text(text):
    """narration text -> list of segment strings: one per line / sentence / dash-separated clause; tiny fragments are joined to their neighbour"""
    parts = []
    for line in (text or "").replace("\r", "").split("\n"):
        for chunk in re.split(r"\s*[—–]\s*", line):
            chunk = chunk.strip()
            if chunk:
                parts += [p.strip() for p in END_MARKS.split(chunk) if p.strip()]
    out = []
    for p in parts:
        p = p.strip(" \t'\"“”‘’")
        if not p:
            continue
        if out and len(p.split()) < 2:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def _timeline(segs, source, duration, audio, fmt, warnings, language="hi"):
    tl = dict(schema=f"kathaya.narration_timeline/{schemas.VERSION}", language=language, format=fmt, source=source, audio=audio, duration=round(duration, 3), warnings=warnings, narration=segs)
    bad = schemas.validate("NarrationTimeline", tl)
    if bad:
        raise ValueError(f"invalid narration timeline: {bad[:3]}")
    prev = -1
    for s in segs:
        if s["end"] <= s["start"] or s["start"] < prev - 1e-6:
            raise ValueError(f"segment {s['id']} has impossible times {s['start']}..{s['end']}")
        prev = s["end"]
    return tl


def _abs(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def from_timing_json(obj, audio=None, fmt="short"):
    """accepts the new {"narration":[{id,start,end,text}]} shape, the legacy {"segments":[...],"audio":...}, or a bare list"""
    if isinstance(obj, str):
        obj = json.loads(obj)
    segs_in = obj if isinstance(obj, list) else (obj.get("narration") or obj.get("segments"))
    if not segs_in:
        raise ValueError("timing JSON has neither 'narration' nor 'segments'")
    audio = audio or (obj.get("audio") if isinstance(obj, dict) else None)
    if audio in ("UPLOADED", ""):
        audio = None
    segs = []
    for i, s in enumerate(segs_in):
        for k in ("text", "start", "end"):
            if k not in s:
                raise ValueError(f"segment {i + 1} lacks '{k}'")
        d = dict(id=f"N{i + 1:02d}", start=round(float(s["start"]), 3), end=round(float(s["end"]), 3), text=s["text"].strip(), orig_id=s.get("id"))
        d["spoken"] = s.get("spoken") or hindi.spoken(d["text"])
        if s.get("words"):
            d["words"] = [dict(word=w["word"], start=round(float(w["start"]), 3), end=round(float(w["end"]), 3)) for w in s["words"]]
        segs.append(d)
    if audio and not os.path.exists(_abs(audio)):
        raise ValueError(f"audio file missing: {audio}")
    return _timeline(segs, "timing_json", segs[-1]["end"], audio, fmt, [], hindi.language_of(" ".join(s["text"] for s in segs)))


def silences(audio):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", "silencedetect=noise=-33dB:d=0.16", "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    out = [(a, b) for a, b in zip(st, en)]
    if len(st) > len(en):                                                                # a silence that runs to the end of the file
        out.append((st[-1], None))
    return out


def from_audio_and_text(audio, text, fmt="short"):
    """segment times from the audio: the speech region (leading / trailing silence trimmed), words distributed proportionally, every interior boundary snapped to the nearest real silence gap"""
    a = _abs(audio)
    dur = _probe_duration(a)
    parts = segment_text(text)
    if not parts:
        raise ValueError("the narration text is empty")
    sil = silences(a)
    s0 = sil[0][1] if sil and sil[0][0] < 0.05 and sil[0][1] else 0.0
    s1 = sil[-1][0] if sil and sil[-1][1] is None else dur
    gaps = [(x, y) for x, y in sil if y is not None and x > s0 and y < s1]
    w = [max(1, len(p.split())) for p in parts]
    tot = float(sum(w))
    cum, b = 0.0, []
    for x in w[:-1]:
        cum += x
        b.append(s0 + (s1 - s0) * cum / tot)
    used, bounds = set(), []
    span = (s1 - s0) / max(len(parts), 1)
    for k, t in enumerate(b):
        best = min(((abs((g[0] + g[1]) / 2 - t), j) for j, g in enumerate(gaps) if j not in used), default=None)
        if best and best[0] <= 0.6 * span and (not bounds or gaps[best[1]][0] > bounds[-1][1]):
            used.add(best[1])
            bounds.append(gaps[best[1]])
        else:
            bounds.append((t - 0.04, t + 0.04))
    edges = [(s0, None)] + [(g[0], g[1]) for g in bounds] + [(None, s1)]
    segs = []
    for i, p in enumerate(parts):
        st = edges[i][1] if edges[i][1] is not None else s0
        en = edges[i + 1][0] if edges[i + 1][0] is not None else s1
        segs.append(dict(id=f"N{i + 1:02d}", start=round(st, 3), end=round(max(en, st + 0.2), 3), text=p, spoken=hindi.spoken(p)))
    snapped = len(used)
    warn = [f"segment times were derived from the audio (speech region {s0:.2f}-{s1:.2f} s, {snapped} of {len(bounds)} boundaries snapped to real silences); this is not forced alignment - supply a timing JSON for exact word times"]
    return _timeline(segs, "audio_and_text", max(dur, segs[-1]["end"]), audio, fmt, warn, hindi.language_of(text))


def estimated(text, fmt="short"):
    parts = segment_text(text)
    t, segs = 0.25, []
    for i, p in enumerate(parts):
        d = max(1.0, len(hindi.spoken(p).split()) / WPS) + 0.2
        segs.append(dict(id=f"N{i + 1:02d}", start=round(t, 3), end=round(t + d, 3), text=p, spoken=hindi.spoken(p)))
        t += d + 0.15
    return _timeline(segs, "estimated", segs[-1]["end"], None, fmt, ["times are ESTIMATED from word counts (no audio yet)"], hindi.language_of(text))


def from_tts(text, out_dir, fmt="short", log=print):
    """Chatterbox Hindi narration (content-hash cached) with real word times. Natural pace: no re-tempo window."""
    from engine.skeleton import narration_io as NI
    parts = segment_text(text)
    lang = hindi.language_of(text)
    if lang != "hi":
        raise ValueError(f"the narrator voice (Chatterbox Hindi) reads Hindi only; this text looks {lang}. Upload your own narration audio (and optionally a timing JSON), or write the narration in Devanagari.")
    beats = [(f"n{i + 1:02d}", hindi.spoken(p)) for i, p in enumerate(parts)]
    bad = [t for _, t in beats if re.search(r"[A-Za-z0-9]", t)]
    if bad:
        raise ValueError(f"the narrator cannot read Latin letters or digits that remain after normalisation: {bad[0][:60]!r}")
    path = NI.synthesize(beats, out_dir, tempo=1.0, lo=0.0, hi=1e9, log=log)
    seg = json.load(open(path, encoding="utf-8"))
    segs = []
    for i, (s, p) in enumerate(zip(seg["segments"], parts)):
        segs.append(dict(id=f"N{i + 1:02d}", start=s["start"], end=s["end"], text=p, spoken=beats[i][1], words=s.get("words") or []))
    return _timeline(segs, "tts", segs[-1]["end"], seg["audio"], fmt, [], "hi")


def build(text=None, audio=None, timing=None, fmt="short", mode="auto", workdir=None, log=print):
    """the one entry point. mode: auto (timing > audio+text > TTS) | estimated (never synthesise)"""
    if timing:
        tl = from_timing_json(timing, audio, fmt)
    elif audio:
        if not text or not text.strip():
            raise ValueError("audio without a text or timing JSON: give the narration text (or timing) so the visuals can follow it")
        tl = from_audio_and_text(audio, text, fmt)
    elif not (text or "").strip():
        raise ValueError("no narration: paste the story / narration text")
    elif mode == "estimated":
        tl = estimated(text, fmt)
    else:
        tl = from_tts(text, workdir or os.path.join(ROOT, "output/kathaya/_tts"), fmt, log)
    if fmt == "short" and tl["duration"] > 60.0:
        tl["warnings"].append(f"the narration is {tl['duration']:.0f} s: longer than a 60 s Short; choose Long-form or shorten it")
    return tl
