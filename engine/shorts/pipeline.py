"""One command: topic -> plan -> voice -> film -> mp4 -> QC. Every artifact is written next to the video."""
import json
import os
import re
import sys
import time

from engine.shorts import film as F, planner, qc, render3, reports, voice
from engine.shorts.raster import ROOT


def slug(topic):
    ascii_part = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:32]
    import hashlib
    return (ascii_part or "topic") + "-" + hashlib.sha1(topic.encode()).hexdigest()[:6]


class QCView:
    def __init__(self, film):
        self.fps, self.shots = film.fps, [(s["t0"], s["t1"], {"id": s["id"]}) for s in film.shots]


def run(topic=None, plan_path=None, brief_path=None, duration=40, seed=1, out_root=None, log=print, plan_only=False, still_times=None):
    t0 = time.time()
    brief = planner.parse_brief(brief_path) if brief_path else None
    if plan_path:
        plan = json.load(open(plan_path))
        topic = plan["topic"]
    elif brief:
        topic = brief.get("title", "story")
    out_dir = os.path.join(out_root or os.path.join(ROOT, "output", "made"), slug(topic))
    os.makedirs(out_dir, exist_ok=True)
    if not plan_path:
        plan = planner.make_plan(topic, duration, seed, log, brief=brief)
        json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w"), ensure_ascii=False, indent=2)
        json.dump(plan.get("capability", {}), open(os.path.join(out_dir, "asset_requirements.json"), "w"), ensure_ascii=False, indent=2)
        log(f"[pipeline] plan written: {out_dir}/plan.json")
    if plan_only:
        return dict(out_dir=out_dir, plan=plan)
    v = voice.synthesize([dict(id=b["id"], text=b["text"]) for b in plan["beats"]], seed=42, log=log)
    GAP = dict(interruption=1.0, attention=0.5, curiosity=0.4, unease=0.4, realization=0.9, takeaway=0.7, payoff=0.6, turn=0.45, hook=0.0)
    v = voice.retime(v, {b["id"]: GAP.get(b.get("role"), 0.3) for b in plan["beats"]}, preroll=0.35)
    json.dump(dict(voice=v["voice"], placeholder=v["placeholder"], duration=v["duration"],
                   beats=[{k: b[k] for k in ("id", "text", "start", "end", "words")} for b in v["beats"]]),
              open(os.path.join(out_dir, "timings.json"), "w"), ensure_ascii=False, indent=2)
    film = F.compile_plan(plan, v, log=log)
    if still_times:
        return dict(out_dir=out_dir, film=film, stills=render3.render_stills(film, still_times, out_dir))
    mp4 = os.path.join(out_dir, "short.mp4")
    res = render3.render_video(film, mp4, log=log)
    rep = qc.run(mp4, QCView(film), res["stats"])
    extra, details = reports.run_all(film, out_dir, res["stats"], lambda t, f: render3.frame_image(film, t, f)[0])
    rep["checks"].update(extra)
    rep["passed"] = all(rep["checks"].values())
    rep["visual_qa"] = details
    rep["voice"] = v["voice"]
    rep["voice_is_placeholder"] = v["placeholder"]
    rep["render_seconds"] = round(res["seconds"], 1)
    rep["total_seconds"] = round(time.time() - t0, 1)
    rep["planner_report"] = plan["planner"]
    json.dump(rep, open(os.path.join(out_dir, "qc.json"), "w"), ensure_ascii=False, indent=2)
    log(f"[pipeline] {mp4}  QC passed: {rep['passed']}  ({rep['total_seconds']}s total)")
    return dict(out_dir=out_dir, mp4=mp4, qc=rep, plan=plan)
