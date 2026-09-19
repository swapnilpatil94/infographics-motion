"""VISUAL DSL: schema + validator for the shot plan (spec sec. 6/19/26). LLM output and hand-written plans are UNTRUSTED until they pass here;
invalid plans fail safely with every error listed, before anything reaches the renderer. Enumerations come from the domain pack and the
capability registries (motion grammar, camera grammar, environments, props, GP effects, procedural graphics, UI screens)."""
from engine.animation import grammar as MG
from engine.camera import grammar as CG
from engine.environments import factory as EF
from engine.factory import procedural as PR, ui_screens as UI
from engine.props import factory as PF
from engine.shorts import gp_strokes

TREATMENTS = ("performance", "insert_ui", "procedural")


class DSLError(ValueError):
    def __init__(self, errors):
        super().__init__(f"{len(errors)} plan error(s):\n  - " + "\n  - ".join(errors[:40]))
        self.errors = errors


def _enum(errs, path, val, options):
    if val not in options:
        errs.append(f"{path}={val!r} not one of {sorted(options)[:14]}{'...' if len(options) > 14 else ''}")


def validate_plan(plan, dom=None):
    errs = []
    for k in ("version", "fps", "duration", "shots", "segments"):
        if k not in plan:
            errs.append(f"plan missing '{k}'")
    if errs:
        raise DSLError(errs)
    actions, styles = MG.supported()
    envs = set(EF.available()) | set((dom["environments"] if dom else {}).keys())
    gp = set(gp_strokes.SPRITES)
    seg_ids = {s["id"] for s in plan["segments"]}
    prev_t1, ids = 0.0, set()
    for i, sh in enumerate(plan["shots"]):
        p = f"shots[{i}]({sh.get('id')})"
        for k in ("id", "treatment", "t0", "t1", "phase", "camera", "lighting"):
            if k not in sh:
                errs.append(f"{p} missing '{k}'")
        if sh.get("id") in ids:
            errs.append(f"{p} duplicate id")
        ids.add(sh.get("id"))
        _enum(errs, f"{p}.treatment", sh.get("treatment"), TREATMENTS)
        if not sh.get("t1", 0) > sh.get("t0", 0):
            errs.append(f"{p} t1<=t0")
        if abs(sh.get("t0", 0) - prev_t1) > 1e-3 and i:
            errs.append(f"{p} gap/overlap with previous shot ({prev_t1:.3f} -> {sh.get('t0')})")
        prev_t1 = sh.get("t1", prev_t1)
        for sid in sh.get("segs", []):
            if sid not in seg_ids:
                errs.append(f"{p} references unknown segment {sid}")
        if sh.get("treatment") == "performance":
            env = sh.get("environment", {}).get("family") if isinstance(sh.get("environment"), dict) else sh.get("location")
            _enum(errs, f"{p}.environment", env, envs | set(plan.get("sets", {}).values()) | set(plan.get("sets", {})))
            for j, a in enumerate(sh.get("actions", [])):
                name = a.get("action") or a.get("verb")
                _enum(errs, f"{p}.actions[{j}].action", name, actions)
                if a.get("emotion") is not None:
                    _enum(errs, f"{p}.actions[{j}].emotion", a["emotion"], styles)
                if not 0 <= a.get("intensity", 0.5) <= 1:
                    errs.append(f"{p}.actions[{j}].intensity outside 0..1")
            for j, pr in enumerate(sh.get("props", [])):
                _enum(errs, f"{p}.props[{j}].prop", pr.get("prop"), PF.PROPS)
            if sh.get("crowd") and not 0 < sh["crowd"].get("count", 0) <= 60:
                errs.append(f"{p}.crowd.count must be 1..60")
            if sh.get("camera", {}).get("intent"):
                _enum(errs, f"{p}.camera.intent", sh["camera"]["intent"], CG.INTENTS)
        if sh.get("treatment") == "insert_ui":
            _enum(errs, f"{p}.ui.screen", sh.get("ui", {}).get("screen"), UI.SCREENS)
        if sh.get("treatment") == "procedural":
            _enum(errs, f"{p}.procedural.type", sh.get("procedural", {}).get("type"), PR.RENDERERS)
        for j, g in enumerate(sh.get("gp", [])):
            _enum(errs, f"{p}.gp[{j}].effect", g.get("effect"), gp)
    if plan["shots"] and plan["shots"][-1]["t1"] < plan["duration"] - 0.5:
        errs.append("last shot ends before plan duration")
    if errs:
        raise DSLError(errs)
    return True
