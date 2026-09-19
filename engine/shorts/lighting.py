"""Light-map lighting for flat layered art.

Each light paints a soft coloured mask on a quarter-resolution buffer
(cheap, and lights are smooth anyway); a layer is multiplied by
ambient + sum(lights that reach its depth). Because it is a MULTIPLY on
albedo, black ink stays black, white fills take the light colour, and a
warm/cool interplay (moon vs phone) reads as real motivated lighting
instead of a colour filter.
"""
import cv2
import numpy as np

from engine.shorts.layers import W, H, C0

QW, QH = W // 4, H // 4


class Light:
    def __init__(self, kind, color, intensity, reach=(0.0, 99.0), attach_par=1.0, **params):
        self.kind = kind
        self.color = np.array(color, np.float32)
        self.intensity = intensity          # float, or callable(t) -> float
        self.reach = reach                  # (min_depth, max_depth) of layers it lights
        self.attach_par = attach_par
        self.p = params

    def level(self, t):
        return float(self.intensity(t)) if callable(self.intensity) else float(self.intensity)


class LightRig:
    def __init__(self, ambient):
        self.ambient = np.array(ambient, np.float32)
        self.lights = []
        self._grid = None

    def add(self, light):
        self.lights.append(light)
        return light

    def _grids(self):
        if self._grid is None:
            ys, xs = np.mgrid[0:QH, 0:QW].astype(np.float32)
            self._grid = (xs * 4 + 2, ys * 4 + 2)
        return self._grid

    def _to_screen(self, cam, par, pt):
        cx, cy, z = cam.view(par)
        return (pt[0] - cx) * z + C0[0], (pt[1] - cy) * z + C0[1], z

    def _paint(self, light, cam, t):
        gx, gy = self._grids()
        lv = light.level(t)
        if lv <= 1e-4:
            return None
        if light.kind == "radial":
            sx, sy, z = self._to_screen(cam, light.attach_par, light.p["center"])
            R = light.p["radius"] * z
            sq = light.p.get("squash", 1.0)
            d = np.sqrt((gx - sx) ** 2 + ((gy - sy) / sq) ** 2) / R
            m = np.clip(1.0 - d, 0.0, 1.0) ** light.p.get("power", 2.0)
        else:  # shaft: a soft-edged polygon that fades along an axis
            pts = []
            for p in light.p["poly"]:
                sx, sy, z = self._to_screen(cam, light.attach_par, p)
                pts.append((sx / 4.0, sy / 4.0))
            mask = np.zeros((QH, QW), np.float32)
            cv2.fillPoly(mask, [np.array(pts, np.int32)], 1.0)
            mask = cv2.GaussianBlur(mask, (0, 0), light.p.get("feather", 14) / 4.0 * 2.0)
            a = np.array(pts[0]) * 0 + np.array(self._to_screen(cam, light.attach_par, light.p["axis"][0])[:2]) / 4.0
            b = np.array(self._to_screen(cam, light.attach_par, light.p["axis"][1])[:2]) / 4.0
            v = b - a
            tt = ((gx / 4.0 - a[0]) * v[0] + (gy / 4.0 - a[1]) * v[1]) / max(float(v @ v), 1e-6)
            fade = light.p.get("fade_end", 0.15)
            ramp = np.clip(1.0 - tt * (1.0 - fade), fade * 0.0, 1.0)
            m = mask * ramp
        return m[:, :, None] * light.color[None, None, :] * lv

    def lightmap(self, cam, t, depth, cache):
        """Full-resolution HxWx3 light multiplier for a layer at `depth`."""
        idx = tuple(i for i, l in enumerate(self.lights) if l.reach[0] <= depth <= l.reach[1])
        if idx in cache:
            return cache[idx]
        q = np.tile(self.ambient, (QH, QW, 1))
        for i in idx:
            key = ("paint", i)
            if key not in cache:
                cache[key] = self._paint(self.lights[i], cam, t)
            if cache[key] is not None:
                q = q + cache[key]
        full = cv2.resize(np.clip(q, 0.015, None), (W, H), interpolation=cv2.INTER_LINEAR)
        cache[idx] = full
        return full


def bloom(img, threshold=0.62, strength=0.55):
    """Glow around emissive/bright areas (window, phone screen)."""
    bright = np.clip(img - threshold, 0.0, None)
    small = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.GaussianBlur(small, (0, 0), 7)
    g2 = cv2.GaussianBlur(small, (0, 0), 22)
    glow = cv2.resize(0.65 * g1 + 0.35 * g2, (W, H), interpolation=cv2.INTER_LINEAR)
    return img + glow * strength
