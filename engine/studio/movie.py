"""MOVIE: what the Final-Movie screen and the Movie Inspector need from a finished production - the shot table, per-shot QC state, and SAFE shot-level edits.

Edits never touch the renderer or bypass validation: every edit goes into the production's story graph (camera nudges as `fixes[beat].camera`, character looks as `dna_patch`, story changes through the existing
graph constructor), the plan is REBUILT by the same director (`production.plan_for`), validated (act grammar, DNA schema, contiguous shots, measured framing) and compared with the rendered plan through the
frame cache's content addresses - so the UI can say, before rendering, exactly which frames a change re-renders.
"""
import copy
import json
import os
import re
import time

from engine.shorts.raster import ROOT
from engine.skeleton import acts as AC, audio_director as AUD, critic as CR, director_opts as DO, dna2, events as EVT, narration_io as NI, production as PR, short, topic_build as TB
from engine.studio import core as C, jobs as J

SIZES = sorted(short.SIZES)
CAM_LIMITS = dict(dx=500.0, dy=500.0, zoom_mul=(0.6, 1.6))
SHOT = re.compile(r"^S\d+$")
NOISE = {"face", "gaze", "blink", "idle", "breathe", "look"}


def _load(pid, name):
    return json.load(open(os.path.join(J.pdir(pid), name), encoding="utf-8"))


def _has(pid, name):
    return os.path.exists(os.path.join(J.pdir(pid), name))


def flag_shots(qc):
    """shot id -> the QC evidence that names it (empty for a clean film)"""
    ev = (qc or {}).get("evidence", {})
    out = {}

    def add(x, why):
        sid = x.get("shot") if isinstance(x, dict) else x
        if isinstance(sid, str) and SHOT.match(sid):
            out.setdefault(sid, []).append(why)
    for k in ("clipped", "under_caption", "too_small"):
        for x in (ev.get("framing") or {}).get(k, []):
            add(x, f"framing: {k.replace('_', ' ')}")
    for k, why in (("duplicate_shots", "duplicate consecutive shot"), ("static_shots", "static shot"), ("missing_frames", "missing rendered frame"), ("rhythm_findings", "editing rhythm"), ("caption_face_overlap_samples", "caption over a face")):
        for x in ev.get(k) or []:
            add(x, why)
    for x in ((ev.get("ik") or {}).get("unreachable_events") or []):
        add(x, "IK target unreachable")
    for x in ((ev.get("contact") or {}).get("bad") or []):
        add(x, "hand-object contact")
    return out


def shots_view(plan, graph, qc):
    beats = {b["id"]: b for b in graph["beats"]}
    segs = {s["id"]: s for s in plan["narration"]["segments"]}
    flagged = flag_shots(qc)
    foley = AUD.foley_events(plan, None)
    sfx = [(e["t"], e["kind"]) for e in plan.get("sfx") or []]
    out = []
    for i, sh in enumerate(plan["shots"]):
        b = beats.get(sh.get("key") or (sh["beats"][0] if sh.get("beats") else None)) or {}
        scene = next((s for s in plan["scenes"] if s["t0"] - 1e-6 <= sh["t0"] < s["t1"] - 1e-6), plan["scenes"][-1])
        cast = [dict(id=c, role=plan["characters"][c]["role"], archetype=plan["characters"][c]["dna"].get("archetype", plan["characters"][c]["dna"].get("role")), hair=plan["characters"][c]["dna"]["hair"]["style"],
                     skin=plan["characters"][c]["dna"]["skin"]["id"], palette=plan["characters"][c]["dna"]["wardrobe"]["palette"], top=plan["characters"][c]["dna"]["wardrobe"]["top"]) for c in scene["cast"] if c in plan["characters"]]
        acts = []
        for a in sh.get("actions", []):
            if sh["t0"] - 0.05 <= a["t"] < sh["t1"] and a["action"] not in NOISE:
                acts.append(dict(char=a["char"], action=a["action"], t=round(a["t"], 2), detail=a.get("target") or a.get("prop") or a.get("name") or a.get("pose") or ""))
        ae = sorted({(round(t, 2), k) for t, k, _g in foley if sh["t0"] <= t < sh["t1"]} | {(round(t, 2), k) for t, k in sfx if sh["t0"] <= t < sh["t1"]})
        fl = flagged.get(sh["id"], [])
        out.append(dict(id=sh["id"], index=i + 1, t0=round(sh["t0"], 2), t1=round(sh["t1"], 2), duration=round(sh["t1"] - sh["t0"], 2), treatment=sh["treatment"], act=sh.get("act"), purpose=sh.get("purpose"), beats=sh.get("beats", []),
                        text=" ".join(segs[x]["text"] for x in sh.get("segs", []) if x in segs), emotion=b.get("emotion"), location=dict(loc=scene["loc"], time=scene["time"]), characters=cast, actions=acts[:14],
                        camera=sh.get("camera"), lighting=dict(mood=(sh.get("lighting") or {}).get("mood"), time=(sh.get("lighting") or {}).get("time")), audio_mood=sh.get("audio_mood"), audio_events=[dict(t=t, kind=k) for t, k in ae][:24],
                        transition_in=sh.get("transition_in"), qc=dict(state="flagged" if fl else "ok", flags=fl), fixes=sh.get("fixes")))
    return out


def plan_view(pid):
    plan, graph = _load(pid, "plan.json"), _load(pid, "story_graph.json")
    qc = _load(pid, "qc_report.json") if _has(pid, "qc_report.json") else {}
    return dict(plan=dict(title=plan["title"], duration=plan["duration"], fps=plan["fps"], scenes=plan["scenes"], acts=plan["acts"], director=plan.get("director"), captions=plan.get("captions", True)), shots=shots_view(plan, graph, qc),
                graph=dict(beats=graph["beats"], cast=graph["cast"], scenes=graph["scenes"], fixes=list((graph.get("fixes") or {}).keys()), dna_patch=graph.get("dna_patch"), director=graph.get("director")),
                qc=dict(passed=qc.get("passed"), n_checks=qc.get("n_checks"), flagged={k: v for k, v in flag_shots(qc).items()}), raw_plan_url=f"/api/production/{pid}/plan?raw=1",
                options=dict(sizes=SIZES, moves=sorted(DO.KNOWN_MOVES), limits=CAM_LIMITS, palettes=list(dna2.PALETTES), tops=list(dna2.TOPS), skins=list(C.D1.SKIN), emotions=C.options()["emotions"], acts=C.options()["acts"]))


# ------------------------------------------------------------------------------------------------ edits
def validate_plan(plan):
    errs = []
    prev = 0.0
    for s in plan["shots"]:
        if abs(s["t0"] - prev) > 0.01 or s["t1"] <= s["t0"]:
            errs.append(f"{s['id']}: non-contiguous or empty")
        prev = s["t1"]
        c = s.get("camera")
        if s["treatment"] == "skeleton" and not c:
            errs.append(f"{s['id']}: skeleton shot without a camera")
        if c and (c.get("size") not in short.SIZES or c.get("move") not in DO.KNOWN_MOVES):
            errs.append(f"{s['id']}: unknown camera size/move {c.get('size')}/{c.get('move')}")
    errs += AC.validate(plan.get("acts") or [])
    for cid in plan["cast_in_short"]:
        errs += [f"{cid}: {e}" for e in dna2.validate(plan["characters"][cid]["dna"])]
    return errs


def frame_keys(plan, samples=10):
    TB.bake_cast(plan)
    actors = short.build_actors(plan, log=lambda *a: None)
    cam = short.build_camera(plan, actors)
    n = int(round(plan["duration"] * plan["fps"]))
    chars = [dict(id=cid, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=a.facing, origin=list(a.origin), channels=a.job_channels()) for cid, a in actors.items()]
    camj = dict(cx=[round(float(x), 3) for x in cam["cx"]], cy=[round(float(x), 3) for x in cam["cy"]], zoom=[round(float(short.view_zoom(cam["zoom"][i], cam["gain"][i])), 4) for i in range(n)])
    fr = sorted({f for sh in plan["shots"] if sh["treatment"] == "skeleton" for f in range(int(round(sh["t0"] * plan["fps"])), min(n, int(round(sh["t1"] * plan["fps"])) + 1)) if f < n})
    return short._frame_keys(plan, chars, camj, fr, samples), fr, actors, cam


def impact(old_plan, new_plan):
    """which frames a change re-renders (content addresses: old vs new), how many of those are already in the frame cache, which shots they belong to"""
    k0, fr0, _, _ = frame_keys(old_plan)
    k1, fr1, actors, cam = frame_keys(new_plan)
    cache = os.path.join(ROOT, "output/cache/actor_frames")
    changed = [f for f in fr1 if k0.get(f) != k1[f]]
    todo = [f for f in changed if not os.path.exists(os.path.join(cache, k1[f] + ".png"))]
    fps = new_plan["fps"]
    shots = sorted({new_plan["shots"][EVT.shot_index(new_plan, f)]["id"] for f in changed})
    a0, a1 = AUD._hash(old_plan, [], None), AUD._hash(new_plan, [], None)
    n = int(round(new_plan["duration"] * fps))
    return dict(frames_total=len(fr1), frames_changed=len(changed), frames_to_render=len(todo), frames_reused=len(fr1) - len(todo), shots_affected=shots, audio_remixed=a0 != a1,
                composite_frames=n, note="Blender re-renders only the changed frames; compositing + encoding always re-runs over the whole film (about 0.23 s per frame)"), actors, cam


def _merge_camera(graph, beat, **kw):
    fx = graph.setdefault("fixes", {}).setdefault(beat, {})
    cam = dict(fx.get("camera") or {})
    for k, v in kw.items():
        if v is not None:
            cam[k] = v
    fx["camera"] = cam


def _op(graph, plan, op):
    kind = op.get("op")
    if kind == "camera":
        sh = next((s for s in plan["shots"] if s["id"] == op.get("shot")), None)
        if not sh or not sh.get("camera"):
            raise C.StudioError("invalid_edit", f"shot '{op.get('shot')}' has no camera to edit (procedural insert shot)")
        beat = sh.get("key") or sh["beats"][0]
        kw = {}
        if op.get("size") is not None:
            if op["size"] not in short.SIZES:
                raise C.StudioError("invalid_edit", f"camera size must be one of {SIZES}")
            kw["size"] = op["size"]
        if op.get("move") is not None:
            if op["move"] not in DO.KNOWN_MOVES:
                raise C.StudioError("invalid_edit", f"camera move must be one of {sorted(DO.KNOWN_MOVES)}")
            kw["move"] = op["move"]
        for k in ("dx", "dy"):
            if op.get(k) is not None:
                v = float(op[k])
                if abs(v) > CAM_LIMITS[k]:
                    raise C.StudioError("invalid_edit", f"camera {k} must be within +-{CAM_LIMITS[k]:.0f}")
                kw[k] = v
        if op.get("zoom_mul") is not None:
            v = float(op["zoom_mul"])
            if not CAM_LIMITS["zoom_mul"][0] <= v <= CAM_LIMITS["zoom_mul"][1]:
                raise C.StudioError("invalid_edit", f"zoom must be within {CAM_LIMITS['zoom_mul']}")
            kw["zoom_mul"] = v
        _merge_camera(graph, beat, **kw)
        return graph
    if kind == "beat":
        ch = {k: op[k] for k in ("act", "emotion", "loc", "time") if op.get(k)}
        if not ch:
            raise C.StudioError("invalid_edit", "nothing to change")
        g = C.edit_beats(graph, {op["beat"]: ch})
        return g
    if kind == "character":
        cid = op.get("char")
        if cid not in plan["characters"]:
            raise C.StudioError("invalid_edit", f"unknown character '{cid}'")
        patch = dict(graph.get("dna_patch", {}).get(cid, {}))
        if op.get("skin"):
            if op["skin"] not in C.D1.SKIN:
                raise C.StudioError("invalid_edit", f"skin must be one of {list(C.D1.SKIN)}")
            patch["skin"] = dict(id=op["skin"], hex=C.D1.SKIN[op["skin"]])
        w = dict(patch.get("wardrobe", {}))
        if op.get("palette"):
            if op["palette"] not in dna2.PALETTES:
                raise C.StudioError("invalid_edit", f"palette must be one of {list(dna2.PALETTES)}")
            top, bottom, shoes, accent = dna2.PALETTES[op["palette"]]
            w.update(palette=op["palette"], top_color=top, bottom_color=bottom, shoe_color=shoes, accent=accent)
        if op.get("top"):
            w["top"] = op["top"]
        if w:
            patch["wardrobe"] = w
        try:
            DO.patch_dna(copy.deepcopy(plan), cid, patch)                                     # validated against the DNA schema now, not at render time
        except ValueError as e:
            raise C.StudioError("invalid_edit", str(e))
        graph.setdefault("dna_patch", {})[cid] = patch
        return graph
    if kind == "director":
        d = dict(graph.get("director") or {})
        for k in ("pacing", "camera", "captions", "audio"):
            if k in op:
                d[k] = op[k]
        try:
            graph["director"] = DO.normalize(d)
        except DO.OptionsInvalid as e:
            raise C.StudioError("invalid_edit", str(e))
        if not graph["director"]:
            graph.pop("director")
        return graph
    raise C.StudioError("invalid_edit", f"unknown edit '{kind}'", hint="camera | beat | character | director | reset")


def edit_state(pid):
    if _has(pid, "edits/working.json"):
        return _load(pid, "edits/working.json")
    return None


def apply_ops(pid, ops, log=print):
    d = J.pdir(pid)
    if not _has(pid, "plan.json") or not _has(pid, "story_graph.json"):
        raise C.StudioError("not_ready", "this production has no finished plan to edit yet", status=409)
    base_plan = _load(pid, "plan.json")
    nar = NI.load(_load(pid, "inputs.json")["narration"])
    ed = edit_state(pid)
    if any(o.get("op") == "reset" for o in ops):
        for f in ("working.json", "working_plan.json"):
            p = os.path.join(d, "edits", f)
            if os.path.exists(p):
                os.remove(p)
        return dict(reset=True, ops=[], impact=None, warnings=[])
    graph = ed["graph"] if ed else _load(pid, "story_graph.json")
    cur_plan = _load(pid, "edits/working_plan.json") if ed else base_plan
    for op in ops:
        graph = _op(graph, cur_plan, op)
        try:
            cur_plan = PR.plan_for(graph, nar, 11, graph.get("fixes"))
        except (ValueError, KeyError) as e:
            raise C.StudioError("invalid_edit", f"the director cannot stage this edit: {e}")
    errs = validate_plan(cur_plan)
    if errs:
        raise C.StudioError("invalid_edit", "The edited plan is not valid.", reasons=errs[:6])
    imp, actors, cam = impact(base_plan, cur_plan)
    geo = CR.measure_geometry(cur_plan, actors, cam)
    edited = {op.get("shot") for op in ops if op.get("shot")} | set(imp["shots_affected"])
    warnings = [dict(shot=g["shot"], problems=[p["kind"] for p in g["problems"]]) for g in geo if not g["ok"] and g["shot"] in edited]
    os.makedirs(os.path.join(d, "edits"), exist_ok=True)
    log_ops = (ed or {}).get("ops", []) + list(ops)
    json.dump(dict(graph=graph, ops=log_ops, impact=imp, warnings=warnings), open(os.path.join(d, "edits", "working.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cur_plan, open(os.path.join(d, "edits", "working_plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    view = {s["id"]: s for s in shots_view(cur_plan, graph, {})}
    return dict(ops=log_ops, impact=imp, warnings=warnings, shots={sid: dict(camera=view[sid]["camera"], emotion=view[sid]["emotion"], act=view[sid]["act"]) for sid in imp["shots_affected"] if sid in view})


def rerender_request(pid):
    ed = edit_state(pid)
    if not ed:
        raise C.StudioError("nothing_to_render", "There are no edits to render.", status=409)
    j = _load(pid, "job.json")
    return dict(kind="rerender", mode=j["mode"], draft_id=j.get("draft_id"), settings=j["settings"], lines=j["lines"], notes=j.get("notes") or {}, graph=ed["graph"], narration=_load(pid, "inputs.json")["narration"], seed=11, samples=10,
                critique_rounds=0, tts=j.get("tts") or {}, title=ed["graph"]["title"], created=time.time(), parent=pid)
