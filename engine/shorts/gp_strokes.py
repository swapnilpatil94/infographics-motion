"""Stroke DESIGN for the Grease Pencil sprite bank (pure Python - no bpy, so Blender and the tests share it).

Every generator returns strokes in LOCAL units (px, y down, origin at the effect's anchor):
    dict(pts=[(x, y, radius, alpha), ...], color=(r, g, b), layer=str, cyclic=False)
`variant` seeds the hand: successive variants of one effect are different 'takes' of the same drawing, so
cycling them at 8 fps gives the classic line-boil. Nothing here is a bitmap; Blender's Grease Pencil renders it.
"""
import math
import random

CYAN = (0.55, 0.88, 1.0)
WHITE = (1.0, 1.0, 1.0)
WARM = (1.0, 0.86, 0.6)


def _taper(n, r0, r1=0.0, ease=1.0):
    return [r0 * ((1 - i / (n - 1)) ** ease * (1 - r1) + r1) for i in range(n)]


def _line(a, b, r0, color, layer, rng, wob=3.0, n=7, alpha=1.0, r1=0.05):
    pts = []
    rs = _taper(n, r0, r1)
    nx, ny = -(b[1] - a[1]), (b[0] - a[0])
    ln = math.hypot(nx, ny) or 1.0
    nx, ny = nx / ln, ny / ln
    for i in range(n):
        u = i / (n - 1)
        w = rng.uniform(-wob, wob) * math.sin(math.pi * u)
        pts.append((a[0] + (b[0] - a[0]) * u + nx * w, a[1] + (b[1] - a[1]) * u + ny * w, rs[i], alpha * (1 - 0.35 * u)))
    return dict(pts=pts, color=color, layer=layer, cyclic=False)


def rays(variant, n=11, length=(90, 230), spread=(-175, -5), color=CYAN):
    """Fan of tapered light strokes leaving a lit screen."""
    r = random.Random(1000 + variant)
    out = []
    for i in range(n):
        ang = math.radians(spread[0] + (spread[1] - spread[0]) * (i + r.uniform(-0.35, 0.35)) / max(n - 1, 1))
        L = r.uniform(*length)
        s = r.uniform(0.10, 0.22) * L + r.uniform(0, 14)
        a = (math.cos(ang) * s, math.sin(ang) * s)
        b = (math.cos(ang) * L, math.sin(ang) * L)
        out.append(_line(a, b, r.uniform(3.5, 6.0), color, "rays", r, wob=4))
    return out


def arcs(variant, color=(0.85, 0.95, 1.0)):
    """Vibration arcs either side of a buzzing phone."""
    r = random.Random(2000 + variant)
    out = []
    for side in (-1, 1):
        for k in range(2):
            rad = 44 + 30 * k + r.uniform(-3, 3)
            mid = math.radians(180 if side < 0 else 0) + r.uniform(-0.1, 0.1)
            pts = []
            for j in range(9):
                a = mid + math.radians(-42 + 84 * j / 8)
                pts.append((side * 8 + math.cos(a) * rad, math.sin(a) * rad * 1.25, 3.8 * math.sin(math.pi * j / 8) + 0.6, 0.95))
            out.append(dict(pts=pts, color=color, layer="arcs", cyclic=False))
    return out


def ticks(variant, n=12, radius=(230, 300), color=WHITE):
    """Radial jolt ticks around a head."""
    r = random.Random(3000 + variant)
    out = []
    for i in range(n):
        ang = 2 * math.pi * (i + r.uniform(-0.25, 0.25)) / n
        r0, r1 = r.uniform(*radius), r.uniform(radius[1] + 40, radius[1] + 110)
        out.append(_line((math.cos(ang) * r0, math.sin(ang) * r0), (math.cos(ang) * r1, math.sin(ang) * r1), r.uniform(5, 8), color, "ticks", r, wob=2, n=5))
    return out


def worry(variant, color=WHITE):
    """Tension marks off the temple (small curved dashes) - the hand-drawn 'something is wrong' accent."""
    r = random.Random(4000 + variant)
    out = []
    for k, (dx, dy, ang) in enumerate(((0, 0, -35), (18, -34, -12), (34, 6, -60))):
        a0 = math.radians(ang)
        pts = []
        for j in range(6):
            a = a0 + math.radians(-16 + 32 * j / 5)
            pts.append((dx + math.cos(a) * 36 + r.uniform(-1.5, 1.5), dy + math.sin(a) * 36 + r.uniform(-1.5, 1.5), 4.2 * math.sin(math.pi * (j + 0.5) / 6) + 0.8, 0.95))
        out.append(dict(pts=pts, color=color, layer="worry", cyclic=False))
    return out


def shaft_hatch(variant, w=1040, h=960, color=(0.62, 0.72, 1.0)):
    """Moonlight hatching: slanted hand-drawn lines through the window light shaft (atmosphere, boils at 8 fps)."""
    r = random.Random(5000 + variant)
    out = []
    # the shaft runs from the top-right (window) to the lower-left; lines cross it diagonally
    for i in range(26):
        u = i / 25.0
        cx = w * (0.84 - 0.63 * u) + r.uniform(-10, 10)          # axis of the window shaft: (870,290) -> (220,1250) world
        cy = h * (0.02 + 0.96 * u)
        half = 90 + 90 * math.sin(math.pi * u) + r.uniform(-8, 8)
        a = (cx - half * 0.55, cy + half * 0.85)
        b = (cx + half * 0.55, cy - half * 0.85)
        out.append(_line(a, b, r.uniform(1.6, 2.6), color, "shaft", r, wob=2.5, n=6, alpha=0.5 + 0.4 * math.sin(math.pi * u), r1=0.6))
    return out


def ring(progress_frames=1, w=800, h=330, color=(1.0, 0.86, 0.55), seed=11):
    """One hand-drawn loop around a rect, slightly overshooting where it closes. Drawn ONCE; Blender's Build
    modifier animates the draw-on."""
    r = random.Random(seed)
    pts, n = [], 44
    for i in range(n + 6):
        a = -math.pi * 0.9 + 2 * math.pi * 1.06 * i / (n + 5)
        rx = w / 2 * (1 + 0.03 * math.sin(3 * a + 1) + 0.02 * (i / n))
        ry = h / 2 * (1 + 0.05 * math.cos(2 * a))
        pts.append((math.cos(a) * rx + r.uniform(-2.5, 2.5), math.sin(a) * ry * 1.02 + r.uniform(-2.5, 2.5), 7.5 * (0.55 + 0.45 * math.sin(math.pi * i / (n + 5))), 1.0))
    return [dict(pts=pts, color=color, layer="ring", cyclic=False)]


# name -> (generator, local size (w, h), px per unit, variants, anchor mode, kwargs)
SPRITES = {
    "rays": dict(gen=rays, size=(560, 560), ppu=2.0, variants=8, anchor="center"),
    "arcs": dict(gen=arcs, size=(300, 300), ppu=2.0, variants=8, anchor="center"),
    "ticks": dict(gen=ticks, size=(920, 920), ppu=1.5, variants=8, anchor="center"),
    "worry": dict(gen=worry, size=(220, 220), ppu=2.0, variants=8, anchor="center"),
    "shaft": dict(gen=shaft_hatch, size=(1040, 960), ppu=1.0, variants=8, anchor="topleft"),
    "ring": dict(gen=lambda v: ring(), size=(920, 440), ppu=1.5, variants=16, anchor="center", build=True),
}
