"""ASSET RESOLUTION. For every requirement of a VisualScenePlan:
    AVAILABLE    the asset exists and supports the required conditions
    UNSUPPORTED  the asset exists but cannot satisfy the condition (a generic bank for a real landmark, a bank at night)
    MISSING      no such asset -> an AssetRequest (reference queries, human approval)
Nothing is ever substituted silently. A user-approved substitution is recorded as SUBSTITUTED. Renderer-capability problems (an action, camera move, effect or transition the renderer does not have) are returned as structured
`capability_errors`, not as asset requests."""
import copy

from engine.skeleton import acts as AC
from kathaya.assets import catalog as CAT

INTENT_DEFAULT_ACT = {"ESTABLISH_LOCATION": "ESTABLISH", "INTRODUCE_CHARACTER": "ARRIVE", "EMOTIONAL_REACTION": "REALIZE", "REALIZATION": "REALIZE", "BUILD_TENSION": "SUSPECT", "CLIMAX": "CLOSE_UP", "CONSEQUENCE": "OBSERVE",
                      "REVEAL_INFORMATION": "INSERT_SCREEN", "SHOW_OBJECT": "CLOSE_UP", "SHOW_ACTION": "OBSERVE", "FORESHADOW": "SUSPECT", "CONTRAST": "OBSERVE", "EXPLAIN_PROCESS": "OBSERVE", "MONTAGE": "OBSERVE", "TIME_PASSAGE": "OBSERVE",
                      "MEMORY": "OBSERVE", "TRANSITION": "OBSERVE"}


def _req_id(kind, subject):
    return "REQ_" + kind[:3].upper() + "_" + "".join(c if c.isalnum() else "_" for c in CAT.norm(subject)).strip("_")[:40].upper()


def _queries(kind, subject, asset_kind, given):
    if given:
        return list(dict.fromkeys(given))[:6]
    s = subject.strip()
    if kind == "environment":
        return [f"{s} exterior", f"{s} street view", f"{s} building"] if asset_kind == "real_landmark" else [f"{s} interior India", f"{s} interior", f"{s} photo"]
    if kind == "character":
        return [f"{s} India portrait", f"{s} photo", f"{s} clothing India"]
    return [f"{s} isolated photo", f"{s} close up", f"{s} object"]


def _request(kind, subject, reason, by, status, asset_kind="generic", conditions=None, queries=None):
    return dict(schema="kathaya.asset_request/1", id=_req_id(kind, subject), type=kind, asset_kind=asset_kind, subject=subject, status=status, reason=reason, required_by=sorted(set(by)), required_conditions=conditions or {},
                reference_queries=_queries(kind, subject, asset_kind, queries), reference_count=3, human_approval_required=True, state="open")


def _add(reqs, r):
    cur = reqs.get(r["id"])
    if cur:
        cur["required_by"] = sorted(set(cur["required_by"]) | set(r["required_by"]))
        cur["required_conditions"] = {**cur["required_conditions"], **r["required_conditions"]} if False else cur["required_conditions"]
    else:
        reqs[r["id"]] = r


def _match(cat, kind, subject):
    s = CAT.norm(subject)
    for a in cat["assets"]:
        if a["type"] == kind and a["status"] == "production_ready" and s in a["subjects"]:
            return a
    return None


def resolve(plan, manifest, catalog):
    """-> (plan with statuses / asset ids filled by the RESOLVER, report)"""
    plan = copy.deepcopy(plan)
    idx = CAT.index(catalog)
    reqs, unsupported, cap_errors, available = {}, [], [], []
    m = manifest
    acts = {a["id"] for a in m["characters"]["capabilities"]}
    shots = {s["id"] for s in m["camera"]["shots"]}
    moves = {x["id"] for x in m["camera"]["movements"]}
    al = m["camera"]["aliases"]
    effects = {e["id"] for e in m["effects"]}
    frame = {(f["subject"], f["shot"]) for f in m["camera"]["framings"]}

    def cap(v, code, field, value, supported, note=""):
        cap_errors.append(dict(code=code, visual=v["id"], field=field, value=value, supported=sorted(supported)[:24], message=f"{v['id']}: {field} '{value}' is not a renderer capability. {note}".strip()))

    # ---- cast
    for c in plan["cast"]:
        a = idx.get(c.get("asset_id")) if c.get("asset_id") else None
        if c.get("asset_id") and not a:
            cap_errors.append(dict(code="UNKNOWN_ASSET", visual=None, field=f"cast.{c['id']}.asset_id", value=c["asset_id"], supported=[], message=f"cast {c['id']}: asset '{c['asset_id']}' does not exist in the catalog"))
            continue
        if not a:
            a = _match(catalog, "character", c.get("archetype") or "")
        if a and a["type"] == "character":
            c["asset_id"], c["archetype"] = a["id"], a["binding"]["archetype"]
            g = (c.get("gender") or "").lower()
            if g in ("male", "female") and a["supports"].get("gender") in ("male", "female") and a["supports"]["gender"] != g:
                c["status"] = "UNSUPPORTED"
                _add(reqs, _request("character", f"{g} {c.get('description') or c['archetype']}", f"cast '{c['id']}' must be {g}; the catalog character {a['id']} is {a['supports']['gender']}", [c["id"]], "UNSUPPORTED", conditions=dict(gender=g)))
            else:
                c["status"] = c.get("status") if c.get("status") == "SUBSTITUTED" else "AVAILABLE"
        else:
            c["status"] = "MISSING"
            _add(reqs, _request("character", c.get("description") or c.get("archetype") or c["id"], f"cast '{c['id']}' ({c.get('archetype') or c.get('description')}) has no matching character in the catalog", [c["id"]], "MISSING"))
    cast_ids = {c["id"] for c in plan["cast"]}
    # ---- visuals
    seq = []
    for v in plan["visuals"]:
        e = v["environment"]
        a = idx.get(e.get("asset_id")) if e.get("asset_id") else None
        if e.get("asset_id") and not a:
            cap_errors.append(dict(code="UNKNOWN_ASSET", visual=v["id"], field="environment.asset_id", value=e["asset_id"], supported=[x["id"] for x in catalog["assets"] if x["type"] == "environment"], message=f"{v['id']}: asset '{e['asset_id']}' does not exist in the catalog"))
        elif not a and e.get("status") != "MISSING_CONFIRMED":
            a = _match(catalog, "environment", e["subject"]) if e["type"] == "generic" else _match(catalog, "environment", e["subject"])
            if a and e["type"] == "real_landmark" and not a.get("landmark"):
                a = None
        if a:
            if a["type"] != "environment":
                cap_errors.append(dict(code="WRONG_ASSET_TYPE", visual=v["id"], field="environment.asset_id", value=a["id"], supported=[], message=f"{v['id']}: {a['id']} is a {a['type']}, not an environment"))
            elif e["type"] == "real_landmark" and CAT.norm(e["subject"]) not in a["subjects"] and e.get("status") != "SUBSTITUTED":
                e["status"] = "UNSUPPORTED"
                _add(reqs, _request("environment", e["subject"], f"the story needs the real landmark '{e['subject']}'; {a['id']} is a generic {a['name']}", [v["id"]], "UNSUPPORTED", "real_landmark", queries=e.get("reference_queries")))
            elif e.get("time_of_day") and e["time_of_day"] not in a["supports"].get("time_of_day", [e["time_of_day"]]) and e.get("status") != "SUBSTITUTED":
                e["status"] = "UNSUPPORTED"
                _add(reqs, _request("environment", f"{e['subject']} at {e['time_of_day']}", f"{a['id']} supports only {a['supports']['time_of_day']}; the story needs {e['time_of_day']}", [v["id"]], "UNSUPPORTED", e["type"],
                                    dict(time_of_day=e["time_of_day"]), e.get("reference_queries")))
            else:
                e["asset_id"] = a["id"]
                e["status"] = "SUBSTITUTED" if e.get("status") == "SUBSTITUTED" else "AVAILABLE"
        elif not e.get("asset_id") or e.get("status") in ("MISSING", "MISSING_CONFIRMED"):
            e["status"] = "MISSING"
            e["asset_id"] = None
            _add(reqs, _request("environment", e["subject"], f"the narration requires '{e['subject']}' and the catalog has no such environment", [v["id"]], "MISSING", e["type"], dict(time_of_day=e.get("time_of_day")) if e.get("time_of_day") else {}, e.get("reference_queries")))
        # characters on screen must be cast members
        for cid in v.get("characters", []):
            if cid not in cast_ids:
                cap_errors.append(dict(code="UNKNOWN_CAST", visual=v["id"], field="characters", value=cid, supported=sorted(cast_ids), message=f"{v['id']}: character '{cid}' is not in the cast"))
        # props
        for p in v.get("props", []):
            pa = idx.get(p.get("asset_id")) if p.get("asset_id") else _match(catalog, "prop", p["name"])
            if pa and pa["type"] == "prop":
                p["asset_id"], p["status"] = pa["id"], ("SUBSTITUTED" if p.get("status") == "SUBSTITUTED" else "AVAILABLE")
            else:
                p["status"], p["asset_id"] = "MISSING", None
                _add(reqs, _request("prop", p["name"], f"the narration shows '{p['name']}' and the catalog has no such prop", [v["id"]], "MISSING"))
        # action capability
        act = v.get("action") or {}
        capname = act.get("capability")
        if not capname:
            capname = INTENT_DEFAULT_ACT.get(v["visual_intent"])
            v["action"] = dict(act or {}, capability=capname, defaulted=True)
        if capname not in acts:
            cap(v, "UNSUPPORTED_CAPABILITY", "action.capability", capname, acts, f"requested: {act.get('requested') or capname}")
        else:
            seq.append((v["id"], capname))
        if (v.get("emotion") or "neutral") not in m["characters"]["emotions"]:
            cap(v, "UNSUPPORTED_EMOTION", "emotion", v.get("emotion"), m["characters"]["emotions"])
        # camera
        c = v["camera"]
        shot, mv = al["camera_shot"].get(c["shot"], c["shot"]), al["camera_movement"].get(c["movement"], c["movement"])
        if shot not in shots:
            cap(v, "UNSUPPORTED_CAMERA_SHOT", "camera.shot", c["shot"], shots)
        if mv not in moves:
            cap(v, "UNSUPPORTED_CAMERA_MOVEMENT", "camera.movement", c["movement"], moves, "unsupported: " + ", ".join(m["camera"]["unsupported"]))
        c["shot_engine"], c["movement_engine"] = shot, mv
        sub = c.get("subject")
        if sub and shot in shots and (sub, shot) not in frame:
            cap(v, "UNSUPPORTED_FRAMING", "camera.subject", f"{sub}/{shot}", [f"{s}/{z}" for s, z in sorted(frame)])
        for fx in v.get("effects", []):
            if fx not in effects:
                cap(v, "UNSUPPORTED_EFFECT", "effects", fx, effects)
        if v.get("transition") and v["transition"] not in m["transitions"]:
            cap(v, "UNSUPPORTED_TRANSITION", "transition", v["transition"], m["transitions"])
    # ---- action sequence rules of the renderer (state the choreography needs)
    if seq:
        for prob in AC.validate([a for _, a in seq]):
            k = int("".join(ch for ch in prob.split(":")[0] if ch.isdigit()) or 0) if prob.startswith("beat") else None
            vid = seq[k][0] if k is not None and k < len(seq) else None
            cap_errors.append(dict(code="SEQUENCE_RULE", visual=vid, field="action.capability", value=seq[k][1] if k is not None and k < len(seq) else None, supported=[], message=(f"{vid}: " if vid else "") + prob))
    for c in plan["cast"]:
        if c["status"] == "AVAILABLE":
            available.append(c["asset_id"])
    for v in plan["visuals"]:
        for x in [v["environment"]] + v.get("props", []):
            if x.get("status") in ("AVAILABLE", "SUBSTITUTED") and x.get("asset_id"):
                available.append(x["asset_id"])
    requests = sorted(reqs.values(), key=lambda r: (r["type"], r["id"]))
    report = dict(ready=not requests and not cap_errors, available_assets=sorted(set(available)), requests=requests, capability_errors=cap_errors,
                  counts=dict(available=len(set(available)), new_required=len(requests), capability_errors=len(cap_errors)))
    return plan, report


def substitute(plan, request_id_or_visuals, asset_id, catalog):
    """the user EXPLICITLY chooses an existing asset instead of creating a new one; recorded as SUBSTITUTED (never silent)"""
    idx = CAT.index(catalog)
    if asset_id not in idx:
        raise ValueError(f"unknown asset {asset_id}")
    plan = copy.deepcopy(plan)
    ids = set(request_id_or_visuals)
    for v in plan["visuals"]:
        if v["id"] in ids and idx[asset_id]["type"] == "environment":
            v["environment"].update(asset_id=asset_id, status="SUBSTITUTED", substituted_by="user")
    for c in plan["cast"]:
        if c["id"] in ids and idx[asset_id]["type"] == "character":
            c.update(asset_id=asset_id, status="SUBSTITUTED", substituted_by="user")
    return plan
