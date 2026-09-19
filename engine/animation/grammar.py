"""MOTION GRAMMAR (spec sec. 5/6): semantic actions in, channel animation out. Nothing here knows a frame number or a Blender key.

    {"character": "neha", "action": "reach_for_phone", "emotion": "hesitant", "intensity": 0.7}

An ACTION is a composition:   base verb  x  STYLE (from the emotion)  x  intensity.
    reach_for_phone + hesitant + 0.7  ->  gaze first, freeze, two-stage reach with a doubt pause, slower, slight tremor
    reach_for_phone + confident       ->  direct, quicker, no pause
The same action names work for any character/DNA. Add a verb = write one function; add a style = add one row.
"""
from engine.factory import verbs as V
from engine.shorts import performance as P

STYLES = {   # emotion -> timing/amplitude modifiers
    "neutral": dict(speed=1.0, hesitate=0.0, tremble=0.0, jerk=0.0, lean=0.0, amp=1.0),
    "hesitant": dict(speed=0.72, hesitate=1.0, tremble=0.12, jerk=0.0, lean=-0.2, amp=0.85),
    "fearful": dict(speed=1.15, hesitate=0.6, tremble=0.5, jerk=1.0, lean=-0.5, amp=0.9),
    "confident": dict(speed=1.3, hesitate=0.0, tremble=0.0, jerk=0.0, lean=0.3, amp=1.1),
    "curious": dict(speed=0.9, hesitate=0.3, tremble=0.0, jerk=0.0, lean=0.7, amp=1.0),
    "angry": dict(speed=1.35, hesitate=0.0, tremble=0.1, jerk=1.0, lean=0.4, amp=1.2),
    "sad": dict(speed=0.6, hesitate=0.2, tremble=0.0, jerk=0.0, lean=-0.4, amp=0.7),
    "nervous": dict(speed=1.05, hesitate=0.5, tremble=0.3, jerk=0.5, lean=-0.2, amp=0.9),
    "relieved": dict(speed=0.8, hesitate=0.0, tremble=0.0, jerk=0.0, lean=-0.3, amp=0.9),
    "suspicious": dict(speed=0.85, hesitate=0.6, tremble=0.0, jerk=0.0, lean=0.2, amp=0.9),
    "shocked": dict(speed=1.4, hesitate=0.0, tremble=0.3, jerk=1.0, lean=-0.6, amp=1.2)}
EMOTION_FACE = dict(hesitant="concerned", fearful="fear", confident="driven", curious="explaining", angry="angry", sad="solemn", nervous="uneasy", relieved="calm",
                    suspicious="suspicious", shocked="shock", neutral=None)


def _style(emotion, intensity):
    s = dict(STYLES.get(emotion, STYLES["neutral"]))
    k = 0.4 + 0.6 * max(0.0, min(1.0, intensity))
    for key in ("hesitate", "tremble", "jerk"):
        s[key] *= k
    s["speed"] = 1.0 + (s["speed"] - 1.0) * k
    s["amp"] = 1.0 + (s["amp"] - 1.0) * k
    return s


def _reach(perf, t, dur, st, **k):
    if st["hesitate"] > 0.3:
        V.hesitate(perf, t - 0.5, 0.9 / st["speed"], target="phone")
        t += 0.4
    end = V.pickup_phone(perf, t, dur / st["speed"])
    if st["tremble"] > 0.05:
        P.tremble(perf, t, dur, st["tremble"], 0.5)
    return end


def _talk(perf, t, dur, st, **k):
    """Mouth flaps at speech rhythm (seeded by the performance seed) - for on-screen speakers."""
    c = perf.channel("mtalk:talk")
    n = int(dur * 5.2)
    for i in range(n):
        a = 0.18 + 0.42 * abs(((i * 7919 + int(perf.phases[0] * 1000)) % 97) / 97.0 - 0.5) * 2
        c.key(t + i / 5.2, a * st["amp"], "smooth")
        c.key(t + (i + 0.55) / 5.2, 0.02, "smooth")
    c.key(t + dur, 0.0, "smooth")
    P.emotion(perf, t, "explaining", 0.15)
    return t + dur


def _type(perf, t, dur, st, **k):
    """Typing at a desk: both forearms tick at keyboard height (hands live behind the desk edge; shoulders/forearms show the motion)."""
    for i in range(int(dur * 4)):
        P.arm_to(perf, "A", t + i * 0.25, t + i * 0.25 + 0.12, 470 + 12 * (i % 3), 1290 - 14 * (i % 2), "smooth")
        P.arm_to(perf, "B", t + i * 0.25 + 0.12, t + i * 0.25 + 0.24, 740 - 12 * (i % 3), 1290 - 14 * ((i + 1) % 2), "smooth")
    P.look(perf, t, "laptop", 0.6, 0.8, "smooth")
    return t + dur


def _walk(perf, t, dur, st, **k):
    """Bust-height walking: the body bobs and sways in step; the CAMERA tracks laterally (see camera grammar 'tracking') so the world slides past."""
    for name, amp in (("bdy:walk", 9.0), ("roll:walk", 1.6), ("hdy:walk", 4.0)):
        c = perf.channel(name)
        for i in range(int(dur * 2.0)):
            c.key(t + i * 0.5, amp * (1 if i % 2 == 0 else -0.6), "smooth")
        c.key(t + dur, 0.0, "smooth")
    return t + dur


def _point(perf, t, dur, st, **k):
    P.arm_to(perf, "B", t, t + 0.5 / st["speed"], 960.0, 800.0, "out")
    P.hand_curl(perf, t, t + 0.4, 0.15)
    P.hand_curl(perf, t + dur, t + dur + 0.3, 0.3)
    P.arm_to(perf, "B", t + dur, t + dur + 0.6, *V.LAP_POS, "smooth")
    return t + dur


def _listen(perf, t, dur, st, **k):
    P.look(perf, t, "other_right", 0.6, 0.6, "smooth")
    V.nod(perf, t + dur * 0.5, 0.8)
    return t + dur


def _turn(perf, t, dur, st, target="other_left", **k):
    P.hesitate(perf, t, target, min(dur, 1.2) / st["speed"], 1.0) if st["hesitate"] > 0.3 else P.look(perf, t, target, 0.6 / st["speed"], 1.0, "smooth")
    return t + dur


def _stand(perf, t, dur, st, **k):
    c = perf.channel("bdy:stand")
    c.key(t - 0.01, 0.0)
    c.key(t + 0.9, -16.0, "out")
    return t + dur


def _sit(perf, t, dur, st, **k):
    c = perf.channel("bdy:stand")
    c.key(t - 0.01, c(t) if c.keys else 0.0)
    c.key(t + 0.9, 0.0, "smooth")
    return t + dur


def _legacy(name):
    def f(perf, t, dur, st, **k):
        return V.VERBS[name](perf, t, dur, **k)
    return f


ACTIONS = {
    "reach_for_phone": _reach, "grab_phone": _reach, "hold_phone": _legacy("pickup_phone"), "read_phone": _legacy("read_phone"), "phone_to_ear": _legacy("phone_to_ear"),
    "put_down_phone": _legacy("phone_down"), "talk": _talk, "typing": _type, "type": _type, "walk": _walk, "walking": _walk, "point": _point, "pointing": _point,
    "gesture": _legacy("gesture"), "listen": _listen, "listening": _listen, "turn": _turn, "stand": _stand, "sit": _sit, "hesitate": _legacy("hesitate"), "shrug": _legacy("shrug"),
    "startle": _legacy("startle"), "freeze": _legacy("freeze"), "lean": _legacy("lean"), "tremble": _legacy("tremble"), "shake_head": _legacy("shake_head"), "nod": _legacy("nod"),
    "hand_to_chest": _legacy("hand_to_chest"), "hands_to_face": _legacy("hands_to_face"), "idle": _legacy("idle"),
    "look_at": lambda perf, t, dur, st, target="ahead", **k: (P.look(perf, t, target, min(dur, 0.8) / st["speed"], 1.0, "smooth"), t + dur)[1],
    "pickup_phone": _legacy("pickup_phone")}


def perform(perf, action, t, dur, emotion="neutral", intensity=0.5, **params):
    """Expand ONE semantic action into channel keys. Returns the end time."""
    if action not in ACTIONS:
        raise KeyError(f"unknown action '{action}' (have {sorted(ACTIONS)})")
    st = _style(emotion, intensity)
    if st["lean"] and action not in ("walk", "walking", "stand", "sit"):
        P.lean(perf, t, min(dur, 1.4), 0.7 * st["lean"] * st["amp"])
    if st["jerk"] > 0.3 and action in ("startle", "reach_for_phone", "grab_phone", "turn"):
        P.startle(perf, t, 0.35 * st["jerk"])
    return ACTIONS[action](perf, t, dur, st, **params)


def emotion_to_face(emotion):
    return EMOTION_FACE.get(emotion)


def supported():
    return sorted(ACTIONS), sorted(STYLES)
