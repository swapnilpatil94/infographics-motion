"""KATHAYA API (mounted under /api/k): the simple flow.  story / narration -> plan -> [approve NEW assets only] -> film.

    POST /api/k/project                      {text, format: short|long, style, audio_upload?, timing_json?, provider: ollama|chatgpt, narration_mode}  -> {project_id, job_id}   (starts the plan job)
    GET  /api/k/project/{id}                 project state + timeline summary + plan + report + asset requests (+ the plan job status)
    POST /api/k/project/{id}/plan            (re)plan
    POST /api/k/project/{id}/render          start the film (only when the plan is ready)  -> {job_id}
    GET  /api/k/project/{id}/chatgpt_prompt  the strict prompt for ChatGPT as creative director
    POST /api/k/project/{id}/chatgpt_reply   {reply}  -> validates + resolves the pasted plan
    GET  /api/k/project/{id}/requests        asset requests
    POST /api/k/project/{id}/request/{rid}/references   search reference candidates (Wikimedia Commons, licence-classified)
    POST /api/k/project/{id}/request/{rid}/approve      {reference}  -> starts the asset build job
    POST /api/k/project/{id}/request/{rid}/substitute   {asset_id}   the user explicitly accepts an existing asset instead
    GET  /api/k/manifest   /api/k/catalog    what the renderer can do / which assets exist
Job progress is the same structured event stream as everywhere: GET /api/production/{job_id}/events (SSE) / status."""
import json
import os
import time

from fastapi import APIRouter

from engine.studio import core as C, jobs as J
from kathaya import pipeline as KP
from kathaya.assets import catalog as CAT, references as REF
from kathaya.renderer import manifest as MF

router = APIRouter()
MGR = {"m": None}


def mgr():
    return MGR["m"]


def _job(project_id, kind, flow, title, **extra):
    job = dict(kind=kind, flow=flow, mode="kathaya", project=project_id, title=title, settings=dict(format="9:16"), lines=[], notes={}, graph=None, created=time.time(), seed=11, samples=10, critique_rounds=1, **extra)
    return mgr().submit(job)


def _status(jid):
    try:
        return mgr().state(jid)
    except C.StudioError:
        return None


def _view(pid):
    s = KP.summary(pid)
    jobs = s["project"].get("jobs", {})
    out = dict(s, plan_job=_status(jobs["plan"]) if jobs.get("plan") else None, render_job=_status(jobs["render"]) if jobs.get("render") else None, build_job=_status(jobs["build"]) if jobs.get("build") else None)
    out["ready_to_render"] = s["project"]["state"] in ("ready", "completed", "completed_with_qc_failures")
    return out


def _start_plan(pid):
    proj = KP.load(pid)
    jid = _job(pid, "kplan", "kplan", "Kathaya plan")
    proj["jobs"]["plan"] = jid
    KP.save(proj)
    return jid


@router.post("/project")
def create(body: dict):
    audio = None
    if body.get("audio_upload"):
        audio = os.path.join(C.UPLOADS, os.path.basename(body["audio_upload"]))
        if not os.path.exists(audio):
            raise KP.ProjectError("narration_invalid", "The uploaded audio file is missing.")
    timing = body.get("timing_json")
    if isinstance(timing, str) and timing.strip():
        try:
            timing = json.loads(timing)
        except ValueError as e:
            raise KP.ProjectError("narration_invalid", "The timing JSON is not valid JSON.", reasons=[str(e)])
    else:
        timing = None
    proj = KP.create(body.get("text", ""), body.get("format", "short"), body.get("style", "kathaya_default"), audio, timing, body.get("narration_mode", "auto"), body.get("provider", "ollama"))
    jid = _start_plan(proj["id"])
    return dict(project_id=proj["id"], job_id=jid)


@router.get("/project/{pid}")
def project(pid: str):
    return _view(pid)


@router.get("/projects")
def projects():
    out = []
    for d in sorted(os.listdir(KP.PROJECTS), reverse=True)[:30] if os.path.isdir(KP.PROJECTS) else []:
        f = os.path.join(KP.PROJECTS, d, "project.json")
        if os.path.exists(f):
            p = json.load(open(f, encoding="utf-8"))
            out.append(dict(id=p["id"], state=p["state"], created=p["created"], text=(p["input"]["text"] or "")[:80], format=p["input"]["format"]))
    return out


@router.post("/project/{pid}/plan")
def replan(pid: str):
    return dict(job_id=_start_plan(pid))


@router.post("/project/{pid}/render")
def render(pid: str):
    proj = KP.load(pid)
    if proj["state"] not in ("ready", "completed", "completed_with_qc_failures"):
        raise KP.ProjectError("not_ready", f"The project is '{proj['state']}': the film can only be rendered when every asset is available.", hint="Approve or substitute the missing assets first.", status=409)
    jid = _job(pid, "krender", "krender", (KP._read(pid, "visual_plan.json") or {}).get("title") or "Kathaya film")
    proj = KP.load(pid)
    proj["jobs"]["render"] = jid
    KP.save(proj)
    return dict(job_id=jid)


@router.get("/project/{pid}/chatgpt_prompt")
def chatgpt_prompt(pid: str):
    return dict(prompt=KP.chatgpt_prompt(pid))


@router.post("/project/{pid}/chatgpt_reply")
def chatgpt_reply(pid: str, body: dict):
    r = KP.apply_chatgpt_reply(pid, body.get("reply"))
    return dict(state=r["state"], report=r["report"]["counts"])


@router.get("/project/{pid}/requests")
def requests_(pid: str):
    return KP.summary(pid)["requests"]


@router.post("/project/{pid}/request/{rid}/references")
def references(pid: str, rid: str):
    req = KP._read(pid, f"requests/{rid}.json")
    if not req:
        raise KP.ProjectError("unknown_request", f"unknown request {rid}", status=404)
    cands = REF.search(req)
    req.update(state="references_found", references=cands)
    KP._write(pid, f"requests/{rid}.json", req)
    return dict(request=req)


@router.post("/project/{pid}/request/{rid}/approve")
def approve(pid: str, rid: str, body: dict):
    req = KP._read(pid, f"requests/{rid}.json")
    if not req:
        raise KP.ProjectError("unknown_request", f"unknown request {rid}", status=404)
    refs = req.get("references") or []
    idx = body.get("reference_index")
    if idx is None or not 0 <= int(idx) < len(refs):
        raise KP.ProjectError("invalid_reference", "Choose one of the listed references to approve.", status=422)
    ref = refs[int(idx)]
    if not ref.get("production_ok"):
        raise KP.ProjectError("licence_refused", f"This reference cannot be used to create a production asset: {ref.get('licence_reason')}", hint="Choose a reference with an accepted licence.")
    req.update(state="approved", approved=dict(by="user", reference=ref, at=time.time()))
    KP._write(pid, f"requests/{rid}.json", req)
    jid = _job(pid, "kbuild", "kbuild", f"Asset: {req['subject']}", request_id=rid, reference=ref)
    proj = KP.load(pid)
    proj["jobs"]["build"] = jid
    KP.save(proj)
    return dict(job_id=jid)


@router.post("/project/{pid}/request/{rid}/substitute")
def substitute(pid: str, rid: str, body: dict):
    r = KP.substitute(pid, rid, body.get("asset_id"))
    return dict(state=r["state"], counts=r["report"]["counts"])


@router.get("/manifest")
def manifest():
    return MF.build()


@router.get("/catalog")
def catalog():
    c = CAT.load()
    return dict(catalog_hash=c["catalog_hash"], renderer_version=c["renderer_version"], assets=[dict(id=a["id"], type=a["type"], name=a["name"], status=a["status"], source=a["source"], license=a["license"], subjects=a["subjects"][:4]) for a in c["assets"]])


@router.get("/project/{pid}/file/{name:path}")
def file(pid: str, name: str):
    from fastapi.responses import FileResponse
    if name not in ("timeline.json", "visual_plan.json", "report.json", "director_raw.json", "compiled/graph.json", "compiled/narration.json"):
        raise KP.ProjectError("not_found", "no such file", status=404)
    return FileResponse(KP.pdir(pid, name))


@router.get("/reference/{rid}/{name}")
def reference_file(rid: str, name: str):
    from fastapi.responses import FileResponse
    if not all(c.isalnum() or c in "_-" for c in rid) or "/" in name or not name.endswith(".jpg"):
        raise KP.ProjectError("not_found", "no such reference", status=404)
    p = os.path.join(REF.REF_DIR, rid, name)
    if not os.path.exists(p):
        raise KP.ProjectError("not_found", "no such reference", status=404)
    return FileResponse(p, media_type="image/jpeg")
