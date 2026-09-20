"""KATHAYA ACCEPTANCE: the test story goes in through the same API as the UI; nothing is authored by hand. Prints + records evidence to docs/kathaya/ACCEPTANCE_RESULT.json.

    .venv/bin/python -m engine.studio.server --port 8791 &        then        .venv/bin/python tools/kathaya_acceptance.py [--port 8791]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8791
BASE = f"http://127.0.0.1:{PORT}/api"
STORY = """एक लड़के के फोन पर अचानक एक मैसेज आया —
'आपने 25 लाख रुपये की लॉटरी जीती है।'
वह हैरान रह गया।
मैसेज में लिखा था कि इनाम लेने के लिए सिर्फ 12,500 रुपये की फीस भरनी होगी।
उसने पैसे भेज दिए।
कुछ मिनट बाद नंबर बंद हो गया।
तभी उसे समझ आया —
लॉटरी जीती ही नहीं थी।
उसका लालच ही उसका सबसे बड़ा जाल बन गया था।"""


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"}, method=method)
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        return json.load(e)


def wait(fn, done, label, timeout=3600):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        v = fn()
        key = (v.get("status"), v.get("active"), round(v.get("overall", 0), 2))
        if key != last:
            print(f"[accept] {label} {key} {((v.get('last') or {}).get('message') or '')[:80]}", flush=True)
            last = key
        if done(v):
            return v
        time.sleep(2)
    raise TimeoutError(label)


if __name__ == "__main__":
    t0 = time.time()
    r = call("POST", "/k/project", dict(text=STORY, format="short", style="kathaya_default", provider="ollama", narration_mode="auto"))
    pid, jid = r["project_id"], r["job_id"]
    print("[accept] project", pid, "plan job", jid, flush=True)
    st = wait(lambda: call("GET", f"/production/{jid}/status"), lambda s: s["status"] in ("completed", "failed", "cancelled"), "plan")
    proj = call("GET", f"/k/project/{pid}")
    res = dict(project=pid, story=STORY, plan_job=jid, plan_status=st["status"], plan_stages={s["id"]: (s["status"], s["seconds"]) for s in st["stages"]}, state=proj["project"]["state"], timeline=proj["timeline"], counts=(proj.get("report") or {}).get("counts"),
               requests=[r["id"] for r in proj.get("requests", [])], capability_errors=[e["message"] for e in (proj.get("report") or {}).get("capability_errors", [])], plan_seconds=round(time.time() - t0, 1))
    os.makedirs(os.path.join(ROOT, "docs/kathaya"), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, "docs/kathaya/ACCEPTANCE_RESULT.json"), "w"), ensure_ascii=False, indent=1)
    print("[accept] after planning:", proj["project"]["state"], res["counts"], flush=True)
    if proj["project"]["state"] != "ready":
        print("[accept] not ready: stopping (the system refused to render; see requests / capability errors)")
        sys.exit(2)
    t1 = time.time()
    rr = call("POST", f"/k/project/{pid}/render")
    rid = rr["job_id"]
    st = wait(lambda: call("GET", f"/production/{rid}/status"), lambda s: s["status"] in ("completed", "failed", "cancelled"), "render")
    proj = call("GET", f"/k/project/{pid}")
    m = call("GET", f"/production/{rid}")
    sm = m.get("summary") or {}
    res.update(render_job=rid, render_status=st["status"], state=proj["project"]["state"], render_seconds=round(time.time() - t1, 1), total_seconds=round(time.time() - t0, 1), summary=dict(video=sm.get("video"), shots=sm.get("shots"), scenes=sm.get("scenes"), timings=sm.get("timings"),
               cache=sm.get("cache"), engine_qc=dict(passed=(sm.get("qc") or {}).get("passed"), n=(sm.get("qc") or {}).get("n_checks"), failed=(sm.get("qc") or {}).get("failed_checks")), kathaya=(sm.get("kathaya") or {}), files=sm.get("files")))
    json.dump(res, open(os.path.join(ROOT, "docs/kathaya/ACCEPTANCE_RESULT.json"), "w"), ensure_ascii=False, indent=1)
    print("[accept] DONE", proj["project"]["state"], json.dumps(res["summary"].get("engine_qc")), flush=True)
