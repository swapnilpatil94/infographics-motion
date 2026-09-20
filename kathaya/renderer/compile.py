"""COMPILER: resolved VisualScenePlan + NarrationTimeline -> the physical renderer's input (story graph + narration segments + plan overrides consumed by `engine.skeleton.production.make`).

This is a pure TRANSFORMATION with fixed tables (capability name -> renderer act, camera subject/shot -> engine target/size, environment asset -> stage layout). It does not read the story text and does not interpret meaning: every
decision was made by the creative director and is in the plan. A plan that is not fully resolved (a MISSING / UNSUPPORTED asset or a capability error) is refused - nothing is force-fitted."""
import hashlib
import json

from engine.skeleton import acts as AC
from kathaya.assets import catalog as CAT
from kathaya.renderer import manifest as MF

DEFAULT_SUBJECT = dict(reveal="environment", wide="environment", wide2="environment", full="protagonist_full", medium="protagonist_head", close="protagonist_head", two="two_shot", two_reach="protagonist_reach")
GENDER = {"male": "masculine", "female": "feminine", "either": "either"}


class NotReady(Exception):
    def __init__(self, report):
        super().__init__(f"the visual plan is not ready: {report['counts']}")
        self.report = report


def camera_for(v, partner_id):
    """(engine target, engine size, engine move) for a visual's camera intent; raises ValueError with the reason when the intent has no valid framing"""
    c = v["camera"]
    shot, mv = c["shot_engine"], c["movement_engine"]
    sub = c.get("subject")
    if not sub:
        sub = DEFAULT_SUBJECT[shot]
        act = v.get("action") or {}
        if sub == "protagonist_head" and partner_id and act.get("actor") == partner_id:
            sub = "partner_head"
    tgt = MF.ENGINE_TARGET[sub]
    if (sub, shot) not in {(f["subject"], f["shot"]) for f in MF.build()["camera"]["framings"]}:
        raise ValueError(f"{v['id']}: no valid framing for {sub}/{shot}")
    return dict(target=tgt, size=shot, move=mv)


def compile_plan(vplan, timeline, catalog, report, plan_hash):
    if not report["ready"]:
        raise NotReady(report)
    idx = CAT.index(catalog)
    cast = {c["id"]: c for c in vplan["cast"]}
    pro = next(c for c in vplan["cast"] if c["role"] == "protagonist")
    partner = next((c for c in vplan["cast"] if c["role"] == "partner"), None)
    extras = [c for c in vplan["cast"] if c["role"] == "extra"]

    def g(c, kind):
        gd = (c.get("gender") or "either").lower()
        return (("male" if gd == "either" else gd) if kind == "pro" else GENDER.get(gd, "either"))
    cast_g = dict(protagonist=dict(gender=g(pro, "pro"), archetype=pro["archetype"], name=pro.get("name", "")),
                  principal=dict(role=partner["id"], archetype=partner["archetype"], gender=g(partner, "o")) if partner else None,
                  extras=[dict(role=e["id"], archetype=e["archetype"], gender=g(e, "o")) for e in extras[:2]])
    beats, segs = [], []
    seg_text = {s["id"]: s["text"] for s in timeline["narration"]}
    for v in vplan["visuals"]:
        e = v["environment"]
        env = idx[e["asset_id"]]
        loc = env["binding"]["location"]
        act = v["action"]["capability"]
        actor = (v["action"] or {}).get("actor")
        prm = dict((v["action"] or {}).get("params") or {})
        props = [idx[p["asset_id"]]["binding"]["prop"] for p in v.get("props", []) if p.get("asset_id")]
        data = {}
        if act == "INSERT_SCREEN":
            sc = v.get("screen") or {}
            data = dict(sender=sc.get("sender") or "UNKNOWN", time="अभी", text=sc.get("text") or seg_text.get(v["narration_id"], v.get("narration_text", "")))
        elif act == "VISUALIZE_FLOW":
            data = dict(amount=int(prm.get("amount") or 100000), from_label=prm.get("from_label") or "आपकी बचत", to=prm.get("to") or ["खाता 1", "खाता 2", "खाता 3"])
        elif act in ("GIVE_OBJECT", "RECEIVE_OBJECT"):
            data = dict(prop=str(prm.get("prop") or (props[0] if props else "money")).lower())
        partner_in = bool(partner and (partner["id"] in v.get("characters", []) or actor == partner["id"]))
        b = dict(id=v["id"], text=v.get("narration_text", ""), act=act, loc=loc, time=e["time_of_day"], emotion=v.get("emotion") or "neutral", props=props, roles=[partner["id"]] if partner_in else [],
                 subject="partner" if (partner and actor == partner["id"]) else "protagonist", data=data)
        if act not in ("INSERT_SCREEN", "VISUALIZE_FLOW"):                                     # those two are full-screen inserts: the camera does not apply
            b["camera"] = camera_for(v, partner["id"] if partner else None)
        if v.get("effects"):
            b["effects"] = list(v["effects"])
        b["ambient_gaze"] = True
        if v.get("transition"):
            b["transition"] = v["transition"]
        if not beats:
            b["transition"] = "fade"                                                          # the renderer always opens by fading in from black (its first frames are black); the manifest states it
        beats.append(b)
        segs.append(dict(id=v["id"], text=v.get("narration_text", ""), start=v["start"], end=v["end"]))
    bad = AC.validate([b["act"] for b in beats])
    if bad:
        raise ValueError("invalid action sequence for the renderer: " + "; ".join(bad))
    scenes, prev = [], None
    for b in beats:
        k = (b["loc"], b["time"])
        if k != prev:
            scenes.append(dict(loc=b["loc"], time=b["time"], first=b["id"], beats=[]))
            prev = k
        scenes[-1]["beats"].append(b["id"])
    sid = "s_" + hashlib.sha1((plan_hash + json.dumps(cast_g, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()[:8]
    ns = [dict(id=s["id"], text=s["text"], start=s["start"], end=s["end"], **({"words": s["words"]} if s.get("words") else {})) for s in timeline["narration"]]
    graph = dict(title=vplan.get("title") or "कहानी", story_id=sid, slug=sid, cast=cast_g, scenes=scenes, beats=beats, provenance=[dict(step="kathaya_visual_scene_plan", plan_hash=plan_hash)], words=sum(len(s["text"].split()) for s in ns),
                 notes={}, schema="kathaya.story_graph/1", fixes={},
                 narration_segments=ns,
                 plan_overrides=dict(transitions_render=True, duration_range=[0.0, 7200.0], kathaya=dict(plan_hash=plan_hash, renderer_version=MF.renderer_version(), catalog_hash=catalog.get("catalog_hash"), format=vplan["format"])))
    nar = dict(segments=segs, audio=timeline.get("audio"), tts=timeline["source"], tempo=1.0)
    return dict(graph=graph, narration=nar)
