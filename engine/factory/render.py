"""Deterministic renderer: SHOT PLAN -> frames. One ShotRenderer per treatment; no LLM, no randomness beyond seeded channels.

  performance : a layered character (rig2) in a 2.5D set, timed acting verbs, mood lighting, motivated camera, Grease Pencil effects
  insert_ui   : full-screen phone UI (procedural screen) with an animated GP ring on the key element
  procedural  : data-driven financial/psychology graphic
Transitions (cut / dissolve / dip / fade) are composed in `frame_at`. Times are absolute film seconds (after pause retiming).
"""
import math
import random

import numpy as np

from engine.factory import procedural as PR, verbs
from engine.factory.ui_screens import ANCHORS, UIScreen
from engine.shorts import film as F, gp_bank, performance as P, sets
from engine.shorts.dust import Dust
from engine.shorts.insert import ScreenInsert
from engine.shorts.layers import Camera, C0, W, H, premultiply
from engine.shorts.lighting import Light, bloom
from engine.shorts.performance import ease
from engine.shorts.post import Post
from engine.shorts.rig2 import LayeredRig, REST_A, REST_B
from engine.shorts.scene import Scene

MOODS = {   # ambient scale, tint (rgb multiplier), exposure, extra vignette
    "neutral": (1.00, (1.00, 1.00, 1.00), 1.00, 0.00), "formal": (0.94, (0.92, 0.97, 1.06), 0.98, 0.05),
    "pressure": (0.86, (1.05, 0.95, 0.92), 0.96, 0.15), "fear": (0.66, (0.90, 0.94, 1.10), 0.94, 0.32),
    "isolated": (0.78, (0.88, 0.92, 1.05), 0.96, 0.25), "dim": (0.58, (0.92, 0.94, 1.05), 0.94, 0.22),
    "warm": (1.06, (1.08, 1.00, 0.90), 1.02, 0.00), "bright": (1.14, (1.04, 1.02, 0.98), 1.05, 0.00),
    "relief": (1.08, (1.06, 1.02, 0.94), 1.02, 0.02)}
SIZES = {"wide": dict(target=(640.0, 1010.0), zoom=1.24, offset=(0, 0), ap=7), "medium": dict(target="chest", zoom=1.72, offset=(10, -150), ap=13),
         "close": dict(target="eyes", zoom=1.95, offset=(0, 175), ap=16), "ecu": dict(target="eyes", zoom=3.0, offset=(0, 25), ap=26)}
MOVE = dict(push=(1.0, 1.11, 0), pull=(1.11, 1.0, 0), hold=(1.0, 1.03, 0), drift=(1.0, 1.05, 32))


def _seed(s):
    return sum(ord(c) * (i + 3) for i, c in enumerate(s)) % 10000


class Ctx:
    """Shared, expensive objects (rigs, GP bank, post pipeline) built once per film."""
    def __init__(self, plan, log=print):
        self.plan, self.log = plan, log
        self.post = Post()
        self.rigs = {}
        self.bank = gp_bank.ensure_bank(log)
        self.vig = None

    def rig(self, cast, outfit):
        k = (cast, outfit)
        if k not in self.rigs:
            self.log(f"[render] building rig {cast}/{outfit}")
            self.rigs[k] = LayeredRig(cast, self.plan["outfits"].get(outfit, self.plan["outfits"]["sweater_speckled"]))
        return self.rigs[k]

    def extra_vignette(self, img, k):
        if k <= 0.01:
            return img
        if self.vig is None:
            ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
            r = np.hypot((xs - W / 2) / (W / 2), (ys - H * 0.46) / (H / 2))
            self.vig = np.clip((r - 0.25) / 0.9, 0, 1)[:, :, None] ** 1.5
        return img * (1 - k * self.vig)


def _sh_adapter(shot_cam, rig, t0, t1):
    return {"cam": shot_cam, "beat": {"rig": rig}, "t0": t0, "t1": t1}


class PerformanceShot:
    def __init__(self, sh, ctx):
        self.sh, self.ctx = sh, ctx
        st = sh["state_before"]
        self.rig = ctx.rig(sh["cast"], sh["outfit"])
        set_id = ctx.plan["sets"][sh["location"]]
        spec = sets.SETS[set_id]
        amb, tint, expo, vig = MOODS.get(sh["lighting"]["mood"], MOODS["neutral"])
        pr = sh["lighting"]["pressure"]
        self.k_amb = amb * (1 - 0.28 * pr)
        self.exposure, self.vig = expo, vig + 0.18 * pr
        self.scene = Scene(self.rig, room=sets.layers_for(set_id), order=sets.order_for(set_id), ambient=tuple(np.array(spec["ambient"]) * np.array(tint)),
                           bloom_strength=spec["bloom"], post=ctx.post)
        self.base_amb = np.array(self.scene.lights.ambient, np.float32)
        for L in spec["lights"](None):
            o = L.intensity
            L.intensity = (lambda t, o=o, k=self.k_amb: (o(t) if callable(o) else o) * k)
            self.scene.lights.add(L)
        self.held = self.scene.lights.add(Light("radial", (0.50, 0.88, 1.0), lambda t: self._phone_light(t), reach=(0, 2.3), attach_par=1.0,
                                                center=(600, 1000), radius=600, power=1.6))
        self.dust = Dust(_seed(sh["id"])) if spec["time"] == "night" else None
        # ---- acting
        perf = P.Performance(seed=_seed(sh["id"]))
        P.init_arms(perf, REST_A, REST_B)
        self.perf = perf
        perf.faces = [(sh["t0"] - 5, sh["emotion"], 0.0)]
        t0, t1 = sh["t0"], sh["t1"]
        if sh.get("emotion_end"):
            P.emotion(perf, t0 + 0.55 * (t1 - t0), sh["emotion_end"], 0.5)
        self.holding0 = bool(st["holding_phone"]) and not any(a["verb"] == "pickup_phone" for a in sh["actions"])
        if self.holding0:                                                        # continuity: the phone is already in his hand
            P.hold_phone(perf, t0 - 2.0)
            tgt = verbs.EAR_POS if st["phone_at_ear"] else verbs.READ_POS
            P.arm_to(perf, "B", t0 - 2.0, t0 - 1.99, *tgt, "linear")
            P.hand_curl(perf, t0 - 2.0, t0 - 1.99, 0.85)
            P.phone_rot(perf, t0 - 2.0, t0 - 1.99, -14.0 if st["phone_at_ear"] else -6.0)
            if st["phone_at_ear"]:
                perf.ch["aB_ear"].key(t0 - 2.0, 1.0)
        for a in sorted(sh["actions"], key=lambda x: x["t"]):
            verbs.VERBS[a["verb"]](perf, a["t"], a["dur"])
        P.auto_blinks(perf, t0, t1, seed=_seed(sh["id"]) + 1)
        held_ui = sh.get("held_ui") or dict(screen="in_call", data=dict(name="बैंक"))
        self.rig.ui = UIScreen(held_ui["screen"], held_ui["data"])
        # ---- camera
        cam = sh["camera"]
        base = SIZES.get(cam["size"], SIZES["medium"])
        z0, z1, drift = MOVE.get(cam["move"], MOVE["hold"])
        mk = lambda tt, u, z: dict(t=tt, target=base["target"], zoom=base["zoom"] * z, offset=(base["offset"][0] + drift * (2 * u - 1), base["offset"][1]),
                                   aperture=base["ap"], focus=1.6)
        self.cam = dict(size=sh["id"], shake=cam.get("shake", 0.5), kf=[mk(t0, 0, z0), mk(t1, 1, z1)])
        self.adapter = _sh_adapter(self.cam, self.rig, t0, t1)
        self.fx = self._fx()

    def _phone_light(self, t):
        return 0.5 * self.perf.ch["aB_hold"](t) * (0.0 if self.perf.ch["aB_ear"](t) > 0.5 else 1.0) * self.k_amb

    def _fx(self):
        bank, sh, rig = self.ctx.bank, self.sh, self.rig
        if bank is None:
            return []
        out = []
        S = gp_bank.screen_of
        for g in sh["gp"]:
            a0, a1 = sh["t0"] + g["start"], sh["t0"] + g["start"] + g["duration"]

            def fx(c, cam, t, g=g, a0=a0, a1=a1):
                if not (a0 <= t <= a1):
                    return c
                u = (t - a0) / max(a1 - a0, 1e-6)
                fade = min(1.0, (t - a0) / 0.12, (a1 - t) / 0.25)
                if g["effect"] == "rays" and g["anchor"] == "phone":
                    x, y, z = S(cam, 1.0, rig.anchor("phone"))
                    bank.draw(c, "rays", t, (x, y), z, opacity=g["intensity"] * fade * (0.0 if self.perf.ch["aB_ear"](t) > 0.5 else 1.0))
                elif g["effect"] == "worry":
                    ex, ey = rig.anchor("eyes")
                    x, y, z = S(cam, 1.0, (ex + 105, ey - 75))
                    bank.draw(c, "worry", t, (x, y), min(z, 1.6) * 1.25, opacity=g["intensity"] * fade)
                elif g["effect"] == "ticks":
                    x, y, z = S(cam, 1.0, rig.anchor("eyes"))
                    bank.draw(c, "ticks", t, (x, y), min(z, 1.55), opacity=g["intensity"] * max(0.0, 1 - u))
                return c
            out.append(fx)
        return out

    def subject_screen(self, t):
        self.rig.update(self.perf, t)
        cam = F.camera_at(None, self.adapter, t)
        cx, cy, z = cam.view(1.0)
        wx, wy = self.rig.anchor("eyes")
        return (wx - cx) * z + C0[0], (wy - cy) * z + C0[1]

    def frame(self, t, f):
        sh, rig, scene = self.sh, self.rig, self.scene
        rig.update(self.perf, t)
        rig.ui.t = max(0.0, t - sh["t0"])
        rig.update_screen(1.0, 0.0)
        self.held.p["center"] = rig.anchor("phone")
        scene.lights.ambient = self.base_amb * self.k_amb
        scene.camera = F.camera_at(None, self.adapter, t)
        self.ctx.post.exposure = self.exposure
        img = scene.render(t, f, 1.0, insert=None, dust=self.dust, fx=self.fx)
        return self.ctx.extra_vignette(img, self.vig)


class InsertShot:
    def __init__(self, sh, ctx):
        self.sh, self.ctx = sh, ctx
        self.ui = UIScreen(sh["ui"]["screen"], sh["ui"]["data"])
        self.ins = ScreenInsert(self.ui)
        amb = MOODS.get(sh["lighting"]["mood"], MOODS["neutral"])
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        base = np.array((0.05, 0.07, 0.12), np.float32) * (0.8 + 0.6 * yy) * amb[1]
        self.bg = np.broadcast_to(base, (H, W, 3)).copy()

    def frame(self, t, f):
        sh, ui = self.sh, self.ui
        u = (t - sh["t0"]) / max(sh["t1"] - sh["t0"], 1e-6)
        ui.t = max(0.0, t - sh["t0"])
        img = self.ins.apply(self.bg, t, u, 1.0, 1.0, 0.0, 0.05)
        img = bloom(img, strength=0.4)
        self.ctx.post.exposure = 1.0
        img = self.ctx.post.apply(img, f, 1.0)
        bank = self.ctx.bank
        for g in sh["gp"]:
            if g["effect"] == "ring" and bank is not None:
                t_on = sh["t0"] + g["start"]
                prog = (t - t_on) / 0.9
                if prog > 0:
                    ax, ay, aw, ah = ANCHORS.get(sh["ui"]["screen"], (60, 320, 320, 110))
                    sx = self.ins.sw / 440.0
                    cx = 540 - self.ins.sw / 2 + (ax + aw / 2) * sx
                    cy = self.ins.center[1] - self.ins.sh / 2 + (ay + ah / 2) * (self.ins.sh / 800.0)
                    img = bank.draw(img, "ring", t, (cx, cy), max(0.6, aw * sx / 780.0), opacity=g["intensity"] * min(1.0, prog * 3), variant=min(15, int(prog * 15)))
            if g["effect"] == "arcs" and bank is not None and sh["t0"] + g["start"] <= t <= sh["t0"] + g["start"] + g["duration"]:
                for side in (-1, 1):
                    img = bank.draw(img, "arcs", t, (540 + side * 470, 620), 1.8, opacity=0.8)
        return img


class ProceduralShot:
    def __init__(self, sh, ctx):
        self.sh, self.ctx = sh, ctx

    def frame(self, t, f):
        sh = self.sh
        u = (t - sh["t0"]) / max(sh["t1"] - sh["t0"], 1e-6)
        img = PR.render(sh["procedural"]["type"], sh["procedural"]["data"], u, t - sh["t0"], seed=_seed(sh["id"]))
        self.ctx.post.exposure = 1.0
        return self.ctx.post.apply(img, f, 1.0)


RENDERERS = dict(performance=PerformanceShot, insert_ui=InsertShot, procedural=ProceduralShot)


class Renderer:
    def __init__(self, plan, log=print):
        self.plan, self.ctx, self.log = plan, Ctx(plan, log), log
        self.shots = plan["shots"]
        self._r = {}
        self.dur = plan["duration"]

    def renderer(self, i):
        if i not in self._r:
            for k in [k for k in self._r if k < i - 2]:                        # keep memory flat: drop old shot renderers
                del self._r[k]
            self._r[i] = RENDERERS[self.shots[i]["treatment"]](self.shots[i], self.ctx)
        return self._r[i]

    def index_at(self, t):
        for i, s in enumerate(self.shots):
            if s["t0"] <= t < s["t1"]:
                return i
        return len(self.shots) - 1

    def frame_at(self, t, f):
        i = self.index_at(t)
        sh = self.shots[i]
        img = self.renderer(i).frame(t, f)
        tin, D = sh["transition_in"], 0.4
        if i and tin in ("dissolve", "dip", "fade") and t - sh["t0"] < D:
            a = ease("smooth", (t - sh["t0"]) / D)
            if tin == "dissolve":
                img = self.renderer(i - 1).frame(t, f) * (1 - a) + img * a
            else:
                img = img * a
        elif i == 0 and t < 0.6:
            img = img * ease("smooth", t / 0.6)
        if i + 1 < len(self.shots) and self.shots[i + 1]["transition_in"] == "dip" and self.shots[i + 1]["t0"] - t < 0.2:
            img = img * max(0.0, (self.shots[i + 1]["t0"] - t) / 0.2)
        if t > self.dur - 1.0:
            img = img * max(0.0, (self.dur - t) / 1.0)
        return img
