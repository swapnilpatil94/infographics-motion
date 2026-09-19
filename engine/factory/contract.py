"""Input contract: story.md + narration segments JSON (+ optional project/style/topic overrides) -> normalized Story.

Minimum input (nothing else is required):
    story.md                        markdown; '# title' optional; paragraphs separated by blank lines
    <name>.wav.segments.json        narration segments; the audio is <name>.wav beside it
Accepted segment JSON shapes:
    {"segments": [{"beat_id"|"id", "text", "start_seconds"|"start", "end_seconds"|"end", "speaker"?, "confidence"?,
                   "emphasis"?, "pause"?, "words"?: [{"word","start","end"}]}], "duration_seconds"?}
    [ {"text", "start", "end", ...}, ... ]
Optional: project.json (title/language/format), style_override.json, topic_override.json (see docs/FACTORY.md).
"""
import json
import os
import re
import unicodedata

_NORM = re.compile(r"[\s\"'“”‘’,.;:!?।…\-–—()\[\]]+")


def norm(s):
    return _NORM.sub("", unicodedata.normalize("NFC", s)).lower()


def parse_story(path):
    text = open(path, encoding="utf-8").read()
    title, paras, cur = None, [], []
    for line in text.splitlines():
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.strip() == "":
            if cur:
                paras.append(" ".join(cur))
                cur = []
        elif not line.startswith("#"):
            cur.append(line.strip())
    if cur:
        paras.append(" ".join(cur))
    return dict(title=title or os.path.splitext(os.path.basename(path))[0], paragraphs=paras, path=path)


def load_narration(path):
    raw = json.load(open(path, encoding="utf-8"))
    items = raw["segments"] if isinstance(raw, dict) else raw
    segs = []
    for i, s in enumerate(items):
        start = s.get("start_seconds", s.get("start"))
        end = s.get("end_seconds", s.get("end"))
        if start is None or end is None or not str(s.get("text", "")).strip():
            raise ValueError(f"narration segment {i} needs text/start/end: {s}")
        segs.append(dict(id=str(s.get("beat_id", s.get("id", f"n{i + 1:03d}"))), text=s["text"].strip(), start=float(start), end=float(end),
                         speaker=s.get("speaker", "narrator"), confidence=s.get("confidence"), emphasis=s.get("emphasis"),
                         pause=s.get("pause"), words=s.get("words")))
    segs.sort(key=lambda x: x["start"])
    audio = re.sub(r"\.segments\.json$", "", path)
    if not audio.endswith((".wav", ".mp3", ".m4a")):
        audio = os.path.splitext(path)[0]
    dur = raw.get("duration_seconds") if isinstance(raw, dict) else None
    return dict(segments=segs, audio=audio if os.path.exists(audio) else None, duration=float(dur or segs[-1]["end"]), path=path)


def align_to_paragraphs(story, segs):
    """Attach each narration segment to the story paragraph that contains it (order-preserving, text-matched)."""
    pn = [norm(p) for p in story["paragraphs"]]
    pi, warnings = 0, []
    for s in segs:
        key = norm(s["text"])
        found = None
        for j in range(pi, len(pn)):
            if key[:24] in pn[j]:
                found = j
                break
        if found is None:
            found = pi
            warnings.append(f"segment {s['id']} text not found in story.md (assigned to paragraph {pi + 1})")
        s["paragraph"] = found
        pi = found
    return warnings


def load_optional(base_dir, name):
    p = os.path.join(base_dir, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def load(story_path, narration_path, project_json=None, style_json=None, topic_json=None):
    story = parse_story(story_path)
    nar = load_narration(narration_path)
    warnings = align_to_paragraphs(story, nar["segments"])
    return dict(story=story, narration=nar, project=json.load(open(project_json)) if project_json else {},
                style_override=json.load(open(style_json)) if style_json else {},
                topic_override=json.load(open(topic_json)) if topic_json else {}, warnings=warnings)
