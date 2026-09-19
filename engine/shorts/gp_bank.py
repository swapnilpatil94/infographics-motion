"""Grease Pencil sprite bank: build (Blender) once, cache by content hash, composite (numpy/cv2) every frame.

Blender renders each hand-drawn effect as a set of GP 'takes' (boil variants) with transparent background.
The compositor plays them at 8 fps and TRACKS them to the action every frame (anchor + camera), so lines stay
glued to a moving phone or head while still boiling like real hand-drawn animation.
"""
import hashlib
import json
import math
import os
import subprocess
import time

import cv2
import numpy as np
from PIL import Image

from engine.shorts import gp_strokes as G
from engine.shorts.layers import W, H, C0
from engine.shorts.raster import ROOT

BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
SCRIPT = os.path.join(ROOT, "engine/render/gp_bank_blender.py")
CACHE = os.path.join(ROOT, "output", "cache", "gp")
BOIL_FPS = 8.0


def _key():
    h = hashlib.sha256()
    for p in (SCRIPT, G.__file__):
        h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


class Bank:
    def __init__(self, dirpath, report, built):
        self.dir, self.report, self.built_now = dirpath, report, built
        self._cache = {}

    def sprite(self, name, variant):
        k = (name, variant)
        if k not in self._cache:
            im = np.asarray(Image.open(os.path.join(self.dir, f"{name}_{variant:02d}.png")).convert("RGBA")).astype(np.float32) / 255.0
            self._cache[k] = im
        return self._cache[k]

    def draw(self, canvas, name, t, screen_xy, scale, opacity=1.0, variant=None, gain=1.0):
        """Additively blend sprite `name` centred (or top-left, per spec) at screen_xy. scale = screen px per local unit."""
        if opacity <= 0.01:
            return canvas
        sp = G.SPRITES[name]
        nvar = sp["variants"]
        v = int(t * BOIL_FPS) % nvar if variant is None else max(0, min(nvar - 1, variant))
        spr = self.sprite(name, v)
        k = scale / sp["ppu"]
        w, h = max(2, int(spr.shape[1] * k)), max(2, int(spr.shape[0] * k))
        img = cv2.resize(spr, (w, h), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
        if sp["anchor"] == "center":
            x0, y0 = int(screen_xy[0] - w / 2), int(screen_xy[1] - h / 2)
        else:
            x0, y0 = int(screen_xy[0]), int(screen_xy[1])
        xs, ys, xe, ye = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
        if xe <= xs or ye <= ys:
            return canvas
        p = img[ys - y0:ye - y0, xs - x0:xe - x0]
        canvas[ys:ye, xs:xe] += p[:, :, :3] * p[:, :, 3:4] * (opacity * gain)
        return canvas


def ensure_bank(log=print):
    """Build (via Blender) or load the sprite bank. Returns a Bank, or None if Blender is unavailable."""
    if not os.path.exists(BLENDER):
        log("[gp] Blender not found - Grease Pencil layer disabled")
        return None
    d = os.path.join(CACHE, _key())
    rep_path = os.path.join(d, "report.json")
    if os.path.exists(rep_path):
        return Bank(d, json.load(open(rep_path)), False)
    os.makedirs(d, exist_ok=True)
    spec = dict(sprites={n: dict(size=s["size"], ppu=s["ppu"], variants=s["variants"], anchor=s["anchor"], build=s.get("build", False))
                         for n, s in G.SPRITES.items()})
    sp = os.path.join(d, "spec.json")
    json.dump(spec, open(sp, "w"))
    t = time.time()
    log("[gp] building Grease Pencil sprite bank in Blender ...")
    r = subprocess.run([BLENDER, "--background", "--python", SCRIPT, "--", sp, d], capture_output=True, text=True)
    if not os.path.exists(rep_path):
        log("[gp] Blender failed:\n" + (r.stdout + r.stderr)[-800:])
        return None
    log(f"[gp] bank ready in {time.time() - t:.1f}s: {json.load(open(rep_path))['renders']} GP renders")
    return Bank(d, json.load(open(rep_path)), True)


def screen_of(cam, par, world_pt):
    cx, cy, z = cam.view(par)
    return (world_pt[0] - cx) * z + C0[0], (world_pt[1] - cy) * z + C0[1], z
