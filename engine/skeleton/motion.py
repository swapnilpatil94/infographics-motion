"""SEMANTIC MOTION GRAMMAR for the full-body skeleton (spec sec. 5).

    {"action": "reach_for_phone", "emotion": "hesitant", "intensity": 0.7}      # NOT {"frame": 34, "rotation": 17}

A `Performance` holds animation CHANNELS (the rig's semantic controls - see engine/blender/skeleton_scene.py for the exact list). An ACTION is a
function that writes channel keys for a time window; the same function drives any character because it only knows the character's PROPORTIONS
(limb lengths, hip/shoulder heights) - a tall or heavy character reaches, walks and sits with its own stride, reach and seat height.
STYLE (from the emotion) and INTENSITY modulate speed, amplitude, hesitation, tremor and lean. Nothing here names a frame or a bone rotation.

Actions: idle blink look_left look_right look_down look_at_phone head_turn head_tilt walk sit stand reach grab hold_phone read_phone point gesture
         talk listen fear surprise confusion realization shrug (+ aliases reach_for_phone, pickup_phone, look_at).
IK: hand and foot targets are the animated quantities; Blender's IK solver (limited 2-bone chains) produces the joint angles.
"""
import math
import random

from engine.animation.grammar import STYLES, _style
from engine.shorts.performance import Channel, ease
from engine.skeleton import rig_def as R

FACE_CH = ["gaze_x", "gaze_y", "blink", "wide", "lid", "narrow", "brow_raise", "brow_tilt", "brow_asym", "mouth_open", "mouth_smile", "mouth_worried",
           "vis_A", "vis_E", "vis_I", "vis_O", "vis_U", "vis_shocked"]
POSE_CH = ["root_x", "root_y", "pelvis_dx", "pelvis_dy", "spine_rot", "chest_rot", "neck_rot", "head_rot", "hair_rot", "hand_L_rot", "hand_R_rot", "shrug",
           "foot_L_rot", "foot_R_rot", "phone_vis", "fingers_vis", "phone_glow", "phone_flat", "card_vis", "money_vis", "hand_L_pose_id", "hand_R_pose_id"]
IK_CH = ["hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y"]

# emotion -> face parameters (same table the bust rig uses: one expression vocabulary for both rigs)
EMO = {
    "calm": dict(raise_=0.1, tilt=0.0, asym=0, wide=0.0, lid=0.0, smile=0.5, mopen=0.0), "smile": dict(raise_=0.2, tilt=0.0, asym=0, wide=0.0, lid=0.0, smile=0.8, mopen=0.0),
    "happy": dict(raise_=0.4, tilt=0.0, asym=0, wide=0.0, lid=0.0, smile=1.0, mopen=0.35), "tired": dict(raise_=-0.25, tilt=0.35, asym=0, wide=0.0, lid=0.7, smile=-0.15, mopen=0.0),
    "blank": dict(raise_=0.0, tilt=0.0, asym=0, wide=0.0, lid=0.15, smile=0.0, mopen=0.0), "serious": dict(raise_=-0.55, tilt=-0.45, asym=0, wide=0.0, lid=0.25, smile=-0.2, mopen=0.0),
    "concerned": dict(raise_=0.5, tilt=0.9, asym=0, wide=0.0, lid=0.0, smile=-0.5, mopen=0.1), "uneasy": dict(raise_=0.6, tilt=1.0, asym=0, wide=0.15, lid=0.0, smile=-0.6, mopen=0.18),
    # ---- the 11 semantic emotions of Factory V2 (eyes state, brow state, mouth state)
    "neutral": dict(raise_=0.0, tilt=0.0, asym=0, wide=0.0, lid=0.05, smile=0.0, mopen=0.0), "curious": dict(raise_=0.45, tilt=-0.1, asym=0.35, wide=0.2, lid=0.0, smile=0.15, mopen=0.0),
    "worried": dict(raise_=0.45, tilt=1.0, asym=0, wide=0.1, lid=0.0, smile=0.0, mopen=0.06, worried=1.0), "surprise": dict(raise_=1.0, tilt=0.2, asym=0, wide=1.0, lid=0.0, smile=0.0, mopen=0.8),
    "realization": dict(raise_=0.9, tilt=0.3, asym=0, wide=0.85, lid=0.0, smile=-0.1, mopen=0.5), "relief": dict(raise_=0.15, tilt=0.5, asym=0, wide=0.0, lid=0.35, smile=0.55, mopen=0.1),
    "sadness": dict(raise_=-0.15, tilt=1.0, asym=0, wide=0.0, lid=0.55, smile=-0.6, mopen=0.0, worried=0.6), "anger": dict(raise_=-0.85, tilt=-1.0, asym=0, wide=0.0, lid=0.0, narrow=0.85, smile=-0.8, mopen=0.15),
    "determination": dict(raise_=-0.55, tilt=-0.6, asym=0, wide=0.0, lid=0.0, narrow=0.5, smile=-0.05, mopen=0.0),
    "shock": dict(raise_=1.0, tilt=0.4, asym=0, wide=1.0, lid=0.0, smile=-0.1, mopen=0.85), "fear": dict(raise_=0.9, tilt=1.0, asym=0, wide=0.85, lid=0.0, smile=-0.7, mopen=0.5),
    "angry": dict(raise_=-0.9, tilt=-1.0, asym=0, wide=0.0, lid=0.3, smile=-0.85, mopen=0.2), "suspicious": dict(raise_=-0.2, tilt=-0.2, asym=0.9, wide=0.0, lid=0.5, smile=-0.2, mopen=0.0),
    "confused": dict(raise_=0.3, tilt=0.5, asym=0.8, wide=0.1, lid=0.0, smile=-0.35, mopen=0.1), "realize": dict(raise_=0.85, tilt=0.2, asym=0, wide=0.9, lid=0.0, smile=-0.15, mopen=0.55),
    "dread": dict(raise_=0.4, tilt=1.0, asym=0, wide=0.4, lid=0.05, smile=-0.8, mopen=0.1), "determined": dict(raise_=-0.6, tilt=-0.5, asym=0, wide=0.0, lid=0.2, smile=-0.1, mopen=0.0),
}
FACE_MAP = dict(raise_="brow_raise", tilt="brow_tilt", asym="brow_asym", wide="wide", lid="lid", smile="mouth_smile", mopen="mouth_open", narrow="narrow", worried="mouth_worried")


class Performance:
    """Channels + geometry of ONE character. `world` gives the props/furniture the actions relate to (seat height, phone position ...), all in rig space."""

    def __init__(self, P, seed=0, world=None, facing=1, origin=(0.0, 0.0), resolver=None, personality=None):
        self.P, self.J = P, R.rest_joints(P)
        self.seed = seed
        self.rng = random.Random(seed)
        self.facing, self.origin = facing, tuple(origin)
        self.resolver = resolver                              # (target_id, t) -> WORLD (x, y): the scene's spatial-target registry
        self.personality = personality or dict(amp=1.0, speed=1.0)
        self.so = R.side_offsets(P)
        self.world = dict(seat_h=P["hip_y"] * 0.56, floor=0.0)
        self.world.update(world or {})
        self.ch = {n: Channel(0.0) for n in POSE_CH + FACE_CH}
        JL, JR = R.side_joints(P, "L"), R.side_joints(P, "R")
        for n, v in dict(hand_L_x=JL["wrist"][0], hand_L_y=JL["wrist"][1], hand_R_x=JR["wrist"][0], hand_R_y=JR["wrist"][1],
                         foot_L_x=JL["ankle"][0] - 16, foot_L_y=P["foot_h"], foot_R_x=JR["ankle"][0] + 24, foot_R_y=P["foot_h"]).items():
            self.ch[n] = Channel(v)
        self.events = []                                  # (t, kind, data) - prop/sfx cues for the compositor
        self.no_blink = []
        self.mood = "blank"
        self.hand_pose = {"L": "closed", "R": "closed"}
        self.ch["hand_L_pose_id"] = Channel(1.0)                  # relaxed hands by default (pose id 1 = closed)
        self.ch["hand_R_pose_id"] = Channel(1.0)

    def to_rig(self, world_xy):
        return ((world_xy[0] - self.origin[0]) * self.facing, self.origin[1] - world_xy[1])

    def to_world(self, rig_xy):
        return (self.origin[0] + self.facing * rig_xy[0], self.origin[1] - rig_xy[1])

    def target_rig(self, target, t):
        """A semantic target (id string like 'PHONE' / 'PERSON_B', {'world': (x, y)}, {'rig': (x, y)} or a bare rig tuple) -> rig-space point."""
        if isinstance(target, dict):
            if "rig" in target:
                return tuple(target["rig"])
            if "world" in target:
                return self.to_rig(target["world"])
        if isinstance(target, (list, tuple)):                 # a bare tuple is ALREADY rig space (v1 convention)
            return tuple(target)
        if self.resolver is None:
            raise KeyError(f"no target resolver installed (target {target!r})")
        return self.to_rig(self.resolver(target, t))

    # ---- helpers
    def v(self, name, t):
        return self.ch[name](t)

    def to(self, name, t0, t1, value, e="smooth"):
        """Anchor the channel at its current value at t0, then ease to `value` at t1."""
        ch = self.ch[name]
        cur = ch(t0)
        ch.key(t0, cur, "linear")
        ch.key(t1, value, e)

    def hold(self, name, t):
        self.ch[name].key(t, self.ch[name](t), "linear")

    def hip(self, t):
        return (self.v("root_x", t) + self.v("pelvis_dx", t), self.P["hip_y"] + self.v("root_y", t) + self.v("pelvis_dy", t))

    def shoulder(self, t):
        """Absolute shoulder-joint position (approximate: follows pelvis + spine lean)."""
        lean = math.radians(self.v("spine_rot", t) + self.v("chest_rot", t))
        hx, hy = self.hip(t)
        h = self.P["shoulder_joint_y"] - self.P["hip_y"]
        return (hx + h * math.sin(lean), hy + h * math.cos(lean))

    def emotion(self, t, name, dur=0.25, amount=1.0):
        e = EMO[name]
        for k, ch_name in FACE_MAP.items():
            self.to(ch_name, t, t + dur, e.get(k, 0.0) * amount, "smooth")
        self.mood = name


# ------------------------------------------------------------------------------------------------------------------ primitive controls
def _hand_side(kw):
    return kw.get("hand", "R")


REST_REACH = 0.95


def _arm_rest(perf, side, t):
    """Where a relaxed hand hangs (absolute), following the body."""
    sh = perf.shoulder(t)
    a = math.radians(6 if side == "R" else -3)                      # arms hang by the sides (v3.5: the old +9/+5 deg forward lean + 0.93 reach put both hands clasped in front of the pelvis)
    r = (perf.P["upper_arm"] + perf.P["forearm"]) * REST_REACH
    return (sh[0] + perf.so["s" + side] + r * math.sin(a), sh[1] - r * math.cos(a))          # the near/far shoulder sit at different x in a 3/4 view


def hand_to(perf, side, t0, t1, target, e="smooth"):
    perf.to(f"hand_{side}_x", t0, t1, target[0], e)
    perf.to(f"hand_{side}_y", t0, t1, target[1], e)


def gaze(perf, t, dur, gx, gy, head=0.0, e="out_back"):
    perf.to("gaze_x", t, t + dur, gx, e)
    perf.to("gaze_y", t, t + dur, gy, e)
    if head is not None:
        perf.to("head_rot", t + 0.05, t + dur + 0.1, head, "smooth")


def _tremble(perf, t0, t1, amount, ch=("hand_R_x", "hand_R_y"), hz=9.0):
    if amount <= 0.02:
        return
    n = int((t1 - t0) * 30)
    for i in range(n):
        tt = t0 + i / 30
        for k, name in enumerate(ch):
            perf.ch[name].keys.append((tt, perf.ch[name](tt) + amount * 3.0 * math.sin(2 * math.pi * hz * tt + k * 1.7), "linear"))
        perf.ch[ch[0]].keys.sort(key=lambda x: x[0])
        perf.ch[ch[1]].keys.sort(key=lambda x: x[0])


# ------------------------------------------------------------------------------------------------------------------ actions
def a_idle(perf, t, dur, st, **kw):
    """Breathing + tiny weight shifts (never a frozen pose)."""
    n = max(1, int(dur * 2))
    for i in range(n + 1):
        tt = t + dur * i / n
        b = math.sin(2 * math.pi * 0.27 * (tt + perf.seed * 0.13))
        perf.ch["chest_rot"].key(tt, perf.ch["chest_rot"](t) + 0.8 * b * st["amp"], "smooth")
        perf.ch["head_rot"].key(tt, perf.ch["head_rot"](t) + 0.6 * math.sin(2 * math.pi * 0.17 * tt + 1.3), "smooth")
    return t + dur


def a_blink(perf, t, dur, st, **kw):
    perf.ch["blink"].key(t, 0.0, "linear")
    perf.ch["blink"].key(t + 0.05, 1.0, "linear")
    perf.ch["blink"].key(t + 0.13, 0.0, "out")
    return t + 0.13


def a_look(kind):
    def f(perf, t, dur, st, **kw):
        d = min(dur, 0.55) / st["speed"]
        if kind == "left":                                  # 'left' = behind the character (it faces +x)
            gaze(perf, t, d, -1.0, 0.05, head=-5.0)
        elif kind == "right":
            gaze(perf, t, d, 1.0, 0.05, head=4.0)
        elif kind == "down":
            gaze(perf, t, d, 0.35, -1.0, head=9.0)
        elif kind == "up":
            gaze(perf, t, d, 0.4, 0.9, head=-6.0)
        elif kind == "ahead":
            gaze(perf, t, d, 0.6, 0.0, head=0.0)
        return t + d
    return f


def a_look_at(perf, t, dur, st, target="phone", **kw):
    """look_at_phone / look_at(target): eyes lead, head follows 0.08 s later (the natural saccade-then-turn)."""
    tx, ty = kw.get("point", (perf.hip(t)[0] + 160, perf.P["shoulder_y"] - 220))
    hx, hy = perf.hip(t)[0], perf.P["neck_top_y"] + perf.v("root_y", t) + perf.v("pelvis_dy", t) + perf.P["head"] * 0.45
    dx, dy = tx - hx, ty - hy
    gx, gy = max(-1, min(1, dx / 260.0)), max(-1, min(1, dy / 200.0))
    pitch = max(-14.0, min(16.0, -math.degrees(math.atan2(dy, max(dx, 60.0))) * 0.55))
    d = min(dur, 0.5) / st["speed"]
    perf.to("gaze_x", t, t + d * 0.7, gx, "out_back")
    perf.to("gaze_y", t, t + d * 0.7, gy, "out_back")
    perf.to("head_rot", t + 0.08, t + d + 0.12, pitch, "smooth")
    perf.to("neck_rot", t + 0.08, t + d + 0.15, pitch * 0.35, "smooth")
    return t + d


def a_head_turn(perf, t, dur, st, direction=1, **kw):
    d = min(dur, 0.6) / st["speed"]
    gaze(perf, t, d, 0.9 * direction, 0.0, head=6.0 * direction * st["amp"])
    return t + d


def a_head_tilt(perf, t, dur, st, angle=10.0, **kw):
    perf.to("head_rot", t, t + min(dur, 0.6), angle * st["amp"], "smooth")
    perf.to("neck_rot", t, t + min(dur, 0.6), angle * 0.3 * st["amp"], "smooth")
    return t + min(dur, 0.6)


def a_shrug(perf, t, dur, st, **kw):
    perf.to("shrug", t, t + 0.18, 1.0, "out")
    perf.to("shrug", t + 0.18 + 0.4, t + 0.9, 0.0, "smooth")
    perf.to("head_rot", t, t + 0.2, 6.0, "smooth")
    return t + 0.9


def a_sit(perf, t, dur, st, seat=None, **kw):
    """Standing -> seated at the given seat height. Pelvis lowers over planted feet; torso leans forward then uprights; knees flex by IK."""
    P, w = perf.P, perf.world
    d = max(dur, 0.9) / st["speed"]
    sit_hip = (seat if seat is not None else w["seat_h"]) + 30 * P["k"]
    x0 = perf.v("root_x", t)
    fx = max(perf.v("foot_R_x", t), x0 + 30)
    perf.to("pelvis_dy", t, t + d, sit_hip - P["hip_y"], "smooth")
    perf.to("root_x", t, t + d, x0 - 190 * P["k"], "smooth")                     # hips move BACK onto the seat while the feet stay planted
    perf.hold("foot_L_x", t)
    perf.hold("foot_R_x", t)
    lean = 14.0 * (1 - 0.4 * st["lean"]) * st["amp"]
    perf.to("spine_rot", t, t + d * 0.5, lean, "out")
    perf.to("spine_rot", t + d * 0.5, t + d, 0.0, "smooth")
    perf.to("head_rot", t, t + d * 0.5, -6.0, "smooth")
    perf.to("head_rot", t + d * 0.5, t + d, 0.0, "smooth")
    return t + d


def a_stand(perf, t, dur, st, **kw):
    """Seated -> standing: lean forward (weight over feet), hips rise and move forward over the planted feet, torso uprights, head lifts."""
    P = perf.P
    d = max(dur, 1.0) / st["speed"]
    x0 = perf.v("root_x", t)
    fx = 0.5 * (perf.v("foot_L_x", t) + perf.v("foot_R_x", t))
    perf.hold("foot_L_x", t)
    perf.hold("foot_R_x", t)
    perf.to("root_x", t + 0.15 * d, t + d, fx - 6, "smooth")
    perf.to("pelvis_dy", t + 0.2 * d, t + d, -9.0 * P["k"], "smooth")
    lean = 26.0 * st["amp"]
    perf.to("spine_rot", t, t + d * 0.38, lean, "out")
    perf.to("spine_rot", t + d * 0.45, t + d, 0.0, "smooth")
    perf.to("head_rot", t, t + d * 0.4, -12.0, "smooth")
    perf.to("head_rot", t + d * 0.5, t + d, 0.0, "smooth")
    if perf.v("phone_vis", t) > 0.5:                                  # v3.5: a phone in the hand travels WITH the body (it used to lag behind the rising shoulder and the arm went taut)
        sh0 = perf.shoulder(t)
        off = (perf.v("hand_R_x", t) - sh0[0], perf.v("hand_R_y", t) - sh0[1])
        tt_prev = t
        for i in range(1, 7):
            tt = t + d * i / 6.0
            s_ = perf.shoulder(tt)
            hand_to(perf, "R", tt_prev, tt, (s_[0] + off[0], s_[1] + off[1]), "smooth")
            tt_prev = tt
        return t + d
    # hands push off the knees while rising
    sh = perf.shoulder(t)
    for side in ("R",):
        knee_x = perf.v("foot_R_x", t) - 10
        hand_to(perf, side, t, t + d * 0.3, (knee_x, perf.world["seat_h"] + 110 * P["k"]), "smooth")
        hand_to(perf, side, t + d * 0.55, t + d + 0.25, _arm_rest(perf, side, t + d), "smooth")
    return t + d


def a_walk(perf, t, dur, st, speed=None, **kw):
    """Procedural gait: root advances with an eased speed profile; stance feet are PLANTED in the world (no sliding), swing feet arc; pelvis bobs,
    arms counter-swing, spine counter-rotates. Stride, cadence and swing scale with the character's own leg length."""
    P = perf.P
    leg = P["thigh"] + P["shin"]
    v = (speed if speed is not None else 300.0 * P["k"]) * (0.85 + 0.3 * st["speed"] - 0.3) * (1.0 if st["speed"] >= 1.0 else st["speed"]) * kw.get("speed_scale", 1.0)
    Ls = 0.5 * leg * 0.98 * kw.get("stride_scale", 1.0)          # step length
    T = 2 * Ls / max(v, 1.0)                                     # gait cycle (s)
    a = 0.6 * Ls
    ramp = min(0.4, dur * 0.3)
    x_start = perf.v("root_x", t)
    lift = 42.0 * P["k"] * st["amp"]
    bob = 11.0 * P["k"] * st["amp"]
    base_h = perf.v("pelvis_dy", t)
    sh0 = perf.shoulder(t)
    fL0 = (perf.v("foot_L_x", t), perf.v("foot_L_y", t))
    fR0 = (perf.v("foot_R_x", t), perf.v("foot_R_y", t))
    stand_off = dict(L=-16.0 * P["k"], R=24.0 * P["k"])
    n = int(dur * 30)
    x = x_start
    keys = {k: [] for k in ("root_x", "pelvis_dy", "spine_rot", "head_rot", "hair_rot", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y", "foot_L_rot", "foot_R_rot",
                            "hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "chest_rot")}
    prev_speed = 0.0
    for i in range(n + 1):
        tt = t + i / 30.0
        u = i / 30.0
        w = min(1.0, u / ramp, (dur - u) / ramp) if ramp > 0 else 1.0
        w = ease("smooth", max(0.0, w))
        sp = v * w
        if i:
            x += 0.5 * (sp + prev_speed) / 30.0
        prev_speed = sp
        ph = (u / T) if T > 0 else 0.0
        keys["root_x"].append((tt, x))
        keys["pelvis_dy"].append((tt, base_h - bob * w * (1 - math.cos(4 * math.pi * ph)) * 0.5 - 0 * bob))
        keys["spine_rot"].append((tt, 3.0 * st["lean"] * w + 2.2 * w * math.sin(2 * math.pi * ph)))
        keys["chest_rot"].append((tt, -2.0 * w * math.sin(2 * math.pi * ph)))
        keys["head_rot"].append((tt, -1.5 * w * math.sin(2 * math.pi * ph * 2)))
        keys["hair_rot"].append((tt, 4.0 * w * math.sin(2 * math.pi * ph * 2 - 0.9)))
        for k, side in enumerate(("L", "R")):
            phk = (ph + 0.5 * k) % 1.0
            if phk < 0.6:
                rel = a - 2 * a * (phk / 0.6)
                fy = P["foot_h"]
                rot = (9.0 * (1 - phk / 0.15) if phk < 0.15 else 0.0) - (24.0 * ((phk - 0.45) / 0.15) if phk > 0.45 else 0.0)   # toe-UP +: heel strike, then toe-off (toe down)
            else:
                uu = (phk - 0.6) / 0.4
                rel = -a + 2 * a * ease("smooth", uu)
                fy = P["foot_h"] + lift * math.sin(math.pi * uu) ** 0.8
                rot = -24.0 * (1 - uu) + 9.0 * uu
            walk_x = x + rel + stand_off[side] * 0.4
            f0 = fL0 if side == "L" else fR0
            sx = x + stand_off[side]
            wb = ease("smooth", min(1.0, u / max(ramp, 1e-3), (dur - u) / max(ramp, 1e-3))) if ramp > 0 else 1.0
            keys[f"foot_{side}_x"].append((tt, (1 - wb) * (f0[0] if u < dur / 2 else sx) + wb * walk_x))
            keys[f"foot_{side}_y"].append((tt, (1 - wb) * P["foot_h"] + wb * fy))
            keys[f"foot_{side}_rot"].append((tt, rot * wb))
        # arms swing opposite to the same-side leg (an arm holding the phone stays raised)
        for k, side in enumerate(("L", "R")):
            if kw.get("hold_" + side):
                sh_ = (x, P["shoulder_joint_y"] + base_h)
                keys[f"hand_{side}_x"].append((tt, sh_[0] + 118 * P["k"] + 3.0 * math.sin(2 * math.pi * ph * 2)))
                keys[f"hand_{side}_y"].append((tt, sh_[1] - 150 * P["k"] + 5.0 * math.sin(2 * math.pi * ph * 2)))
                continue
            phk = (ph + 0.5 * (1 - k)) % 1.0
            th = math.radians(10.0 + 26.0 * st["amp"] * w * math.sin(2 * math.pi * phk))
            r = (P["upper_arm"] + P["forearm"]) * (0.90 - 0.10 * abs(math.sin(2 * math.pi * phk)))
            shx, shy = x + 0.0, P["shoulder_joint_y"] + base_h - bob * w * 0.4
            hx, hy = shx + r * math.sin(th), shy - r * math.cos(th)
            wb = w
            rest = _arm_rest(perf, side, t)
            keys[f"hand_{side}_x"].append((tt, (1 - wb) * (rest[0] if u < dur / 2 else x + 0.0 + (P["upper_arm"] + P["forearm"]) * 0.93 * math.sin(math.radians(7))) + wb * hx))
            keys[f"hand_{side}_y"].append((tt, (1 - wb) * (rest[1] if u < dur / 2 else P["shoulder_joint_y"] + base_h - (P["upper_arm"] + P["forearm"]) * 0.93 * math.cos(math.radians(7))) + wb * hy))
    for name, lst in keys.items():
        chn = name if name in perf.ch else None
        if name.startswith("foot_") and name.endswith("_rot"):
            chn = name
        for tt, val in lst:
            perf.ch[chn].key(tt, val, "linear")
    perf.events.append((t, "walk", dict(t1=t + dur, x0=x_start, x1=x, T=T)))
    return t + dur


def a_reach(perf, t, dur, st, target=None, hand="R", **kw):
    """Reach a world point (rig space, absolute) with the near hand: eyes first, torso commits forward, arm leads with the elbow, overshoot-settle; a
    hesitant style adds a doubt pause and tremor. Returns the time the hand arrives."""
    P = perf.P
    tgt = target or (perf.hip(t)[0] + 240, P["hip_y"] * 0.7)
    d = dur / st["speed"]
    arrive = t + d
    sh = perf.shoulder(t)
    reach_len = P["upper_arm"] + P["forearm"]
    dist = math.hypot(tgt[0] - sh[0], tgt[1] - sh[1])
    lean = max(0.0, min(26.0, (dist - reach_len * 0.7) / 6.0)) * st["amp"]
    gaze_pt = tgt
    a_look_at(perf, t, 0.35, st, point=gaze_pt)
    perf.to("spine_rot", t + 0.1, arrive, lean, "smooth")
    perf.to("head_rot", t + 0.1, arrive, -8.0 * st["amp"], "smooth")
    start = (perf.v(f"hand_{hand}_x", t), perf.v(f"hand_{hand}_y", t))
    if st["hesitate"] > 0.3:
        mid = (start[0] + (tgt[0] - start[0]) * 0.55, start[1] + (tgt[1] - start[1]) * 0.55 + 22)
        t1 = t + d * 0.45
        hand_to(perf, hand, t + 0.12, t1, mid, "smooth")
        hand_to(perf, hand, t1 + 0.22 * st["hesitate"] * 1.4, arrive, tgt, "out_back")            # the doubt pause, then commit
        perf.hold(f"hand_{hand}_x", t1 + 0.0)
        _tremble(perf, t1, t1 + 0.3 * st["hesitate"] * 1.4, st["tremble"] * 2.2, (f"hand_{hand}_x", f"hand_{hand}_y"))
    else:
        hand_to(perf, hand, t + 0.1, arrive, tgt, "out_back")
    perf.to(f"hand_{hand}_rot", t, arrive, -10.0, "smooth")
    return arrive


def a_grab(perf, t, dur, st, hand="R", **kw):
    """Close the fingers over the phone: fingers overlay appears, phone attaches to the hand, screen-glow starts. Emits the pick-up event."""
    perf.ch["phone_vis"].key(t - 0.001, 0.0, "linear")
    perf.ch["phone_vis"].key(t, 1.0, "linear")
    perf.ch["fingers_vis"].key(t - 0.001, 0.0, "linear")
    perf.ch["fingers_vis"].key(t + 0.06, 1.0, "linear")
    perf.to("phone_glow", t, t + 0.4, 1.0, "out")
    perf.events.append((t, "phone_grab", dict(hand=hand)))
    return t + 0.1


def a_hold_phone(perf, t, dur, st, pos="chest", hand="R", **kw):
    """Bring the held phone into a carry position: chest (reading), face (close look) or ear (call). Forearm lifts, wrist tilts the screen toward the eyes."""
    P = perf.P
    sh = perf.shoulder(t)
    d = dur / st["speed"]
    if pos == "ear":
        tgt, rot = (sh[0] + 38 * P["k"], sh[1] + 58 * P["k"]), -78.0
    elif pos == "face":
        tgt, rot = (sh[0] + 150 * P["k"], sh[1] - 20 * P["k"]), -25.0
    else:
        tgt, rot = (sh[0] + 130 * P["k"], sh[1] - 175 * P["k"]), -38.0
    hand_to(perf, hand, t, t + d, tgt, "smooth")
    perf.to(f"hand_{hand}_rot", t, t + d, rot, "smooth")
    perf.to("spine_rot", t, t + d, 2.0, "smooth")
    return t + d


def a_read_phone(perf, t, dur, st, **kw):
    """Eyes drop to the screen, head pitches down, gaze makes reading saccades (left->right jumps), a small scroll nudge of the hand."""
    P = perf.P
    perf.to("head_rot", t, t + 0.35, 11.0 * st["amp"], "smooth")
    perf.to("neck_rot", t, t + 0.35, 4.0, "smooth")
    perf.to("gaze_y", t, t + 0.25, -0.9, "out_back")
    perf.to("gaze_x", t, t + 0.25, 0.25, "out_back")
    n = max(2, int(dur / 0.55))
    for i in range(n):
        tt = t + 0.3 + i * (dur - 0.3) / n
        perf.ch["gaze_x"].key(tt, -0.25, "out")
        perf.ch["gaze_x"].key(tt + 0.22 * (dur - 0.3) / n * 2, 0.55, "linear")
        perf.ch["gaze_y"].key(tt + 0.12, -0.85 - 0.12 * (i % 2), "smooth")
    hx, hy = perf.v("hand_R_x", t + 0.2), perf.v("hand_R_y", t + 0.2)
    for i in range(int(dur / 0.7)):
        perf.ch["hand_R_y"].key(t + 0.4 + 0.7 * i, hy + 6, "smooth")
        perf.ch["hand_R_y"].key(t + 0.6 + 0.7 * i, hy - 3, "smooth")
    return t + dur


def a_point(perf, t, dur, st, target=None, hand="R", **kw):
    P = perf.P
    sh = perf.shoulder(t)
    tgt = target or (sh[0] + (P["upper_arm"] + P["forearm"]) * 0.98, sh[1] + 10)
    d = min(dur, 0.6) / st["speed"]
    hand_to(perf, hand, t, t + d, tgt, "out_back")
    perf.to(f"hand_{hand}_rot", t, t + d, -4.0, "smooth")
    perf.to("spine_rot", t, t + d, 5.0 * st["amp"], "smooth")
    a_look_at(perf, t, d, st, point=(tgt[0] + 100, tgt[1]))
    return t + d


def a_gesture(perf, t, dur, st, hand="R", **kw):
    """Beat gestures while speaking/explaining: the hand rises and falls on emphasis, out of phase with the head."""
    P = perf.P
    n = max(1, int(dur / 0.55 * st["speed"]))
    for i in range(n):
        tt = t + i * dur / n
        sh = perf.shoulder(tt)
        up = (sh[0] + 120 * P["k"] + 30 * st["amp"], sh[1] - 170 * P["k"] + 55 * st["amp"] * (1 if i % 2 == 0 else 0.2))
        hand_to(perf, hand, tt, tt + 0.5 * dur / n, up, "out")
        perf.to("head_rot", tt, tt + 0.4 * dur / n, 2.0 * (1 if i % 2 == 0 else -0.5), "smooth")
    hand_to(perf, hand, t + dur, t + dur + 0.4, _arm_rest(perf, hand, t + dur), "smooth")
    return t + dur


def a_talk(perf, t, dur, st, **kw):
    """Mouth flaps at syllable rate (open/close pulses); brows punctuate; a light nod on stressed syllables."""
    n = int(dur * 7.5)
    r = random.Random(perf.seed * 7 + int(t * 10))
    for i in range(n):
        tt = t + i / 7.5
        o = 0.15 + 0.5 * r.random() if r.random() > 0.18 else 0.05
        perf.ch["mouth_open"].key(tt, o, "linear")
        perf.ch["mouth_open"].key(tt + 0.09, 0.05, "linear")
        if i % 6 == 3:
            perf.ch["brow_raise"].key(tt, perf.ch["brow_raise"](t) + 0.25, "out")
            perf.ch["brow_raise"].key(tt + 0.25, perf.ch["brow_raise"](t), "smooth")
    perf.ch["mouth_open"].key(t + dur + 0.1, 0.0, "smooth")
    return t + dur


def a_listen(perf, t, dur, st, **kw):
    perf.to("head_rot", t, t + 0.4, 3.0, "smooth")
    n = max(1, int(dur / 1.3))
    for i in range(n):
        tt = t + 0.5 + i * dur / n
        perf.ch["head_rot"].key(tt, 3.0 - 3.0, "smooth")
        perf.ch["head_rot"].key(tt + 0.25, 3.0, "smooth")
    return t + dur


def a_emotion(name, body):
    def f(perf, t, dur, st, **kw):
        perf.emotion(t, name, 0.14 if st["jerk"] > 0.3 else 0.3)
        body(perf, t, dur, st)
        return t + dur
    return f


def _fear_body(perf, t, dur, st):
    P = perf.P
    perf.to("spine_rot", t, t + 0.18, -9.0 * st["amp"], "out")
    perf.to("head_rot", t, t + 0.18, -5.0, "out")
    perf.to("shrug", t, t + 0.18, 0.9, "out")
    perf.to("pelvis_dx", t, t + 0.2, -10.0 * P["k"], "out")
    for side in ("L", "R"):
        sh = perf.shoulder(t)
        hand_to(perf, side, t, t + 0.25, (sh[0] + 70 * P["k"], sh[1] - 175 * P["k"]), "out_back")     # hands snap up defensively
    _tremble(perf, t + 0.25, t + dur, max(st["tremble"], 0.25), ("hand_L_x", "hand_L_y"))
    _tremble(perf, t + 0.25, t + dur, max(st["tremble"], 0.25), ("hand_R_x", "hand_R_y"), hz=11.0)
    perf.to("shrug", t + dur * 0.6, t + dur, 0.35, "smooth")


def _surprise_body(perf, t, dur, st):
    P = perf.P
    perf.to("spine_rot", t, t + 0.1, -12.0 * st["amp"], "out")
    perf.to("head_rot", t, t + 0.1, -9.0, "out")
    perf.to("pelvis_dx", t, t + 0.12, -14.0 * P["k"], "out")
    perf.to("shrug", t, t + 0.1, 1.0, "out")
    perf.to("spine_rot", t + 0.4, t + dur, -3.0, "smooth")
    perf.to("shrug", t + 0.35, t + dur, 0.2, "smooth")
    perf.to("pelvis_dx", t + 0.4, t + dur, -4.0 * P["k"], "smooth")


def _confusion_body(perf, t, dur, st):
    perf.to("head_rot", t, t + 0.4, 10.0, "smooth")
    perf.to("neck_rot", t, t + 0.4, 4.0, "smooth")
    perf.to("gaze_x", t, t + 0.3, 0.3, "smooth")
    perf.to("gaze_y", t + 0.6, t + 0.9, 0.5, "smooth")
    perf.to("shrug", t + 0.5, t + 0.8, 0.5, "smooth")


def _realize_body(perf, t, dur, st):
    P = perf.P
    perf.to("gaze_x", t, t + 0.12, 0.0, "out")
    perf.to("gaze_y", t, t + 0.12, 0.0, "out")
    perf.to("head_rot", t, t + 0.2, -7.0, "out")
    perf.to("spine_rot", t, t + 0.25, -5.0, "out")
    perf.to("shrug", t, t + 0.2, 0.6, "out")
    perf.emotion(t + dur * 0.55, "dread", 0.5)                                    # the realisation sinks in
    perf.to("head_rot", t + dur * 0.55, t + dur, 6.0, "smooth")
    perf.to("shrug", t + dur * 0.55, t + dur, 0.0, "smooth")


ACTIONS = {
    "idle": a_idle, "blink": a_blink,
    "look_left": a_look("left"), "look_right": a_look("right"), "look_down": a_look("down"), "look_up": a_look("up"), "look_ahead": a_look("ahead"),
    "look_at_phone": a_look_at, "look_at": a_look_at, "head_turn": a_head_turn, "head_tilt": a_head_tilt, "shrug": a_shrug,
    "walk": a_walk, "sit": a_sit, "stand": a_stand,
    "reach": a_reach, "reach_for_phone": a_reach, "grab": a_grab, "pickup_phone": a_grab, "hold_phone": a_hold_phone, "read_phone": a_read_phone,
    "point": a_point, "gesture": a_gesture, "talk": a_talk, "listen": a_listen,
    "fear": a_emotion("fear", _fear_body), "surprise": a_emotion("shock", _surprise_body), "confusion": a_emotion("confused", _confusion_body),
    "realization": a_emotion("realize", _realize_body),
}
def a_face(perf, t, dur, st, name="blank", amount=1.0, **kw):
    perf.emotion(t, name, max(0.08, min(dur, 0.35)), amount)
    return t + dur


def a_eyes_closed(perf, t, dur, st, **kw):
    perf.to("blink", t, t + 0.12, 1.0, "out")
    perf.no_blink.append((t, t + dur))
    return t + dur


def a_wake(perf, t, dur, st, **kw):
    """Eyes open (slowly at first, then the startle-blink of waking), head lifts out of the slump."""
    perf.to("blink", t, t + 0.35, 0.55, "smooth")
    perf.to("blink", t + 0.35, t + 0.5, 0.0, "out")
    perf.to("head_rot", t, t + 0.6, 0.0, "smooth")
    perf.to("spine_rot", t, t + 0.6, 2.0, "smooth")
    perf.to("neck_rot", t, t + 0.5, 0.0, "smooth")
    return t + max(dur, 0.6)


def a_slump(perf, t, dur, st, **kw):
    """Dozing posture: head sagging forward, slow breathing, eyes closed."""
    perf.to("head_rot", t, t + 0.4, 15.0, "smooth")
    perf.to("neck_rot", t, t + 0.4, 6.0, "smooth")
    perf.to("spine_rot", t, t + 0.4, 9.0, "smooth")
    perf.to("blink", t, t + 0.2, 1.0, "smooth")
    perf.no_blink.append((t, t + dur))
    for i in range(int(dur * 0.4) + 1):
        tt = t + 0.6 + i * 2.5
        perf.ch["chest_rot"].key(tt, 0.0, "smooth")
        perf.ch["chest_rot"].key(tt + 1.25, 1.6, "smooth")
    return t + dur


def a_buzz(perf, t, dur, st, **kw):
    """The held/resting phone vibrates: cue for sfx + GP arcs + light flicker; a held phone shakes the hand."""
    perf.events.append((t, "phone_buzz", dict(dur=dur)))
    perf.to("phone_glow", t, t + 0.08, 1.0, "out")
    if perf.v("phone_vis", t) > 0.5:
        _tremble(perf, t, t + dur, 0.8, ("hand_R_x", "hand_R_y"), hz=17.0)
    return t + dur


def a_hangup(perf, t, dur, st, **kw):
    """Phone comes away from the ear, thumb ends the call, screen goes dark."""
    a_hold_phone(perf, t, dur * 0.6, st, pos="chest")
    perf.to("phone_glow", t + dur * 0.6, t + dur, 0.0, "smooth")
    perf.events.append((t + dur * 0.6, "hangup", {}))
    return t + dur


def a_hand_down(perf, t, dur, st, hand="R", **kw):
    hand_to(perf, hand, t, t + dur, _arm_rest(perf, hand, t + dur), "smooth")
    perf.to(f"hand_{hand}_rot", t, t + dur, 0.0, "smooth")
    return t + dur


ACTIONS.update({"face": a_face, "eyes_closed": a_eyes_closed, "wake": a_wake, "slump": a_slump, "buzz": a_buzz, "hangup": a_hangup, "hand_down": a_hand_down})


EMOTION_ACTION = {"emotion": None}


def supported():
    return sorted(ACTIONS), sorted(STYLES)


def perform(perf, action, t, dur, emotion="neutral", intensity=0.5, **params):
    """Expand ONE semantic action into channel keys. Returns the end time."""
    if action not in ACTIONS:
        raise KeyError(f"unknown action '{action}' (have {sorted(ACTIONS)})")
    st = _style(emotion, intensity)
    if action not in ("walk", "sit", "stand", "blink", "idle") and st["lean"] and action in ("reach", "reach_for_phone", "point", "gesture"):
        pass
    return ACTIONS[action](perf, t, dur, st, **params)


def pose_stand(perf, t=-1.0, x=0.0):
    """Initial standing pose (feet planted, slight knee flex)."""
    P = perf.P
    perf.ch["root_x"].key(t, x, "linear")
    perf.ch["pelvis_dy"].key(t, -9.0 * P["k"], "linear")
    for side, off in (("L", -16.0), ("R", 24.0)):
        perf.ch[f"foot_{side}_x"].key(t, x + off * P["k"] + perf.so["h" + side], "linear")
    reach = (P["upper_arm"] + P["forearm"]) * REST_REACH
    for side, a in (("L", -3.0), ("R", 6.0)):
        sh_y = P["shoulder_joint_y"] - 9.0 * P["k"]
        perf.ch[f"hand_{side}_x"].key(t, x + reach * math.sin(math.radians(a)) + perf.so["s" + side], "linear")
        perf.ch[f"hand_{side}_y"].key(t, sh_y - reach * math.cos(math.radians(a)), "linear")


def pose_sit(perf, t=-1.0, seat=None, x=0.0):
    """Initial seated pose: hips on the seat, thighs ~horizontal, feet planted ahead, hands resting on the thighs."""
    P, w = perf.P, perf.world
    sit_hip = (seat if seat is not None else w["seat_h"]) + 30 * P["k"]
    perf.ch["root_x"].key(t, x, "linear")
    perf.ch["pelvis_dy"].key(t, sit_hip - P["hip_y"], "linear")
    knee_x = math.sqrt(max(P["thigh"] ** 2 - (sit_hip - (P["foot_h"] + P["shin"])) ** 2, 1.0))
    perf.ch["foot_L_x"].key(t, x + knee_x - 22 * P["k"] + perf.so["hL"], "linear")
    perf.ch["foot_R_x"].key(t, x + knee_x + 14 * P["k"] + perf.so["hR"], "linear")
    perf.ch["spine_rot"].key(t, 4.0, "linear")
    for side, dx in (("L", 0.06), ("R", 0.11)):                    # v3.5: hands rest nearer the lap, so the reach to the nightstand is a real movement for every body size
        perf.ch[f"hand_{side}_x"].key(t, x + knee_x * dx, "linear")
        perf.ch[f"hand_{side}_y"].key(t, sit_hip + 45 * P["k"], "linear")


def set_face(perf, t, name, dur=0.25, amount=1.0):
    perf.emotion(t, name, dur, amount)


def auto_blinks(perf, t0, t1, seed=0):
    r = random.Random(seed + 991)
    t = t0 + r.uniform(0.6, 2.0)
    while t < t1:
        if not any(a <= t <= b for a, b in perf.no_blink):
            a_blink(perf, t, 0.13, dict(speed=1.0))
            if r.random() < 0.18:
                a_blink(perf, t + 0.28, 0.13, dict(speed=1.0))
        t += r.uniform(2.0, 4.8)


# ------------------------------------------------------------------------------------------------------------------ sampling
def sample(perf, fps, t0, t1):
    """-> dict channel -> list of per-frame values for frames covering [t0, t1) + derived foot-compensation channels the rig needs."""
    n = int(round((t1 - t0) * fps))
    P = perf.P
    out = {}
    for name, ch in perf.ch.items():
        out[name] = [ch(t0 + i / fps) for i in range(n)]
    # foot orientation (toe-UP positive, CCW): keep the sole at the requested world pitch by compensating the analytic shin angle
    rest_shin = R.REST["thigh"] + R.REST["knee"]
    for side in ("L", "R"):
        loc = []
        for i in range(n):
            hip = (out["root_x"][i] + out["pelvis_dx"][i] + perf.so["h" + side], P["hip_y"] + out["root_y"][i] + out["pelvis_dy"][i])
            _, _, a1, a2 = R.two_bone(hip, (out[f"foot_{side}_x"][i], out[f"foot_{side}_y"][i] + out["root_y"][i] * 0), P["thigh"], P["shin"], bend=+1)
            loc.append(out[f"foot_{side}_rot"][i] - (a2 - rest_shin))
        out[f"foot_{side}_local"] = loc
    return out


from engine.skeleton import motion_v2  # noqa: E402,F401  (registers the V2 actions on ACTIONS)
