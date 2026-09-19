"""Scene assembly + per-frame rendering."""
import json
import os

import numpy as np

from engine.shorts.layers import Camera, Layer, composite_over, W, H
from engine.shorts.lighting import LightRig, Light, bloom
from engine.shorts.post import Post
from engine.shorts.raster import rasterize_file, ROOT

ROOM_RES = 1.5
ROOM_DIR = "assets/environment/generated/night_bedroom"
# draw order back -> front; "@char" is where the character layers go
ROOM_ORDER = ["wall", "decor", "sky", "clouds", "window", "curtain_l", "curtain_r", "headboard", "nightstand",
              "stand_phone", "stand_screen", "pillows", "@char", "blanket_mid", "blanket_fg"]


def load_room_layers(room_dir=ROOM_DIR):
    """Layers of a set. Understands both manifest formats: flat {name: meta} (night_bedroom)
    and {"order": [...], "layers": {...}} (sets from asset_pipeline/set_art.py)."""
    with open(os.path.join(ROOT, room_dir, "layers.json")) as f:
        man = json.load(f)
    man = man.get("layers", man)
    layers = {}
    for name, m in man.items():
        arr, (ox, oy) = rasterize_file(os.path.join(ROOT, m["svg"]), zoom=ROOM_RES)
        layers[name] = Layer(name, arr, (m["world"][0] + ox / ROOM_RES, m["world"][1] + oy / ROOM_RES), ROOM_RES,
                             par=m["par"], depth=m["depth"], emissive=m.get("emissive", False),
                             sway=6.0 if m.get("sway") else 0.0)
        layers[name].opacity = m.get("opacity", 1.0)
    return layers


class Scene:
    def __init__(self, rig, room=None, order=None, ambient=(0.16, 0.20, 0.32), bloom_strength=0.55, post=None):
        self.room = room if room is not None else load_room_layers()
        self.order = order or ROOM_ORDER
        self.rig = rig
        self.extra = []                 # (order_name_after, layer) e.g. phone screen, dust
        self.camera = Camera()
        self.lights = LightRig(ambient=ambient)
        self.post = post or Post()
        self.emissive_gain = {"sky": 1.0}
        self.bloom_strength = bloom_strength

    def ordered(self):
        out = []
        for name in self.order:
            if name == "@char":
                out += self.rig.layers
                out += [l for (after, l) in self.extra if after == "@char"]
            else:
                out.append(self.room[name])
                out += [l for (after, l) in self.extra if after == name]
        return out

    def render(self, t, frame, fade=1.0, insert=None, dust=None, fx=()):
        cam = self.camera
        canvas = np.zeros((H, W, 3), np.float32)
        canvas[:] = (0.02, 0.025, 0.05)
        cache = {}
        for layer in self.ordered():
            r = layer.rasterize_to_screen(cam, t)
            if r is None:
                continue
            patch, x0, y0 = r
            if layer.emissive:
                composite_over(canvas, patch, x0, y0, None, layer.opacity, self.emissive_gain.get(layer.name, 1.0))
            else:
                light = self.lights.lightmap(cam, t, layer.depth, cache)
                composite_over(canvas, patch, x0, y0, light, layer.opacity)
        if dust is not None:
            canvas = dust(canvas, cam, t)
        for effect in fx:
            canvas = effect(canvas, cam, t)
        if insert is not None:
            canvas = insert(canvas)
        canvas = bloom(canvas, strength=self.bloom_strength)
        return self.post.apply(canvas, frame, fade)
