"""SHORT DIRECTOR (deterministic, no LLM): narration beat timings -> `plan.json` for the skeleton-factory proof short "एक कॉल ने सब बदल दिया".

The plan is pure data: characters as DNA, an environment, shots (treatment / camera intent / lighting / GP effects) and per-character SEMANTIC ACTIONS
({"char","action","t","dur","emotion","intensity", ...params}) - never a frame number or a bone rotation. `engine/skeleton/short.py` renders it.
13 beats <-> 13 shots (spec sec. 7). All times are absolute seconds of the paced narration.
"""
import hashlib

from engine.characters import dna as DNA
from engine.dsl import variation as VAR
from engine.environments import bedroom_wide as BW

TITLE = "एक कॉल ने सब बदल दिया"
FPS = 30
BEATS = ["n01", "n02", "n03", "n04", "n05", "n06", "n07", "n08", "n09", "n10", "n11", "n12", "n13"]

# named world targets (world px; the renderer converts them to each character's rig space)
TARGETS = dict(nightstand_phone=list(BW.PHONE_POS), door=[1040.0, BW.FLOOR_Y])


def cast(story_id):
    """A young male, B young female, C middle-aged male, D middle-aged female - ONE rig, four DNAs. A and D act in the short; B, C appear in the factory tests."""
    mk = lambda arch, key, g: DNA.make(arch, f"{story_id}:{key}", gender=g)
    return {
        "A": dict(name="अर्जुन", role="protagonist", dna=mk("young_man", "A", "male"), facing=1, origin=[380.0, BW.FLOOR_Y]),
        "B": dict(name="प्रिया", role="variation", dna=mk("young_woman", "B", "female"), facing=1, origin=[0.0, BW.FLOOR_Y]),
        "C": dict(name="बैंक मैनेजर (कॉलर)", role="variation", dna=mk("middle_aged_man", "C", "male"), facing=1, origin=[0.0, BW.FLOOR_Y]),
        "D": dict(name="माँ", role="family", dna=mk("middle_aged_woman", "D", "female"), facing=-1, origin=[1335.0, BW.FLOOR_Y]),
    }


def _word_t(seg, needle, default):
    for w in seg.get("words") or []:
        if needle in w["word"]:
            return w["start"]
    return default


def build_plan(nar, seed=7, tts=None, name="skeleton_factory_proof"):
    segs = {s["id"]: s for s in nar["segments"]}
    missing = [b for b in BEATS if b not in segs]
    if missing:
        raise ValueError(f"narration is missing beats {missing}")
    st = lambda n: segs[n]["start"]
    en = lambda n: segs[n]["end"]
    story_id = "call_" + hashlib.sha1(TITLE.encode()).hexdigest()[:5]
    tail = 1.9
    dur = round(en("n13") + tail, 3)
    # shot boundaries: continuous coverage, each cut lands just before its beat (cuts lead the voice by ~0.12 s: the eye moves first)
    cuts = [0.0] + [round(max(st(n) - 0.12, 0.0), 3) for n in BEATS[1:]] + [dur]
    T = {f"S{i + 1:02d}": (cuts[i], cuts[i + 1]) for i in range(13)}
    acts = []
    A = lambda **k: acts.append(dict(char="A", **k))
    D = lambda **k: acts.append(dict(char="D", **k))

    # ---- S01 wide bedroom: A dozes on the bed edge; the phone lights up
    t0, t1 = T["S01"]
    t_buzz = round(_word_t(segs["n01"], "फ़ोन", t0 + 1.0), 3)
    A(action="slump", t=0.0, dur=t1, emotion="sad", intensity=0.4)
    A(action="face", t=0.0, dur=0.3, name="tired")
    A(action="idle", t=0.3, dur=t1 - 0.3, emotion="sad", intensity=0.3)
    A(action="buzz", t=t_buzz, dur=1.0, intensity=0.8)
    # ---- S02 medium: he wakes and notices the phone (eyes lead, head follows)
    t0, t1 = T["S02"]
    A(action="wake", t=t0 - 0.05, dur=0.6, emotion="nervous", intensity=0.5)
    A(action="face", t=t0 + 0.2, dur=0.3, name="uneasy")
    A(action="look_at_phone", t=t0 + 0.25, dur=0.5, emotion="curious", intensity=0.6, point=[TARGETS["nightstand_phone"][0], TARGETS["nightstand_phone"][1]], world=True)
    # ---- S03: reach + grab (hand and arm animate; hesitant, with a doubt pause)
    t0, t1 = T["S03"]
    t_arrive = round(min(t0 + 0.95, t1 - 0.45), 3)
    A(action="reach_for_phone", t=t0 + 0.05, dur=t_arrive - t0 - 0.05, emotion="hesitant", intensity=0.8, target="nightstand_phone")
    A(action="grab", t=t_arrive, dur=0.1)
    A(action="hold_phone", t=t_arrive + 0.12, dur=max(0.45, t1 - t_arrive - 0.12), emotion="hesitant", intensity=0.6, pos="chest")
    # ---- S04 close: he reads; eyes travel, head turns slightly
    t0, t1 = T["S04"]
    A(action="face", t=t0, dur=0.3, name="concerned")
    A(action="read_phone", t=t0 + 0.05, dur=t1 - t0 - 0.05, emotion="nervous", intensity=0.6)
    A(action="head_turn", t=t0 + 0.55, dur=0.5, emotion="nervous", intensity=0.5, direction=-1)
    # ---- S05: phone insert (suspicious bank notification) - A keeps reading off-screen
    t0, t1 = T["S05"]
    A(action="face", t=t0 + 0.2, dur=0.3, name="fear")
    # ---- S06 full body: he shoots to his feet
    t0, t1 = T["S06"]
    A(action="surprise", t=t0 + 0.02, dur=0.5, emotion="shocked", intensity=0.7)
    A(action="stand", t=t0 + 0.12, dur=min(1.35, t1 - t0 - 0.2), emotion="fearful", intensity=0.7)
    # ---- S07 tracking: a few nervous steps, phone still in hand
    t0, t1 = T["S07"]
    A(action="face", t=t0, dur=0.3, name="uneasy")
    A(action="walk", t=t0 + 0.05, dur=max(1.0, t1 - t0 - 0.2), emotion="nervous", intensity=0.7, speed=178.0, stride_scale=0.42, hold_R=True)
    # ---- S08 two-shot: his mother walks in; they interact
    t0, t1 = T["S08"]
    t_bete = round(_word_t(segs["n08"], "बेटा", t0 + 0.9), 3)
    A(action="head_turn", t=t0 + 0.25, dur=0.5, emotion="shocked", intensity=0.6, direction=1)
    A(action="face", t=t0 + 0.25, dur=0.3, name="shock")
    A(action="hand_down", t=t0 + 0.6, dur=0.4, hand="R")
    D(action="walk", t=t0 - 0.6, dur=max(1.6, t_bete - t0 + 0.6), emotion="hesitant", intensity=0.6, speed=252.0, stride_scale=0.85)
    D(action="face", t=t0, dur=0.3, name="concerned")
    D(action="talk", t=t_bete, dur=max(0.9, t1 - t_bete), emotion="hesitant", intensity=0.6)
    D(action="gesture", t=t_bete, dur=max(0.9, t1 - t_bete), emotion="hesitant", intensity=0.5, hand="R")
    # ---- S09 close: the phone rings again - hand to ear
    t0, t1 = T["S09"]
    A(action="buzz", t=t0 + 0.02, dur=0.8, intensity=0.9)
    A(action="hold_phone", t=t0 + 0.35, dur=0.55, emotion="fearful", intensity=0.6, pos="ear")
    A(action="face", t=t0 + 0.4, dur=0.3, name="uneasy")
    D(action="look_left", t=t0 + 0.3, dur=0.5, emotion="hesitant", intensity=0.5)
    D(action="listen", t=t0 + 0.5, dur=max(0.8, t1 - t0 - 0.5))
    # ---- S10: camera pushes through the 2.5D layers; fear builds
    t0, t1 = T["S10"]
    A(action="fear", t=t0 + 0.1, dur=t1 - t0 - 0.1, emotion="fearful", intensity=0.85)
    D(action="face", t=t0 + 0.2, dur=0.3, name="fear")
    # ---- S11: money visualisation (procedural). A keeps acting off-screen
    t0, t1 = T["S11"]
    A(action="idle", t=t0, dur=t1 - t0)
    # ---- S12 close: the realisation
    t0, t1 = T["S12"]
    A(action="realization", t=t0 + 0.03, dur=t1 - t0 - 0.03, emotion="shocked", intensity=0.9)
    A(action="hand_down", t=t0 + 0.2, dur=0.5, hand="R")
    A(action="look_at_phone", t=t0 + 0.45, dur=0.5, emotion="suspicious", intensity=0.7, point=[420.0, 1080.0], world=True)
    # ---- S13 final reveal: he ends the call; the lamp comes on
    t0, t1 = T["S13"]
    A(action="hangup", t=t0 + 0.1, dur=0.9, emotion="relieved", intensity=0.6)
    A(action="face", t=t0 + 0.9, dur=0.5, name="determined")
    A(action="face", t=t1 - 0.6, dur=0.6, name="calm")
    D(action="face", t=t0 + 0.3, dur=0.4, name="calm")
    D(action="listen", t=t0 + 1.2, dur=max(0.5, t1 - t0 - 1.2 + tail))

    shots = []
    sh = lambda i, treat, beats, **kw: shots.append(dict(id=f"S{i:02d}", treatment=treat, t0=T[f"S{i:02d}"][0], t1=T[f"S{i:02d}"][1], beats=beats, segs=beats,
                                                          **{**dict(gp=[], transition_in="cut", sfx=[], phase="-", location="bedroom"), **kw}))
    sh(1, "skeleton", ["n01"], purpose="Wide Indian bedroom: A dozes on the bed edge; the phone lights up", camera=dict(target="stage", size="wide", move="push"), lighting=dict(mood="dim", moon=1.0, phone=1.0),
       gp=[dict(effect="arcs", anchor="phone_free", start=t_buzz - T["S01"][0], duration=1.0, intensity=0.8, relationship="the phone vibrating on the nightstand")], transition_in="fade")
    sh(2, "skeleton", ["n02"], purpose="He notices the phone: eyes lead, head follows", camera=dict(target="A.chest", size="medium", move="push"), lighting=dict(mood="dim", moon=1.0, phone=1.0))
    sh(3, "skeleton", ["n03"], purpose="He reaches for the phone (arm + hand animate) and grabs it", camera=dict(target="A.reach", size="two_reach", move="drift"), lighting=dict(mood="dim", moon=1.0, phone=1.0),
       gp=[dict(effect="rays", anchor="phone", start=0.3, duration=1.4, intensity=0.35, relationship="light from the screen")])
    sh(4, "skeleton", ["n04"], purpose="He reads the message: eyes move, head turns slightly", camera=dict(target="A.head", size="close", move="push"), lighting=dict(mood="fear", moon=0.7, phone=1.0),
       gp=[dict(effect="worry", anchor="temple", start=0.6, duration=1.2, intensity=0.9, relationship="something is wrong")])
    sh(5, "insert_ui", ["n05"], purpose="The suspicious bank notification", ui=dict(screen="sms", data=dict(sender="HDFC-KYC", time="अभी", text="आपका खाता 30 मिनट में ब्लॉक होगा। अभी वेरिफ़ाई करें: bit.ly/kyc-now")),
       lighting=dict(mood="fear"), gp=[dict(effect="ring", start=0.5, duration=1.0, anchor="ui", intensity=0.9, relationship="the urgent phrase")])
    sh(6, "skeleton", ["n06"], purpose="He stands up - full body visible", camera=dict(target="A.full", size="full", move="pull"), lighting=dict(mood="fear", moon=0.9, phone=1.0),
       gp=[dict(effect="ticks", anchor="eyes", start=0.05, duration=0.7, intensity=0.9, relationship="the jolt")])
    sh(7, "skeleton", ["n07"], purpose="Real skeletal walk: a few nervous steps", camera=dict(target="A.full", size="full", move="track"), lighting=dict(mood="fear", moon=0.9, phone=1.0))
    sh(8, "skeleton", ["n08"], purpose="His mother enters; two characters interact", camera=dict(target="A+D", size="two", move="drift"), lighting=dict(mood="dim", moon=0.9, phone=0.6, hall=1.0))
    sh(9, "skeleton", ["n09"], purpose="Another call: the phone vibrates, hand to ear", camera=dict(target="A.head", size="close", move="push"), lighting=dict(mood="fear", moon=0.7, phone=1.0, hall=1.0),
       gp=[dict(effect="arcs", anchor="phone", start=0.0, duration=0.9, intensity=0.9, relationship="the phone vibrating in his hand"), dict(effect="worry", anchor="temple", start=0.7, duration=1.2, intensity=0.9, relationship="dread")])
    sh(10, "skeleton", ["n10"], purpose="Camera pushes THROUGH the 2.5D layers", camera=dict(target="A+D", size="two", move="dolly_through"), lighting=dict(mood="fear", moon=0.6, phone=1.0, hall=1.0),
       gp=[dict(effect="smoke", anchor="low", start=0.0, duration=2.5, intensity=0.6, relationship="the room closing in")])
    sh(11, "procedural", ["n11"], purpose="Money / account / network visualisation", procedural=dict(type="money_flow", data=dict(amount=182000, **{"from": "आपकी बचत"}, to=["खाता 1", "खाता 2", "खाता 3"])), lighting=dict(mood="fear"))
    sh(12, "skeleton", ["n12"], purpose="He realises something is wrong: eyes, brows, head", camera=dict(target="A.head", size="close", move="push"), lighting=dict(mood="dim", moon=0.9, phone=0.5, hall=0.6),
       gp=[dict(effect="ticks", anchor="eyes", start=0.05, duration=0.7, intensity=0.95, relationship="the jolt of realisation")], transition_in="dip")
    sh(13, "skeleton", ["n13"], purpose="Final reveal: call ended, the lamp glows, wide pull-out", camera=dict(target="A+D", size="reveal", move="pull"), lighting=dict(mood="relief", moon=0.6, phone=0.0, hall=0.4, lamp=1.0),
       gp=[dict(effect="rays", anchor="lamp", start=0.3, duration=2.5, intensity=0.5, relationship="warm light returns")])
    for s in shots:
        s["actions"] = [a for a in acts if s["t0"] - 1.0 <= a["t"] < s["t1"]]
    sfx = [dict(t=round(t_buzz, 3), kind="buzz", gain=0.9), dict(t=round(t_buzz + 0.05, 3), kind="ding", gain=0.5), dict(t=round(T["S09"][0] + 0.02, 3), kind="buzz", gain=0.9),
           dict(t=round(T["S09"][0] + 0.05, 3), kind="ding", gain=0.5), dict(t=round(T["S12"][0] + 0.05, 3), kind="impact", gain=0.8), dict(t=round(T["S12"][0] + 0.55, 3), kind="heartbeat", gain=0.8),
           dict(t=round(T["S06"][0] + 0.1, 3), kind="impact", gain=0.5)]
    for i in range(1, 13):
        sfx.append(dict(t=round(cuts[i] - 0.06, 3), kind="whoosh", gain=0.22))
    mood = [(0.0, T["S04"][0], "dim"), (T["S04"][0], T["S12"][0], "fear"), (T["S12"][0], T["S13"][0], "dim"), (T["S13"][0], dur, "relief")]
    plan = dict(kind="skeleton_short", version=1, title=TITLE, story_id=story_id, seed=seed, fps=FPS, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name=name,
                environment=dict(family="bedroom_wide", variation=dict(palette=VAR.seed_int(story_id, "env", "pal") % 3), seed=VAR.seed_int(story_id, "env", "seed") % 1000),
                characters=cast(story_id), cast_in_short=["A", "D"], narration=dict(segments=nar["segments"], audio=nar.get("audio"), tts=tts or nar.get("tts", "unknown"), tempo=nar.get("tempo", 1.0)),
                targets=TARGETS, shots=shots, sfx=sfx, mood_track=mood, title_card=dict(t0=round(dur - 1.7, 3), t1=dur, text=TITLE), lamp_on=round(T["S13"][0] + 0.3, 3),
                hall_on=round(T["S08"][0] - 0.5, 3))
    return plan
