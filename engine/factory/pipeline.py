"""The factory: story.md + narration segments JSON  ->  finished film + a self-contained project folder.

    python3 studio.py --story stories/x.md --narration narration/x.wav.segments.json
    python3 studio.py --project-plan output/projects/x/project/shot_plan.json      # deterministic re-render, NO LLM

Stages (each timed in logs/timing_log.json): contract -> analysis (LLM, cached) -> director -> continuity -> pause design + retime ->
asset completeness -> plan (DSL) -> render -> mix -> encode -> QC -> reports -> vertical-derivative plan.
"""
import hashlib
import json
import os
import subprocess
import time

import numpy as np
from PIL import Image

from engine.dsl import schema as DSL
from engine.factory import analysis as AN, assets, audio_pipeline as AP, contract, director, domain, project as PJ, qc as FQC, render as R, state
from engine.shorts import captions, film as F, timelog
from engine.shorts.layers import W, H
from engine.shorts.raster import ROOT

FPS = 30


def _inputs_hash(story, nar):
    h = hashlib.sha256()
    h.update("\n".join(story["paragraphs"]).encode())
    h.update(json.dumps([s["text"] for s in nar["segments"]], ensure_ascii=False).encode())
    h.update(b"analysis-v2")
    return h.hexdigest()[:16]


def _captions(segs):
    track = []
    for s in segs:
        words = s.get("words")
        if not words:
            toks = s["text"].split()
            tot = sum(len(w) for w in toks) or 1
            cur, words = s["start"], []
            for w in toks:
                d = (s["end"] - s["start"]) * len(w) / tot
                words.append(dict(word=w, start=cur, end=cur + d))
                cur += d
        chunks = F._chunk_words(words, max_words=4, max_chars=26)
        for j, ch in enumerate(chunks):
            t0 = ch[0]["start"] - 0.04
            t1 = chunks[j + 1][0]["start"] - 0.02 if j + 1 < len(chunks) else ch[-1]["end"] + 0.25
            track.append([round(t0, 3), round(t1, 3), " ".join(w["word"] for w in ch)])
    return track


def build_plan(story_path, narration_path, name=None, dom_id="money_psychology", out_root=None, allow_fallbacks=False, log=print, tl=None, seed_salt=""):
    tl = tl or timelog.TimeLog()
    dom = domain.load(dom_id)
    with tl.stage("contract"):
        c = contract.load(story_path, narration_path)
    story, nar = c["story"], c["narration"]
    pj = PJ.Project(name or PJ.slug(story["title"]) + "_" + hashlib.sha1(story["title"].encode()).hexdigest()[:5], out_root)
    pj.copy_in(story_path, "project/story.md")
    pj.copy_in(narration_path, "project/narration.segments.json")
    for w in c["warnings"]:
        log(f"[contract] {w}")
    key = _inputs_hash(story, nar)
    cache = pj.path("project", "analysis_cache.json")
    with tl.stage("analysis (LLM)") as st:
        if os.path.exists(cache) and json.load(open(cache)).get("key") == key:
            cached = json.load(open(cache))
            analysis, tags = cached["analysis"], cached["tags"]
            for s in nar["segments"]:
                s["tags"], s["phase"] = tags[s["id"]]["tags"], tags[s["id"]]["phase"]
            analysis = AN.rederive(dom, story, nar["segments"], analysis)          # cheap: re-apply current evidence rules to cached LLM tags
            st["cached"] = True
        else:
            analysis = AN.analyze(dom, story, nar, log)
            json.dump(dict(key=key, analysis=analysis, tags={s["id"]: dict(tags=s["tags"], phase=s["phase"]) for s in nar["segments"]}),
                      open(cache, "w"), ensure_ascii=False)
            st["cached"] = False
    segs = nar["segments"]
    with tl.stage("director"):
        story_id = PJ.slug(story["title"]) + "_" + hashlib.sha1(story["title"].encode()).hexdigest()[:5] + (f"~{seed_salt}" if seed_salt else "")   # seed = story_id (+ optional style seed) + shot_id
        shots, dwarn, chars = director.build_shots(dom, analysis, segs, log, story_id)
        gaps = director.pause_plan(segs, shots)
        # the phone on screen shows the most recent UI insert of the same scene
        last_ui = None
        for sh in shots:
            if sh["treatment"] == "insert_ui":
                last_ui = sh["ui"]
            elif sh["treatment"] == "performance":
                sh["held_ui"] = last_ui
        continuity = state.continuity_check(shots)
    with tl.stage("retime (designed pauses)"):
        raw = AP.read_audio(nar["audio"]) if nar["audio"] else np.zeros(int(nar["duration"] * AP.SR), np.float32)
        new_audio, new_segs, remap = AP.retime(raw, segs, gaps)
        for sh in shots:
            sh["t0"], sh["t1"] = remap(sh["t0"]), remap(sh["t1"])
            for a in sh["actions"]:
                a["t"] = remap(a["t"])
        shots[0]["t0"] = 0.0
        duration = len(new_audio) / AP.SR + 0.8
        shots[-1]["t1"] = duration
        wav = pj.path("assets", "narration_retimed.wav")
        AP.write = None
        from engine.shorts.audio import write_wav
        write_wav(wav, new_audio)
    with tl.stage("asset check"):
        cast_ids = {c_["id"]: c_ for c_ in analysis["characters"]}
        ar = assets.check(dom, shots, cast_ids, log)
    outfits = dom["outfits"]
    sfx = []
    for sh in shots:
        for e in sh["sfx"]:
            sfx.append([round(sh["t0"] + e["at"], 3), e["kind"], e["gain"]])
    moods = [[sh["t0"], sh["t1"], sh["lighting"]["mood"]] for sh in shots]
    covered = sum(1 for s in new_segs if any(sh["t0"] - 0.01 <= s["start"] < sh["t1"] for sh in shots))
    plan = dict(version=2, story_id=story_id, seed=0, characters=chars, domain=dom_id, title=story["title"], fps=FPS, format=dict(w=W, h=H, name="9x16"), duration=round(duration, 3), shots=shots,
                segments=[{k: s[k] for k in ("id", "text", "start", "end", "words", "phase", "speaker")} for s in new_segs],
                captions=_captions(new_segs), sfx=sfx, mood_track=moods, outfits=outfits, sets={k: v["set"] for k, v in dom["environments"].items()},
                narration_audio=os.path.relpath(wav, pj.dir), pauses=gaps, coverage=dict(segments=len(new_segs), uncovered_segments=len(new_segs) - covered),
                treatment=analysis["treatment"], warnings=dict(director=dwarn, continuity=continuity, story_quality=analysis["quality_warnings"],
                                                               analysis=analysis["warnings"], contract=c["warnings"]))
    DSL.validate_plan(plan, dom)                                     # untrusted until validated: fail safely BEFORE render
    _write_views(pj, story, nar, analysis, plan, ar, dom)
    if ar["missing"] and not allow_fallbacks:
        raise SystemExit(f"FAILED before render: {len(ar['missing'])} required asset(s) missing - see {pj.path('project', 'asset_requirements.json')}")
    return pj, plan, ar, tl, continuity, analysis


def _write_views(pj, story, nar, analysis, plan, ar, dom):
    w = pj.write_json
    shots = plan["shots"]
    w("project/story.json", dict(title=story["title"], paragraphs=story["paragraphs"], narration=plan["segments"]))
    w("project/story_analysis.json", {k: analysis[k] for k in ("title_en", "logline", "central_question", "topics", "phases", "llm_phases", "paragraph_modes", "paragraph_summaries", "financial_events", "quality_warnings", "warnings")})
    w("project/characters.json", [dict(c, dna=(plan.get("characters", {}).get(c["id"]) or {}).get("dna")) for c in analysis["characters"]])
    w("project/locations.json", [dict(kind=k, set=plan["sets"].get(k), used_in=[s["id"] for s in shots if s.get("location") == k]) for k in dom.env_kinds()])
    w("project/props.json", dict(ui_screens=sorted({s["ui"]["screen"] for s in shots if s["treatment"] == "insert_ui"}), procedural=sorted({s["procedural"]["type"] for s in shots if s["treatment"] == "procedural"})))
    w("project/psychology.json", analysis["psychology"])
    w("project/visual_treatment.json", analysis["treatment"])
    w("project/shot_plan.json", plan)
    w("project/animation_plan.json", [dict(shot=s["id"], character=s.get("character"), emotion=s.get("emotion"), emotion_end=s.get("emotion_end"), actions=s["actions"]) for s in shots if s["treatment"] == "performance"])
    w("project/camera_plan.json", [dict(shot=s["id"], t0=s["t0"], t1=s["t1"], **s["camera"]) for s in shots])
    w("project/lighting_plan.json", [dict(shot=s["id"], **s["lighting"]) for s in shots])
    w("project/gp_plan.json", [dict(shot=s["id"], effects=s["gp"]) for s in shots if s["gp"]])
    w("project/asset_requirements.json", dict(missing=ar["missing"], used=[dict(kind=u["kind"], name=u["name"], how=u["how"]) for u in ar["used"]]))
    w("assets/manifest.json", ar["used"])
    w("assets/licenses.json", [dict(kind=u["kind"], name=u["name"], license=u["license"]) for u in ar["used"]])


def vertical_plan(plan, n=3):
    """Candidate 9:16 windows (30-58 s) aligned to shot boundaries, scored on hook/reveal strength; subjects tracked per shot."""
    shots = plan["shots"]
    imp = {s["id"]: s for s in plan["segments"]}
    cands = []
    for i in range(len(shots)):
        for j in range(i + 1, len(shots)):
            d = shots[j]["t1"] - shots[i]["t0"]
            if d < 30:
                continue
            if d > 58:
                break
            score = sum(2 if sh["phase"] in ("REVEAL", "CLIMAX", "INCITING", "HOOK") else 1 for sh in shots[i:j + 1]) / (j - i + 1)
            score += 1.5 if shots[i]["phase"] in ("HOOK", "INCITING", "REVEAL") else 0
            score += 0.5 * sum(1 for sh in shots[i:j + 1] if sh["treatment"] == "insert_ui") / (j - i + 1)
            cands.append((score, i, j))
    cands.sort(reverse=True)
    picked, used = [], []
    for score, i, j in cands:
        if any(not (j < a or i > b) for a, b in used):
            continue
        used.append((i, j))
        picked.append(dict(start=round(shots[i]["t0"], 2), end=round(shots[j]["t1"], 2), score=round(score, 2), first_shot=shots[i]["id"], last_shot=shots[j]["id"],
                           hook_phase=shots[i]["phase"], subjects=[dict(shot=s["id"], subject=s["camera"].get("subject")) for s in shots[i:j + 1]]))
        if len(picked) >= n:
            break
    return dict(master_format=plan["format"], note="master is 9:16-native; windows are candidates for standalone Shorts (16:9 native output is not implemented)", candidates=picked)


def render_project(pj, plan, ar, tl, continuity, out_name="master.mp4", window=None, stills=None, qc_only=False, log=print):
    with tl.stage("renderer init"):
        rn = R.Renderer(plan, log)
        plan["gp_bank"] = dict(renders=rn.ctx.bank.report["renders"], blender=rn.ctx.bank.report["blender"], sprites=rn.ctx.bank.report["sprites"]) if rn.ctx.bank else None
    if stills:
        outs = []
        for t in stills:
            img = rn.frame_at(t, int(t * FPS))
            p = pj.path("render", "composited", f"still_{t:07.2f}.png")
            Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
            outs.append((t, rn.shots[rn.index_at(t)]["id"], p))
        return outs
    dur = plan["duration"]
    t_a, t_b = window or (0.0, dur)
    if qc_only:                                                       # re-run QC/reports on an existing render (no frames)
        out = pj.path("final", "master.mp4")
        stats = json.load(open(pj.path("render", "stats.json")))
        return _finish(pj, plan, ar, tl, continuity, rn, out, stats, log)
    with tl.stage("audio mix"):
        narr = AP.read_audio(pj.path(plan["narration_audio"]))
        wav = AP.mix(dur, narr, plan["sfx"], plan["mood_track"], out_dir=pj.path("render", "final"))
    out = pj.path("final", "master.mp4") if window is None else pj.path("final", "shorts", out_name)
    n0, n1 = int(t_a * FPS), int(t_b * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", str(t_a), "-t", str(t_b - t_a), "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    import subprocess as sp
    proc = sp.Popen(cmd, stdin=sp.PIPE)
    caps = plan["captions"]
    stats, prev, t0 = [], None, time.perf_counter()
    with tl.stage("render (frames+encode)") as st:
        ci = 0
        for f in range(n0, n1):
            t = f / FPS
            tf = time.perf_counter()
            img = rn.frame_at(t, f)
            text = bbox = None
            while ci < len(caps) and caps[ci][1] < t:
                ci += 1
            for c in caps[max(0, ci - 1):ci + 2]:
                if c[0] <= t <= c[1]:
                    op = max(0.0, min(1.0, (t - c[0]) / 0.08, (c[1] - t) / 0.08))
                    arr, bbox = captions.render(c[2], size=68, center_y=1440)
                    img = captions.overlay(img, arr, op)
                    text = c[2]
                    break
            small = img[::40, ::40]
            diff = float(np.abs(small - prev).mean()) if prev is not None else 1.0
            prev = small.copy()
            proc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
            stats.append(dict(f=f - n0, shot=rn.shots[rn.index_at(t)]["id"], mean=float(img.mean()), caption=text, bbox=bbox, diff=diff, ms=round((time.perf_counter() - tf) * 1000, 1)))
            if (f - n0) % 300 == 0:
                el = time.perf_counter() - t0
                log(f"[render] frame {f - n0}/{n1 - n0}  {el:.0f}s elapsed  ETA {el / max(f - n0, 1) * (n1 - n0 - (f - n0)):.0f}s")
        proc.stdin.close()
        proc.wait()
        st.update(frames=n1 - n0, s_per_frame=round((time.perf_counter() - t0) / max(n1 - n0, 1), 3))
    if window is not None:
        return out
    json.dump(stats, open(pj.path("render", "stats.json"), "w"))
    return _finish(pj, plan, ar, tl, continuity, rn, out, stats, log)


def _finish(pj, plan, ar, tl, continuity, rn, out, stats, log):
    with tl.stage("qc + reports"):
        rep = FQC.run(out, plan, stats, rn, ar, plan["warnings"]["director"] + plan["warnings"]["story_quality"] + plan["warnings"]["analysis"], continuity, log)
        FQC.contact_sheet(rn, plan, pj.path("qc", "contact_sheet.png"))
        FQC.timeline_png(plan, pj.path("qc", "shot_timeline.png"))
    per = {}
    for s in stats:
        a = per.setdefault(s["shot"], [0, 0.0])
        a[0] += 1
        a[1] += s["ms"]
    trep = tl.report(dict(video_seconds=rep["duration_s"], realtime_ratio=round(tl.total() / max(rep["duration_s"], 1e-6), 1),
                          per_shot_render={k: dict(frames=n, seconds=round(ms / 1000, 1), ms_per_frame=round(ms / n)) for k, (n, ms) in per.items()}))
    pj.write_json("qc/qc.json", rep)
    pj.write_json("qc/timing_report.json", dict(shots=[dict(id=s["id"], phase=s["phase"], treatment=s["treatment"], t0=round(s["t0"], 2), t1=round(s["t1"], 2),
                                                             dur=round(s["t1"] - s["t0"], 2), location=s["location"], camera=s["camera"], mood=s["lighting"]["mood"]) for s in plan["shots"]],
                                                 pauses=plan["pauses"]))
    pj.write_json("qc/warnings.json", plan["warnings"])
    pj.write_json("logs/timing_log.json", trep)
    pj.write_json("project/vertical_plan.json", vertical_plan(plan))
    timelog.append_history(trep, topic=plan["title"], out=os.path.relpath(out, ROOT), passed=rep["passed"])
    log("\n" + tl.table(trep))
    log(f"[factory] {out}  QC passed: {rep['passed']}  ({trep['total_seconds']}s total, {trep['realtime_ratio']}x realtime)")
    for k, v in rep["checks"].items():
        if not v:
            log(f"[qc] FAILED: {k}")
    return out, rep


def run(story=None, narration=None, project_plan=None, name=None, dom_id="money_psychology", out_root=None, stills=None, window=None,
        allow_fallbacks=False, plan_only=False, qc_only=False, log=print, seed_salt="", aspect_ratios=("9:16",)):
    tl = timelog.TimeLog()
    if project_plan:
        plan = json.load(open(project_plan))
        pj = PJ.Project(os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(project_plan)))), os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(project_plan)))))
        ar = dict(missing=[], license_ok=True, used=[])
        ar_path = pj.path("project", "asset_requirements.json")
        if os.path.exists(ar_path):
            ar["missing"] = json.load(open(ar_path))["missing"]
        continuity = plan["warnings"]["continuity"]
    else:
        pj, plan, ar, tl, continuity, analysis = build_plan(story, narration, name, dom_id, out_root, allow_fallbacks, log, tl, seed_salt)
    if plan_only:
        log(f"[factory] plan written: {pj.path('project', 'shot_plan.json')}  ({len(plan['shots'])} shots, {plan['duration']:.1f}s)")
        json.dump(tl.report(), open(pj.path("logs", "timing_log_plan.json"), "w"), indent=2)
        return pj, plan
    res = render_project(pj, plan, ar, tl, continuity, window=window, stills=stills, qc_only=qc_only, log=log)
    if isinstance(res, tuple) and "16:9" in aspect_ratios and not stills:
        from engine.compositing import reframe_16x9
        d = pj.path("final", "master_16x9_blurpad.mp4")
        reframe_16x9(res[0], d)
        log(f"[factory] 16:9 blur-pad derivative (NOT a native widescreen composition): {d}")
    return res
