"""AUTO DIRECTOR: story (beats tagged with dramatic ACTS) + paced narration timings -> a version-3 skeleton plan. Deterministic, no LLM: every camera, light, GP effect and character action is
derived from the act vocabulary (`acts.py`) and the narration timings. `short_director_v3` is the hand-authored reference for the same 20-act story; `auto_director` is what runs for any topic.
"""
import hashlib

from engine.dsl import variation as VAR
from engine.environments import bedroom_wide as BW
from engine.skeleton import acts as AC, dna2

FPS = 30
HANDOVER = (905.0, 860.0)
TAIL = 3.0

PROTAGONISTS = {
    "male": ("young_man", {"wardrobe.top": "hoodie", "wardrobe.bottom": "trousers", "wardrobe.shoes": "slippers", "wardrobe.palette": "ink_blue", "wardrobe.pattern": "plain", "wardrobe.accessories": [], "glasses": "* None",
                           "facial_hair": "* None", "hair.style": "Short 4", "hair.length": "short", "posture": "slouched", "personality": "anxious", "age": 22, "eyes": "round", "eyebrows": "normal"}),
    "female": ("young_woman", {"wardrobe.top": "sweater", "wardrobe.bottom": "trousers", "wardrobe.shoes": "slippers", "wardrobe.palette": "sage", "wardrobe.pattern": "plain", "wardrobe.accessories": ["earrings"],
                               "posture": "slouched", "personality": "anxious", "age": 24, "hair.style": "Medium 1", "hair.length": "medium", "eyes": "almond", "eyebrows": "arched"})}
OTHERS = {
    "mother": ("middle_aged_woman", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals", "wardrobe.palette": "terracotta", "wardrobe.pattern": "plain", "wardrobe.accessories": ["earrings"], "age": 47,
                                     "hair.style": "Bun 2", "hair.length": "long", "posture": "upright", "personality": "calm", "eyes": "almond", "eyebrows": "arched"}),
    "father": ("middle_aged_man", {"wardrobe.top": "shirt", "wardrobe.bottom": "trousers", "wardrobe.shoes": "formal", "wardrobe.palette": "terracotta", "wardrobe.pattern": "plain", "wardrobe.accessories": ["watch"], "age": 50,
                                   "hair.style": "Short 2", "hair.length": "short", "facial_hair": "* None", "posture": "upright", "personality": "stern"}),
    "sister": ("young_woman", {"wardrobe.top": "tee", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "plum", "wardrobe.pattern": "plain", "wardrobe.accessories": ["earrings"], "age": 20,
                               "hair.style": "Long", "hair.length": "long", "personality": "cheerful"}),
    "friend": ("young_man", {"wardrobe.top": "jacket", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "terracotta", "wardrobe.pattern": "plain", "wardrobe.accessories": [], "age": 24,
                             "hair.style": "Short 1", "hair.length": "short", "facial_hair": "* None", "personality": "calm"}),
}


def cast(story):
    c = story.get("cast", {})
    pro, oth = c.get("protagonist", {}), c.get("other", {})
    sid = story["story_id"]
    role, ov = PROTAGONISTS.get(pro.get("gender", "male"), PROTAGONISTS["male"])
    A = dna2.make(f"{sid}:A", role, ov)
    role2, ov2 = OTHERS.get(oth.get("relation", "mother"), OTHERS["mother"])
    D = dna2.make(f"{sid}:D", role2, ov2)
    return {"A": dict(name=pro.get("name", "A"), role="protagonist", dna=A, facing=1, origin=[380.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="sit"),
            "D": dict(name=oth.get("name", "D"), role=oth.get("relation", "family"), dna=D, facing=-1, origin=[1440.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")}


# Framing corrections the CRITIC discovered on the first two generated films (the same 4 acts were clipped in both: heads cut by the frame edge at these stage positions). They are now the director's
# defaults so a new film starts clean; the critic still verifies and re-solves every shot (other cast sizes / timings can need different values).
PRESETS = {"PHONE_ALERT": dict(zoom_mul=0.85, dx=-165.0), "PICK_UP": dict(zoom_mul=0.91, dx=-120.0, dy=-160.0), "PERSON_ENTERS": dict(zoom_mul=0.79, dx=197.0), "HAND_OVER": dict(zoom_mul=0.93, dx=-18.0)}


def _cam(target, size, move, **k):
    return dict(target=target, size=size, move=move, **k)


def apply_fixes(sh, fx):
    """Critic fixes are keyed by BEAT id (not time), so they survive re-timing: camera nudges, lighting scalars, size/move overrides."""
    if not fx:
        return sh
    c = fx.get("camera")
    if c and sh.get("camera"):
        cam = dict(sh["camera"])
        for k in ("size", "move", "target"):
            if k in c:
                cam[k] = c[k]
        for k in ("dx", "dy"):
            if k in c:
                cam[k] = round(cam.get(k, 0.0) + c[k], 2)
        if "zoom_mul" in c:
            cam["zoom_mul"] = round(cam.get("zoom_mul", 1.0) * c["zoom_mul"], 4)
        sh["camera"] = cam
    if fx.get("lighting"):
        sh["lighting"] = {**sh["lighting"], **fx["lighting"]}
    if fx.get("ui") and sh.get("ui"):
        sh["ui"] = {**sh["ui"], **fx["ui"]}
    sh["fixes"] = fx
    return sh


def build_plan(story, nar, seed=11, name=None, tts=None, fixes=None, presets=None):
    """story = dict(title, story_id, cast, beats=[dict(id, act, text, data)]); nar = dict(segments=[dict(id,text,start,end,words)], audio, tts, tempo)."""
    beats = story["beats"]
    seq = [b["act"] for b in beats]
    problems = AC.validate(seq)
    if problems:
        raise ValueError("invalid act sequence: " + "; ".join(problems))
    segs = {s["id"]: s for s in nar["segments"]}
    miss = [b["id"] for b in beats if b["id"] not in segs]
    if miss:
        raise ValueError(f"narration is missing beats {miss}")
    sid = story["story_id"]
    st, en = (lambda i: segs[i]["start"]), (lambda i: segs[i]["end"])
    dur = round(en(beats[-1]["id"]) + TAIL, 3)
    cuts = [0.0] + [round(max(st(b["id"]) - 0.12, 0.0), 3) for b in beats[1:]] + [dur]
    acts, shots = [], []
    A = lambda **k: acts.append(dict(char="A", **k))
    D = lambda **k: acts.append(dict(char="D", **k))
    D(action="idle", t=0.0, dur=dur)
    first = {}
    for i, b in enumerate(beats):
        first.setdefault(b["act"], i)

    fixes = fixes or {}
    if presets is None:                                   # stories saved before the presets existed carry critic fixes solved WITHOUT them: never stack the two
        presets = bool(story.get("presets", False))

    def shot(i, treat, purpose, **kw):
        t0, t1 = cuts[i], cuts[i + 1]
        if presets and beats[i]["act"] in PRESETS and kw.get("camera"):
            kw = dict(kw, camera=dict(kw["camera"], **PRESETS[beats[i]["act"]]))
        shots.append(apply_fixes(dict(id=f"S{i + 1:02d}", treatment=treat, t0=t0, t1=t1, beats=[beats[i]["id"]], segs=[beats[i]["id"]], purpose=purpose, act=beats[i]["act"],
                          **{**dict(gp=[], transition_in="cut", sfx=[], phase="-", location="bedroom", lighting=dict(mood="dim", moon=1.0, phone=1.0)), **kw}), fixes.get(beats[i]["id"])))

    prev = None
    for i, b in enumerate(beats):
        a = b["act"]
        t0, t1 = cuts[i], cuts[i + 1]
        L = t1 - t0
        d = b.get("data", {}) or {}
        if a == "ESTABLISH":
            A(action="face", t=0.0, dur=0.3, name="tired")
            A(action="idle", t=0.3, dur=max(0.5, L - 0.3), emotion="sad", intensity=0.4)
            shot(i, "skeleton", "Wide establishing: the protagonist alone in the room at night", camera=_cam("stage", "wide", "push"), transition_in="fade")
        elif a == "PHONE_ALERT":
            A(action="buzz", t=t0 + 0.05, dur=1.0, intensity=0.9)
            A(action="flinch", t=t0 + 0.25, dur=0.6, emotion="fearful", intensity=0.4)
            shot(i, "skeleton", "The phone lights up", camera=_cam("A.reach", "two_reach", "reveal", dir=1),
                 gp=[dict(effect="arcs", anchor="phone_free", start=0.05, duration=min(1.1, L - 0.1), intensity=0.85, relationship="the phone vibrating on the nightstand")])
        elif a == "LOOK_AT_PHONE":
            A(action="look_at", t=t0 + 0.05, dur=max(0.4, L - 0.05), target="PHONE", track=True, emotion="curious", intensity=0.6)
            A(action="face", t=t0 + 0.1, dur=0.35, name="curious")
            shot(i, "skeleton", "He looks at the phone", camera=_cam("A.head", "medium", "isolate"))
        elif a == "EYES_CHANGE":
            A(action="face", t=t0 + 0.05, dur=0.3, name="determination")
            A(action="face", t=t0 + min(0.9, L * 0.5), dur=0.4, name="worried")
            shot(i, "skeleton", "His eyes change", camera=_cam("A.head", "close", "push"), lighting=dict(mood="fear", moon=0.8, phone=1.0),
                 gp=[dict(effect="ticks", anchor="eyes", start=0.1, duration=0.7, intensity=0.6, relationship="the eyes narrow: something is off")])
        elif a == "REACH_PHONE":
            A(action="reach", t=t0 + 0.02, dur=max(0.8, L - 0.3), target="PHONE", emotion="hesitant", intensity=0.8, grip="hold_phone")
            shot(i, "skeleton", "He reaches for the phone", camera=_cam("A.reach", "two_reach", "drift"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
        elif a == "PICK_UP":
            A(action="grab", t=t0 + 0.12, dur=0.1, prop="phone", from_table=True)
            A(action="hold_phone", t=t0 + 0.3, dur=max(0.5, L - 0.3), pos="chest", emotion="hesitant", intensity=0.6)
            shot(i, "skeleton", "He picks it up", camera=_cam("A.phone", "close", "push"), lighting=dict(mood="fear", moon=0.8, phone=1.0),
                 gp=[dict(effect="rays", anchor="phone", start=0.3, duration=min(1.2, L - 0.3), intensity=0.35, relationship="light from the screen")])
        elif a == "READ_MESSAGE":
            A(action="read_phone", t=t0 + 0.05, dur=L - 0.05, emotion="nervous", intensity=0.6)
            A(action="face", t=t0 + 0.1, dur=0.3, name="concerned")
            shot(i, "skeleton", "He reads the message", camera=_cam("A.head", "medium", "rack_focus"), lighting=dict(mood="fear", moon=0.7, phone=1.0))
        elif a == "REALIZE":
            A(action="realization", t=t0 + 0.05, dur=max(1.3, L - 0.05), emotion="shocked", intensity=0.8)
            shot(i, "skeleton", "His expression changes", camera=_cam("A.head", "close", "push"), lighting=dict(mood="fear", moon=0.6, phone=1.0),
                 gp=[dict(effect="worry", anchor="temple", start=0.4, duration=min(1.2, L - 0.4), intensity=0.9, relationship="dread")])
        elif a == "STAND_UP":
            A(action="fear", t=t0, dur=1.0, emotion="fearful", intensity=0.7, body=False)
            A(action="stand", t=t0 + 0.08, dur=min(1.3, max(1.0, L - 0.1)), emotion="fearful", intensity=0.7)
            shot(i, "skeleton", "He stands: full body", camera=_cam("A.full", "full", "pull"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
        elif a == "WALK_ACROSS":
            A(action="walk_to", t=t0 + 0.05, dur=L - 0.1, target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.6, hold_R=True, emotion="nervous", intensity=0.7)
            shot(i, "skeleton", "He walks across the room", camera=_cam("A.full", "full", "track"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
        elif a == "PERSON_ENTERS":
            D(action="walk_to", t=max(0.0, t0 - 1.1), dur=max(2.4, L + 1.2), target="D_STOP", stop_before=0.0, speed=205.0, stride_scale=0.7, emotion="hesitant", intensity=0.5)
            D(action="face", t=t0 + 0.3, dur=0.4, name="concerned")
            D(action="notice", t=t0 + 0.35, dur=0.7, target="PERSON_A", emotion="hesitant", intensity=0.5)
            A(action="notice", t=t0 + 0.2, dur=0.7, target="DOOR", emotion="shocked", intensity=0.5)
            A(action="eye_contact", t=t0 + 0.95, dur=max(1.0, L - 0.85), target="PERSON_D")
            D(action="eye_contact", t=t0 + 1.1, dur=max(1.0, L - 0.9), target="PERSON_A")
            shot(i, "skeleton", "The door opens; a second person comes in", camera=_cam("A+D", "two", "reveal", dir=-1), lighting=dict(mood="dim", moon=0.8, phone=0.7, hall=1.0))
        elif a == "EYE_CONTACT":
            A(action="eye_contact", t=t0 + 0.02, dur=L - 0.02, target="PERSON_D", emotion="nervous", intensity=0.5)
            D(action="eye_contact", t=t0 + 0.05, dur=L - 0.05, target="PERSON_A", emotion="hesitant", intensity=0.5)
            D(action="confusion", t=t0 + 0.4, dur=min(1.1, max(1.1, L - 0.5)), emotion="hesitant", intensity=0.5)
            shot(i, "skeleton", "They look at each other", camera=_cam("A+D", "two", "hold"), lighting=dict(mood="dim", moon=0.8, phone=0.7, hall=1.0))
        elif a == "OTHER_LOOKS_AT_PHONE":
            D(action="look_at", t=t0 + 0.05, dur=L - 0.05, target="PHONE", track=True, emotion="suspicious", intensity=0.6)
            A(action="hold_phone", t=t0 + 0.2, dur=0.6, pos="face", emotion="hesitant", intensity=0.4)
            A(action="look_at", t=t0 + 0.6, dur=0.5, target="PERSON_D", emotion="nervous", intensity=0.4)
            shot(i, "skeleton", "She looks at the phone in his hand", camera=_cam("D.head", "medium", "isolate"), lighting=dict(mood="dim", moon=0.7, phone=1.0, hall=1.0),
                 gp=[dict(effect="arrow", anchor="phone", start=0.3, duration=min(1.1, L - 0.3), intensity=0.8, relationship="attention drawn to the phone")])
        elif a == "HAND_OVER":
            t_meet = round(t0 + max(0.8, L * 0.55), 3)
            A(action="hand_over", t=t0 + 0.05, dur=t_meet - t0 - 0.05, target="PERSON_D", point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.6)
            D(action="receive", t=t0 + 0.15, dur=t_meet - t0 - 0.1, point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.5)
            A(action="release", t=t_meet + 0.55, dur=0.5, prop="phone")
            D(action="hold_phone", t=t_meet + 0.65, dur=max(0.4, t1 - t_meet - 0.65), pos="chest", emotion="hesitant", intensity=0.5)
            shot(i, "skeleton", "He hands her the phone", camera=_cam("A+D", "two", "truck", dir=1), lighting=dict(mood="dim", moon=0.8, phone=1.0, hall=1.0))
        elif a == "OTHER_REACTS":
            D(action="fear", t=t0 + 0.05, dur=1.2, emotion="fearful", intensity=0.6)
            D(action="read_phone", t=t0 + 0.5, dur=max(0.6, L - 0.5), emotion="nervous", intensity=0.5)
            D(action="face", t=t0 + 0.3, dur=0.4, name="worried")
            A(action="look_at", t=t0 + 0.1, dur=L - 0.1, target="PERSON_D", track=True)
            shot(i, "skeleton", "She reacts; the screen lights her face", camera=_cam("D.head", "close", "push"), lighting=dict(mood="fear", moon=0.5, phone=1.0, hall=1.0),
                 gp=[dict(effect="scribble", anchor="head", start=0.6, duration=min(1.3, L - 0.6), intensity=0.6, relationship="alarm")])
        elif a == "INSERT_SCREEN":
            shot(i, "insert_ui", "The suspicious message", ui=dict(screen="sms", data=dict(sender=d.get("sender", "BANK-KYC"), time=d.get("time", "अभी"), text=d.get("text", ""))),
                 lighting=dict(mood="fear"), gp=[dict(effect="ring", start=0.5, duration=min(1.0, L - 0.5), anchor="ui", intensity=0.9, relationship="the demand")])
        elif a == "VISUALIZE_FLOW":
            shot(i, "procedural", "Money and account network visualisation", procedural=dict(type="money_flow", data={"amount": d.get("amount", 250000), "from_label": d.get("from", "आपकी बचत"), "to": d.get("to", ["खाता 1", "खाता 2", "खाता 3"])}),
                 lighting=dict(mood="fear"))
        elif a == "BOTH_REALIZE":
            A(action="realization", t=t0 + 0.05, dur=max(1.3, L - 0.05), emotion="shocked", intensity=0.8)
            D(action="freeze", t=t0 + 0.05, dur=0.6)
            D(action="look_at", t=t0 + 0.7, dur=max(0.4, L - 0.7), target="PERSON_A", emotion="fearful", intensity=0.6)
            shot(i, "skeleton", "Both realise the danger", camera=_cam("A+D", "two", "pull"), lighting=dict(mood="fear", moon=0.6, phone=1.0, hall=1.0),
                 gp=[dict(effect="ticks", anchor="eyes", start=0.1, duration=0.7, intensity=0.9, relationship="the jolt of realisation")], transition_in="dip")
        elif a == "CLOSE_UP":
            A(action="face", t=t0 + 0.05, dur=0.5, name="determination")
            A(action="look_at", t=t0 + 0.1, dur=max(0.4, L - 0.1), target="CAMERA")
            D(action="hand_pose", t=t0, dur=0.1, side="R", pose="open")
            shot(i, "skeleton", "Final close-up", camera=_cam("A.head", "close", "isolate"), lighting=dict(mood="dim", moon=0.9, phone=0.4, hall=0.8))
        elif a == "RESOLVE":
            A(action="relief", t=t0 + 0.2, dur=L + TAIL - 0.4, emotion="relieved", intensity=0.6)
            D(action="relief", t=t0 + 0.6, dur=L + TAIL - 1.0, emotion="relieved", intensity=0.5)
            A(action="look_at", t=t0 + 0.2, dur=1.0, target="PERSON_D", head=True)
            shot(i, "skeleton", "They stop and think; the lamp comes on; wide pull-out", camera=_cam("A+D", "reveal", "pull"), lighting=dict(mood="relief", moon=0.6, phone=0.0, hall=0.4, lamp=1.0),
                 gp=[dict(effect="rays", anchor="lamp", start=0.3, duration=min(2.6, L + TAIL - 0.3), intensity=0.5, relationship="warm light returns")])
        prev = a
    for s_ in shots:
        s_["actions"] = [x for x in acts if s_["t0"] - 1.0 <= x["t"] < s_["t1"]]
    T = {a: cuts[i] for a, i in first.items()}
    sfx = []
    for i, b in enumerate(beats):
        a = b["act"]
        if a == "PHONE_ALERT":
            sfx += [dict(t=round(cuts[i] + 0.05, 3), kind="buzz", gain=0.9), dict(t=round(cuts[i] + 0.1, 3), kind="ding", gain=0.55)]
        if a in ("EYES_CHANGE", "BOTH_REALIZE"):
            sfx.append(dict(t=round(cuts[i] + 0.1, 3), kind="heartbeat", gain=0.6 if a == "EYES_CHANGE" else 0.8))
        if a in ("STAND_UP", "OTHER_REACTS", "PERSON_ENTERS"):
            sfx.append(dict(t=round(cuts[i] + 0.1, 3), kind="impact", gain={"STAND_UP": 0.5, "PERSON_ENTERS": 0.35, "OTHER_REACTS": 0.6}[a]))
    for i in range(1, len(beats)):
        sfx.append(dict(t=round(cuts[i] - 0.06, 3), kind="whoosh", gain=0.2))
    mood, cur = [], None
    for s_ in shots:
        m = s_["lighting"].get("mood", "dim")
        if cur and cur[2] == m:
            cur[1] = s_["t1"]
        else:
            cur = [s_["t0"], s_["t1"], m]
            mood.append(cur)
    mood[-1][1] = dur
    ent = T.get("PERSON_ENTERS")
    lamp = T.get("RESOLVE")
    tfix = fixes.get("_targets", {})
    targets = dict(PHONE=list(BW.PHONE_POS), DOOR=[960.0, 1000.0], NIGHTSTAND=[670.0, 1180.0], BED=[200.0, 1230.0], LAMP=[600.0, 1110.0], WINDOW=[865.0, 560.0], A_STOP=[830.0, BW.FLOOR_Y], D_STOP=[1070.0, BW.FLOOR_Y],
                   HANDOVER=list(HANDOVER), SCREEN=[540.0, 900.0], MONEY=[540.0, 900.0], nightstand_phone=list(BW.PHONE_POS))
    targets.update({k: list(v) for k, v in tfix.items()})
    return dict(kind="skeleton_short", version=3, title=story["title"], story_id=sid, seed=seed, fps=FPS, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name=name or story.get("slug", sid),
                environment=dict(family="bedroom_wide", variation=dict(palette=VAR.seed_int(sid, "env", "pal") % 3), seed=VAR.seed_int(sid, "env", "seed") % 1000),
                characters=cast(story), cast_in_short=["A", "D"], narration=dict(segments=nar["segments"], audio=nar.get("audio"), tts=tts or nar.get("tts", "unknown"), tempo=nar.get("tempo", 1.0)),
                targets=targets, shots=shots, sfx=sfx, mood_track=[tuple(m) for m in mood], title_card=dict(t0=round(dur - 1.9, 3), t1=dur, text=story["title"]),
                lamp_on=round(lamp + 0.3, 3) if lamp is not None else 1e9, hall_on=round(ent - 0.5, 3) if ent is not None else 1e9, rim=dict(moon=0.5), duration_range=[45.0, 60.0],
                acts=[b["act"] for b in beats])
