"""KATHAYA PIPELINE: story / narration -> narration timeline -> visual scene plan (creative director) -> asset check -> [human approval only for NEW assets] -> deterministic render -> QC.

A PROJECT is a folder (output/kathaya/projects/<id>/) with every artifact of the run: input.json, timeline.json, director_raw.json, visual_plan.json (resolved), report.json, requests/*.json, compiled/*.
Its `state`: created -> planning -> needs_assets | blocked | ready -> rendering -> completed | failed. Nothing is rendered while a requirement is MISSING / UNSUPPORTED (unless the user explicitly substitutes)."""
import json
import os
import time
import uuid

from engine.shorts.raster import ROOT
from kathaya import schemas
from kathaya.assets import catalog as CAT, resolver as RES
from kathaya.director import prompt as PR, providers as PV, visual_planner as VP
from kathaya.renderer import compile as CP, manifest as MF
from kathaya.story import narration as NAR

PROJECTS = os.environ.get("KATHAYA_PROJECTS") or os.path.join(ROOT, "output/kathaya/projects")


class ProjectError(Exception):
    def __init__(self, code, message, reasons=None, hint=None, status=422):
        super().__init__(message)
        self.code, self.message, self.reasons, self.hint, self.status = code, message, list(reasons or []), hint, status

    def to_dict(self):
        return dict(code=self.code, message=self.message, reasons=self.reasons, hint=self.hint)


def pdir(pid, *p):
    if not pid or not all(c.isalnum() or c in "_-" for c in pid):
        raise ProjectError("unknown_project", f"unknown project '{pid}'", status=404)
    return os.path.join(PROJECTS, pid, *p)


def load(pid):
    f = pdir(pid, "project.json")
    if not os.path.exists(f):
        raise ProjectError("unknown_project", f"unknown project '{pid}'", status=404)
    return json.load(open(f, encoding="utf-8"))


def save(proj):
    os.makedirs(pdir(proj["id"]), exist_ok=True)
    tmp = pdir(proj["id"], "project.json.tmp")
    proj["updated"] = time.time()
    json.dump(proj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, pdir(proj["id"], "project.json"))
    return proj


def _read(pid, name, default=None):
    f = pdir(pid, name)
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else default


def _write(pid, name, obj):
    f = pdir(pid, name)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump(obj, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def create(text, fmt="short", style="kathaya_default", audio=None, timing=None, narration_mode="auto", provider="ollama", direction=""):
    if fmt not in ("short", "long"):
        raise ProjectError("invalid_options", f"format must be short or long, got {fmt!r}")
    if style != "kathaya_default":
        raise ProjectError("invalid_options", f"unknown style '{style}'", hint="Available: kathaya_default")
    if not (text or "").strip() and not timing:
        raise ProjectError("empty_input", "Paste the story / narration first.")
    proj = dict(id="k_" + time.strftime("%Y%m%d-%H%M%S") + "_" + uuid.uuid4().hex[:4], created=time.time(), state="created", input=dict(text=text or "", format=fmt, style=style, audio=audio, timing=timing, narration_mode=narration_mode, provider=provider, direction=(direction or "").strip()),
                jobs={}, history=[])
    return save(proj)


def set_state(pid, state, **kw):
    proj = load(pid)
    proj["state"] = state
    proj.setdefault("history", []).append(dict(t=time.time(), state=state, **kw))
    return save(proj)


def _director(proj, pid):
    prov = proj["input"].get("provider", "ollama")
    if prov == "chatgpt":
        reply = _read(pid, "chatgpt_reply.json")
        if not reply:
            raise ProjectError("chatgpt_reply_missing", "Paste ChatGPT's reply for the visual plan first.", hint="Open the project's ChatGPT prompt, paste it into ChatGPT and paste the reply back.")
        return PV.PasteProvider(reply)
    if prov == "file":
        return PV.FileProvider(pdir(pid, "director_raw.json"))
    p = PV.OllamaProvider()
    if not p.available():
        raise ProjectError("director_unavailable", "The creative director (local LLM qwen3:14b) is not available.", reasons=["ollama is not running or the model is not installed"],
                           hint="Start ollama, or switch the project to the ChatGPT provider (copy the prompt into ChatGPT and paste the reply).", status=503)
    return p


def build_timeline(pid, workdir=None, log=print):
    proj = load(pid)
    i = proj["input"]
    timing = i.get("timing")
    try:
        tl = NAR.build(text=i["text"], audio=i.get("audio"), timing=timing, fmt=i["format"], mode=i.get("narration_mode", "auto"), workdir=workdir or pdir(pid, "narration"), log=log)
    except ValueError as e:
        raise ProjectError("narration_invalid", str(e), hint="Provide Hindi narration text, or your own audio (+ timing JSON).")
    _write(pid, "timeline.json", tl)
    return tl


def design(pid, timeline=None, log=print, progress=None):
    """creative director -> resolved plan + report; writes the artifacts and the project state"""
    proj = load(pid)
    tl = timeline or _read(pid, "timeline.json")
    m, cat = MF.build(), CAT.load()
    res = VP.design(tl, m, cat, _director(proj, pid), proj["input"]["format"], log=log, progress=progress, direction=proj["input"].get("direction", ""))
    if res.get("raw"):
        _write(pid, "director_raw.json", res["raw"])
    if res["plan"] is None:
        raise ProjectError("plan_invalid", "The creative director's plan is not usable.", reasons=res.get("unresolved", []))
    return _store(pid, res["plan"], res["report"], res["plan_hash"], res.get("unresolved", []), res.get("attempts"))


def _store(pid, plan, report, plan_hash, notes=(), attempts=None):
    _write(pid, "visual_plan.json", plan)
    _write(pid, "report.json", dict(report, plan_hash=plan_hash, notes=list(notes), attempts=attempts))
    for r in report["requests"]:
        old = _read(pid, f"requests/{r['id']}.json")
        _write(pid, f"requests/{r['id']}.json", dict(r, state=(old or {}).get("state", "open"), references=(old or {}).get("references", []), approved=(old or {}).get("approved")))
    state = "blocked" if report["capability_errors"] else ("needs_assets" if report["requests"] else "ready")
    set_state(pid, state, plan_hash=plan_hash, counts=report["counts"])
    return dict(state=state, plan_hash=plan_hash, report=report)


def recheck(pid):
    """re-resolve the stored plan against the CURRENT catalog (after an asset was built / a substitution was approved)"""
    plan = _read(pid, "visual_plan.json")
    if not plan:
        raise ProjectError("no_plan", "This project has no visual plan yet.", status=409)
    m, cat = MF.build(), CAT.load()
    plan, report = RES.resolve(plan, m, cat)
    return _store(pid, plan, report, VP.plan_hash(plan), _read(pid, "report.json", {}).get("notes", []))


def substitute(pid, request_id, asset_id):
    """the user explicitly accepts an existing asset instead of creating the requested one (recorded, never silent)"""
    req = _read(pid, f"requests/{request_id}.json")
    if not req:
        raise ProjectError("unknown_request", f"unknown request {request_id}", status=404)
    plan = _read(pid, "visual_plan.json")
    cat = CAT.load()
    try:
        plan = RES.substitute(plan, req["required_by"], asset_id, cat)
    except ValueError as e:
        raise ProjectError("invalid_substitution", str(e))
    req.update(state="substituted", approved=dict(by="user", asset_id=asset_id, at=time.time()))
    _write(pid, f"requests/{request_id}.json", req)
    _write(pid, "visual_plan.json", plan)
    return recheck(pid)


def chatgpt_prompt(pid):
    proj = load(pid)
    tl = _read(pid, "timeline.json") or build_timeline(pid)
    return PR.build(tl, MF.compact(MF.build()), CAT.compact(CAT.load()), proj["input"]["format"], direction=proj["input"].get("direction", ""))


def apply_chatgpt_reply(pid, reply):
    tl = _read(pid, "timeline.json")
    if not tl:
        raise ProjectError("no_timeline", "Build the narration timeline first.", status=409)
    try:
        raw = PV.extract_json(reply) if isinstance(reply, str) else reply
        plan = VP.finalize(raw, tl, load(pid)["input"]["format"])
    except (ValueError, VP.PlanError) as e:
        raise ProjectError("plan_invalid", "ChatGPT's reply is not a usable visual plan.", reasons=(e.errors if isinstance(e, VP.PlanError) else [str(e)]), hint="Ask ChatGPT to fix exactly these problems and paste the new reply.")
    m, cat = MF.build(), CAT.load()
    plan, report = RES.resolve(plan, m, cat)
    _write(pid, "director_raw.json", raw)
    return _store(pid, plan, report, VP.plan_hash(plan), VP.rhythm_errors(plan))


def prepare_render(pid):
    """-> compiled renderer inputs (graph + narration); refuses while anything is MISSING / UNSUPPORTED"""
    plan = _read(pid, "visual_plan.json")
    tl = _read(pid, "timeline.json")
    m, cat = MF.build(), CAT.load()
    plan, report = RES.resolve(plan, m, cat)
    if not report["ready"]:
        raise CP.NotReady(report)
    ph = VP.plan_hash(plan)
    out = CP.compile_plan(plan, tl, cat, report, ph)
    _write(pid, "compiled/graph.json", out["graph"])
    nar = dict(out["narration"])
    _write(pid, "compiled/narration.json", nar)
    return dict(graph=out["graph"], narration_path=pdir(pid, "compiled", "narration.json"), plan=plan, timeline=tl, catalog=cat, plan_hash=ph)


def summary(pid):
    proj = load(pid)
    rep = _read(pid, "report.json")
    tl = _read(pid, "timeline.json")
    plan = _read(pid, "visual_plan.json")
    reqs = [_read(pid, f"requests/{f}") for f in sorted(os.listdir(pdir(pid, "requests")))] if os.path.isdir(pdir(pid, "requests")) else []
    return dict(project=proj, timeline=tl and dict(source=tl["source"], duration=tl["duration"], segments=len(tl["narration"]), warnings=tl["warnings"], audio=bool(tl.get("audio"))), plan=plan, report=rep, requests=reqs)
