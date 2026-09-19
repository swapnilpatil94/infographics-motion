"""LayeredRig: a performer built from independent parts with real joints.

Parts (draw order): torso, arm A (upper, fore, hand), arm B (upper, fore, hand states, phone body,
phone screen), head shell, nose, eyes, brows, mouth. Nothing about an expression is a swapped
picture: brows, eyelids, gaze, convergence and mouth are continuous parameters blended from the
emotion table and re-inked per frame (cached by quantised value). Arms are 2-bone IK chains
(shoulder -> elbow -> wrist) driven by wrist-target channels; the phone is its own part that the
hand grips and carries. Head turns are sold by shifting features slightly MORE than the head shell
(cut-out 'turn' trick), eyes lead the head (see performance.look), shoulders rise with `shrug`.

Everything is expressed in bust-canvas coordinates (same frame as the Open Peeps head/body assets).
"""
import json
import math
import os

import cv2
import numpy as np

from asset_pipeline import rig_art as A
from engine.shorts.character import ORIGIN, RES, SC, c2w, NECK, SEAT, _T, _R, _S
from engine.shorts.layers import Layer, premultiply
from engine.shorts.phone import PhoneScreen
from engine.shorts.raster import rasterize, ROOT

Z = SC * RES                                  # raster px per canvas px
S_A, S_B = (262.0, 862.0), (872.0, 868.0)     # shoulder pivots (canvas)
L1, L2 = 330.0, 300.0                         # upper arm, forearm (to wrist)
REST_A, REST_B = (480.0, 1092.0), (700.0, 1096.0)
REST_PIVOT = (300.0, 300.0)                   # where every limb part is DRAWN (its own rest frame)
PHONE_REST = (760.0, 300.0)
GRIP = 70.0                                   # wrist -> phone centre along the hand axis
CURL_STATES = (0.0, 0.17, 0.33, 0.5, 0.67, 0.83, 1.0)

# emotion -> continuous face parameters
EMO = {
    #            brow: raise tilt arch asym | eyes: open lid | mouth: smile open width shift
    "calm":       dict(raise_=0.1, tilt=0.0, arch=0.1, asym=0, open_=0.38, lid=0.0, smile=0.5, mopen=0.0, width=1.0, shift=0),
    "smile":      dict(raise_=0.2, tilt=0.0, arch=0.2, asym=0, open_=0.85, lid=0.0, smile=0.8, mopen=0.0, width=1.05, shift=0),
    "happy":      dict(raise_=0.4, tilt=0.0, arch=0.4, asym=0, open_=0.6, lid=0.0, smile=1.0, mopen=0.35, width=1.15, shift=0),
    "tired":      dict(raise_=-0.25, tilt=0.35, arch=-0.3, asym=0, open_=0.8, lid=0.75, smile=-0.15, mopen=0.0, width=0.9, shift=0),
    "blank":      dict(raise_=0.0, tilt=0.0, arch=0.0, asym=0, open_=1.0, lid=0.15, smile=0.0, mopen=0.0, width=0.9, shift=0),
    "serious":    dict(raise_=-0.55, tilt=-0.45, arch=-0.2, asym=0, open_=0.92, lid=0.25, smile=-0.2, mopen=0.0, width=0.95, shift=0),
    "concerned":  dict(raise_=0.5, tilt=0.9, arch=0.25, asym=0, open_=1.0, lid=0.0, smile=-0.5, mopen=0.1, width=0.9, shift=0),
    "uneasy":     dict(raise_=0.6, tilt=1.0, arch=0.5, asym=0, open_=1.05, lid=0.0, smile=-0.6, mopen=0.18, width=0.85, shift=0),
    "shock":      dict(raise_=1.0, tilt=0.4, arch=0.8, asym=0, open_=1.28, lid=0.0, smile=-0.1, mopen=0.85, width=0.7, shift=0),
    "fear":       dict(raise_=0.9, tilt=1.0, arch=0.5, asym=0, open_=1.2, lid=0.0, smile=-0.7, mopen=0.5, width=0.8, shift=0),
    "awe":        dict(raise_=0.8, tilt=0.0, arch=0.7, asym=0, open_=1.2, lid=0.0, smile=0.15, mopen=0.45, width=0.8, shift=0),
    "angry":      dict(raise_=-0.9, tilt=-1.0, arch=-0.3, asym=0, open_=0.95, lid=0.3, smile=-0.85, mopen=0.2, width=1.05, shift=0),
    "suspicious": dict(raise_=-0.2, tilt=-0.2, arch=0.0, asym=0.9, open_=0.65, lid=0.5, smile=-0.2, mopen=0.0, width=0.9, shift=4),
    "contempt":   dict(raise_=0.0, tilt=0.0, arch=0.0, asym=0.6, open_=0.8, lid=0.35, smile=0.3, mopen=0.0, width=0.9, shift=6),
    "driven":     dict(raise_=-0.4, tilt=-0.5, arch=-0.1, asym=0, open_=0.95, lid=0.1, smile=0.25, mopen=0.0, width=1.0, shift=0),
    "explaining": dict(raise_=0.3, tilt=0.1, arch=0.3, asym=0, open_=1.0, lid=0.0, smile=0.3, mopen=0.35, width=1.0, shift=0),
    "solemn":     dict(raise_=0.1, tilt=0.65, arch=0.0, asym=0, open_=0.8, lid=0.4, smile=-0.4, mopen=0.0, width=0.9, shift=0),
    "cheeky":     dict(raise_=0.3, tilt=0.0, arch=0.2, asym=0.5, open_=1.0, lid=0.0, smile=0.75, mopen=0.1, width=1.0, shift=3),
}
FEATURE_TURN = {"nose": 0.6, "eyes": 0.5, "brows": 0.4, "mouth": 0.55}      # extra shift vs the head shell when the head turns


def _place(name, svg, zoom=Z, region=None):
    arr, (ox, oy) = rasterize(svg, zoom=zoom)
    rx, ry = (region[0], region[1]) if region else (0, 0)
    origin = (ORIGIN[0] + SC * rx + ox / RES, ORIGIN[1] + SC * ry + oy / RES)
    return Layer(name, arr, origin, RES, par=1.0, depth=1.6)


def _xf_part(rest_pivot, now_pivot, delta_deg):
    """Rigid world transform taking a part drawn at `rest_pivot` (canvas) to `now_pivot` rotated by delta_deg."""
    rw, nw = c2w(rest_pivot), c2w(now_pivot)
    return _T(nw[0], nw[1]) @ _R(delta_deg) @ _T(-rw[0], -rw[1])


def ik(shoulder, target, l1=L1, l2=L2, below=True):
    """Two-bone IK -> (elbow, wrist, upper_angle_deg, fore_angle_deg). Wrist is clamped to reach."""
    sx, sy = shoulder
    dx, dy = target[0] - sx, target[1] - sy
    d = math.hypot(dx, dy)
    d = min(max(d, abs(l1 - l2) + 8), l1 + l2 - 2)
    base = math.atan2(dy, dx)
    cosa = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.acos(max(-1.0, min(1.0, cosa)))
    best = None
    for s in (1, -1):
        ang = base + s * a
        ex, ey = sx + l1 * math.cos(ang), sy + l1 * math.sin(ang)
        if best is None or (ey > best[1]) == below:
            best = (ex, ey, ang)
    ex, ey, up = best
    wx, wy = sx + d * math.cos(base), sy + d * math.sin(base)
    fore = math.atan2(wy - ey, wx - ex)
    return (ex, ey), (wx, wy), math.degrees(up), math.degrees(fore)


class LayeredRig:
    def __init__(self, cast_id):
        spec = json.load(open(os.path.join(ROOT, "assets/character/cast/cast.json")))
        self.cast_id = cast_id
        self.head_path = spec["characters"][cast_id]["head_base"]
        self.nose_atom = os.path.join(A.__file__.rsplit("/asset_pipeline", 1)[0],
                                      "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/face/Serious.svg")
        P = REST_PIVOT
        self.torso = _place("torso", A.torso())
        self.up = {"A": _place("armA_up", A.sleeve(P, L1, 128, 0, 11)), "B": _place("armB_up", A.sleeve(P, L1, 128, 0, 12))}
        self.fore = {"A": _place("armA_fore", A.sleeve(P, L2 - 8, 112, 0, 13, cuff=True)), "B": _place("armB_fore", A.sleeve(P, L2 - 8, 112, 0, 14, cuff=True))}
        self.handA = _place("handA", A.hand((P[0] + L2 - 8, P[1]), 0, curl=0.3, spread=0.4, thumb=0.4))
        self.handB = [_place(f"handB_{i}", A.hand((P[0] + L2 - 8, P[1]), 0, curl=c, spread=0.35 * (1 - c), thumb=0.6 - 0.4 * c)) for i, c in enumerate(CURL_STATES)]
        self.phone_body = _place("phone_body", A.phone_body(PHONE_REST))
        self.ui = PhoneScreen()                                  # UI compositor (lock screen + banner)
        x, y, w, h = A.phone_screen_rect(PHONE_REST)
        self._scr_rect = (x, y, w, h)
        self.phone_screen = Layer("phone_screen", np.zeros((4, 4, 4), np.uint8), (0, 0), RES, par=1.0, depth=1.6, emissive=True)
        self.phone_screen.origin = (ORIGIN[0] + SC * x, ORIGIN[1] + SC * y)
        self.head = _place("head", open(os.path.join(ROOT, self.head_path), encoding="utf-8").read())
        self.nose = _place("nose", A.nose_svg(self.nose_atom), region=A.FACE_REGION)
        self._feat = {}                                          # (kind, quantised params) -> (arr, origin)
        self.eyes = Layer("eyes", np.zeros((4, 4, 4), np.uint8), (0, 0), RES, par=1.0, depth=1.6)
        self.brows = Layer("brows", np.zeros((4, 4, 4), np.uint8), (0, 0), RES, par=1.0, depth=1.6)
        self.mouth = Layer("mouth", np.zeros((4, 4, 4), np.uint8), (0, 0), RES, par=1.0, depth=1.6)
        self.state = {}
        self.neck_w, self.seat_w = c2w(NECK), c2w(SEAT)
        self._hold = 0.0
        self._grip_world = c2w(REST_B)
        self._wrist_canvas = REST_B
        self.arm = {}
        self.pose_cache = {}

    # ------------------------------------------------------------------ layers
    @property
    def layers(self):
        return [self.torso, self.up["A"], self.fore["A"], self.handA, self.up["B"], self.fore["B"], *self.handB,
                self.phone_body, self.phone_screen, self.head, self.nose, self.eyes, self.brows, self.mouth]

    def use(self, *a, **k):                                      # API parity with CastRig (film calls rig.use)
        return None

    # ---------------------------------------------------------------- features
    def _feature(self, kind, key, svg_fn):
        k = (kind, key)
        if k not in self._feat:
            svg = svg_fn()
            arr, (ox, oy) = rasterize(svg, zoom=Z)
            rx, ry = A.FACE_REGION[0], A.FACE_REGION[1]
            self._feat[k] = (arr, (ORIGIN[0] + SC * rx + ox / RES, ORIGIN[1] + SC * ry + oy / RES))
        return self._feat[k]

    def _set_layer(self, layer, arr, origin):
        layer.base = premultiply(arr)
        layer._mips = {0: layer.base}
        layer._blur = {}
        layer.origin = origin

    def face_params(self, weights):
        wb = weights.get("blink", 0.0)
        ws = {k: v for k, v in weights.items() if k != "blink" and k in EMO}
        tot = sum(ws.values()) or 1.0
        p = {}
        for name, w in ws.items():
            for k, v in EMO[name].items():
                p[k] = p.get(k, 0.0) + v * w / tot
        p["open_"] = p.get("open_", 1.0) * (1.0 - wb)
        return p

    # ------------------------------------------------------------------- pose
    def update(self, perf, t):
        s = perf.state(t)
        self.state = s
        q = lambda v, st: round(v / st) * st
        # ---- face
        p = self.face_params(s["weights"])
        gx, gy, conv = s.get("gx", 0.0), s.get("gy", 0.0), s.get("conv", 0.0)
        eyes = self._feature("eyes", (q(p["open_"], 0.05), q(gx, 0.1), q(gy, 0.1), q(conv, 0.2), q(p["lid"], 0.1)),
                             lambda: A.eyes_svg(q(p["open_"], 0.05), (q(gx, 0.1), q(gy, 0.1)), q(conv, 0.2), q(p["lid"], 0.1)))
        brows = self._feature("brows", tuple(q(p[k], 0.08) for k in ("raise_", "tilt", "arch", "asym")),
                              lambda: A.brows_svg(*(q(p[k], 0.08) for k in ("raise_", "tilt", "arch", "asym"))))
        mouth = self._feature("mouth", tuple(q(p[k], 0.08) for k in ("smile", "mopen", "width")) + (round(p["shift"]),),
                              lambda: A.mouth_svg(q(p["smile"], 0.08), q(p["mopen"], 0.08), q(p["width"], 0.05), round(p["shift"])))
        self._set_layer(self.eyes, *eyes)
        self._set_layer(self.brows, *brows)
        self._set_layer(self.mouth, *mouth)
        # ---- body / head matrices (same convention as BustRig)
        b = s["breathe"]
        sx, sy = self.seat_w
        mb = _T(sx + s["bdx"], sy + s["bdy"]) @ _S(1 + b * 0.35, 1 + b) @ _T(-sx, -sy)
        nx, ny = self.neck_w
        mh = mb @ _T(nx + s["hdx"], ny + s["hdy"]) @ _R(s["roll"]) @ _T(-nx, -ny)
        self.torso.world_xf = mb
        self.head.world_xf = mh
        for kind, layer in (("nose", self.nose), ("eyes", self.eyes), ("brows", self.brows), ("mouth", self.mouth)):
            k = FEATURE_TURN[kind]
            layer.world_xf = _T(k * s["hdx"] * 0.6, k * s["hdy"] * 0.4) @ mh
        # ---- arms
        shrug = s.get("shrug", 0.0)
        for side, sh, rest in (("A", S_A, REST_A), ("B", S_B, REST_B)):
            shoulder = (sh[0], sh[1] - 16 * shrug)
            tx = perf.ch[f"a{side}_x"](t) if f"a{side}_x" in perf.ch else rest[0]
            ty = perf.ch[f"a{side}_y"](t) if f"a{side}_y" in perf.ch else rest[1]
            if side == "A":
                ty += 5 * math.sin(0.9 * t) * (1 - s.get("stillness", 0.0))     # idle: hand rises with the breath
            elbow, wrist, ua, fa = ik(shoulder, (tx, ty), below=True)
            self.up[side].world_xf = mb @ _xf_part(REST_PIVOT, shoulder, ua)
            self.fore[side].world_xf = mb @ _xf_part(REST_PIVOT, elbow, fa)
            if side == "A":
                self.handA.world_xf = mb @ _xf_part(REST_PIVOT, wrist, fa) @ _T(0, 0)
                self.handA.world_xf = mb @ _xf_part((REST_PIVOT[0] + L2 - 8, REST_PIVOT[1]), wrist, fa)
            else:
                curl = perf.ch["aB_curl"](t) if "aB_curl" in perf.ch else 0.3
                hold = perf.ch["aB_hold"](t) if "aB_hold" in perf.ch else 0.0
                hand_m = mb @ _xf_part((REST_PIVOT[0] + L2 - 8, REST_PIVOT[1]), wrist, fa)
                near = min(range(len(CURL_STATES)), key=lambda j: abs(CURL_STATES[j] - curl))
                for i, layer in enumerate(self.handB):                # nearest state (cross-fading two hands ghosts)
                    layer.opacity, layer.visible, layer.world_xf = 1.0, i == near, hand_m
                rot = perf.ch["aB_prot"](t) if "aB_prot" in perf.ch else -4.0
                gp = (wrist[0] + GRIP * math.cos(math.radians(fa)), wrist[1] + GRIP * math.sin(math.radians(fa)))
                # held phone stays upright-ish: it follows the grip point, not the forearm angle
                pm = mb @ _xf_part(PHONE_REST, gp, rot)
                for layer in (self.phone_body, self.phone_screen):
                    layer.world_xf, layer.visible = pm, hold > 0.5
                self._hold, self._wrist_canvas, self._grip_canvas = hold, wrist, gp
                self._mb = mb
        return s

    def update_screen(self, bright, banner_pos):
        """Dynamic emissive phone screen: the lock-screen UI (with sliding notification) inked onto the phone face."""
        ui = self.ui.compose_ui(bright, banner_pos)
        x, y, w, h = self._scr_rect
        pw, ph = int(w * Z), int(h * Z)
        img = cv2.resize(ui, (pw, ph), interpolation=cv2.INTER_AREA)
        rr = int(13 * Z)
        yy, xx = np.mgrid[0:ph, 0:pw]
        cx, cy = np.clip(xx, rr, pw - rr), np.clip(yy, rr, ph - rr)
        m = (np.hypot(xx - cx, yy - cy) <= rr).astype(np.float32)
        img = img.astype(np.float32)
        img[:, :, 3] *= m
        self.phone_screen.base = premultiply(np.clip(img, 0, 255).astype(np.uint8))
        self.phone_screen._mips = {0: self.phone_screen.base}
        self.phone_screen._blur = {}

    def anchor(self, name):
        if name in ("head", "eyes"):
            return c2w((650.0, 478.0))
        if name == "chest":
            return c2w((620.0, 930.0))
        if name == "phone":
            g = getattr(self, "_grip_canvas", REST_B)
            return c2w(g)
        raise KeyError(name)
