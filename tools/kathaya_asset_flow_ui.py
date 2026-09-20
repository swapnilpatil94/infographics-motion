"""UI test of the MISSING -> references -> approve -> build -> ready flow with a REAL landmark (Wikimedia Commons references). Drives the browser like a user; ChatGPT (paste) is the creative director so no LLM/TTS runs.
    .venv/bin/python tools/kathaya_asset_flow_ui.py [--port 8791] [--landmark "Gateway of India Mumbai"]"""
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8791"
LM = sys.argv[sys.argv.index("--landmark") + 1] if "--landmark" in sys.argv else "Gateway of India Mumbai"
U = f"http://127.0.0.1:{PORT}"
OUT = os.path.join(ROOT, "docs/kathaya/screens")
TEXT = "उस दिन वह पहली बार गेटवे ऑफ इंडिया के सामने खड़ा था।\nउसके फोन पर एक मैसेज आया।\nउसने रुककर सोचा।"


def api(path, body=None):
    req = urllib.request.Request(U + "/api" + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def plan_reply(tl):
    acts = ["ESTABLISH", "OBSERVE", "PHONE_ALERT", "REALIZE", "RESOLVE"]
    vis = []
    for i, s in enumerate(tl["narration"]):
        k = 2 if (s["end"] - s["start"] > 5.5 or (i == 0 and s["end"] - s["start"] > 3.0)) else 1
        for j in range(k):
            n = len(vis)
            vis.append(dict(narration_id=s["id"], visual_intent="ESTABLISH_LOCATION" if n == 0 else "SHOW_ACTION", environment=dict(type="real_landmark", subject=LM, asset_id=None, time_of_day="day", reference_queries=[f"{LM} exterior", f"{LM} street view"]),
                            characters=["boy"], props=[], action=dict(capability=acts[min(n, 4)]), emotion="neutral", camera=dict(shot=["wide", "medium", "close", "full"][n % 4], movement=["push", "drift", "pull", "hold"][n % 4],
                            subject=["environment", "protagonist_head", "protagonist_head", "protagonist_full"][n % 4])))
    vis[-1]["action"]["capability"] = "RESOLVE"
    return dict(title="परीक्षण", cast=[dict(id="boy", role="protagonist", archetype="young man", gender="male")], visuals=vis)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    r = api("/k/project", dict(text=TEXT, format="short", provider="chatgpt", narration_mode="estimated"))
    pid = r["project_id"]
    for _ in range(120):
        if api(f"/k/project/{pid}")["project"]["state"] == "awaiting_chatgpt":
            break
        time.sleep(0.5)
    tl = json.load(open(os.path.join(ROOT, "output/kathaya/projects", pid, "timeline.json"), encoding="utf-8"))
    res = api(f"/k/project/{pid}/chatgpt_reply", dict(reply=json.dumps(plan_reply(tl), ensure_ascii=False)))
    print("state after the plan:", res["state"], res["report"], flush=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_context(viewport=dict(width=1360, height=1000)).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f"{U}/#/k/{pid}")
        pg.wait_for_selector(".assetcard", timeout=20000)
        pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(OUT, "04_new_asset_required.png"), full_page=True)
        print("UI shows NEW ASSET REQUIRED:", pg.inner_text(".assetcard h3"), "|", pg.inner_text(".assetcard div[style*='serif']"), flush=True)
        pg.click("[data-k=refs]")
        pg.wait_for_selector(".ref", timeout=60000)
        pg.wait_for_timeout(1500)
        pg.screenshot(path=os.path.join(OUT, "05_references_for_approval.png"), full_page=True)
        refs = pg.query_selector_all(".ref")
        print("references shown:", len(refs), [ (x.inner_text().split("\n")[1] if "\n" in x.inner_text() else "")[:30] for x in refs], flush=True)
        pg.click("[data-k=approve] >> nth=0")
        t0 = time.time()
        pg.wait_for_selector("[data-k=render]", timeout=180000)                            # the "Generate film" button appears when the asset is built and the plan is ready
        pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(OUT, "06_asset_ready_generate_film.png"), full_page=True)
        print(f"asset built and plan ready after approval in {time.time() - t0:.0f}s; UI text:", pg.inner_text(".card >> nth=0")[:120].replace("\n", " "), flush=True)
        print("js errors:", errs)
        b.close()
    v = api(f"/k/project/{pid}")
    print("final state:", v["project"]["state"], v["report"]["counts"], [(x["state"], x.get("approved", {}).get("reference", {}).get("licence")) for x in v["requests"]])
    json.dump(dict(project=pid, landmark=LM, state=v["project"]["state"], counts=v["report"]["counts"], request=v["requests"][0] if v["requests"] else None), open(os.path.join(ROOT, "docs/kathaya/ASSET_FLOW_RESULT.json"), "w"), ensure_ascii=False, indent=1)
