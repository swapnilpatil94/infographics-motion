"""CastRig: one character whose BODY (pose/prop) can change between shots and whose faces are
loaded on demand. Heads and bodies live in the same canvas frame (asset_pipeline/cast_builder.py),
so any head/body pair aligns. Everything else (breathing, look, tremor, blend of faces) is BustRig."""
import json
import os

from engine.shorts.character import BustRig, ORIGIN, RES, SC, c2w, NECK, SEAT
from engine.shorts.layers import Layer
from engine.shorts.raster import rasterize_file, ROOT

CAST_JSON = "assets/character/cast/cast.json"


def _load(path, name):
    arr, (ox, oy) = rasterize_file(os.path.join(ROOT, path), zoom=SC * RES)
    return Layer(name, arr, (ORIGIN[0] + ox / RES, ORIGIN[1] + oy / RES), RES, par=1.0, depth=1.6)


def spec():
    return json.load(open(os.path.join(ROOT, CAST_JSON)))


class CastRig(BustRig):
    def __init__(self, cast_id):
        self.spec = spec()
        self.cast_id = cast_id
        ch = self.spec["characters"][cast_id]
        self._head_paths = ch["heads"]
        self._bodies = {}
        self.heads = {}
        self.body_name = None
        self.body = None
        self.neck_w = c2w(NECK)
        self.seat_w = c2w(SEAT)
        self.state = dict(roll=0.0, hdx=0.0, hdy=0.0, bdx=0.0, bdy=0.0, breathe=0.0, weights={"calm": 1.0})

    def use(self, body, faces):
        """Switch pose and make sure every face the shot needs (plus 'blink') is loaded."""
        if body not in self.spec["bodies"]:
            raise KeyError(f"unknown body '{body}'")
        if body not in self._bodies:
            self._bodies[body] = _load(self.spec["bodies"][body], f"{self.cast_id}_body_{body}")
        self.body, self.body_name = self._bodies[body], body
        for f in set(faces) | {"blink"}:
            if f not in self.heads:
                self.heads[f] = _load(self._head_paths[f], f"{self.cast_id}_head_{f}")
