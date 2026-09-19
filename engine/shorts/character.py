"""Bust character rig for the 2D compositor.

Body and head are separate rasters sharing the source composite's canvas
frame (see asset_pipeline.bust_rig), so:
  * the head rolls/nods on a neck pivot independently of the torso,
  * every face expression is a full head layer we cross-fade between,
  * breathing / tremor / startle move the body and carry the head with it.

Granularity is what the Open Peeps art supports: a rigid torso (no elbow
or finger articulation - the hand holding the phone is part of the torso
drawing), a rigid head, whole-face expressions. The actions library
(engine.shorts.actions) drives only these channels.
"""
import json
import math
import os

import numpy as np

from engine.shorts.layers import Layer
from engine.shorts.raster import rasterize_file, ROOT

SC = 0.66                 # canvas px -> world units
RES = 3.0                 # raster px per world unit (allows ~3x push-in)
ORIGIN = (55.0, 513.0)    # world position of the bust canvas origin

# Anchors measured off the art (canvas px at zoom 1, see phone_grid audit).
NECK = (612.0, 655.0)
SEAT = (568.0, 1344.0)
EYES = (600.0, 470.0)
PHONE_QUAD = [(806, 820), (922, 826), (826, 1030), (706, 1030)]
PHONE_VISIBLE_IMG3 = [(345, 150), (700, 165), (561, 440), (480, 610), (430, 715), (396, 790), (420, 735),
                      (470, 660), (478, 625), (440, 570), (360, 520), (345, 470), (205, 455), (264, 300)]
PHONE_CENTER = (815.0, 930.0)


def c2w(p):
    return (ORIGIN[0] + p[0] * SC, ORIGIN[1] + p[1] * SC)


def _T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1.0]])


def _S(sx, sy):
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1.0]])


def _R(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


class BustRig:
    def __init__(self, spec_path):
        with open(os.path.join(ROOT, spec_path)) as f:
            spec = json.load(f)
        self.spec = spec
        z = SC * RES
        arr, (ox, oy) = rasterize_file(os.path.join(ROOT, spec["body_svg"]), zoom=z)
        self.body = Layer("rahul_body", arr, (ORIGIN[0] + ox / RES, ORIGIN[1] + oy / RES), RES, par=1.0, depth=1.6)
        self.heads = {}
        for name, info in spec["faces"].items():
            arr, (ox, oy) = rasterize_file(os.path.join(ROOT, info["svg"]), zoom=z)
            self.heads[name] = Layer(f"rahul_head_{name}", arr, (ORIGIN[0] + ox / RES, ORIGIN[1] + oy / RES),
                                     RES, par=1.0, depth=1.6)
        self.neck_w = c2w(NECK)
        self.seat_w = c2w(SEAT)
        self.state = dict(roll=0.0, hdx=0.0, hdy=0.0, bdx=0.0, bdy=0.0, breathe=0.0, weights={"tired": 1.0})

    @property
    def layers(self):
        return [self.body] + list(self.heads.values())

    def anchor(self, name):
        if name == "head":
            return c2w(EYES)
        if name == "phone":
            return c2w(PHONE_CENTER)
        if name == "chest":
            return c2w((620, 900))
        if name == "eyes":
            return c2w(EYES)
        raise KeyError(name)

    def body_matrix(self):
        s = self.state
        b = s["breathe"]
        sx, sy = self.seat_w
        return _T(sx + s["bdx"], sy + s["bdy"]) @ _S(1 + b * 0.35, 1 + b) @ _T(-sx, -sy)

    def apply(self):
        s = self.state
        mb = self.body_matrix()
        nx, ny = self.neck_w
        mh = mb @ _T(nx + s["hdx"], ny + s["hdy"]) @ _R(s["roll"]) @ _T(-nx, -ny)
        self.body.world_xf = mb
        wsum = sum(s["weights"].values()) or 1.0
        for name, layer in self.heads.items():
            w = s["weights"].get(name, 0.0) / wsum
            layer.world_xf = mh
            layer.opacity = w
            layer.visible = w > 0.001
