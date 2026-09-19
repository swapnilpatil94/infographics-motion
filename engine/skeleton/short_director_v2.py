"""SHORT DIRECTOR V2 (deterministic, no LLM): "एक गलत कॉल" - 20 beats -> 20 shots (`plan.json`, kind skeleton_short, version 2).

Everything the characters do is a SEMANTIC ACTION with SEMANTIC TARGET IDS ({"action":"look_at","target":"PHONE"}, {"action":"hand_over","target":"PERSON_D"} ...); the motion engine
generates the animation. Cameras are intents (target, size, move). Lights are named states. All times come from the paced narration.
"""
import hashlib

from engine.dsl import variation as VAR
from engine.environments import bedroom_wide as BW
from engine.skeleton import dna2

TITLE = "एक गलत कॉल"
FPS = 30
BEATS = [f"n{i:02d}" for i in range(1, 21)]
HANDOVER = (905.0, 860.0)


def cast(story_id):
    A = dna2.make(f"{story_id}:A", "young_man", {"wardrobe.top": "hoodie", "wardrobe.bottom": "trousers", "wardrobe.shoes": "slippers", "wardrobe.palette": "ink_blue", "wardrobe.pattern": "plain",
                                                 "wardrobe.accessories": [], "glasses": "* None", "facial_hair": "* None", "hair.style": "Short 4", "hair.length": "short", "posture": "slouched", "personality": "anxious", "age": 22, "eyes": "round", "eyebrows": "normal"})
    D = dna2.make(f"{story_id}:D", "middle_aged_woman", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals", "wardrobe.palette": "terracotta", "wardrobe.pattern": "plain",
                                                         "wardrobe.accessories": ["earrings"], "age": 47, "hair.style": "Bun 2", "hair.length": "long", "posture": "upright", "personality": "calm", "eyes": "almond", "eyebrows": "arched"})
    return {"A": dict(name="अर्जुन", role="protagonist", dna=A, facing=1, origin=[380.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="sit"),
            "D": dict(name="माँ", role="family", dna=D, facing=-1, origin=[1335.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")}


def _w(seg, needle, default):
    for w in seg.get("words") or []:
        if needle in w["word"]:
            return w["start"]
    return default


def build_plan(nar, seed=11, tts=None, name="skeleton_factory_v2"):
    segs = {s["id"]: s for s in nar["segments"]}
    missing = [b for b in BEATS if b not in segs]
    if missing:
        raise ValueError(f"narration is missing beats {missing}")
    st, en = (lambda n: segs[n]["start"]), (lambda n: segs[n]["end"])
    story_id = "galat_" + hashlib.sha1(TITLE.encode()).hexdigest()[:5]
    tail = 3.0
    dur = round(en("n20") + tail, 3)
    cuts = [0.0] + [round(max(st(n) - 0.12, 0.0), 3) for n in BEATS[1:]] + [dur]
    T = {f"S{i + 1:02d}": (cuts[i], cuts[i + 1]) for i in range(20)}
    acts = []
    A = lambda **k: acts.append(dict(char="A", **k))
    D = lambda **k: acts.append(dict(char="D", **k))
    t0, t1 = T["S01"]
    A(action="face", t=0.0, dur=0.3, name="tired")
    A(action="idle", t=0.3, dur=t1 - 0.3, emotion="sad", intensity=0.4)
    D(action="idle", t=0.0, dur=dur)
    # S02 the phone rings
    t0, t1 = T["S02"]
    A(action="buzz", t=t0 + 0.05, dur=1.0, intensity=0.9)
    A(action="flinch", t=t0 + 0.25, dur=0.6, emotion="fearful", intensity=0.4)
    # S03 he looks at the phone
    t0, t1 = T["S03"]
    A(action="look_at", t=t0 + 0.05, dur=t1 - t0 - 0.05, target="PHONE", track=True, emotion="curious", intensity=0.6)
    A(action="face", t=t0 + 0.1, dur=0.35, name="curious")
    # S04 his eyes change
    t0, t1 = T["S04"]
    A(action="face", t=t0 + 0.05, dur=0.3, name="determination")
    A(action="face", t=t0 + 0.9, dur=0.4, name="worried")
    # S05 he reaches
    t0, t1 = T["S05"]
    A(action="reach", t=t0 + 0.02, dur=max(0.8, t1 - t0 - 0.3), target="PHONE", emotion="hesitant", intensity=0.8, grip="hold_phone")
    # S06 he picks it up
    t0, t1 = T["S06"]
    A(action="grab", t=t0 + 0.12, dur=0.1, prop="phone")
    A(action="hold_phone", t=t0 + 0.3, dur=max(0.5, t1 - t0 - 0.3), pos="chest", emotion="hesitant", intensity=0.6)
    # S07 he reads
    t0, t1 = T["S07"]
    A(action="read_phone", t=t0 + 0.05, dur=t1 - t0 - 0.05, emotion="nervous", intensity=0.6)
    A(action="face", t=t0 + 0.1, dur=0.3, name="concerned")
    # S08 his expression changes
    t0, t1 = T["S08"]
    A(action="realization", t=t0 + 0.05, dur=t1 - t0 - 0.05, emotion="shocked", intensity=0.8)
    # S09 he stands
    t0, t1 = T["S09"]
    A(action="face", t=t0, dur=0.3, name="fear")
    A(action="stand", t=t0 + 0.08, dur=min(1.3, max(1.0, t1 - t0 - 0.1)), emotion="fearful", intensity=0.7)
    # S10 he walks across the room
    t0, t1 = T["S10"]
    A(action="walk_to", t=t0 + 0.05, dur=t1 - t0 - 0.1, target="A_STOP", stop_before=0.0, speed=170.0, stride_scale=0.5, hold_R=True, emotion="nervous", intensity=0.7)
    # S11 the mother enters
    t0, t1 = T["S11"]
    D(action="walk_to", t=t0 - 0.2, dur=max(1.4, t1 - t0 + 0.2), target="D_STOP", stop_before=0.0, speed=230.0, stride_scale=0.7, emotion="hesitant", intensity=0.5)
    D(action="face", t=t0 + 0.2, dur=0.4, name="concerned")
    A(action="head_turn", t=t0 + 0.3, dur=0.5, direction=1, emotion="shocked", intensity=0.5)
    # S12 he looks at her, she looks at him
    t0, t1 = T["S12"]
    A(action="look_at", t=t0 + 0.05, dur=t1 - t0 - 0.05, target="PERSON_D", track=True, emotion="nervous", intensity=0.5)
    D(action="look_at", t=t0 + 0.15, dur=t1 - t0 - 0.15, target="PERSON_A", track=True, emotion="hesitant", intensity=0.5)
    # S13 she looks at the phone
    t0, t1 = T["S13"]
    D(action="look_at", t=t0 + 0.05, dur=t1 - t0 - 0.05, target="PHONE", track=True, emotion="suspicious", intensity=0.6)
    A(action="hold_phone", t=t0 + 0.2, dur=0.6, pos="face", emotion="hesitant", intensity=0.4)
    A(action="look_at", t=t0 + 0.6, dur=0.5, target="PERSON_D", emotion="nervous", intensity=0.4)
    # S14 he hands her the phone
    t0, t1 = T["S14"]
    t_meet = round(t0 + max(0.8, (t1 - t0) * 0.55), 3)
    A(action="hand_over", t=t0 + 0.05, dur=t_meet - t0 - 0.05, target="PERSON_D", point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.6)
    D(action="receive", t=t0 + 0.15, dur=t_meet - t0 - 0.1, point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.5)
    A(action="release", t=t_meet + 0.12, dur=0.5, prop="phone")
    D(action="hold_phone", t=t_meet + 0.35, dur=max(0.4, t1 - t_meet - 0.35), pos="chest", emotion="hesitant", intensity=0.5)
    # S15 she reacts
    t0, t1 = T["S15"]
    D(action="flinch", t=t0 + 0.05, dur=0.6, emotion="fearful", intensity=0.6)
    D(action="read_phone", t=t0 + 0.5, dur=max(0.6, t1 - t0 - 0.5), emotion="nervous", intensity=0.5)
    D(action="face", t=t0 + 0.3, dur=0.4, name="worried")
    A(action="look_at", t=t0 + 0.1, dur=t1 - t0 - 0.1, target="PERSON_D", track=True)
    # S16 / S17 insert + visualisation: acting continues off-screen
    t0, t1 = T["S16"]
    D(action="face", t=t0 + 0.2, dur=0.4, name="fear")
    # S18 both realise
    t0, t1 = T["S18"]
    A(action="realization", t=t0 + 0.05, dur=t1 - t0 - 0.05, emotion="shocked", intensity=0.8)
    D(action="freeze", t=t0 + 0.05, dur=0.6)
    D(action="look_at", t=t0 + 0.7, dur=t1 - t0 - 0.7, target="PERSON_A", emotion="fearful", intensity=0.6)
    # S19 final close-up
    t0, t1 = T["S19"]
    A(action="face", t=t0 + 0.05, dur=0.5, name="determination")
    A(action="look_at", t=t0 + 0.1, dur=t1 - t0 - 0.1, target="CAMERA")
    D(action="hand_pose", t=t0, dur=0.1, side="R", pose="open")
    # S20 end: relief, the lamp comes on
    t0, t1 = T["S20"]
    A(action="relief", t=t0 + 0.2, dur=t1 - t0 + tail - 0.4, emotion="relieved", intensity=0.6)
    D(action="relief", t=t0 + 0.6, dur=t1 - t0 + tail - 1.0, emotion="relieved", intensity=0.5)
    A(action="look_at", t=t0 + 0.2, dur=1.0, target="PERSON_D", head=True)

    shots = []

    def sh(i, treat, **kw):
        shots.append(dict(id=f"S{i:02d}", treatment=treat, t0=T[f"S{i:02d}"][0], t1=T[f"S{i:02d}"][1], beats=[f"n{i:02d}"], segs=[f"n{i:02d}"],
                          **{**dict(gp=[], transition_in="cut", sfx=[], phase="-", location="bedroom", lighting=dict(mood="dim", moon=1.0, phone=1.0)), **kw}))
    cam = lambda target, size, move, **k: dict(target=target, size=size, move=move, **k)
    sh(1, "skeleton", purpose="Wide establishing: a young man alone in his bedroom at night", camera=cam("stage", "wide", "push"), transition_in="fade")
    sh(2, "skeleton", purpose="The phone rings", camera=cam("A.reach", "two_reach", "reveal", dir=1), gp=[dict(effect="arcs", anchor="phone_free", start=0.05, duration=1.1, intensity=0.85, relationship="the phone vibrating on the nightstand")])
    sh(3, "skeleton", purpose="He looks at the phone", camera=cam("A.head", "medium", "isolate"))
    sh(4, "skeleton", purpose="His eyes change", camera=cam("A.head", "close", "push"), lighting=dict(mood="fear", moon=0.8, phone=1.0),
       gp=[dict(effect="ticks", anchor="eyes", start=0.1, duration=0.7, intensity=0.6, relationship="the eyes narrow: something is off")])
    sh(5, "skeleton", purpose="He reaches for the phone", camera=cam("A.reach", "two_reach", "drift"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
    sh(6, "skeleton", purpose="He picks it up", camera=cam("A.phone", "close", "push"), lighting=dict(mood="fear", moon=0.8, phone=1.0),
       gp=[dict(effect="rays", anchor="phone", start=0.3, duration=1.2, intensity=0.35, relationship="light from the screen")])
    sh(7, "skeleton", purpose="He reads the message", camera=cam("A.head", "medium", "rack_focus"), lighting=dict(mood="fear", moon=0.7, phone=1.0))
    sh(8, "skeleton", purpose="His expression changes", camera=cam("A.head", "close", "push"), lighting=dict(mood="fear", moon=0.6, phone=1.0),
       gp=[dict(effect="worry", anchor="temple", start=0.4, duration=1.2, intensity=0.9, relationship="dread")])
    sh(9, "skeleton", purpose="He stands: full body", camera=cam("A.full", "full", "pull"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
    sh(10, "skeleton", purpose="He walks across the room", camera=cam("A.full", "full", "track"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
    sh(11, "skeleton", purpose="The door opens; his mother comes in", camera=cam("A+D", "two", "reveal", dir=-1), lighting=dict(mood="dim", moon=0.8, phone=0.7, hall=1.0))
    sh(12, "skeleton", purpose="He looks at her; she looks at him", camera=cam("A+D", "two", "hold"), lighting=dict(mood="dim", moon=0.8, phone=0.7, hall=1.0))
    sh(13, "skeleton", purpose="She looks at the phone in his hand", camera=cam("D.head", "medium", "isolate"), lighting=dict(mood="dim", moon=0.7, phone=1.0, hall=1.0),
       gp=[dict(effect="arrow", anchor="phone", start=0.3, duration=1.1, intensity=0.8, relationship="attention drawn to the phone")])
    sh(14, "skeleton", purpose="He hands her the phone", camera=cam("A+D", "two", "truck", dir=1), lighting=dict(mood="dim", moon=0.8, phone=1.0, hall=1.0))
    sh(15, "skeleton", purpose="She reacts; the screen lights her face", camera=cam("D.head", "close", "push"), lighting=dict(mood="fear", moon=0.5, phone=1.0, hall=1.0),
       gp=[dict(effect="scribble", anchor="head", start=0.6, duration=1.3, intensity=0.6, relationship="alarm")])
    sh(16, "insert_ui", purpose="The suspicious banking message", ui=dict(screen="sms", data=dict(sender="HDFC-KYC", time="अभी", text="ओटीपी बताइए, वरना आपका खाता बंद कर दिया जाएगा। bit.ly/kyc-now")),
       lighting=dict(mood="fear"), gp=[dict(effect="ring", start=0.5, duration=1.0, anchor="ui", intensity=0.9, relationship="the demand for the OTP")])
    sh(17, "procedural", purpose="Money and account network visualisation", procedural=dict(type="money_flow", data={"amount": 250000, "from": "आपकी बचत", "to": ["खाता 1", "खाता 2", "खाता 3"]}),
       lighting=dict(mood="fear"))
    sh(18, "skeleton", purpose="Both realise the danger", camera=cam("A+D", "two", "pull"), lighting=dict(mood="fear", moon=0.6, phone=1.0, hall=1.0),
       gp=[dict(effect="ticks", anchor="eyes", start=0.1, duration=0.7, intensity=0.9, relationship="the jolt of realisation")], transition_in="dip")
    sh(19, "skeleton", purpose="Final close-up", camera=cam("A.head", "close", "isolate"), lighting=dict(mood="dim", moon=0.9, phone=0.4, hall=0.8))
    sh(20, "skeleton", purpose="They stop and think; the lamp comes on; wide pull-out", camera=cam("A+D", "reveal", "pull"), lighting=dict(mood="relief", moon=0.6, phone=0.0, hall=0.4, lamp=1.0),
       gp=[dict(effect="rays", anchor="lamp", start=0.3, duration=2.6, intensity=0.5, relationship="warm light returns")])
    for s_ in shots:
        s_["actions"] = [a for a in acts if s_["t0"] - 1.0 <= a["t"] < s_["t1"]]
    t_ring = T["S02"][0] + 0.05
    sfx = [dict(t=round(t_ring, 3), kind="buzz", gain=0.9), dict(t=round(t_ring + 0.05, 3), kind="ding", gain=0.55), dict(t=round(T["S04"][0] + 0.1, 3), kind="heartbeat", gain=0.6),
           dict(t=round(T["S09"][0] + 0.1, 3), kind="impact", gain=0.5), dict(t=round(T["S11"][0] + 0.1, 3), kind="impact", gain=0.35), dict(t=round(T["S15"][0] + 0.05, 3), kind="impact", gain=0.6),
           dict(t=round(T["S18"][0] + 0.05, 3), kind="heartbeat", gain=0.8)]
    for i in range(1, 20):
        sfx.append(dict(t=round(cuts[i] - 0.06, 3), kind="whoosh", gain=0.2))
    mood = [(0.0, T["S04"][0], "dim"), (T["S04"][0], T["S11"][0], "fear"), (T["S11"][0], T["S18"][0], "dim"), (T["S18"][0], T["S20"][0], "fear"), (T["S20"][0], dur, "relief")]
    targets = dict(PHONE=list(BW.PHONE_POS), DOOR=[960.0, 1000.0], NIGHTSTAND=[670.0, 1180.0], BED=[200.0, 1230.0], LAMP=[600.0, 1110.0], WINDOW=[865.0, 560.0],
                   A_STOP=[800.0, BW.FLOOR_Y], D_STOP=[1030.0, BW.FLOOR_Y], HANDOVER=list(HANDOVER), SCREEN=[540.0, 900.0], MONEY=[540.0, 900.0], nightstand_phone=list(BW.PHONE_POS))
    return dict(kind="skeleton_short", version=2, title=TITLE, story_id=story_id, seed=seed, fps=FPS, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name=name,
                environment=dict(family="bedroom_wide", variation=dict(palette=VAR.seed_int(story_id, "env", "pal") % 3), seed=VAR.seed_int(story_id, "env", "seed") % 1000),
                characters=cast(story_id), cast_in_short=["A", "D"], narration=dict(segments=nar["segments"], audio=nar.get("audio"), tts=tts or nar.get("tts", "unknown"), tempo=nar.get("tempo", 1.0)),
                targets=targets, shots=shots, sfx=sfx, mood_track=mood, title_card=dict(t0=round(dur - 1.9, 3), t1=dur, text=TITLE), lamp_on=round(T["S20"][0] + 0.3, 3), hall_on=round(T["S11"][0] - 0.5, 3),
                rim=dict(moon=0.5), duration_range=[45.0, 60.0])
