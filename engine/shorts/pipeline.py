"""One command: topic -> plan -> voice -> film -> mp4 -> QC. Every artifact is written next to the video."""
import json
import os
import re
import sys
import time

from engine.shorts import film as F, planner, qc, render3, reports, timelog, voice
from engine.shorts.raster import ROOT


def slug(topic):
    ascii_part = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:32]
    import hashlib
    return (ascii_part or "topic") + "-" + hashlib.sha1(topic.encode()).hexdigest()[:6]


class QCView:
    def __init__(self, film):
        self.fps, self.shots = film.fps, [(s["t0"], s["t1"], {"id": s["id"]}) for s in film.shots]


def run(topic=None, plan_path=None, brief_path=None, duration=40, seed=1, out_root=None, log=print, plan_only=False, still_times=None):
    tl = timelog.TimeLog()
    brief = planner.parse_brief(brief_path) if brief_path else None
    if plan_path:
        plan = json.load(open(plan_path))
        topic = plan["topic"]
    elif brief:
        topic = brief.get("title", "story")
    out_dir = os.path.join(out_root or os.path.join(ROOT, "output", "made"), slug(topic))
    os.makedirs(out_dir, exist_ok=True)
    if not plan_path:
        with tl.stage("plan (LLMs)", source="brief" if brief else "topic"):
            plan = planner.make_plan(topic, duration, seed, log, brief=brief)
        json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w"), ensure_ascii=False, indent=2)
        json.dump(plan.get("capability", {}), open(os.path.join(out_dir, "asset_requirements.json"), "w"), ensure_ascii=False, indent=2)
        log(f"[pipeline] plan written: {out_dir}/plan.json")
    if plan_only:
        return dict(out_dir=out_dir, plan=plan)
    vbeats = [dict(id=b["id"], text=b["text"]) for b in plan["beats"]]
    was_cached = os.path.exists(os.path.join(voice.VOICE_DIR, voice._key(vbeats, 42), "align.json"))       # checked BEFORE synthesis
    with tl.stage("voice (TTS+align)", cached=was_cached):
        v = voice.synthesize(vbeats, seed=42, log=log)
    GAP = dict(interruption=1.0, attention=0.5, curiosity=0.4, unease=0.4, realization=0.9, takeaway=0.7, payoff=0.6, turn=0.45, hook=0.0)
    with tl.stage("retime (pauses)"):
        v = voice.retime(v, {b["id"]: GAP.get(b.get("role"), 0.3) for b in plan["beats"]}, preroll=0.35)
    json.dump(dict(voice=v["voice"], placeholder=v["placeholder"], duration=v["duration"],
                   beats=[{k: b[k] for k in ("id", "text", "start", "end", "words")} for b in v["beats"]]),
              open(os.path.join(out_dir, "timings.json"), "w"), ensure_ascii=False, indent=2)
    with tl.stage("compile (acting+camera+GP bank)") as st:
        film = F.compile_plan(plan, v, log=log)
        if getattr(film, "gp", None):
            st.update(gp_renders=film.gp["renders"], gp_bank="built now (Blender %.1fs)" % film.gp["build_seconds"] if film.gp["built_now"] else "cache hit")
    if still_times:
        with tl.stage("stills"):
            stills = render3.render_stills(film, still_times, out_dir)
        log("\n" + tl.table())
        return dict(out_dir=out_dir, film=film, stills=stills)
    mp4 = os.path.join(out_dir, "short.mp4")
    with tl.stage("render (frames+encode)") as st:
        res = render3.render_video(film, mp4, log=log)
        st.update(frames=res["frames"], s_per_frame=round(res["seconds"] / max(res["frames"], 1), 3))
    with tl.stage("qc + reports"):
        rep = qc.run(mp4, QCView(film), res["stats"])
        extra, details = reports.run_all(film, out_dir, res["stats"], lambda t, f: render3.frame_image(film, t, f)[0])
    extra["grease_pencil_layer_rendered_by_blender"] = bool(getattr(film, "gp", None) and film.gp["renders"] > 0)
    rep["checks"].update(extra)
    rep["passed"] = all(rep["checks"].values())
    rep["visual_qa"] = details
    rep["grease_pencil"] = getattr(film, "gp", None)
    rep["voice"] = v["voice"]
    rep["voice_is_placeholder"] = v["placeholder"]
    rep["render_seconds"] = round(res["seconds"], 1)
    rep["planner_report"] = plan["planner"]
    # per-shot render cost (where the frame time goes)
    per = {}
    for s in res["stats"]:
        a = per.setdefault(s["shot"], [0, 0.0])
        a[0] += 1
        a[1] += s.get("ms", 0.0)
    shots = {k: dict(frames=n, seconds=round(ms / 1000, 1), ms_per_frame=round(ms / n)) for k, (n, ms) in per.items()}
    trep = tl.report(dict(video_seconds=rep["duration_s"], realtime_ratio=round(tl.total() / max(rep["duration_s"], 1e-6), 1), per_shot_render=shots))
    rep["total_seconds"] = trep["total_seconds"]
    rep["timing"] = trep
    json.dump(rep, open(os.path.join(out_dir, "qc.json"), "w"), ensure_ascii=False, indent=2)
    json.dump(trep, open(os.path.join(out_dir, "timing_log.json"), "w"), ensure_ascii=False, indent=2)
    timelog.append_history(trep, topic=topic, out=os.path.relpath(mp4, ROOT), passed=rep["passed"])
    log("\n" + tl.table(trep))
    log(f"[pipeline] {mp4}  QC passed: {rep['passed']}  ({trep['total_seconds']}s total, {trep['realtime_ratio']}x realtime)")
    return dict(out_dir=out_dir, mp4=mp4, qc=rep, plan=plan)
