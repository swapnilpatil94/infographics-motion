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


def _circle(cx, cy, rad, r, color, layer, rng, n=14, w=3.5, alpha=1.0):
    pts = []
    a0 = rng.uniform(0, 6.28)
    for i in range(n + 2):
        a = a0 + 2 * math.pi * 1.04 * i / (n + 1)
        rr = rad * (1 + rng.uniform(-0.05, 0.05))
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.92, w * (0.7 + 0.3 * math.sin(math.pi * i / (n + 1))), alpha))
    return dict(pts=pts, color=color, layer=layer, cyclic=False)


def arrow(variant, color=WARM):
    """Hand-drawn curved arrow whose TIP is at the sprite centre: 'look here' (attention grammar)."""
    r = random.Random(6000 + variant)
    pts = []
    n = 12
    for i in range(n):
        u = i / (n - 1)
        x = -190 + 190 * u + r.uniform(-2.5, 2.5)
        y = -170 + 170 * u - 70 * math.sin(math.pi * u) + r.uniform(-2.5, 2.5)
        pts.append((x, y, 5.0 * (0.55 + 0.45 * math.sin(math.pi * min(1, u * 1.2 + 0.1))), 1.0))
    out = [dict(pts=pts, color=color, layer="arrow", cyclic=False)]
    tx, ty = pts[-1][0], pts[-1][1]
    ang = math.atan2(pts[-1][1] - pts[-3][1], pts[-1][0] - pts[-3][0])
    for side in (-1, 1):
        a = ang + math.pi + side * math.radians(28)
        out.append(_line((tx, ty), (tx + math.cos(a) * 46 + r.uniform(-2, 2), ty + math.sin(a) * 46 + r.uniform(-2, 2)), 5.0, color, "arrow", r, wob=1.5, n=4, r1=0.5))
    return out


def underline(variant, color=WARM, w=620):
    """Two loose emphasis strokes (the classic double underline)."""
    r = random.Random(7000 + variant)
    out = []
    for k, dy in enumerate((-12, 14)):
        pts = []
        for i in range(12):
            u = i / 11
            pts.append((-w / 2 + w * (0.02 * k + 0.96 * u) + r.uniform(-3, 3), dy + 6 * math.sin(2.4 * u + k) + r.uniform(-2.5, 2.5), 5.5 * (0.6 + 0.4 * math.sin(math.pi * u)), 0.95))
        out.append(dict(pts=pts, color=color, layer="underline", cyclic=False))
    return out


def scribble(variant, color=WHITE):
    """Panic scribble: a tight back-and-forth zigzag loop cluster around the head."""
    r = random.Random(8000 + variant)
    out = []
    for k in range(3):
        pts = []
        cx, cy = r.uniform(-30, 30), r.uniform(-20, 20)
        n = 16
        for i in range(n):
            u = i / (n - 1)
            zig = (1 if i % 2 == 0 else -1)
            pts.append((cx + zig * (60 + 30 * k) * math.sin(math.pi * u * 0.9 + 0.2) + r.uniform(-6, 6), cy - 110 + 220 * u + r.uniform(-8, 8), 3.4 + r.uniform(-0.6, 0.6), 0.9))
        out.append(dict(pts=pts, color=color, layer="scribble", cyclic=False))
    return out


def money_flow(variant, color=(1.0, 0.82, 0.38)):
    """Coins (rings with a bar) streaming down a curved path with speed lines: money leaving."""
    r = random.Random(9000 + variant)
    out = []
    for i in range(6):
        u = (i + variant * 0.125) % 6 / 6.0
        x = 90 * math.sin(u * 5.0) + r.uniform(-6, 6)
        y = -330 + 660 * u
        rad = 24 * (0.6 + 0.6 * u)
        out.append(_circle(x, y, rad, 0, color, "money", r, w=4.0, alpha=0.6 + 0.4 * math.sin(math.pi * u)))
        out.append(_line((x - rad * 0.4, y), (x + rad * 0.4, y), 3.5, color, "money", r, wob=1, n=3, r1=0.8, alpha=0.8))
        out.append(_line((x, y - 34 - rad), (x, y - 100 - rad * 2), 3.0, color, "money", r, wob=2, n=4, r1=0.1, alpha=0.5))
    return out


def network(variant, color=(0.7, 0.85, 1.0)):
    """Social-pressure graph: many nodes, thin connections, one node highlighted (everyone is already in)."""
    r = random.Random(10000 + variant)
    base = random.Random(10001)                                       # fixed node layout; only the hand wobble varies per take
    pts = [(-330 + 660 * (i + base.uniform(0.1, 0.9)) / 11 + r.uniform(-4, 4), base.uniform(-170, 170) + r.uniform(-4, 4)) for i in range(11)]
    out = []
    for i, a in enumerate(pts):
        for j in ((i + 1) % 11, (i + 3) % 11):
            out.append(_line(a, pts[j], 2.2, color, "network", r, wob=2, n=5, alpha=0.7, r1=0.7))
    for i, (x, y) in enumerate(pts):
        out.append(_circle(x, y, 13 if i else 20, 0, color if i else WARM, "network", r, n=10, w=3.5 if i else 5.0))
    return out


def smoke(variant, color=(0.85, 0.87, 0.95)):
    """Slow rising wisps: unease/atmosphere. Boils as loose S-curves."""
    r = random.Random(11000 + variant)
    out = []
    for k in range(4):
        x0 = -110 + 75 * k + r.uniform(-12, 12)
        pts = []
        for i in range(12):
            u = i / 11
            pts.append((x0 + 42 * math.sin(3.2 * u + k * 1.3 + variant * 0.4) * (0.4 + u) + r.uniform(-2, 2), 300 - 600 * u, 3.0 + 4.5 * math.sin(math.pi * u), 0.25 + 0.35 * math.sin(math.pi * u)))
        out.append(dict(pts=pts, color=color, layer="smoke", cyclic=False))
    return out


def dust(variant, w=1080, h=1920, color=(1.0, 0.95, 0.85)):
    """Floating motes over the whole frame (quiet, lonely, time passing)."""
    r = random.Random(12000 + variant)
    out = []
    for i in range(46):
        x, y = r.uniform(30, w - 30), r.uniform(60, h - 60)
        a = r.uniform(0, 6.28)
        L = r.uniform(4, 13)
        out.append(dict(pts=[(x, y, r.uniform(1.6, 3.0), 0.7), (x + math.cos(a) * L, y + math.sin(a) * L, r.uniform(1.2, 2.4), 0.4)], color=color, layer="dust", cyclic=False))
    return out


def sweep(w=1080, h=1920, color=(0.9, 0.95, 1.0), seed=13):
    """Broad diagonal brush strokes that paint ACROSS the frame (Build modifier animates the paint-on): a hand-drawn scene transition."""
    r = random.Random(seed)
    out = []
    for k in range(7):
        y0 = -80 + k * (h + 160) / 6.0
        pts = []
        for i in range(10):
            u = i / 9
            pts.append((-60 + (w + 120) * u + r.uniform(-8, 8), y0 + 260 * u * (1 if k % 2 == 0 else -1) + r.uniform(-14, 14), 74 * (0.7 + 0.3 * math.sin(math.pi * u)), 0.55))
        out.append(dict(pts=pts, color=color, layer="sweep", cyclic=False))
    return out


# name -> (generator, local size (w, h), px per unit, variants, anchor mode, kwargs)
SPRITES = {
    "rays": dict(gen=rays, size=(560, 560), ppu=2.0, variants=8, anchor="center"),
    "arcs": dict(gen=arcs, size=(300, 300), ppu=2.0, variants=8, anchor="center"),
    "ticks": dict(gen=ticks, size=(920, 920), ppu=1.5, variants=8, anchor="center"),
    "worry": dict(gen=worry, size=(220, 220), ppu=2.0, variants=8, anchor="center"),
    "shaft": dict(gen=shaft_hatch, size=(1040, 960), ppu=1.0, variants=8, anchor="topleft"),
    "ring": dict(gen=lambda v: ring(), size=(920, 440), ppu=1.5, variants=16, anchor="center", build=True),
    "arrow": dict(gen=arrow, size=(420, 420), ppu=2.0, variants=8, anchor="center"),
    "underline": dict(gen=underline, size=(720, 120), ppu=2.0, variants=8, anchor="center"),
    "scribble": dict(gen=scribble, size=(420, 420), ppu=2.0, variants=8, anchor="center"),
    "money_flow": dict(gen=money_flow, size=(420, 800), ppu=1.5, variants=8, anchor="center"),
    "network": dict(gen=network, size=(760, 440), ppu=1.5, variants=8, anchor="center"),
    "smoke": dict(gen=smoke, size=(420, 680), ppu=1.5, variants=8, anchor="center"),
    "dust": dict(gen=dust, size=(1080, 1920), ppu=0.5, variants=8, anchor="topleft"),
    "sweep": dict(gen=lambda v: sweep(), size=(1080, 1920), ppu=0.5, variants=16, anchor="topleft", build=True),
}
