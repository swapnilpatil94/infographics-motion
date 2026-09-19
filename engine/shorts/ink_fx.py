"""Living ink: hand-drawn accents laid over the composited frame.

The role Grease Pencil plays in a Blender pipeline (a hand-crafted layer that 'boils' on top of
designed art), done here in the 2D compositor: strokes are re-drawn with seeded jitter at 8 fps
(the classic line-boil), anchored to world positions through the same camera, and blended
additively so they glow with the light they represent. Nothing here is a bitmap asset.
Effects: light_rays (fan of strokes from a screen), buzz_marks (vibration arcs), impact_ticks
(radial ticks around a head at a shock beat).
"""
import math

import cv2
import numpy as np

from engine.shorts.layers import W, H, C0

BOIL_FPS = 8.0


def _to_screen(cam, p):
    cx, cy, z = cam.view(1.0)
    return ((p[0] - cx) * z + C0[0], (p[1] - cy) * z + C0[1], z)


def _rng(t, salt):
    return np.random.default_rng(int(t * BOIL_FPS) * 7919 + salt)


def _stroke(layer, a, b, width, color, taper=True):
    """Tapered stroke: 5 segments, thickness falling from `width` to ~0."""
    for k in range(5):
        u0, u1 = k / 5, (k + 1) / 5
        p0 = (a[0] + (b[0] - a[0]) * u0, a[1] + (b[1] - a[1]) * u0)
        p1 = (a[0] + (b[0] - a[0]) * u1, a[1] + (b[1] - a[1]) * u1)
        w = max(1, int(round(width * (1 - u0) if taper else width)))
        fade = (1 - u0) ** 1.4
        cv2.line(layer, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), tuple(float(c * fade) for c in color), w, cv2.LINE_AA)


def light_rays(canvas, cam, t, origin, level, color=(0.55, 0.85, 1.0), n=11, length=(90, 230), spread=(-170, -10)):
    """Fan of hand-drawn light strokes from a lit screen. spread = angle range in degrees."""
    if level <= 0.02:
        return canvas
    r = _rng(t, 11)
    ox, oy, z = _to_screen(cam, origin)
    fx = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        ang = math.radians(spread[0] + (spread[1] - spread[0]) * (i + r.uniform(-0.35, 0.35)) / max(n - 1, 1))
        L = r.uniform(*length) * z * (0.75 + 0.25 * min(level, 1.4))
        s = r.uniform(0.10, 0.22) * L
        a = (ox + math.cos(ang) * (s + r.uniform(0, 14)), oy + math.sin(ang) * (s + r.uniform(0, 14)))
        b = (ox + math.cos(ang) * L, oy + math.sin(ang) * L)
        _stroke(fx, a, b, max(2, 4 * z ** 0.6), color)
    return canvas + fx * (0.34 * min(level, 1.3))


def buzz_marks(canvas, cam, t, origin, level, color=(0.85, 0.95, 1.0)):
    """Two arcs either side of a vibrating phone."""
    if level <= 0.02:
        return canvas
    r = _rng(t, 23)
    ox, oy, z = _to_screen(cam, origin)
    fx = np.zeros((H, W, 3), np.float32)
    for side in (-1, 1):
        for k in range(2):
            rad = (44 + 30 * k + r.uniform(-3, 3)) * z
            a0 = 100 if side < 0 else -80
            cv2.ellipse(fx, (int(ox + side * 8 * z), int(oy)), (int(rad), int(rad * 1.25)), 0,
                        a0 - 26 + r.uniform(-6, 6), a0 + 26 + r.uniform(-6, 6), color, max(2, int(3.4 * z ** 0.6)), cv2.LINE_AA)
    return canvas + fx * (0.55 * min(level, 1.2))


def impact_ticks(canvas, cam, t, origin, level, color=(1.0, 1.0, 1.0), n=12, radius=(230, 300)):
    """Short radial ticks around a head: the hand-drawn 'jolt' mark. Boils; fades with `level`."""
    if level <= 0.02:
        return canvas
    r = _rng(t, 41)
    ox, oy, z = _to_screen(cam, origin)
    fx = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        ang = 2 * math.pi * (i + r.uniform(-0.25, 0.25)) / n
        r0, r1 = r.uniform(*radius) * z, r.uniform(radius[1] + 40, radius[1] + 110) * z
        a = (ox + math.cos(ang) * r0, oy + math.sin(ang) * r0)
        b = (ox + math.cos(ang) * r1, oy + math.sin(ang) * r1)
        _stroke(fx, a, b, max(3, 6 * z ** 0.5), color, taper=True)
    return canvas + fx * (0.5 * min(level, 1.0))
