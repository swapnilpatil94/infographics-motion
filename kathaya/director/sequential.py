"""SEQUENTIAL CREATIVE DIRECTOR (used with a local LLM). The plan is written one visual at a time. The LLM makes every creative decision (what to show, where, with whom, which action, which camera); the SYSTEM only narrows
each step's menu to what the renderer can legally do next: the renderer's action state (an action needs what earlier actions set), unused `once` actions, a valid framing that differs from the previous shot, and a partner only if
the cast has one. "OTHER" is always allowed: a needed action / camera move the renderer does not have is reported as a capability error instead of being replaced.

The number of visuals per narration segment follows the narration (long sentence -> more visuals; the renderer's shot-length limits), never a fixed count or duration."""
import json
import math

from engine.skeleton import acts as AC
from kathaya import schemas
from kathaya.director import prompt as PR
from kathaya.director import visual_planner as VP

TWO_PERSON = {"MEET", "PERSON_ENTERS", "CONVERSE", "EYE_CONTACT", "OTHER_LOOKS_AT_PHONE", "HAND_OVER", "GIVE_OBJECT", "RECEIVE_OBJECT", "OTHER_REACTS", "BOTH_REALIZE"}
PARTNER_SUBJECTS = {"partner_head", "two_shot"}
HEAD = """You are the creative director of Kathaya, a deterministic 2D story renderer. You design the film for a narration, one visual at a time. The narration is the source of truth: show what is being narrated, when it is narrated.
The story requirement always wins: never pick an environment, person, prop or action because it is available; pick it because the narration needs it. If the catalog has no such environment / character / prop, set asset_id to null and
describe the real subject exactly (a real place is type "real_landmark" with its full name); give 2-3 reference_queries. If none of the offered actions can show what the narration needs, choose "OTHER" and describe it in
action.requested. Do not invent people or events that are not in the narration."""


def _schema_cast(archetypes):
    return {"type": "object", "required": ["title", "cast"], "properties": {"title": {"type": "string"}, "cast": {"type": "array", "items": {"type": "object", "required": ["id", "role", "archetype", "gender", "description"], "properties": {
        "id": {"type": "string"}, "role": {"enum": ["protagonist", "partner", "extra"]}, "archetype": {"enum": archetypes + ["OTHER"]}, "gender": {"enum": ["male", "female", "either"]}, "name": {"type": "string"}, "description": {"type": "string"}}}}}}


def _schema_visual(legal, framings, movements, emotions, effects, continues, transitions):
    return {"type": "object", "required": ["visual_intent", "environment", "characters", "action", "emotion", "camera", "continues", "moved"], "properties": {
        "visual_intent": {"enum": schemas.INTENTS},
        "environment": {"type": "object", "required": ["type", "subject", "time_of_day"], "properties": {"type": {"enum": ["generic", "real_landmark"]}, "subject": {"type": "string"}, "asset_id": {"type": ["string", "null"]},
                                                                                                         "time_of_day": {"enum": ["day", "dusk", "night"]}, "reference_queries": {"type": "array", "items": {"type": "string"}}}},
        "characters": {"type": "array", "items": {"type": "string"}}, "props": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}},
        "action": {"type": "object", "required": ["capability"], "properties": {"capability": {"enum": legal + ["OTHER"]}, "actor": {"type": ["string", "null"]}, "requested": {"type": "string"}, "params": {"type": "object"}}},
        "emotion": {"enum": emotions}, "camera": {"type": "object", "required": ["framing", "movement"], "properties": {"framing": {"enum": framings + ["OTHER"]}, "movement": {"enum": movements + ["OTHER"]}, "requested": {"type": "string"}}},
        "effects": {"type": "array", "items": {"enum": effects}}, "transition": {"enum": transitions}, "moved": {"type": "boolean"}, "screen": {"type": ["object", "null"], "properties": {"sender": {"type": "string"}, "text": {"type": "string"}}}, "rationale": {"type": "string"},
        "continues": {"enum": continues}}}


def legal_actions(have, seen, first, last, has_partner):
    out = []
    for a, d in AC.ACTS.items():
        if first and a not in AC.FIRSTS:
            continue
        if not first and a in AC.FIRSTS and a == "ESTABLISH":
            continue
        if last != (a == AC.LAST):
            continue
        if d.get("once") and a in seen:
            continue
        if any(n not in have for n in d["needs"]):
            continue
        if a in TWO_PERSON and not has_partner:
            continue
        out.append(a)
    return out


def _advance(have, seen, a):
    d = AC.ACTS[a]
    have |= set(d["sets"])
    have -= set(d.get("clears", []))
    seen.append(a)


def design(timeline, manifest, catalog, llm, fmt="short", log=print, progress=None):
    from kathaya.assets import catalog as CAT
    from kathaya.assets import resolver as RES
    from kathaya.renderer import manifest as MF
    mc, cc = MF.compact(manifest), CAT.compact(catalog)
    nar = [dict(id=s["id"], start=s["start"], end=s["end"], duration=round(s["end"] - s["start"], 2), text=s["text"]) for s in timeline["narration"]]
    fmt_note = ("SHORTS 9:16: a hook, quick reactions, one clear climax, a closing beat." if fmt == "short" else "LONG-FORM: more room for establishing shots and slower pacing.")
    # ---- step 0: the cast
    prompt = f"{HEAD}\n\nFORMAT: {fmt_note}\n\nSTEP 1 of the design: decide the CAST and a short Hindi title for the whole narration.\nRules: exactly one protagonist; at most one partner and at most two extras. Count ONLY people who are seen on screen doing something in the narration ('वह', 'उसने', 'लड़का' = the protagonist). A person who only sends a message, is only mentioned, or is never seen (a scammer, an unknown caller) is NOT in the cast; a narration with one person has a cast of exactly one. " \
             f"Choose each `archetype` from the catalog archetypes; if nobody fits, use OTHER and describe the person in `description`.\n\nNARRATION (JSON)\n{json.dumps(nar, ensure_ascii=False)}\n\nCATALOG ARCHETYPES: {json.dumps(mc['archetypes'])}"
    c0 = llm(prompt, _schema_cast(mc["archetypes"]))
    cast = [dict(id=str(c["id"]), role=c["role"], archetype=None if c["archetype"] == "OTHER" else c["archetype"], gender=c.get("gender"), name=c.get("name", ""), description=c.get("description", "")) for c in c0["cast"]]
    for c in cast:
        c["asset_id"] = ("char_" + c["archetype"].replace(" ", "_").replace("-", "_")) if c["archetype"] else None
    if sum(1 for c in cast if c["role"] == "protagonist") != 1:
        cast = [dict(c, role="protagonist" if i == 0 else ("extra" if c["role"] == "protagonist" else c["role"])) for i, c in enumerate(cast)]
    cast = cast[:4]
    has_partner = any(c["role"] == "partner" for c in cast)
    log(f"[director] cast: {[(c['id'], c['role'], c['archetype']) for c in cast]}  title: {c0['title']}")
    # ---- step 2..: the visuals
    have, seen, visuals, prev_framing = set(), [], [], None
    framings_all = [f"{f['subject']}/{f['shot']}" for f in mc["valid_framings"] if f["subject"] != "protagonist_at_atm"]      # (the ATM framing is the same reach framing under another name)
    proven = sorted({m for f in mc["valid_framings"] for m in f["movements"]})                                         # camera moves the renderer has proven inside a framing (dolly_through is a lab move)
    n_seg = len(nar)
    for k, s in enumerate(nar):
        dur = s["duration"] + (0.0 if k else s["start"])
        last_seg = k == n_seg - 1
        n_min = max(1, math.ceil(dur / VP.MAX_VISUAL + 1e-9))
        n_max = 3 if dur >= 5.4 else (2 if dur >= 2 * VP.MIN_VISUAL + 1.3 else 1)
        n_max = max(n_min, n_max)
        if last_seg:
            n_max = n_min = 2 if dur > VP.MAX_VISUAL else 1
        for j in range(n_max):
            is_last_visual = last_seg and j == n_max - 1
            legal = legal_actions(have, seen, first=(not visuals), last=is_last_visual, has_partner=has_partner)
            recent_acts = [v["action"]["capability"] for v in visuals[-2:]]
            fresh = [a for a in legal if a not in recent_acts]
            legal = fresh if len(fresh) >= 2 else legal                                     # variety: an action used in the last two visuals is not offered again while there are alternatives
            framings = [f for f in framings_all if f != prev_framing and (has_partner or f.split("/")[0] not in PARTNER_SUBJECTS)]
            recent_sizes = {v["_framing"].split("/")[-1] for v in visuals[-2:] if "/" in v["_framing"]}
            freshf = [f for f in framings if f.split("/")[-1] not in recent_sizes]
            framings = freshf if len(freshf) >= 3 else framings                              # variety of shot sizes
            recent_mv = [v["camera"]["movement"] for v in visuals[-2:]]
            moves = [m for m in proven if m not in recent_mv[-1:]] or proven
            cont = [True] if j + 1 < n_min else ([False] if j + 1 >= n_max else [False, True])
            sofar = [dict(narration=v["narration_id"], action=v["action"]["capability"], environment=v["environment"].get("asset_id") or v["environment"]["subject"], framing=v["_framing"]) for v in visuals[-6:]]
            prompt = (f"{HEAD}\n\nFORMAT: {fmt_note}\n\nSTEP 3: design ONE visual for narration segment {s['id']} (visual {j + 1} of this segment; the segment lasts {s['duration']} s"
                      + (", so it needs more than one visual" if n_min > 1 else "") + ").\n\nFULL NARRATION (JSON, for context)\n" + json.dumps(nar, ensure_ascii=False) +
                      f"\n\nCAST: {json.dumps(cast, ensure_ascii=False)}\nVISUALS SO FAR (last few): {json.dumps(sofar, ensure_ascii=False)}\n\nTHIS SEGMENT: {json.dumps(s, ensure_ascii=False)}\n\n"
                      f"CATALOG ENVIRONMENTS: {json.dumps(cc['environments'], ensure_ascii=False)}\nCATALOG PROPS: {json.dumps([p['name'] for p in cc['props']])}\n\n"
                      f"ACTIONS YOU MAY CHOOSE NOW (the renderer's state allows only these{', and this visual closes the film' if is_last_visual else ''}): {json.dumps([dict(id=a, does=AC.ACTS[a]['doc']) for a in legal], ensure_ascii=False)}\n"
                      f"CAMERA framings you may choose (subject/shot; different from the previous shot): {json.dumps(framings)}\nCAMERA movements: {json.dumps(mc['movements'], ensure_ascii=False)} (tilt / orbit are not available: use OTHER + camera.requested if you need them)\n"
                      f"EMOTIONS: {json.dumps(mc['emotions'])}\nEFFECTS (optional): {json.dumps(mc['effects'], ensure_ascii=False)}\n\n"
                      "Fill the visual: the environment of THIS moment of the story (asset_id from CATALOG ENVIRONMENTS only if it really is that place; the time_of_day the story implies), the cast ids on screen in `characters`, the props shown (use catalog prop names), "
                      "the action, the emotion, the camera. A full-screen phone message uses action INSERT_SCREEN with screen {sender (generic fictional id), text (the exact words from the narration)}; money moving uses VISUALIZE_FLOW with "
                      "action.params {amount (integer rupees), from_label (Hindi), to (list)}. Use INSERT_SCREEN only for the moment the message / screen text itself is shown, VISUALIZE_FLOW when money moves, PHONE_CALL for a call, REALIZE for the moment of understanding; "
                      "match each action to what THIS narration segment says. Camera: build tension with a slow push, react in close-ups, reveal with reveal / truck, end wide; vary the movement. `moved` is true ONLY if this visual is in a different place or at a different time than the previous visual; otherwise false (the environment and time of day then stay exactly as in the previous visual). `transition` is cut unless the film starts (fade) or the story jumps in time / place (dip). `continues` = whether this SAME narration segment needs another visual after this one.")
            v = llm(prompt, _schema_visual(legal, framings, moves, mc["emotions"], sorted(mc["effects"]), cont, mc["transitions"]))
            cap = v["action"]["capability"]
            if cap != "OTHER":
                _advance(have, seen, cap)
            fr = v["camera"]["framing"]
            v["camera"] = dict(shot=(fr.split("/")[1] if "/" in fr else "OTHER"), subject=(fr.split("/")[0] if "/" in fr else None), movement=v["camera"]["movement"], requested=v["camera"].get("requested"))
            if visuals and not v.get("moved"):                                             # the director said the story does not move: same place, same time as before
                prev_e = visuals[-1]["environment"]
                if v["environment"].get("time_of_day") != prev_e.get("time_of_day") or (v["environment"].get("asset_id") or v["environment"]["subject"]) != (prev_e.get("asset_id") or prev_e["subject"]):
                    log(f"[director] {s['id']}.{j + 1}: environment/time kept as before (moved=false)")
                v["environment"] = dict(prev_e)
            v["narration_id"], v["_framing"] = s["id"], fr
            prev_framing = fr if fr != "OTHER" else prev_framing
            visuals.append(v)
            log(f"[director] {s['id']}.{j + 1}: {cap} | {fr} {v['camera']['movement']} | env {v['environment'].get('asset_id') or v['environment']['subject']}")
            if progress:
                progress(k, n_seg, f"{s['id']}: {cap}, {fr} {v['camera']['movement']}", len(visuals))
            if not v.get("continues") or j + 1 >= n_max:
                break
    used = {c for v in visuals for c in (v.get("characters") or [])} | {(v.get("action") or {}).get("actor") for v in visuals}
    cast = [c for c in cast if c["role"] == "protagonist" or c["id"] in used]                     # a cast member that appears in no visual is dropped (no ghost characters)
    for v in visuals:
        v.pop("_framing", None)
        v.pop("continues", None)
        v.pop("moved", None)
    return dict(title=c0["title"], cast=cast, visuals=visuals)
