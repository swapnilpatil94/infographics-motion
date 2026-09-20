"""Screenshots of the real UI (headless Chromium via Playwright) into docs/studio/screens/.

    .venv/bin/python tools/studio/screens.py static            create / director / expert / review / edit-story / productions + final + inspector of the newest completed production
    .venv/bin/python tools/studio/screens.py live [--wait 900]  waits for a RUNNING production and captures its dashboard while Blender renders and while compositing
    .venv/bin/python tools/studio/screens.py state failed|cancelled   dashboard of the newest production in that state
"""
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = os.environ.get("STUDIO_URL", "http://127.0.0.1:8765")
OUT = os.path.join(ROOT, "docs/studio/screens")
os.makedirs(OUT, exist_ok=True)


def api(path, body=None):
    req = urllib.request.Request(URL + "/api" + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def newest(status, kind=None):
    for p in api("/productions"):
        if p["status"] == status and (kind is None or p["kind"] == kind):
            return p["id"]


def page_for(pw, w=1360, h=1000):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=dict(width=w, height=h), device_scale_factor=1)
    ctx.add_init_script("localStorage.setItem('ks.level','simple')")
    return b, ctx.new_page()


def shot(page, name, full=False):
    page.wait_for_timeout(600)
    page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full)
    print("saved", name, flush=True)


def level(page, lv):
    page.evaluate(f"localStorage.setItem('ks.level','{lv}')")
    page.reload()
    page.wait_for_timeout(500)


def static():
    with sync_playwright() as pw:
        b, page = page_for(pw)
        page.goto(URL + "/#/")
        page.wait_for_selector("#go")
        page.click("[data-topic]")
        shot(page, "01_create_simple")
        level(page, "director")
        shot(page, "02_create_director", full=True)
        level(page, "expert")
        shot(page, "03_create_expert", full=True)
        level(page, "simple")
        page.click("[data-topic]")
        page.click("#go")
        page.wait_for_selector("#btn-approve", timeout=30000)
        shot(page, "04_review_story_and_script", full=True)
        page.click("#btn-edit")
        shot(page, "05_review_edit_story", full=True)
        page.goto(URL + "/#/")
        page.wait_for_selector("#go")
        page.click("[data-mode=script]")
        page.fill("[data-f=script_text]", "hello world")
        page.click("#go")
        page.wait_for_selector("#create-err .err", timeout=20000)
        shot(page, "06_validation_error_not_hindi")
        page.click("[data-mode=create]")
        page.fill("[data-f=topic]", "ancient temple mythology")
        page.click("#go")
        page.wait_for_selector("#create-err .err", timeout=20000)
        shot(page, "07_validation_error_unsupported_topic")
        page.goto(URL + "/#/productions")
        page.wait_for_timeout(1200)
        shot(page, "08_productions_list", full=True)
        pid = os.environ.get("SCREEN_PID") or newest("completed", "generate") or newest("completed")
        if pid:
            page.goto(URL + f"/#/production/{pid}")
            page.wait_for_selector("#vid", timeout=20000)
            shot(page, "09_final_movie_overview", full=True)
            page.click("[data-tab=inspector]")
            page.wait_for_selector(".tl", timeout=20000)
            page.click(".tl >> nth=6")
            shot(page, "10_movie_inspector", full=True)
            level(page, "expert")
            page.goto(URL + f"/#/production/{pid}")
            page.wait_for_selector("#vid", timeout=20000)
            page.click("[data-tab=expert]")
            page.wait_for_selector("pre.json", timeout=20000)
            shot(page, "11_expert_plan_and_graph")
        b.close()


def live(wait=900):
    end = time.time() + wait
    got = set()
    with sync_playwright() as pw:
        b, page = page_for(pw)
        while time.time() < end and len(got) < 3:
            run = [p for p in api("/productions") if p["status"] == "running"]
            if run:
                pid = run[0]["id"]
                s = api(f"/production/{pid}/status")
                act = s["active"]
                key = act if act in ("scene_direction", "blender_render", "compositing", "narration") else None
                if key and key not in got and (act != "blender_render" or (s["last"] or {}).get("rendered", 0) > 5):
                    page.goto(URL + f"/#/production/{pid}")
                    page.wait_for_selector(".stages", timeout=15000)
                    shot(page, f"12_dashboard_{key}", full=True)
                    got.add(key)
            time.sleep(3)
        b.close()


def state(status):
    pid = newest(status)
    if not pid:
        print("no production in state", status)
        return
    with sync_playwright() as pw:
        b, page = page_for(pw)
        page.goto(URL + f"/#/production/{pid}")
        page.wait_for_selector(".stages", timeout=15000)
        shot(page, f"13_dashboard_{status}", full=True)
        b.close()


def final(pid, name):
    with sync_playwright() as pw:
        b, page = page_for(pw)
        page.goto(URL + f"/#/production/{pid}")
        page.wait_for_selector("#vid", timeout=20000)
        shot(page, name, full=True)
        b.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "static"
    if cmd == "final":
        final(sys.argv[2], sys.argv[3])
    elif cmd == "static":
        static()
    elif cmd == "live":
        live(int(sys.argv[3]) if len(sys.argv) > 3 else 900)
    else:
        state(sys.argv[2])
