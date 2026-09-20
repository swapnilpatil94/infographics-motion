"""STUDIO END-TO-END (real renders, over HTTP, against a running studio server started with --test-mode):

    .venv/bin/python -m engine.studio.server --port 8765 --test-mode &
    .venv/bin/python tools/studio/e2e.py [scenario ...]        scenarios: accepted script create cancel failed director   (default: all)

Every scenario drives the same API the browser uses and records EVIDENCE (events, stage timings, cache reuse, QC) into docs/studio/E2E_RESULTS.json.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.environ.get("STUDIO_URL", "http://127.0.0.1:8765") + "/api"
OUT = os.path.join(ROOT, "docs/studio/E2E_RESULTS.json")
RES = json.load(open(OUT)) if os.path.exists(OUT) else {}


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"}, method=method)
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        return json.load(e)


def save(name, ev):
    cur = json.load(open(OUT)) if os.path.exists(OUT) else {}                     # merge with what other runs wrote meanwhile
    cur[name] = RES[name] = ev
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(cur, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"[e2e] {name}: {json.dumps(ev, ensure_ascii=False)[:600]}", flush=True)


def wait(pid, until=("completed", "failed", "cancelled"), timeout=3600, cond=None):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        s = call("GET", f"/production/{pid}/status")
        line = (s["status"], s["active"], round(s["overall"], 3), (s["last"] or {}).get("frame"))
        if line != last and (last is None or line[:2] != last[:2] or time.time() % 20 < 1):
            print(f"[e2e] {pid} {line}", flush=True)
        last = line
        if s["status"] in until or (cond and cond(s)):
            return s
        time.sleep(1.0)
    raise TimeoutError(pid)


def draft(**req):
    d = call("POST", "/story", req)
    assert "error" not in d, d
    return d


def start(d, **extra):
    r = call("POST", "/generate", dict(draft_id=d["id"], approve=True, **extra))
    assert "production_id" in r, r
    return r["production_id"]


def summary(pid):
    return call("GET", f"/production/{pid}")["summary"]


def brief(pid):
    m = call("GET", f"/production/{pid}")
    s, st = m["summary"], m["status"]
    ev = [json.loads(l) for l in open(os.path.join(ROOT, m["dir"], "events.jsonl"))]
    return dict(production=pid, status=st["status"], qc=f"{len(s['qc']['passed_checks'])}/{s['qc']['n_checks']}", qc_failed=s["qc"]["failed_checks"], autofix=[r["fixes"] for r in s["qc"]["autofix_rounds"] if r["fixes"]], duration=s["video"]["duration"], shots=s["shots"],
                cache=s["cache"], timings=s["timings"], events=len(ev), progress_events=sum(1 for e in ev if e["event"] == "progress"), overall_monotone=[e["overall"] for e in ev] == sorted(e["overall"] for e in ev),
                stages={x["id"]: (x["status"], x["seconds"]) for x in st["stages"]}, file=s["files"]["video"], requested=s.get("requested"), captions=s.get("captions"), director=s.get("director"))


def accepted():
    for key in ("b_lottery_fee", "c_atm_helper"):
        d = draft(mode="production", example=key)
        pid = start(d)
        wait(pid)
        save(f"accepted_{key}", brief(pid))


def script_mode():
    seg = json.load(open(os.path.join(ROOT, "stories/production/b_lottery_fee/segments.json"), encoding="utf-8"))["segments"]
    text = "# जो इनाम माँगा ही नहीं\n" + "\n".join(s["text"] for s in seg)
    d = draft(mode="script", script_text=text, format="16:9")
    pid = start(d)
    s = wait(pid)
    b = brief(pid)
    b["narration_cache_hit"] = bool((s["stages"][3].get("detail") or {}).get("cached"))
    b["files_16x9"] = os.path.exists(os.path.join(ROOT, "output/studio/productions", pid, "final_16x9.mp4"))
    save("script_mode", b)


def create_mode():
    d = draft(mode="create", topic="instant loan app blackmail scam", duration="55")
    pid = start(d)
    s = wait(pid)
    b = brief(pid)
    b["narration"] = s["stages"][3]
    b["topic_title"] = d["review"]["title"]
    save("create_mode", b)


def variation():
    """the create-mode film failed one QC gate the engine cannot auto-fix: re-run it as the next variation (what the UI's 'Try another variation' button does)"""
    prev = RES["create_mode"]["production"]
    job = json.load(open(os.path.join(ROOT, "output/studio/productions", prev, "job.json")))
    attach = os.environ.get("ATTACH")                                                # an already submitted production (same request) to record
    if attach:
        d = call("GET", f"/draft/{job['draft_id']}")
        pid = attach
    else:
        d = call("POST", "/story", dict(draft_id=job["draft_id"], regenerate=True))
        assert "error" not in d, d
        pid = start(d)
    wait(pid)
    b = brief(pid)
    b["variation"] = d["variation"]
    b["previous"] = dict(production=prev, qc=RES["create_mode"]["qc"], qc_failed=RES["create_mode"]["qc_failed"])
    b["topic_title"] = d["review"]["title"]
    save("create_mode_variation_retry", b)


def cancel():
    d = draft(mode="production", example="c_atm_helper", variation=3, director=dict(pacing="intense"))
    pid = start(d)
    s = wait(pid, cond=lambda s: s["active"] == "blender_render" and (s["last"] or {}).get("rendered", 0) >= 15)
    assert s["active"] == "blender_render", s["active"]
    procs = lambda: [l for l in subprocess.run(["pgrep", "-fl", pid], capture_output=True, text=True).stdout.splitlines() if "pgrep" not in l]      # every process whose command line names THIS production (worker, Blender, ffmpeg)
    before = "\n".join(procs())
    t = time.time()
    r = call("POST", "/cancel", dict(production_id=pid))
    took = round(time.time() - t, 2)
    time.sleep(1.5)
    after = "\n".join(procs())
    ev = [json.loads(l) for l in open(os.path.join(ROOT, "output/studio/productions", pid, "events.jsonl"))]
    save("cancel_real_blender", dict(production=pid, status=r["status"], cancelled_stage=[x["id"] for x in r["stages"] if x["status"] == "cancelled"], seconds_to_cancel=took, processes_naming_this_production_before=len(before.splitlines()), processes_naming_this_production_after=len(after.splitlines()),
                                     has_video=os.path.exists(os.path.join(ROOT, "output/studio/productions", pid, "final.mp4")), last_events=[(e["event"], e["stage"]) for e in ev[-3:]],
                                     frame_copies_cleaned=not os.path.isdir(os.path.join(ROOT, "output/studio/productions", pid, "work/actor_frames")), rendered_when_cancelled=(s["last"] or {}).get("rendered")))


def failed():
    d = draft(mode="production", example="a_whatsapp_investment")
    pid = start(d, env=dict(BLENDER="/nonexistent/Blender"))
    s = wait(pid)
    save("failed_render_blender_missing", dict(production=pid, status=s["status"], error=s["error"], stages={x["id"]: x["status"] for x in s["stages"]}))


def director():
    d = draft(mode="production", example="a_whatsapp_investment", director=dict(pacing="calm", audio=dict(music=0.5)), typography=dict(captions=False))
    pid = start(d)
    wait(pid)
    save("director_options_calm_nocaptions_music50", brief(pid))


if __name__ == "__main__":
    which = sys.argv[1:] or ["accepted", "cancel", "failed", "script", "create", "director"]
    fns = dict(accepted=accepted, script=script_mode, create=create_mode, cancel=cancel, failed=failed, director=director, variation=variation)
    for w in which:
        print(f"[e2e] ===== {w} =====", flush=True)
        fns[w]()
