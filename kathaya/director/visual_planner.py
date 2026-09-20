"""VISUAL PLANNER: the creative director's answer -> a validated `VisualScenePlan` with exact times.

The director never writes times: each narration segment gets 1-3 visuals with a `share`; the times are derived here from the NarrationTimeline (word times when the narration has them). The plan is then validated against
the renderer's capability manifest and resolved against the asset catalog. Malformed / renderer-rule-violating answers go back to the director with the exact reasons (repair loop); MISSING assets, UNSUPPORTED
requirements and unsupported capabilities are NOT repaired away - they are the result."""
import copy
import hashlib
import json

from kathaya import schemas
from kathaya.assets import resolver as RES
from kathaya.director import prompt as PR
from kathaya.story import hindi

MIN_VISUAL, MAX_VISUAL, HOOK_MAX = 0.9, 6.0, 4.5


class PlanError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors[:4]))
        self.errors = errors


def finalize(raw, timeline, fmt="short"):
    errs = []
    if not isinstance(raw, dict) or not raw.get("visuals") or not raw.get("cast"):
        raise PlanError(["the answer needs 'cast' and 'visuals'"])
    seg = {s["id"]: s for s in timeline["narration"]}
    order = [s["id"] for s in timeline["narration"]]
    cast = []
    for i, c in enumerate(raw["cast"]):
        cid = str(c.get("id") or f"c{i + 1}")
        cast.append(dict(id=cid, role=c.get("role") if c.get("role") in ("protagonist", "partner", "extra") else "extra", archetype=c.get("archetype"), gender=c.get("gender"), name=c.get("name", ""),
                         description=c.get("description", ""), asset_id=c.get("asset_id"), status="MISSING"))
    roles = [c["role"] for c in cast]
    if roles.count("protagonist") != 1:
        errs.append(f"the cast needs exactly one protagonist (found {roles.count('protagonist')})")
    if roles.count("partner") > 1 or roles.count("extra") > 2:
        errs.append("the renderer supports one protagonist, at most one partner and at most two extras")
    by = {}
    for v in raw["visuals"]:
        by.setdefault(v.get("narration_id"), []).append(v)
    unknown = [k for k in by if k not in seg]
    if unknown:
        errs.append(f"unknown narration ids {unknown}; use only {order[0]}..{order[-1]}")
    for k in order:
        if k not in by:
            errs.append(f"narration segment {k} has no visual: every segment must be shown")
    last = -1
    for v in raw["visuals"]:
        if v.get("narration_id") in seg:
            i = order.index(v["narration_id"])
            if i < last:
                errs.append("visuals must follow the narration order")
                break
            last = i
    if errs:
        raise PlanError(errs)
    visuals, vid = [], 0
    for k, sid in enumerate(order):
        s = seg[sid]
        vs = by[sid]
        sh = [max(0.05, float(v.get("share") or 1.0)) for v in vs]
        tot = sum(sh)
        words = s.get("words") or []
        tokens = s["text"].split()
        t0, cum = s["start"], 0.0
        starts = []
        for j, v in enumerate(vs):
            if j == 0:
                starts.append(0.0 if k == 0 else s["start"])
            else:
                aw = v.get("at_word")
                t = words[aw]["start"] if (isinstance(aw, int) and words and 0 <= aw < len(words)) else t0 + (s["end"] - s["start"]) * (cum / tot)
                starts.append(max(t, starts[-1] + 0.05))
            cum += sh[j]
        for j, v in enumerate(vs):
            vid += 1
            e = dict(v.get("environment") or {})
            e = dict(type=e.get("type") if e.get("type") in ("generic", "real_landmark") else "generic", subject=str(e.get("subject") or "").strip(), asset_id=e.get("asset_id") or None, time_of_day=e.get("time_of_day") if e.get("time_of_day") in ("day", "dusk", "night") else "day",
                     tags=e.get("tags") or [], status="MISSING", reference_queries=[q for q in (e.get("reference_queries") or []) if isinstance(q, str)])
            if not e["subject"]:
                errs.append(f"visual {vid} (narration {sid}): environment.subject is empty")
            a = v.get("action") or {}
            frac0, frac1 = (starts[j] - (0 if k == 0 else s["start"])) / max(s["end"] - (0 if k == 0 else s["start"]), 1e-6), None
            cam = dict(v.get("camera") or {})
            visuals.append(dict(id=f"V{vid:02d}", narration_id=sid, start=round(starts[j], 3), end=0.0, visual_intent=v.get("visual_intent") if v.get("visual_intent") in schemas.INTENTS else "SHOW_ACTION", environment=e,
                                characters=[c for c in (v.get("characters") or []) if isinstance(c, str)], props=[dict(name=str(p.get("name")).strip(), asset_id=None, status="MISSING") for p in (v.get("props") or []) if isinstance(p, dict) and p.get("name")],
                                action=dict(capability=a.get("capability"), actor=a.get("actor"), requested=a.get("requested"), params=a.get("params") or {}) if a else None, emotion=v.get("emotion") or "neutral",
                                camera=dict(shot=cam.get("shot", ""), movement=cam.get("movement", ""), subject=cam.get("subject") or None, requested=cam.get("requested")), effects=[x for x in (v.get("effects") or []) if isinstance(x, str)],
                                transition=v.get("transition") or "cut", screen=v.get("screen") if isinstance(v.get("screen"), dict) else None, rationale=str(v.get("rationale") or "")[:300]))
        # caption text per visual (proportional to time, or by word times)
        if len(vs) == 1:
            visuals[-1]["narration_text"] = s["text"]
        else:
            idx = [len(visuals) - len(vs) + j for j in range(len(vs))]
            bounds = [starts[j] for j in range(len(vs))] + [s["end"]]
            n = len(tokens)
            cuts = [0]
            for j in range(1, len(vs)):
                frac = (bounds[j] - s["start"]) / max(s["end"] - s["start"], 1e-6)
                cuts.append(min(n - 1, max(cuts[-1] + 1, int(round(frac * n))))) if n > 1 else cuts.append(0)
            cuts.append(n)
            for j, i in enumerate(idx):
                visuals[i]["narration_text"] = " ".join(tokens[cuts[j]:cuts[j + 1]]) or s["text"]
    corrections = []
    for v in visuals:                                                                        # facts shown on screen must come from the narration: an amount the narration never says is replaced by the last amount it did say
        act = v.get("action") or {}
        if act.get("capability") == "VISUALIZE_FLOW":
            said = [n for s_ in timeline["narration"][:order.index(v["narration_id"]) + 1] for n in hindi.numbers_in(s_["text"])]
            try:
                amt = int(act["params"].get("amount"))
            except (TypeError, ValueError, KeyError):
                amt = None
            if said and amt not in said:
                new = said[-1]
                corrections.append(dict(visual=v["id"], field="action.params.amount", was=amt, now=new, why="the narration never says that amount; it says " + ", ".join(f"{x:,}" for x in dict.fromkeys(said))))
                act["params"] = dict(act.get("params") or {}, amount=new)
    for i, v in enumerate(visuals):
        v["end"] = round(visuals[i + 1]["start"] if i + 1 < len(visuals) else timeline["duration"], 3)
    for v in visuals:
        d = v["end"] - v["start"]
        if d < MIN_VISUAL:
            errs.append(f"{v['id']} (narration {v['narration_id']}) lasts {d:.1f} s; the renderer's minimum is {MIN_VISUAL} s: use fewer visuals for this short segment")
        if d > MAX_VISUAL:
            errs.append(f"{v['id']} (narration {v['narration_id']}) lasts {d:.1f} s; the maximum is {MAX_VISUAL} s: split this segment into 2-3 visuals with different framing")
    if fmt == "short" and visuals and visuals[0]["end"] - visuals[0]["start"] > HOOK_MAX:
        errs.append(f"the first visual lasts {visuals[0]['end'] - visuals[0]['start']:.1f} s; a hook must not exceed {HOOK_MAX} s")
    if errs:
        raise PlanError(errs)
    plan = dict(schema=f"kathaya.visual_scene_plan/{schemas.VERSION}", format=fmt, title=str(raw.get("title") or ""), cast=cast, visuals=visuals)
    if corrections:
        plan["corrections"] = corrections
    bad = schemas.validate("VisualScenePlan", plan)
    if bad:
        raise PlanError([f"{b['path']}: {b['message']}" for b in bad[:6]])
    return plan


def rhythm_errors(plan):
    """renderer-side editing rules the plan must already satisfy (the same rules QC measures on the film)"""
    errs, prev = [], None
    for v in plan["visuals"]:
        key = (v["camera"].get("subject") or v["camera"].get("shot_engine"), v["camera"].get("shot_engine"))
        if prev and key == prev and v["environment"].get("asset_id") == plan["visuals"][plan["visuals"].index(v) - 1]["environment"].get("asset_id"):
            errs.append(f"{v['id']} repeats the framing of the previous visual: change the shot size or the subject")
        prev = key
    sizes = {v["camera"].get("shot_engine") for v in plan["visuals"]}
    if len(plan["visuals"]) >= 8 and len(sizes) < 4:
        errs.append(f"the film uses only {len(sizes)} shot sizes; use at least 4 different ones")
    return errs


def plan_hash(plan):
    return hashlib.sha1(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def design(timeline, manifest, catalog, provider, fmt="short", rounds=3, log=print, progress=None):
    """-> dict(plan, report, attempts). `provider(prompt, schema) -> raw JSON`."""
    from kathaya.assets import catalog as CAT
    from kathaya.renderer import manifest as MF
    if getattr(provider, "sequential", False):
        from kathaya.director import sequential
        raw = sequential.design(timeline, manifest, catalog, provider, fmt, log, progress)
        try:
            plan = finalize(raw, timeline, fmt)
        except PlanError as pe:
            return dict(plan=None, report=None, attempts=[dict(round=0, status="rejected", errors=pe.errors)], plan_hash=None, unresolved=pe.errors, raw=raw)
        plan, report = RES.resolve(plan, manifest, catalog)
        errs = rhythm_errors(plan)
        return dict(plan=plan, report=report, attempts=[dict(round=0, status="ok" if not errs else "notes", errors=errs)], plan_hash=plan_hash(plan), unresolved=errs, raw=raw)
    mc, cc = MF.compact(manifest), CAT.compact(catalog)
    schema = PR.output_schema(mc, cc)
    attempts, repair = [], None
    plan = report = None
    for r in range(rounds + 1):
        prompt = PR.build(timeline, mc, cc, fmt, repair)
        try:
            raw = provider(prompt, schema)
        except Exception as e:                                                                    # noqa: BLE001 - provider failures are reported, never hidden
            attempts.append(dict(round=r, status="provider_error", error=f"{type(e).__name__}: {e}"))
            raise
        try:
            plan = finalize(raw, timeline, fmt)
            plan, report = RES.resolve(plan, manifest, catalog)
            errs = rhythm_errors(plan)
            structural = [e["message"] for e in report["capability_errors"] if not (e["code"] == "UNSUPPORTED_CAPABILITY" and (e["value"] == "OTHER")) and not (e["code"] in ("UNSUPPORTED_CAMERA_SHOT", "UNSUPPORTED_CAMERA_MOVEMENT") and e["value"] == "OTHER")]
            errs += structural
        except PlanError as pe:
            errs = pe.errors
            plan = report = None
        attempts.append(dict(round=r, status="ok" if not errs else "rejected", errors=errs[:14]))
        log(f"[director] round {r}: {'accepted' if not errs else str(len(errs)) + ' problem(s)'}")
        if not errs:
            return dict(plan=plan, report=report, attempts=attempts, plan_hash=plan_hash(plan))
        repair = errs
    if plan is None:
        raise PlanError(repair)
    return dict(plan=plan, report=report, attempts=attempts, plan_hash=plan_hash(plan), unresolved=repair)
