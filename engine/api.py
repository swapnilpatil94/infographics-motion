"""Programmatic API for the film factory - the seam a future UI / job queue calls (the CLI is a thin wrapper over this).

    from engine import api
    api.generate({"story": "stories/x.md", "narration_segments": "narration/x.wav.segments.json",
                  "style": {"domain": "money_psychology", "seed": "v2", "name": "my_film"}, "aspect_ratio": "9:16"})

Request fields
  story               path to story.md, or the story text itself (must contain a newline)
  narration_segments  path to narration.segments.json, or the already-parsed dict
  style               optional dict: domain (domain pack id), seed (string salt -> controlled variation), name (project folder),
                      allow_fallbacks (bool), plan_only (bool)
  aspect_ratio        "9:16" (native) | "16:9" (blur-pad derivative; see engine/compositing/reframe.py) | "both"
Returns a JSON-serialisable dict: status, project_dir, plan, master, derivatives, qc summary, errors.
The LLM only plans (analysis JSON, validated); it never emits Blender/Python code. Everything after analysis is deterministic.
"""
import json
import os
import tempfile
import time

from engine.factory import domain as DOM
from engine.shorts.raster import ROOT

ASPECTS = {"9:16": ("9:16",), "16:9": ("9:16", "16:9"), "both": ("9:16", "16:9")}
STYLE_KEYS = {"domain", "seed", "name", "allow_fallbacks", "plan_only"}


class RequestError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_request(req):
    errs = []
    if not isinstance(req, dict):
        return ["request must be an object"]
    for k in ("story", "narration_segments"):
        if not req.get(k):
            errs.append(f"missing '{k}'")
    st = req.get("style") or {}
    if not isinstance(st, dict):
        errs.append("'style' must be an object")
    else:
        for k in st:
            if k not in STYLE_KEYS:
                errs.append(f"unknown style key '{k}' (allowed: {sorted(STYLE_KEYS)})")
        dom = st.get("domain", "money_psychology")
        if not os.path.exists(os.path.join(ROOT, "domains", dom, "domain.json")):
            errs.append(f"unknown domain pack '{dom}'")
    if req.get("aspect_ratio", "9:16") not in ASPECTS:
        errs.append(f"aspect_ratio must be one of {sorted(ASPECTS)}")
    for k in ("story",):
        v = req.get(k)
        if isinstance(v, str) and "\n" not in v and not os.path.exists(v if os.path.isabs(v) else os.path.join(ROOT, v)):
            errs.append(f"{k} path not found: {v}")
    n = req.get("narration_segments")
    if isinstance(n, str) and not os.path.exists(n if os.path.isabs(n) else os.path.join(ROOT, n)):
        errs.append(f"narration_segments path not found: {n}")
    if isinstance(n, dict) and not n.get("segments"):
        errs.append("narration_segments dict has no 'segments'")
    return errs


def _materialise(req, tmp):
    story, nar = req["story"], req["narration_segments"]
    if isinstance(story, str) and "\n" in story:
        p = os.path.join(tmp, "story.md")
        open(p, "w", encoding="utf-8").write(story)
        story = p
    if isinstance(nar, dict):
        p = os.path.join(tmp, "narration.wav.segments.json")
        json.dump(nar, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        nar = p
    return story, nar


def generate(req, log=print):
    errs = validate_request(req)
    if errs:
        return dict(status="rejected", errors=errs)
    from engine.factory import pipeline
    st = req.get("style") or {}
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        story, nar = _materialise(req, tmp)
        try:
            res = pipeline.run(story=story, narration=nar, name=st.get("name"), dom_id=st.get("domain", "money_psychology"), allow_fallbacks=bool(st.get("allow_fallbacks")),
                               plan_only=bool(st.get("plan_only")), log=log, seed_salt=str(st.get("seed", "")), aspect_ratios=ASPECTS[req.get("aspect_ratio", "9:16")])
        except Exception as e:                                        # a failed job must return a structured error, never crash the caller
            return dict(status="failed", errors=[f"{type(e).__name__}: {e}"], seconds=round(time.time() - t0, 1))
    if st.get("plan_only"):
        pj, plan = res
        return dict(status="planned", project_dir=pj.dir, plan=os.path.join(pj.dir, "project/shot_plan.json"), shots=len(plan["shots"]), duration=plan["duration"], seconds=round(time.time() - t0, 1))
    out, rep = res
    pdir = os.path.dirname(os.path.dirname(out))
    deriv = {k: os.path.join(pdir, "final", v) for k, v in (("16:9_blurpad", "master_16x9_blurpad.mp4"),) if os.path.exists(os.path.join(pdir, "final", v))}
    return dict(status="done" if rep["passed"] else "done_with_qc_failures", project_dir=pdir, master=out, derivatives=deriv, plan=os.path.join(pdir, "project/shot_plan.json"),
                qc=dict(passed=rep["passed"], failed=[k for k, v in rep["checks"].items() if not v], duration_s=rep["duration_s"]), seconds=round(time.time() - t0, 1))


def rerender(plan_path, log=print, **kw):
    """Deterministic re-render of a saved plan: NO LLM, NO analysis."""
    from engine.factory import pipeline
    return pipeline.run(project_plan=plan_path, log=log, **kw)


def domains():
    return sorted(d for d in os.listdir(os.path.join(ROOT, "domains")) if os.path.exists(os.path.join(ROOT, "domains", d, "domain.json")))
