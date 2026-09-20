"""KATHAAYA STUDIO SERVER: a thin JSON + SSE layer over `engine.studio.core` / `movie` / `jobs` (and through them `engine.skeleton.backend`, `production`). The browser holds no business logic.

    python3 studio.py --ui [--port 8765]        (or:  .venv/bin/python -m engine.studio.server)

    GET  /api/options                       the choices the UI offers (languages, formats, voices, styles, environments, characters, pacing ...)
    POST /api/story                         create a draft (CREATE topic | SCRIPT text / story.md / story.json | PRODUCTION story + segments JSON) -> story review + script; with draft_id: edit / regenerate the story
    POST /api/script                        with draft_id: edit segments / regenerate selected segments (LLM, validated); without: a new SCRIPT-mode draft
    GET  /api/draft/{id}
    POST /api/generate                      approve a draft -> start a production (queued when another one is running)  {production_id}
    POST /api/preview                       one shot's still  {production_id, shot_id, source: "final" | "working"}
    POST /api/render                        render the edited plan of a production as a new production (only changed frames re-render)
    POST /api/cancel                        {production_id}
    GET  /api/productions
    GET  /api/production/{id}               meta + final summary
    GET  /api/production/{id}/status        state folded from the event log (stages, overall %, active stage detail)
    GET  /api/production/{id}/events        Server-Sent Events: the structured production events (replay from ?after=<seq> / Last-Event-ID, then live)
    GET  /api/production/{id}/qc  /plan     QC report / plan + shot inspector view
    POST /api/production/{id}/edit          safe shot-level edits (camera, beat, character, director) through the graph -> validated plan + cache impact
    GET  /api/production/{id}/video  /poster  /shot/{shot}.jpg  /file/{name}
The same routes are also served without the /api prefix.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, FastAPI, Request                                          # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse   # noqa: E402
from fastapi.staticfiles import StaticFiles                                              # noqa: E402

from engine.shorts.raster import ROOT                                                    # noqa: E402
from engine.skeleton import events as EVT                                                # noqa: E402
from engine.studio import core as C, jobs as J, movie as M                               # noqa: E402

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
FILES = {"contact_sheet.png", "qc_report.json", "audio_report.json", "manifest.json", "story_graph.json", "plan.json", "summary.json", "events.jsonl", "poster.jpg", "critique/report.json"}
router = APIRouter()
MGR = {"m": None}


def mgr():
    return MGR["m"]


def _pf(pid, name):
    p = os.path.join(J.pdir(pid), name)
    if not os.path.exists(p):
        raise C.StudioError("not_found", f"'{name}' does not exist for {pid} (yet)", status=404)
    return p


def _json(pid, name):
    return json.load(open(_pf(pid, name), encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ drafts
@router.get("/options")
def options():
    return C.options()


@router.get("/guide")
def guide():
    return C.guide()


@router.post("/guide/check")
def guide_check(body: dict):
    return C.check_reply(body.get("kind", "script"), body.get("text"))


@router.post("/story")
def story(body: dict):
    if body.get("draft_id"):
        d = C.edit_story(body["draft_id"], body.get("edits"), bool(body.get("regenerate")), body.get("settings"))
    else:
        d = C.create_draft(body)
    return C.view(d)


@router.post("/script")
def script(body: dict):
    if body.get("draft_id"):
        return C.view(C.edit_script(body["draft_id"], body.get("segments"), body.get("regenerate")))
    return C.view(C.create_draft(dict(body, mode="script")))


@router.get("/draft/{did}")
def draft(did: str):
    return C.view(C.load_draft(did))


@router.post("/upload")
async def upload(request: Request, kind: str = "audio", name: str = "upload.bin"):
    ext = os.path.splitext(name)[1].lower()
    ok = {".wav", ".mp3", ".m4a", ".flac", ".ogg"} if kind == "audio" else {".json", ".md", ".txt"}
    if ext not in ok:
        raise C.StudioError("invalid_input", f"a {kind} upload must be one of {sorted(ok)}")
    data = await request.body()
    if len(data) > 60 * 1024 * 1024:
        raise C.StudioError("invalid_input", "the file is larger than 60 MB")
    os.makedirs(C.UPLOADS, exist_ok=True)
    fn = f"u_{int(time.time())}_{os.path.basename(name).replace(' ', '_')}"
    open(os.path.join(C.UPLOADS, fn), "wb").write(data)
    return dict(upload_id=fn, bytes=len(data))


# ------------------------------------------------------------------------------------------------ productions
@router.post("/generate")
def generate(body: dict):
    d = C.load_draft(body.get("draft_id"))
    if body.get("approve") is False:
        raise C.StudioError("not_approved", "The story must be approved before generating.")
    job = C.job_request(d)
    if mgr().test_mode:                                                                     # simulated productions / environment overrides exist only for the automated tests
        if body.get("test"):
            job["test"] = body["test"]
        if body.get("env"):
            job["env"] = body["env"]
    pid = mgr().submit(job)
    return dict(production_id=pid, status=mgr().state(pid))


@router.post("/render")
def render(body: dict):
    pid = body["production_id"]
    job = M.rerender_request(pid)
    new = mgr().submit(job, parent=pid)
    return dict(production_id=new, parent=pid, impact=M.edit_state(pid)["impact"], status=mgr().state(new))


@router.post("/cancel")
def cancel(body: dict):
    return mgr().cancel(body["production_id"])


@router.get("/productions")
def productions():
    return mgr().list()


@router.get("/production/{pid}")
def production(pid: str):
    st = mgr().state(pid)
    j = mgr().job(pid)
    s = os.path.join(J.pdir(pid), "summary.json")
    kids = [p["id"] for p in mgr().list(200) if p.get("parent") == pid]
    return dict(id=pid, title=j.get("title"), mode=j.get("mode"), kind=j.get("kind", "generate"), parent=j.get("parent"), draft_id=j.get("draft_id"), children=kids, settings=j.get("settings"), status=st, summary=json.load(open(s, encoding="utf-8")) if os.path.exists(s) else None,
                dir=os.path.relpath(J.pdir(pid), ROOT))


@router.get("/production/{pid}/status")
def status(pid: str):
    return mgr().state(pid)


@router.get("/production/{pid}/qc")
def qc(pid: str):
    q = _json(pid, "qc_report.json")
    s = _json(pid, "summary.json") if os.path.exists(os.path.join(J.pdir(pid), "summary.json")) else {}
    return dict(passed=q["passed"], n_checks=q["n_checks"], checks=[dict(name=k, ok=bool(v)) for k, v in q["checks"].items()], failed=[k for k, v in q["checks"].items() if not v], evidence=q["evidence"], autofix=(s.get("qc") or {}).get("autofix_rounds", []),
                critic_fixes=(s.get("qc") or {}).get("critic_fixes"))


@router.get("/production/{pid}/plan")
def plan(pid: str, raw: int = 0):
    if raw:
        return _json(pid, "plan.json")
    v = M.plan_view(pid)
    ed = M.edit_state(pid)
    v["edits"] = dict(ops=ed["ops"], impact=ed["impact"], warnings=ed["warnings"]) if ed else None
    if ed:
        wp = _json(pid, "edits/working_plan.json")
        v["working_shots"] = {s["id"]: dict(camera=s["camera"], emotion=s["emotion"], act=s["act"], characters=s["characters"]) for s in M.shots_view(wp, ed["graph"], {})}
    return v


@router.post("/production/{pid}/edit")
def edit(pid: str, body: dict):
    return M.apply_ops(pid, body.get("ops") or [])


@router.post("/preview")
async def preview(body: dict):
    pid, sid = body["production_id"], body["shot_id"]
    v = M.plan_view(pid)
    sh = next((s for s in v["shots"] if s["id"] == sid), None)
    if not sh:
        raise C.StudioError("unknown_shot", f"there is no shot '{sid}'", status=404)
    if body.get("source", "final") == "final":
        return dict(url=f"/api/production/{pid}/shot/{sid}.jpg", source="final")
    if not M._has(pid, "edits/working_plan.json"):
        raise C.StudioError("nothing_to_render", "There are no edits for this shot yet.", status=409)
    proc = await asyncio.create_subprocess_exec(J.PY, "-u", "-m", "engine.studio.worker", "preview", J.pdir(pid), sid, cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=240)
    except asyncio.TimeoutError:
        proc.kill()
        raise C.StudioError("preview_failed", "the preview render timed out", status=504)
    if proc.returncode != 0:
        raise C.StudioError("preview_failed", "the preview render failed", reasons=[out.decode(errors="replace")[-400:]], status=500)
    return dict(url=f"/api/production/{pid}/edits/preview_{sid}.png?t={int(time.time())}", source="working")


@router.get("/production/{pid}/edits/{name}")
def edit_file(pid: str, name: str):
    if "/" in name or not name.startswith("preview_"):
        raise C.StudioError("not_found", "no such file", status=404)
    return FileResponse(_pf(pid, "edits/" + name))


@router.get("/production/{pid}/video")
def video(pid: str, variant: str = ""):
    name = "final_16x9.mp4" if variant in ("16x9", "16:9") else "final.mp4"
    return FileResponse(_pf(pid, name), media_type="video/mp4", filename=f"{pid}{'_16x9' if variant else ''}.mp4" if variant == "download" else None)


@router.get("/production/{pid}/download")
def download(pid: str, variant: str = ""):
    name = "final_16x9.mp4" if variant in ("16x9", "16:9") else "final.mp4"
    return FileResponse(_pf(pid, name), media_type="video/mp4", filename=f"{pid}{'_16x9' if variant else ''}.mp4")


@router.get("/production/{pid}/poster")
def poster(pid: str):
    return FileResponse(_pf(pid, "poster.jpg"), media_type="image/jpeg")


@router.get("/production/{pid}/shot/{sid}.jpg")
def shot_img(pid: str, sid: str):
    p = os.path.join(J.pdir(pid), "shots", f"{sid}.jpg")
    if not os.path.exists(p):
        raise C.StudioError("not_found", "no preview for this shot", status=404)
    return FileResponse(p, media_type="image/jpeg")


@router.get("/production/{pid}/file/{name:path}")
def file(pid: str, name: str):
    if name not in FILES:
        raise C.StudioError("not_found", "no such file", status=404)
    return FileResponse(_pf(pid, name))


@router.get("/production/{pid}/events")
async def events(pid: str, request: Request, after: int = 0):
    path = os.path.join(J.pdir(pid), "events.jsonl")
    last = int(request.headers.get("last-event-id") or after or 0)

    async def gen():
        offset, seen, idle = 0, last, 0.0
        state = EVT.State()
        yield "retry: 1500\n\n"
        while True:
            evs, offset = EVT.tail(path, offset)
            done = False
            out = []
            for ev in evs:
                state.apply(ev)                                                       # the browser renders this server-side fold; it never re-implements it
                if ev["seq"] <= seen:
                    continue
                seen = ev["seq"]
                out.append(ev)
                if ev.get("stage") == "job" and ev["event"] in EVT.TERMINAL:
                    done = True
            for i, ev in enumerate(out):
                msg = dict(event=ev)
                if i == len(out) - 1:
                    msg["state"] = dict(state.snapshot(), id=pid, now=time.time())
                yield f"id: {ev['seq']}\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n"
                idle = 0.0
            if done:
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.25)
            idle += 0.25
            if idle >= 15:
                yield ": keepalive\n\n"
                idle = 0.0
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------------------------------------ app
def create_app(test_mode=False, max_running=1):
    app = FastAPI(title="Kathaaya Studio")
    MGR["m"] = J.Manager(max_running=max_running, test_mode=test_mode)

    @app.exception_handler(C.StudioError)
    async def _studio_error(request, exc):
        return JSONResponse(status_code=exc.status, content=dict(error=exc.to_dict()))

    @app.exception_handler(KeyError)
    async def _key_error(request, exc):
        return JSONResponse(status_code=422, content=dict(error=dict(code="missing_field", message=f"missing field {exc}", reasons=[], hint=None)))

    @app.middleware("http")
    async def _no_cache(request, call_next):
        r = await call_next(request)
        if request.url.path.startswith("/static/"):
            r.headers["Cache-Control"] = "no-cache"
        return r

    app.include_router(router, prefix="/api")
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(open(os.path.join(WEB, "index.html"), encoding="utf-8").read(), headers={"Cache-Control": "no-cache"})
    return app


def main():
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", 8765)))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--test-mode", action="store_true", help="enable the simulated-production hooks used by the automated tests")
    a = ap.parse_args()
    print(f"Kathaaya Studio  ->  http://{a.host}:{a.port}", flush=True)
    uvicorn.run(create_app(test_mode=a.test_mode), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
