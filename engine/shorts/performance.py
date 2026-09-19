"""Channels, easing, and the reusable character-action library.

A Performance is a set of named channels (numbers over time) plus discrete
face/blink events. Actions never touch a renderer: they only write keys
onto channels, so the same action functions drive any rig that exposes the
same channel names (roll / hdx / hdy / bdx / bdy) and look-target table.
Motion is never linear: every move is a keyed ease with anticipation and
overshoot/settle where a real person would have them.
"""
import math
import random


# ---------------------------------------------------------------- easing
def ease(name, u):
    u = min(1.0, max(0.0, u))
    if name == "linear":
        return u
    if name == "in":
        return u ** 3
    if name == "out":
        return 1 - (1 - u) ** 3
    if name == "out_back":                       # overshoot then settle
        c1 = 1.9
        return 1 + (c1 + 1) * (u - 1) ** 3 + c1 * (u - 1) ** 2
    if name == "spring":                         # damped oscillation to rest
        return 1 - math.exp(-7.0 * u) * math.cos(2 * math.pi * 1.7 * u)
    return u * u * (3 - 2 * u)                   # smooth


class Channel:
    def __init__(self, default=0.0):
        self.default = default
        self.keys = []                            # (t, value, ease)

    def key(self, t, v, e="smooth"):
        self.keys.append((t, v, e))
        self.keys.sort(key=lambda k: k[0])

    def __call__(self, t):
        ks = self.keys
        if not ks:
            return self.default
        if t <= ks[0][0]:
            return ks[0][1]
        for i in range(1, len(ks)):
            if t <= ks[i][0]:
                t0, v0, _ = ks[i - 1]
                t1, v1, e = ks[i]
                if t1 - t0 < 1e-6:
                    return v1
                return v0 + (v1 - v0) * ease(e, (t - t0) / (t1 - t0))
        return ks[-1][1]


# Where the head goes for each look target: (roll deg, dx, dy) in world units.
LOOK_TARGETS = {
    "ceiling": (4.5, 5.0, -13.0),
    "window": (3.0, 9.0, -7.0),
    "phone": (-4.5, -3.0, 17.0),
    "down": (-3.0, -2.0, 23.0),
    "ahead": (0.0, 0.0, 0.0),
    "stand": (2.6, 12.0, 5.0),          # toward the nightstand (right of frame)
    "away": (-3.0, -8.0, -4.0),         # glance off to the side, avoiding the thing
}


class Performance:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.ch = {}
        self.faces = [(0.0, "tired", 0.0)]        # (t, face, crossfade_dur)
        self.blinks = []                          # (t, dur)
        self.no_blink = []                        # (t0, t1) windows
        self.look_state = (0.0, 0.0, 0.0)
        self.tremble_amp = Channel(0.0)
        self.stillness = Channel(0.0)             # 1 = frozen (idle drift/breathing suppressed)
        self.phases = [self.rng.uniform(0, 6.28) for _ in range(6)]

    def channel(self, name):
        return self.ch.setdefault(name, Channel(0.0))

    def total(self, prefix, t):
        return sum(c(t) for n, c in self.ch.items() if n.split(":")[0] == prefix)

    # -------------------------------------------------------- state at time t
    def state(self, t):
        still = 1.0 - 0.92 * self.stillness(t)
        b_slow = 0.5 - 0.5 * math.cos(2 * math.pi * t / 4.0)          # ~15 breaths/min
        breathe = 0.0065 * (b_slow - 0.5) * 2 * still
        p = self.phases
        drift_r = still * (0.55 * math.sin(0.61 * t + p[0]) + 0.3 * math.sin(1.13 * t + p[1]))
        drift_x = still * (1.6 * math.sin(0.43 * t + p[2]) + 0.8 * math.sin(0.97 * t + p[3]))
        drift_y = still * (1.3 * math.sin(0.37 * t + p[4]) + 0.6 * math.sin(1.21 * t + p[5]))
        amp = self.tremble_amp(t)
        tr_x = amp * math.sin(2 * math.pi * 9.3 * t) * 0.9
        tr_y = amp * math.sin(2 * math.pi * 11.7 * t + 1.0) * 0.7
        return dict(
            gx=self.total("gx", t) + self._saccade(t, 1), gy=self.total("gy", t) + self._saccade(t, 2),
            conv=self.total("conv", t), shrug=self.total("shrug", t),
            roll=self.total("roll", t) + drift_r,
            hdx=self.total("hdx", t) + drift_x,
            hdy=self.total("hdy", t) + drift_y + breathe * 60,
            bdx=self.total("bdx", t) + tr_x,
            bdy=self.total("bdy", t) + tr_y,
            breathe=breathe,
            weights=self.face_weights(t),
        )

    def _saccade(self, t, k):
        """Eyes are never perfectly still: tiny step-like gaze jitter, seeded, ~1 shift per second."""
        f = lambda n: (math.sin(n * 12.9898 + k * 78.233 + self.phases[0] * 3.1) * 43758.5453) % 1.0 * 2 - 1
        i, j = int(t * 1.15), (t * 1.15) % 1.0
        u = min(1.0, j / 0.10)
        u = u * u * (3 - 2 * u)
        return 0.07 * (f(i) * (1 - u) + f(i + 1) * u) * (1.0 - 0.8 * self.stillness(t))

    def face_weights(self, t):
        cur_i = 0
        for i, (ft, _, _) in enumerate(self.faces):
            if ft <= t:
                cur_i = i
        ft, cur, dur = self.faces[cur_i]
        w = {cur: 1.0}
        if cur_i > 0 and dur > 0 and t - ft < dur:
            u = ease("smooth", (t - ft) / dur)
            prev = self.faces[cur_i - 1][1]
            w = {prev: 1 - u, cur: u} if prev != cur else {cur: 1.0}
        wb = 0.0
        for bt, bd in self.blinks:
            if bt <= t <= bt + bd:
                x = (t - bt) / bd
                wb = max(wb, min(1.0, x / 0.3, (1 - x) / 0.35))
        if wb > 0:
            w = {k: v * (1 - wb) for k, v in w.items()}
            w["blink"] = wb
        return w


# ---------------------------------------------------------------- actions
def emotion(perf, t, to, dur=0.12):
    perf.faces.append((t, to, dur))
    perf.faces.sort(key=lambda f: f[0])


GAZE = {"ceiling": (0.25, -0.9), "window": (0.75, -0.45), "phone": (-0.05, 0.75), "down": (0.0, 0.95), "ahead": (0.0, 0.0),
        "stand": (0.95, 0.15), "away": (-0.85, -0.2)}


def _gaze(perf, t, target, dur, amount):
    """Eyes LEAD the head: they arrive ~0.14s before it, then settle to ~60% as the head takes over the turn."""
    gx, gy = (v * amount for v in GAZE[target])
    for name, v1 in (("gx:look", gx), ("gy:look", gy)):
        ch = perf.channel(name)
        cur = ch(t) if ch.keys else 0.0
        ch.key(max(t - 0.16, 0.001), cur, "linear")
        ch.key(t - 0.02, v1, "out")
        ch.key(t + dur + 0.25, v1 * 0.62, "smooth")


def look(perf, t, target, dur=0.5, amount=1.0, e="out_back"):
    _gaze(perf, t, target, dur, amount)
    _look_head(perf, t, target, dur, amount, e)


def _look_head(perf, t, target, dur=0.5, amount=1.0, e="out_back"):
    """Head moves to a look target with a small anticipation dip the other
    way first, then eases in with overshoot and settles."""
    roll, dx, dy = (v * amount for v in LOOK_TARGETS[target])
    r0, x0, y0 = perf.look_state
    ant = 0.16
    for name, v0, v1 in (("roll:look", r0, roll), ("hdx:look", x0, dx), ("hdy:look", y0, dy)):
        ch = perf.channel(name)
        if not ch.keys:
            ch.key(0.0, v0)
        ch.key(max(t - 0.10, 0.001), v0 - (v1 - v0) * ant, "out")
        ch.key(t + dur, v1, e)
    perf.look_state = (roll, dx, dy)


def startle(perf, t, amount=1.0):
    """Body/head jolt that decays - the 'something just happened' flinch."""
    for name, peak in (("bdy:startle", -9.0), ("hdy:startle", -8.0), ("roll:startle", 2.6), ("hdx:startle", -6.0)):
        ch = perf.channel(name)
        ch.key(t - 0.001, 0.0)
        ch.key(t + 0.07, peak * amount, "out")
        ch.key(t + 0.55, 0.0, "spring")


def lean(perf, t, dur, amount=1.0):
    """Slow drawn-in lean toward the phone."""
    for name, v in (("bdy:lean", 7.0 * amount), ("hdy:lean", 5.0 * amount)):
        ch = perf.channel(name)
        if not ch.keys:
            ch.key(0.0, 0.0)
        ch.key(t, ch(t) if ch.keys else 0.0)
        ch.key(t + dur, v, "smooth")


def tremble(perf, t, dur, amount=1.0, ramp=0.5):
    perf.tremble_amp.key(t, perf.tremble_amp(t))
    perf.tremble_amp.key(t + ramp, amount, "smooth")
    perf.tremble_amp.key(t + dur, amount, "linear")


def auto_blinks(perf, t0, t1, seed=1):
    r = random.Random(seed)
    t = t0 + r.uniform(0.8, 1.6)
    while t < t1:
        if not any(a <= t <= b for a, b in perf.no_blink):
            perf.blinks.append((t, 0.14))
        t += r.uniform(2.2, 4.4)


def blink_at(perf, t):
    perf.blinks.append((t, 0.14))


# ------------------------------------------------- micro-acting primitives
def freeze(perf, t, dur, ramp=0.06):
    """Micro-freeze: the involuntary stillness of a person who just noticed something.
    Breathing and idle drift are suppressed, so the surrounding motion reads as 'held breath'."""
    c = perf.stillness
    c.key(t - ramp, c(t - ramp), "out")
    c.key(t, 1.0, "out")
    c.key(t + dur, 1.0, "linear")
    c.key(t + dur + 0.35, 0.0, "smooth")


def hesitate(perf, t, target, dur=1.1, amount=1.0):
    """Turn toward a target in two stages with a retreat between them: commit, doubt, commit."""
    look(perf, t, target, dur * 0.35, amount * 0.55, "out")
    look(perf, t + dur * 0.45, target, dur * 0.2, amount * 0.30, "smooth")     # pull back (doubt)
    look(perf, t + dur * 0.75, target, dur * 0.3, amount * 1.0, "out_back")    # then commit


def glance(perf, t, target, dur=0.9, amount=0.8):
    """Look away and come back: the 'I don't want to believe this' flick."""
    prev = perf.look_state
    look(perf, t, target, 0.25, amount, "out")
    roll, dx, dy = prev
    for name, v in (("roll:look", roll), ("hdx:look", dx), ("hdy:look", dy)):
        perf.channel(name).key(t + dur, v, "smooth")
    perf.look_state = prev


# ------------------------------------------------------------ arms / shoulders
def init_arms(perf, rest_a, rest_b):
    for side, r in (("A", rest_a), ("B", rest_b)):
        perf.ch[f"a{side}_x"], perf.ch[f"a{side}_y"] = Channel(r[0]), Channel(r[1])
    perf.ch["aB_curl"], perf.ch["aB_hold"], perf.ch["aB_prot"], perf.ch["aB_ear"] = Channel(0.3), Channel(0.0), Channel(-4.0), Channel(0.0)


def _to(ch, t0, t1, v, e="smooth"):
    ch.key(t0, ch(t0))
    ch.key(t1, v, e)


def arm_to(perf, side, t0, t1, x, y, e="smooth"):
    """Move the wrist of arm `side` to canvas point (x, y) between t0 and t1 (the IK chain follows)."""
    _to(perf.ch[f"a{side}_x"], t0, t1, x, e)
    _to(perf.ch[f"a{side}_y"], t0, t1, y, e)


def hand_curl(perf, t0, t1, curl, e="smooth"):
    _to(perf.ch["aB_curl"], t0, t1, curl, e)


def hold_phone(perf, t, on=True):
    c = perf.ch["aB_hold"]
    c.key(t - 0.001, c(t - 0.001))
    c.key(t, 1.0 if on else 0.0, "linear")


def phone_rot(perf, t0, t1, deg, e="smooth"):
    _to(perf.ch["aB_prot"], t0, t1, deg, e)


def shrug(perf, t, amount=1.0, dur=0.9):
    """Shoulders rise on a breath in and settle: tension, hesitation."""
    c = perf.channel("shrug:act")
    c.key(t - 0.001, c(t - 0.001) if c.keys else 0.0)
    c.key(t + dur * 0.35, amount, "out")
    c.key(t + dur * 1.6, 0.0, "smooth")


def converge(perf, t0, t1, amount):
    """Near focus: eyes converge slightly and drop (reading a screen)."""
    c = perf.channel("conv:focus")
    c.key(t0, c(t0) if c.keys else 0.0)
    c.key(t1, amount, "smooth")
