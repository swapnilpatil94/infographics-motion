"""Test-input helper (NOT part of the factory): story.md -> sentence segments -> real Hindi narration + segments JSON.

Stands in for the user's own narration pipeline (mythic-video-studio): produces
  narration/<name>.wav  and  narration/<name>.wav.segments.json
in the same shape that tool writes (segments with start_seconds/end_seconds/text; word timings included as an extra).
Usage: .venv/bin/python tools/make_narration.py stories/x.md narration/x
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.shorts import voice          # noqa: E402


def sentences(md, max_words=17):
    text = "\n".join(l for l in md.splitlines() if not l.startswith("#"))
    raw = [s.strip() for s in re.split(r"(?<=[।?!])\s+", text.replace("\n", " ")) if s.strip()]
    out = []
    for s in raw:                                         # split over-long sentences at commas
        words = s.split()
        if len(words) <= max_words:
            out.append(s)
            continue
        cur = []
        for w in words:
            cur.append(w)
            if len(cur) >= 8 and w.endswith(","):
                out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
    return out


if __name__ == "__main__":
    story, base = sys.argv[1], sys.argv[2]
    segs = sentences(open(story, encoding="utf-8").read())
    print(len(segs), "segments,", sum(len(s.split()) for s in segs), "words", flush=True)
    beats = [dict(id=f"n{i + 1:03d}", text=t) for i, t in enumerate(segs)]
    v = voice.synthesize(beats, seed=42)
    key = voice._key(beats, 42)
    os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
    shutil.copy(os.path.join(voice.VOICE_DIR, key, "narration.wav"), base + ".wav")
    out = dict(segments=[dict(beat_id=b["id"], text=b["text"], start_seconds=round(b["start"], 3), end_seconds=round(b["end"], 3),
                              words=[dict(word=w["word"], start=round(w["start"], 3), end=round(w["end"], 3)) for w in b["words"]])
                         for b in v["beats"]], duration_seconds=round(v["duration"], 3))
    json.dump(out, open(base + ".wav.segments.json", "w"), ensure_ascii=False, indent=1)
    print("DONE", base + ".wav", round(v["duration"], 1), "s", flush=True)
