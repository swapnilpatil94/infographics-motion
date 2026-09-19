"""Dust motes drifting through the moonlight: seeded, parallaxed by depth,
and defocused with the same depth-of-field rule as the layers, so near
motes become soft bokeh and far ones stay pin-sharp. Cheap atmosphere that
makes the still art feel like air with light in it.
"""
import math

import cv2
import numpy as np

from engine.shorts.layers import W, H


class Dust:
    def __init__(self, seed=5, n=54):
        r = np.random.default_rng(seed)
        self.x0 = r.uniform(60, 980, n)
        self.y0 = r.uniform(260, 1500, n)
        self.depth = r.uniform(0.9, 2.9, n)
        self.size = r.uniform(1.4, 3.8, n)
        self.vx = r.normal(0, 4.0, n)
        self.vy = r.uniform(-5.0, 7.0, n)
        self.ph = r.uniform(0, 6.28, n)
        self.n = n

    def _shaft_weight(self, x, y):
        ax, ay, bx, by = 870.0, 290.0, 220.0, 1250.0
        vx, vy = bx - ax, by - ay
        tt = ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)
        px, py = ax + vx * tt, ay + vy * tt
        d = math.hypot(x - px, y - py)
        return 0.25 + 0.75 * math.exp(-(d / 240.0) ** 2)

    def __call__(self, canvas, cam, t):
        out = canvas
        for i in range(self.n):
            par = 1.25 - 0.28 * self.depth[i]
            x = self.x0[i] + self.vx[i] * t + 14 * math.sin(0.31 * t + self.ph[i])
            y = self.y0[i] + self.vy[i] * t + 9 * math.sin(0.23 * t + self.ph[i] * 1.7)
            x = 60 + (x - 60) % 920
            y = 240 + (y - 240) % 1300
            cx, cy, z = cam.view(par)
            sx, sy = (x - cx) * z + W / 2, (y - cy) * z + H / 2
            rad = self.size[i] * z
            blur = cam.blur_screen_px(self.depth[i])
            sigma = max(0.7, math.sqrt((rad * 0.5) ** 2 + (blur * 0.9) ** 2))
            half = int(sigma * 3) + 2
            if not (-half < sx < W + half and -half < sy < H + half):
                continue
            x0, y0 = int(sx) - half, int(sy) - half
            xs0, ys0 = max(x0, 0), max(y0, 0)
            xs1, ys1 = min(x0 + 2 * half + 1, W), min(y0 + 2 * half + 1, H)
            if xs1 <= xs0 or ys1 <= ys0:
                continue
            gy, gx = np.mgrid[ys0:ys1, xs0:xs1].astype(np.float32)
            g = np.exp(-(((gx - sx) ** 2 + (gy - sy) ** 2) / (2 * sigma ** 2)))
            tw = 0.65 + 0.35 * math.sin(1.7 * t + self.ph[i] * 3)
            amp = 0.55 * tw * self._shaft_weight(x, y) * min(1.0, 4.0 / max(sigma, 1.0) + 0.35)
            out[ys0:ys1, xs0:xs1] += g[:, :, None] * amp * np.array([0.70, 0.82, 1.0], np.float32)
        return out
