"""TOPIC -> FILM orchestrator.   python3 studio.py --skeleton-topic "<topic>" [--critique-rounds 3] [--no-llm] [--draft]

  topic_story.write  ->  narration (Chatterbox Hindi TTS per beat, cached; or DRAFT timing estimated from word counts)  ->  auto_director plan  ->  CRITIC loop (critic.py: measure, VLM-review, auto-fix)
  ->  final render (Blender rig + 2.5D compositor) -> qc_v3 -> critique of the FINAL video.   Fixes are keyed by beat id and stored in story.json, so a re-run with the same story is deterministic.
"""
import hashlib
import json
import os
import subprocess
import time

from engine.shorts.raster import ROOT
from engine.skeleton import auto_director as AD, pace, parts_art2 as PA2, short, topic_story as TS

OUT = os.path.join(ROOT, "output/shorts/topic")
WPS = 3.0


def draft_narration(story):
    """Estimated beat timings (no TTS): used for fast critique passes. Shape identical to a real narration dict."""
    t, segs = 0.22, []
    for b in story["beats"]:
        n = max(len(b["text"].split()), 1)
        d = n / WPS + 0.25
        segs.append(dict(id=b["id"], text=b["text"], start=round(t, 3), end=round(t + d, 3), words=[]))
        t += d + 0.10
    return dict(segments=segs, audio=None, tts="draft-estimate", tempo=1.0)


def real_narration(story, out_dir, tempo=1.08, log=print):
    """Chatterbox Hindi TTS for the story's beats (content-hash cached under narration/topic/<hash>/), paced."""
    beats = [(b["id"], b["text"]) for b in story["beats"]]
    h = hashlib.sha1(json.dumps(beats, ensure_ascii=False).encode()).hexdigest()[:12]
    d = os.path.join(ROOT, "narration/topic", h)
    os.makedirs(d, exist_ok=True)
    bj = os.path.join(d, "beats.json")
    json.dump([dict(id=i, text=t) for i, t in beats], open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    raw, seg = os.path.join(d, "raw.wav"), os.path.join(d, "raw.wav.segments.json")
    if not (os.path.exists(raw) and os.path.exists(seg)):
        log(f"[tts] Chatterbox Hindi for {len(beats)} beats (cache {h}) ...")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), os.path.join(ROOT, "tools/tts_beats.py"), bj, os.path.join(d, "raw")], check=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT))
    os.makedirs(os.path.join(out_dir, "narration"), exist_ok=True)
    pw, pj = os.path.join(out_dir, "narration/paced.wav"), os.path.join(out_dir, "narration/paced.json")
    lo, hi = 45.0, 60.0                                                       # the Short must land in 45-60 s: re-pace (pitch-preserving tempo) until it does, no new TTS needed
    for _ in range(8):
        p = pace.build(raw, seg, beats, pw, pj, tempo=tempo)
        dur = p["segments"][-1]["end_seconds"] + 3.0
        if lo <= dur <= hi:
            break
        new = round(min(1.3, max(0.9, tempo * (dur / (0.5 * (lo + hi))) ** 0.8)), 3)
        log(f"[pace] duration {dur:.1f}s outside {lo}-{hi}: tempo {tempo} -> {new}")
        if new == tempo:
            break
        tempo = new
    nar = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in p["segments"]], audio=os.path.relpath(pw, ROOT), tts="chatterbox", tempo=tempo)
    return nar, {k: p[k] for k in ("raw_duration", "raw_words_per_s", "paced_words_per_s", "gap_cap", "beat_gap", "tempo")}


def bake_cast(plan):
    atoms = sorted({a["name"] for s in plan["shots"] for a in s.get("actions", []) if a["action"] == "face_atom"})          # replacement faces the style asks for
    for cid in plan["cast_in_short"]:
        c = plan["characters"][cid]
        PA2.bake2(c["dna"], c.get("view", "profile"), c.get("hand_set", "full"))
        if atoms:
            PA2.bake_face_atoms(c["dna"], c.get("view", "profile"), atoms)


def make(topic, out_dir=None, use_llm=True, rounds=3, draft=False, samples=10, seed=11, log=print, story=None, tempo=1.08):
    from engine.skeleton import critic as CR
    story = story or TS.write(topic, use_llm=use_llm, log=log)
    out_dir = out_dir or os.path.join(OUT, story["slug"])
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    TS.save(story, os.path.join(out_dir, "story.json"))
    log(f"[story] '{story['title']}' domain={story['domain']} beats={len(story['beats'])} words={story['words']} cast={story['cast']}")
    pace_info = None
    if draft:
        nar = draft_narration(story)
    else:
        nar, pace_info = real_narration(story, out_dir, tempo, log)
    fixes = dict(story.get("fixes", {}))
    plan = AD.build_plan(story, nar, seed=seed, tts=nar["tts"], name=story["slug"], fixes=fixes)
    bake_cast(plan)
    rep = CR.improve(plan, story, nar, out_dir, rounds=rounds, log=log, samples=samples, seed=seed)         # -> fixed plan + reports
    plan, fixes = rep["plan"], rep["fixes"]
    story["fixes"] = fixes
    TS.save(story, os.path.join(out_dir, "story.json"))
    if pace_info:
        plan["narration"]["pacing"] = pace_info
    res = short.render_film(plan, out_dir, log, samples=samples)
    fin = CR.review_final(plan, out_dir, log)
    m = json.load(open(os.path.join(out_dir, "manifest.json")))
    m["topic"] = dict(topic=topic, domain=story["domain"], total_s=round(time.time() - t_all, 1), critique=os.path.relpath(os.path.join(out_dir, "critique/report.json"), out_dir))
    json.dump(m, open(os.path.join(out_dir, "manifest.json"), "w"), ensure_ascii=False, indent=1)
    return dict(out_dir=out_dir, story=story, plan=plan, result=res, critique=rep["summary"], final_review=fin)
