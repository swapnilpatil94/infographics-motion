"""CROWD factory (spec sec. 14): many people from a few archetypes, without hand-making any of them.

Each member = ONE baked sprite (torso + skinned head + face) from a DNA, so a 30-person crowd costs 30 layers, not 30 rigs. Variation is seeded:
character selection, scale, position, depth, clothing, colour, orientation (mirror), animation phase. Background members get simplified motion
(sway, bob, breathing); foreground characters keep full rig acting. Depth blur comes from the same DOF rule as every other layer.
"""
import math
import random
import re

import numpy as np

from asset_pipeline import rig_art as A
from engine.characters import dna as D
from engine.shorts.character import SC, _R, _S, _T
from engine.shorts.layers import Layer
from engine.shorts.raster import ROOT, rasterize

NECK = (612.0, 655.0)
ZOOM = 0.9
_cache = {}


def _inner(svg):
    m = re.search(r"<defs>.*?</defs>(.*)</svg>", svg, re.S) or re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    return m.group(1)


def member_svg(dna):
    """Merged SVG (canvas coords) of a static neutral member."""
    import os
    torso = A.torso(fill=D.outfit(dna)["fill"], seeds_on=D.outfit(dna)["seeds"], pattern=D.outfit(dna)["pattern"], collar=D.outfit(dna)["collar"],
                    badge=D.outfit(dna).get("badge", False), epaulettes=D.outfit(dna).get("epaulettes", False))
    head = open(os.path.join(ROOT, D.head_svg_path(dna)), encoding="utf-8").read()
    parts = [_inner(torso), _inner(head)]
    face = D.EYES[dna["eyes"]]
    for svg in (A.eyes_svg(0.95, (0, 0), 0, 0.1, face), A.brows_svg(0.0, 0.0, 0.0, 0.0, D.BROWS[dna["eyebrows"]]), A.mouth_svg(0.15, 0.0, dna["mouth_width"]),
                A.nose_svg(os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/face/Serious.svg"))):
        parts.append(re.search(r"(<g transform=.*</g>)", svg, re.S).group(1))
    extras = "".join(_inner(getattr(A, n)()) for n in dna.get("extra", []))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{A.CANVAS[0]}" height="{A.CANVAS[1]}" viewBox="0 0 {A.CANVAS[0]} {A.CANVAS[1]}">{"".join(parts)}{extras}</svg>'


def _sprite(dna, mirror):
    k = (dna["id"], mirror)
    if k not in _cache:
        svg = member_svg(dna)
        if mirror:
            svg = svg.replace(">", f' transform="translate({A.CANVAS[0]} 0) scale(-1 1)">', 1) if False else svg
        arr, (ox, oy) = rasterize(svg, zoom=ZOOM)
        if mirror:
            arr = arr[:, ::-1].copy()
            ox = int(A.CANVAS[0] * ZOOM) - ox - arr.shape[1]
        _cache[k] = (arr, (ox, oy))
    return _cache[k]


class Crowd:
    """A seeded crowd. `members` is plain data (re-creatable from the plan); `layers()` builds the sprites lazily."""

    def __init__(self, seed, count, pool=("customer", "office_worker", "young_man", "young_woman", "middle_aged_man", "middle_aged_woman", "elderly_man", "student", "shopkeeper"),
                 x_range=(40, 1040), neck_y=(1010, 1230), scale=(0.42, 0.7), depth=(2.4, 3.0), par=(0.72, 0.9), name="crowd"):
        r = random.Random(f"crowd|{seed}")
        self.name, self.members = name, []
        for i in range(count):
            arch = r.choice(pool)
            t = r.random()
            self.members.append(dict(dna=D.make(arch, f"{seed}:{i}"), x=r.uniform(*x_range), y=neck_y[0] + (neck_y[1] - neck_y[0]) * t, scale=scale[0] + (scale[1] - scale[0]) * t,
                                     depth=depth[1] - (depth[1] - depth[0]) * t, par=par[0] + (par[1] - par[0]) * (1 - t), mirror=r.random() < 0.5, phase=r.uniform(0, 6.28),
                                     sway=r.uniform(0.6, 1.6), bob=r.uniform(1.0, 3.0), speed=r.uniform(0.5, 1.1)))
        self.members.sort(key=lambda m: m["y"])                       # far (high on screen) first
        self._layers = None

    def layers(self):
        if self._layers is None:
            self._layers = []
            for i, m in enumerate(self.members):
                arr, (ox, oy) = _sprite(m["dna"], m["mirror"])
                res = ZOOM / (SC * m["scale"])
                nx = (A.CANVAS[0] - NECK[0] if m["mirror"] else NECK[0])
                origin = (m["x"] - nx * SC * m["scale"] + ox / res, m["y"] - NECK[1] * SC * m["scale"] + oy / res)
                L = Layer(f"{self.name}_{i}", arr, origin, res, par=m["par"], depth=m["depth"])
                self._layers.append(L)
        return self._layers

    def update(self, t):
        for L, m in zip(self.layers(), self.members):
            ang = m["sway"] * math.sin(t * m["speed"] * 1.3 + m["phase"])
            bob = m["bob"] * math.sin(t * m["speed"] * 2.1 + m["phase"] * 1.7)
            br = 0.006 * math.sin(t * 1.0 + m["phase"])
            nx = (A.CANVAS[0] - NECK[0] if m["mirror"] else NECK[0])
            pivot = (m["x"], m["y"] + 40 * m["scale"])
            L.world_xf = _T(pivot[0], pivot[1] + bob) @ _R(ang) @ _S(1 + br, 1 + br * 1.5) @ _T(-pivot[0], -pivot[1])

    def add_to(self, scene, after="wall"):
        for L in self.layers():
            scene.room[L.name] = L
        order = list(scene.order)
        i = order.index(after) + 1
        for L in self.layers():
            order.insert(i, L.name)
            i += 1
        scene.order = order
