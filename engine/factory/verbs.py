"""Character verbs: reusable, parameterised acting phrases that only write channels (no rendering, no story knowledge).

Every verb takes (perf, t, dur, **params) and returns the time it ends. The visual director chooses verbs and timing from the story;
this file is the ACTING LIBRARY (anticipation, hesitation, overshoot come from the primitives in engine.shorts.performance).
Coordinates are bust-canvas px (see engine/shorts/rig2.py).
"""
import math

from engine.shorts import performance as P
from engine.shorts.rig2 import REST_A, REST_B

READ_POS = (770.0, 1012.0)         # phone held at the chest, readable
EAR_POS = (812.0, 600.0)           # wrist position that puts the phone at the ear
LAP_POS = (700.0, 1330.0)
CHEST_POS = (650.0, 905.0)


def idle(perf, t, dur, **k):
    return t + dur


def look_at(perf, t, dur, target="ahead", amount=1.0, **k):
    P.look(perf, t, target, min(dur, 0.8), amount, "smooth")
    return t + dur


def hesitate(perf, t, dur, target="phone", **k):
    P.hesitate(perf, t, target, min(dur, 1.4), 1.0)
    P.freeze(perf, t, min(0.4, dur * 0.3))
    return t + dur


def shrug(perf, t, dur, amount=0.9, **k):
    P.shrug(perf, t, amount, min(dur, 1.1))
    return t + dur


def startle(perf, t, dur, amount=0.9, **k):
    P.startle(perf, t, amount)
    P.freeze(perf, t + 0.25, min(0.6, dur))
    return t + dur


def freeze(perf, t, dur, **k):
    P.freeze(perf, t, dur)
    return t + dur


def lean(perf, t, dur, amount=0.8, **k):
    P.lean(perf, t, dur, amount)
    return t + dur


def tremble(perf, t, dur, amount=0.6, **k):
    P.tremble(perf, t, dur, amount, 0.8)
    return t + dur


def shake_head(perf, t, dur, **k):
    c = perf.channel("roll:shake")
    c.key(t - 0.01, 0.0)
    for i in range(5):
        c.key(t + 0.18 * (i + 0.5), (5.0 if i % 2 == 0 else -5.0) * (1 - i / 6), "smooth")
    c.key(t + 1.1, 0.0, "smooth")
    return t + dur


def nod(perf, t, dur, **k):
    c = perf.channel("hdy:nod")
    c.key(t - 0.01, 0.0)
    for i in range(3):
        c.key(t + 0.2 * (i + 0.5), 9.0 * (1 - i / 4), "smooth")
        c.key(t + 0.2 * (i + 1), 0.0, "smooth")
    return t + dur


def pickup_phone(perf, t, dur=1.3, **k):
    """The phone rises from below into the hand: grip closes, arm lifts, eyes drop to the screen."""
    P.hold_phone(perf, t)
    P.arm_to(perf, "B", t - 0.01, t, LAP_POS[0], LAP_POS[1], "linear")
    P.hand_curl(perf, t, t + 0.2, 0.85, "out")
    P.arm_to(perf, "B", t, t + dur, *READ_POS, "smooth")
    P.phone_rot(perf, t, t + dur, -6.0)
    P.look(perf, t + 0.15, "phone", 0.7, 1.0, "smooth")
    P.converge(perf, t + 0.5, t + dur, 0.9)
    return t + dur


def read_phone(perf, t, dur, **k):
    if not perf.ch["aB_hold"](t):
        pickup_phone(perf, t, 1.0)
    for i in range(int(dur / 0.34)):
        perf.channel("gx:read").key(t + 0.05 + 0.34 * i, (-0.3 if i % 2 == 0 else 0.32), "out")
    perf.channel("gy:read").key(t, 0.35, "smooth")
    perf.channel("gy:read").key(t + dur, 0.0, "smooth")
    return t + dur


def phone_to_ear(perf, t, dur=1.0, **k):
    """Lift the phone to the ear (screen turns away from camera); head tilts slightly toward it."""
    if not perf.ch["aB_hold"](t):
        pickup_phone(perf, t - 0.9, 0.9)
    P.arm_to(perf, "B", t, t + dur, *EAR_POS, "smooth")
    P.phone_rot(perf, t, t + dur, -14.0)
    c = perf.ch["aB_ear"]
    c.key(t + dur * 0.6, 0.0)
    c.key(t + dur * 0.7, 1.0, "linear")
    rc = perf.channel("roll:ear")
    rc.key(t, 0.0)
    rc.key(t + dur, 3.5, "smooth")
    return t + dur


def phone_down(perf, t, dur=1.0, **k):
    c = perf.ch["aB_ear"]
    c.key(t - 0.01, c(t))
    c.key(t, 0.0, "linear")
    rc = perf.channel("roll:ear")
    rc.key(t, rc(t) if rc.keys else 0.0)
    rc.key(t + dur, 0.0, "smooth")
    P.arm_to(perf, "B", t, t + dur, *LAP_POS, "smooth")
    P.hold_phone(perf, t + dur, False)
    P.hand_curl(perf, t + dur - 0.2, t + dur, 0.3)
    return t + dur


def hand_to_chest(perf, t, dur=0.9, **k):
    P.arm_to(perf, "B", t, t + dur, *CHEST_POS, "smooth")
    P.hand_curl(perf, t, t + dur, 0.55)
    return t + dur


def hands_to_face(perf, t, dur=1.0, **k):
    P.arm_to(perf, "A", t, t + dur, 560.0, 700.0, "smooth")
    P.arm_to(perf, "B", t, t + dur, 720.0, 690.0, "smooth")
    P.hand_curl(perf, t, t + dur, 0.6)
    return t + dur


def gesture(perf, t, dur, **k):
    x, y = 930.0, 960.0
    P.arm_to(perf, "B", t, t + 0.5, x, y, "smooth")
    for i in range(max(1, int(dur / 0.6))):
        P.arm_to(perf, "B", t + 0.5 + 0.6 * i, t + 0.5 + 0.6 * i + 0.3, x + 30 * (1 if i % 2 == 0 else -1), y - 40 * (1 if i % 2 == 0 else 0), "smooth")
    P.hand_curl(perf, t, t + 0.5, 0.1)
    return t + dur


VERBS = dict(idle=idle, look_at=look_at, hesitate=hesitate, shrug=shrug, startle=startle, freeze=freeze, lean=lean, tremble=tremble,
             shake_head=shake_head, nod=nod, pickup_phone=pickup_phone, read_phone=read_phone, phone_to_ear=phone_to_ear,
             phone_down=phone_down, hand_to_chest=hand_to_chest, hands_to_face=hands_to_face, gesture=gesture)
