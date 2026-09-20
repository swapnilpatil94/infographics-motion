"""PRODUCTION WORKER: one subprocess per production (so a render can be cancelled for real, a crash cannot take the server down, and Blender / ffmpeg children die with it).

    python -m engine.studio.worker <production_dir>            run the production described by <production_dir>/job.json, appending structured events to <production_dir>/events.jsonl
    python -m engine.studio.worker preview <production_dir> <shot_id>    render one shot's still from the working (edited) plan

The worker only orchestrates: story checks, narration, then `production.make` (the proven engine) - which reports its own stages through `engine.skeleton.events` - then the export step.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.shorts.raster import ROOT                                                    # noqa: E402
from engine.skeleton import acts as AC, events as EVT, narration_io as NI, production as PR, story_semantics as SS   # noqa: E402
from engine.studio import core as C                                                      # noqa: E402


class Cancelled(BaseException):
    """raised by SIGTERM: BaseException so no `except Exception` inside the engine can swallow a cancel"""


_CANCEL = threading.Event()


def _term(signum, frame):
    _CANCEL.set()
    raise Cancelled()


def _sh(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, **k)


def _probe(mp4):
    r = _sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration", "-show_entries", "format=duration,size", "-of", "json", mp4])
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    num, den = (st.get("r_frame_rate") or "30/1").split("/")
    return dict(width=st.get("width"), height=st.get("height"), fps=round(float(num) / float(den), 2), frames=int(st.get("nb_frames") or 0), duration=round(float(j.get("format", {}).get("duration") or 0), 3), size_mb=round(int(j.get("format", {}).get("size") or 0) / 1e6, 1))


# ------------------------------------------------------------------------------------------------ stages
def _story_stages(job, pdir, rep):
    mode, lines, s = job["mode"], job["lines"], job["settings"]
    with rep.stage("story_analysis", message="re-checking that the approved story is one the studio can stage") as done:
        if mode != "production":
            errs, _ = C.lint_script([l["text"] for l in lines])
            if errs:
                raise C.StudioError("script_invalid", "; ".join(errs))
        d = dict(settings=s, notes=job["notes"], lines=lines, narration=job.get("narration"), story_edits=job.get("story_edits", {}), variation=job.get("variation", 0), cast_edit=None)
        C._analyze_lines(d)
        if d["graph"]["story_id"] != job["graph"]["story_id"]:
            raise C.StudioError("draft_changed", "The approved story no longer analyses to the same graph; open the review again.")
        done["message"] = f"{len(lines)} segments analysed: supported story, {len(d['graph']['scenes'])} scene(s)"
    with rep.stage("story_graph", message="building the story graph") as done:
        g = job["graph"]
        bad = AC.validate([b["act"] for b in g["beats"]])
        if bad:
            raise SS.StoryNotSupported("; ".join(bad))
        json.dump(g, open(os.path.join(pdir, "story_graph.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        done["message"] = f"{len(g['beats'])} beats, {len(g['scenes'])} scene(s), {1 + bool(g['cast'].get('principal')) + len(g['cast'].get('extras', []))} character(s), act grammar valid"
    if mode == "production":
        rep.skip("script", "provided by you (Production mode)", segments=len(lines))
    else:
        with rep.stage("script", message="locking the approved script") as done:
            done["message"] = f"{len(lines)} approved lines"
    return g


def _narration(job, pdir, rep):
    """-> path of the narration segments JSON"""
    if job["mode"] == "production":
        NI.load(job["narration"])
        rep.skip("narration", "provided by you: narration segments + audio (Production mode)", segments=len(job["lines"]))
        return job["narration"]
    beats = [(l["id"], l["text"]) for l in job["lines"]]
    cached = NI.is_cached(beats)
    rep.start("narration", message="narration found in the cache" if cached else "synthesising the narration with Chatterbox Hindi on this Mac - the TTS reports no progress, only elapsed time", cached=cached, lines=len(beats))
    stop = threading.Event()

    def beat():
        while not stop.wait(1.0):
            rep.progress("narration", fraction=None, message="Chatterbox Hindi is synthesising" if not cached else "assembling the cached narration", cached=cached, lines=len(beats), current_operation="text to speech (Chatterbox Hindi)")
    th = threading.Thread(target=beat, daemon=True)
    th.start()
    try:
        t = job["tts"]
        path = NI.synthesize(beats, os.path.join(pdir, "narration"), tempo=t.get("tempo", 1.08), lo=t.get("lo", 44.0), hi=t.get("hi", 60.0), log=lambda m: rep.log(m, "narration"))
    finally:
        stop.set()
    n = NI.load(path)
    rep.complete("narration", message=f"{len(n['segments'])} lines, {n['segments'][-1]['end']:.1f} s of speech, tempo {n['tempo']}", cached=cached, lines=len(beats), duration=n["segments"][-1]["end"], tempo=n["tempo"])
    return path


def _cleanup(pdir):
    """the rendered frames live in the content-addressed cache; the per-production copy (0.7 MB / frame) is only needed by a running job"""
    shutil.rmtree(os.path.join(pdir, "work", "actor_frames"), ignore_errors=True)


def _skip_story(rep, parent):
    for st in ("story_analysis", "story_graph", "script", "narration"):
        rep.skip(st, f"unchanged: re-rendering an edited plan of {parent}")


# ------------------------------------------------------------------------------------------------ export
def _export(job, pdir, r, rep):
    plan, qc = r["plan"], r["qc"]
    mp4 = r["mp4"]
    v = _probe(mp4)
    fmt = job["settings"].get("format", "9:16")
    files = {}
    tdir = os.path.join(pdir, "shots")
    os.makedirs(tdir, exist_ok=True)
    rep.progress("export", fraction=0.1, message="poster and per-shot previews", force=True)
    for sh in plan["shots"]:
        t = round((sh["t0"] + sh["t1"]) / 2, 2)
        _sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", mp4, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", os.path.join(tdir, f"{sh['id']}.jpg")])
    _sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2.0", "-i", mp4, "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "3", os.path.join(pdir, "poster.jpg")])
    if fmt == "16:9":
        rep.progress("export", fraction=0.5, message="16:9 export (9:16 master on a blurred backdrop)", force=True)
        out = os.path.join(pdir, "final_16x9.mp4")
        f = "[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=40:6,eq=brightness=-0.12[bg];[b]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
        rr = _sh(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-filter_complex", f, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "copy", "-movflags", "+faststart", out])
        if rr.returncode != 0:
            raise RuntimeError("16:9 export failed: " + rr.stderr[-400:])
        files["video_16x9"] = os.path.relpath(out, ROOT)
    wa = os.path.join(pdir, "work", "actor_frames")
    freed = 0.0
    if os.path.isdir(wa):                                                                 # the frames live in the content-addressed cache; the per-production copy is 0.7 MB / frame
        freed = round(sum(os.path.getsize(os.path.join(wa, f)) for f in os.listdir(wa)) / 1e6, 1)
        shutil.rmtree(wa, ignore_errors=True)
    aud = json.load(open(os.path.join(pdir, "audio_report.json"))) if os.path.exists(os.path.join(pdir, "audio_report.json")) else {}
    st = rep.state
    sec = {k: round(st.stages[k]["seconds"], 1) for k in EVT.ORDER}
    cache = dict(st.cache or {})
    if cache.get("frames"):
        cache["rendered"] = cache.get("to_render")
        cache["reuse_pct"] = round(100.0 * (cache.get("reused") or 0) / cache["frames"], 1)
    ad = st.stages["audio"]["detail"] or {}
    crit = os.path.join(pdir, "critique", "report.json")
    critic_fixes = 0
    if os.path.exists(crit):
        critic_fixes = sum(1 for rd in json.load(open(crit)).get("rounds", []) for a in rd.get("applied", []) if a.get("fix"))
    checks = [dict(name=k, ok=bool(x)) for k, x in qc["checks"].items()]
    def rel(p):
        return os.path.relpath(os.path.join(pdir, p), ROOT)
    files.update(video=rel("final.mp4"), plan=rel("plan.json"), story_graph=rel("story_graph.json"), qc_report=rel("qc_report.json"), audio_report=rel("audio_report.json"), manifest=rel("manifest.json"), contact_sheet=rel("contact_sheet.png"),
                 poster=rel("poster.jpg"), events=rel("events.jsonl"), summary=rel("summary.json"))
    files["absolute_dir"] = pdir
    summary = dict(id=os.path.basename(pdir), kind=job.get("kind", "generate"), mode=job["mode"], title=plan["title"], format=fmt, video=v, shots=len(plan["shots"]), scenes=[dict(loc=s["loc"], time=s["time"], t0=s["t0"], t1=s["t1"]) for s in plan["scenes"]],
                   characters=[dict(id=k, role=c["role"], archetype=c["dna"].get("archetype", c["dna"].get("role")), hair=c["dna"]["hair"]["style"]) for k, c in plan["characters"].items() if k in plan["cast_in_short"]],
                   audio=dict(foley_events=(aud.get("layers") or {}).get("foley_events"), sfx_events=len(plan.get("sfx") or []), ambience_scenes=[f"{a} ({b})" for a, b in (aud.get("layers") or {}).get("ambience_scenes", [])],
                              music_moods=(aud.get("layers") or {}).get("music_moods"), peak=aud.get("peak"), speech_to_bed_db=aud.get("speech_to_bed_db"), rms_db=aud.get("rms_db"), mix_cache_hit=bool(ad.get("cache_hit"))),
                   timings=dict(total=round(time.time() - rep.t0, 1), blender=sec["blender_render"], asset_preparation=sec["asset_preparation"], audio=sec["audio"], compositing=sec["compositing"], qc=sec["qc"], scene_direction=sec["scene_direction"],
                                narration=sec["narration"], export=sec["export"]), cache=dict(cache, mix_cache_hit=bool(ad.get("cache_hit")), narration_cached=bool((st.stages["narration"]["detail"] or {}).get("cached")), freed_mb=freed),
                   qc=dict(passed=qc["passed"], n_checks=qc["n_checks"], passed_checks=[c["name"] for c in checks if c["ok"]], failed_checks=[c["name"] for c in checks if not c["ok"]], checks=checks, not_applicable=qc["evidence"].get("not_applicable_gates", []),
                           autofix_rounds=[dict(round=h["round"], passed=h["passed"], failed=h["failed"], fixes=h["fixes_applied"]) for h in r["history"]], critic_fixes=critic_fixes, passes=len(r["history"])),
                   files=files, director=plan.get("director") or {}, captions=plan.get("captions", True), parent=job.get("parent"), created=job.get("created"), completed=time.time(),
                   requested=dict(format=fmt, duration=job["settings"].get("duration"), voice=job["settings"].get("voice")))
    json.dump(summary, open(os.path.join(pdir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return summary


# ------------------------------------------------------------------------------------------------ run
def _simulate(job, rep):
    """test hook (KATHAYA_STUDIO_TEST=1): a scripted production through the real event / cancel / failure plumbing, no engine"""
    sim = job["test"]
    for st in EVT.ORDER:
        rep.start(st, message=f"simulated {st}")
        n = 10 if st in ("blender_render", "compositing") else 1
        for k in range(n):
            time.sleep(sim.get("step", 0.15))
            if sim.get("fail_at") == st and k == n // 2:
                raise RuntimeError(f"simulated failure in {st}")
            rep.progress(st, fraction=(k + 1) / n, frame=k + 1, total_frames=n, shot=1 + k // 4, total_shots=3, fps=2.5, eta_seconds=(n - k - 1) * 0.4, force=True)
        rep.complete(st)
    return dict(simulated=True)


# ------------------------------------------------------------------------------------------------ Kathaya flows (plan / build / render)
def run_kplan(job, pdir, rep):
    """narration -> timeline -> creative director -> asset check"""
    from kathaya import pipeline as KP
    pid = job["project"]
    KP.set_state(pid, "planning", job=os.path.basename(pdir))
    proj = KP.load(pid)
    i = proj["input"]
    tts = i.get("narration_mode", "auto") != "estimated" and not i.get("audio") and not i.get("timing")
    rep.start("narration", message="synthesising the narration (Chatterbox Hindi; no progress is reported inside the TTS)" if tts else "reading the narration audio / timing")
    stop = threading.Event()

    def beat():
        while not stop.wait(1.0):
            rep.progress("narration", fraction=None, message="Chatterbox Hindi is synthesising" if tts else "analysing the narration audio", current_operation="text to speech (Chatterbox Hindi)" if tts else "audio analysis")
    th = threading.Thread(target=beat, daemon=True)
    th.start()
    try:
        tl = KP.build_timeline(pid, workdir=os.path.join(KP.pdir(pid), "narration"), log=lambda m: rep.log(m, "narration"))
    finally:
        stop.set()
    rep.complete("narration", message=f"{tl['source']}: {len(tl['narration'])} segments, {tl['duration']:.1f} s", source=tl["source"], duration=tl["duration"])
    with rep.stage("timeline", message="building the narration timeline") as done:
        done["message"] = f"{len(tl['narration'])} timestamped segments, {tl['duration']:.1f} s" + (" - " + tl["warnings"][0][:90] if tl["warnings"] else "")
        done["warnings"] = tl["warnings"]
    if i.get("provider") == "chatgpt":                                                       # ChatGPT is the creative director: the user copies the prompt and pastes the reply (no LLM runs here)
        rep.skip("visual_design", "waiting for ChatGPT's visual plan (copy the prompt, paste the reply)")
        rep.skip("asset_check", "runs when the plan arrives")
        KP.set_state(pid, "awaiting_chatgpt")
        return dict(project=pid, state="awaiting_chatgpt")
    rep.start("visual_design", message="the creative director designs the visuals for every narration segment", total_segments=len(tl["narration"]))

    def cb(k, n, msg, nvis):
        rep.progress("visual_design", fraction=(k + 1) / n, message=msg, segment=k + 1, total_segments=n, visuals=nvis, current_operation="creative director (local LLM): one visual at a time")
    res = KP.design(pid, tl, log=lambda m: rep.log(m, "visual_design"), progress=cb)
    rep.complete("visual_design", message=f"{res['report']['counts']['available'] + 0} assets used; plan {res['plan_hash']}", plan_hash=res["plan_hash"])
    c = res["report"]["counts"]
    with rep.stage("asset_check", message="checking every environment, character, prop and action against the catalog") as done:
        done["message"] = f"{c['available']} assets available, {c['new_required']} new required, {c['capability_errors']} capability problem(s)"
        done.update(available=c["available"], new_required=c["new_required"], capability_errors=c["capability_errors"])
    return dict(project=pid, state=res["state"], counts=c)


def run_kbuild(job, pdir, rep):
    from kathaya.assets import builder as AB
    from kathaya import pipeline as KP
    pid, rid = job["project"], job["request_id"]
    rep.start("asset_build", message=f"creating the Kathaya asset for request {rid}")
    asset = AB.build_from_request(pid, rid, job["reference"], log=lambda m: rep.log(m, "asset_build"), progress=lambda f, m: rep.progress("asset_build", fraction=f, message=m))
    rep.complete("asset_build", message=f"asset {asset['id']} created and added to the library", asset_id=asset["id"])
    res = KP.recheck(pid)
    return dict(project=pid, state=res["state"], asset_id=asset["id"], counts=res["report"]["counts"])


def run_krender(job, pdir, rep):
    from kathaya import pipeline as KP
    from kathaya.cache import keys as KK
    from kathaya.qc import technical as KQ
    pid = job["project"]
    KP.set_state(pid, "rendering", job=os.path.basename(pdir))
    with rep.stage("compile", message="compiling the visual scene plan for the renderer") as done:
        prep = KP.prepare_render(pid)
        done["message"] = f"{len(prep['graph']['beats'])} visuals, {len(prep['graph']['scenes'])} scene(s), plan {prep['plan_hash']}"
    json.dump(dict(narration=prep["narration_path"]), open(os.path.join(pdir, "inputs.json"), "w"))
    r = PR.make(None, prep["narration_path"], out_dir=pdir, seed=job.get("seed", 11), samples=job.get("samples", 10), critique_rounds=job.get("critique_rounds", 1), log=rep.log, graph=prep["graph"])
    rep.start("export", message="technical QC, previews and the summary")
    fake = dict(job, mode="kathaya", settings=dict(format="16:9" if prep["plan"]["format"] == "long" else "9:16"), kind="generate")            # long-form: the 9:16 master plus a 16:9 export (the renderer's only native size is 9:16)
    summary = _export(fake, pdir, r, rep)
    plan, tl, cat = prep["plan"], prep["timeline"], prep["catalog"]
    checks = KQ.plan_checks(plan, json.load(open(os.path.join(KP.pdir(pid), "report.json"))), tl, {a["id"] for a in cat["assets"]}) + KQ.film_checks(r["mp4"], r["plan"], tl, r["qc"], fmt=plan["format"])
    k = KQ.summarize(checks, r["qc"])
    adj = getattr(r["plan"], "get", lambda *_: None)("camera_adjustments")
    summary["kathaya"] = dict(qc=k, keys=KK.run_keys(plan, tl, cat, prep["graph"]["plan_overrides"]["kathaya"]["renderer_version"]), title=plan.get("title"), narration_source=tl["source"], visuals=len(plan["visuals"]), camera_adjustments=(r["plan"].get("camera_adjustments") or []))
    json.dump(summary, open(os.path.join(pdir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(k, open(os.path.join(pdir, "kathaya_qc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep.complete("export", message="movie ready", video=summary["files"]["video"])
    proj = KP.load(pid)
    proj["render"] = dict(job=os.path.basename(pdir), video=summary["files"]["video"], qc=k["technical_passed"] and k["engine_passed"], at=time.time())
    KP.save(proj)
    KP.set_state(pid, "completed" if (k["technical_passed"] and k["engine_passed"]) else "completed_with_qc_failures", video=summary["files"]["video"])
    return dict(project=pid, video=summary["files"]["video"], technical_qc=k["technical_passed"], engine_qc=k["engine_passed"])


def run(job, pdir, rep):
    if job.get("test"):
        if os.environ.get("KATHAYA_STUDIO_TEST") != "1":
            raise RuntimeError("test hooks are disabled")
        return _simulate(job, rep)
    for k, v in (job.get("env") or {}).items():                                            # e.g. BLENDER for a failure test (only honoured when the server runs in test mode)
        if os.environ.get("KATHAYA_STUDIO_TEST") == "1":
            os.environ[k] = v
            if k == "BLENDER":
                from engine.skeleton import blender_job
                blender_job.BLENDER = v
    if job.get("kind") in ("kplan", "kbuild", "krender"):
        return {"kplan": run_kplan, "kbuild": run_kbuild, "krender": run_krender}[job["kind"]](job, pdir, rep)
    if job.get("kind") == "rerender":
        _skip_story(rep, job.get("parent"))
        narration, graph = job["narration"], job["graph"]
    else:
        graph = _story_stages(job, pdir, rep)
        narration = _narration(job, pdir, rep)
    json.dump(dict(narration=narration), open(os.path.join(pdir, "inputs.json"), "w"))
    r = PR.make(None, narration, out_dir=pdir, seed=job.get("seed", 11), samples=job.get("samples", 10), critique_rounds=job.get("critique_rounds", 1), log=rep.log, graph=graph)
    rep.start("export", message="collecting files, previews and the summary")
    summary = _export(job, pdir, r, rep)
    rep.complete("export", message="movie ready", video=summary["files"]["video"])
    return dict(summary=summary["files"]["summary"], video=summary["files"]["video"], qc_passed=summary["qc"]["passed"], qc=f"{len(summary['qc']['passed_checks'])}/{summary['qc']['n_checks']}", duration=summary["video"]["duration"])


def main(pdir):
    job = json.load(open(os.path.join(pdir, "job.json"), encoding="utf-8"))
    rep = EVT.install(EVT.Reporter(path=os.path.join(pdir, "events.jsonl"), resume=True))
    signal.signal(signal.SIGTERM, _term)
    rep.emit("started", "job", message="production started", mode=job["mode"], kind=job.get("kind", "generate"), title=job.get("title"), pid=os.getpid(), flow=job.get("flow"))
    def cancelled():
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        _cleanup(pdir)
        act = rep.state.active
        if act and rep.state.stages[act]["status"] == "running":
            rep.emit("cancelled", act, message="cancelled by the user")
        rep.emit("cancelled", "job", message="cancelled by the user")
        rep.close()
        try:
            os.killpg(0, signal.SIGKILL)                                                   # Blender / ffmpeg children go with it
        finally:
            os._exit(130)
    try:
        result = run(job, pdir, rep)
    except Cancelled:
        cancelled()
    except Exception as e:                                                                 # noqa: BLE001 - every failure is reported with its stage and reason
        if _CANCEL.is_set():                                                               # a child died from the same SIGTERM before the handler ran: this is a cancel, not a failure
            cancelled()
        act = rep.state.active
        if act and rep.state.stages[act]["status"] == "running":
            rep.fail(act, e)
        reasons = getattr(e, "reasons", None) or ([r.strip() for r in str(e).split(";") if r.strip()][:6] if isinstance(e, (SS.StoryNotSupported, NI.NarrationInvalid)) else [])
        hint = getattr(e, "hint", None)
        if "Blender" in str(e):
            hint = "Blender could not run. Check that Blender is installed at /Applications/Blender.app (or set BLENDER); the Blender log is in the production's work/blender_stdout_live.txt."
        rep.emit("failed", "job", message=str(e)[:300], error=dict(stage=act, type=type(e).__name__, message=str(e)[:1200], reasons=reasons, hint=hint))
        rep.close()
        _cleanup(pdir)
        sys.exit(1)
    rep.emit("completed", "job", message="production complete", result=result)
    rep.close()


def preview(pdir, shot):
    """render the working plan's shot mid-frame (Blender, frame-cached) -> <pdir>/edits/preview_<shot>.png"""
    from engine.skeleton import backend as BE
    plan = json.load(open(os.path.join(pdir, "edits", "working_plan.json"), encoding="utf-8"))
    from engine.skeleton import topic_build as TB
    TB.bake_cast(plan)
    out = os.path.join(pdir, "edits", "preview")
    p = BE.preview_shot(plan, shot, out)
    dst = os.path.join(pdir, "edits", f"preview_{shot}.png")
    shutil.copyfile(p, dst)
    print("PREVIEW", dst)


if __name__ == "__main__":
    if sys.argv[1] == "preview":
        preview(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1])
