"""Generates the night-bedroom environment as separate SVG layers (wall,
decor, sky, window, curtains, headboard, pillows, nightstand, blankets).

Hand-authored in code — there is no licensed source whose style matches
Open Peeps' linework for interiors (see asset_pipeline/discover.py), and
mismatched clip-art would hurt more than help. All shapes use the same ink
weight/wobble/hatching language as the character so the two read as one
illustrator's work. Seeded: same seed -> byte-identical SVG.

World space: 1080x1920 (the wide-shot screen). Each layer's SVG viewBox IS
its world rectangle, so placing a layer needs no extra offset math.

Colours are DAYLIGHT ALBEDO. The night look comes entirely from the
compositor's light-maps (ambient + moon + phone), not from painting dark
colours here — that is what lets black ink stay black and lit areas glow.
"""
import json
import math
import os
import random

from asset_pipeline.ink import Ink, INK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets/environment/generated/night_bedroom")
SEED = 1207


def wall_layer():
    a = Ink(-160, -160, 1400, 2240, SEED + 1)
    a.raw('<rect x="-160" y="-160" width="1400" height="2240" fill="#d6cfc0"/>')
    for x in range(-150, 1240, 64):                       # wallpaper stripes
        a.path([(x, -160), (x + a.rng.uniform(-2, 2), 1130)], sw=2.2, wobble=1.6, step=90, opacity=0.16)
    a.rect(-160, 1130, 1400, 400, fill="#b9af9c", sw=0, wobble=0)   # wainscot
    for x in range(-160, 1240, 210):                      # wainscot panels
        a.rect(x + 22, 1180, 166, 290, fill="#c4baa7", sw=3.5, wobble=1.4)
    a.rect(-160, 1112, 1400, 26, fill="#e3dccb", sw=5, wobble=1.2)  # chair rail
    a.rect(-160, 1520, 1400, 70, fill="#e6dfd0", sw=5, wobble=1.2)  # baseboard
    a.rect(-160, 1590, 1400, 490, fill="#a98859", sw=0, wobble=0)   # floor
    for i, y in enumerate((1640, 1730, 1840, 1980)):
        a.path([(-160, y), (1240, y)], sw=4, wobble=1.5, step=80)
        off = 40 * (i % 2)
        for x in range(-100 + off, 1240, 230):
            a.path([(x, y), (x + 8 * i - 4, y + 90 + i * 12)], sw=3.5, wobble=1.2, step=60)
    a.hatch([(-160, 1590), (1240, 1590), (1240, 1660), (-160, 1660)], 80, 9, 2.4, 0.55, gradient=(7, 26))
    # shade the upper corners with hatching (engraved vignette)
    a.hatch([(-160, -160), (520, -160), (-160, 640)], 42, 10, 2.4, 0.5, gradient=(7, 34))
    a.hatch([(1240, -160), (700, -160), (1240, 420)], 138, 10, 2.4, 0.5, gradient=(7, 34))
    return "wall", a, dict(par=0.6, depth=3.2)


def decor_layer():
    a = Ink(0, 200, 700, 400, SEED + 2)
    cx, cy, r = 420, 372, 84
    a.ellipse(cx, cy, r, r, fill="#efe9da", sw=7)
    a.ellipse(cx, cy, r - 13, r - 13, fill="none", sw=2.5)
    for k in range(12):
        ang = math.radians(k * 30)
        L = 13 if k % 3 == 0 else 7
        a.line((cx + (r - 16) * math.sin(ang), cy - (r - 16) * math.cos(ang)),
               (cx + (r - 16 - L) * math.sin(ang), cy - (r - 16 - L) * math.cos(ang)),
               sw=4 if k % 3 == 0 else 2.5, wobble=0.3)
    hh = math.radians((2 + 47 / 60) * 30)     # 2:47 — the hour that sets the mood
    mm = math.radians(47 * 6)
    a.line((cx, cy), (cx + 40 * math.sin(hh), cy - 40 * math.cos(hh)), sw=7, wobble=0.3)
    a.line((cx, cy), (cx + 60 * math.sin(mm), cy - 60 * math.cos(mm)), sw=4.5, wobble=0.3)
    a.ellipse(cx, cy, 6, 6, fill=INK, sw=0)
    # framed hills-and-sun drawing
    fx, fy, fw, fh = 100, 270, 190, 230
    a.line((fx + fw / 2, fy), (fx + fw / 2 - 26, fy - 38), sw=3, wobble=0.5)
    a.line((fx + fw / 2, fy), (fx + fw / 2 + 26, fy - 38), sw=3, wobble=0.5)
    a.rect(fx, fy, fw, fh, fill="#7a5a3a", sw=7)
    a.rect(fx + 16, fy + 16, fw - 32, fh - 32, fill="#efe9da", sw=3)
    a.ellipse(fx + 128, fy + 78, 20, 20, fill="#e7c56b", sw=3)
    hills = [(fx + 16, fy + 170), (fx + 62, fy + 132), (fx + 110, fy + 152), (fx + 150, fy + 120),
             (fx + fw - 16, fy + 150), (fx + fw - 16, fy + fh - 16), (fx + 16, fy + fh - 16)]
    a.poly(hills, fill="#b3bf9f", sw=3.5, smooth=False, wobble=1.0)
    a.hatch(hills, 60, 7, 1.8, 0.6)
    return "decor", a, dict(par=0.6, depth=3.1)


def sky_layer():
    x0, y0, w, h = 690, 250, 360, 560
    a = Ink(x0, y0, w, h, SEED + 3)
    a.defs.append('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
                  '<stop offset="0" stop-color="#0c1532"/><stop offset="0.55" stop-color="#1f3064"/>'
                  '<stop offset="1" stop-color="#3a4d8c"/></linearGradient>'
                  '<radialGradient id="halo"><stop offset="0" stop-color="#dfe6ff" stop-opacity="0.55"/>'
                  '<stop offset="1" stop-color="#dfe6ff" stop-opacity="0"/></radialGradient>')
    a.raw(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="url(#sky)"/>')
    for _ in range(46):
        sx, sy = a.rng.uniform(x0 + 20, x0 + w - 20), a.rng.uniform(y0 + 30, y0 + 330)
        a.raw(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{a.rng.uniform(0.8, 2.3):.1f}" '
              f'fill="#fff" opacity="{a.rng.uniform(0.35, 1):.2f}"/>')
    mx, my = 930, 400
    a.raw(f'<circle cx="{mx}" cy="{my}" r="150" fill="url(#halo)"/>')
    a.raw(f'<circle cx="{mx}" cy="{my}" r="50" fill="#f6f1d6"/>')
    for (dx, dy, r) in ((-14, -10, 9), (12, 8, 12), (-4, 20, 6), (18, -18, 5)):
        a.raw(f'<circle cx="{mx + dx}" cy="{my + dy}" r="{r}" fill="none" stroke="#b8b9a4" stroke-width="2" opacity="0.55"/>')
    for (cx, cy, rx, ry, op) in ((860, 470, 120, 16, 0.62), (960, 452, 90, 12, 0.55), (760, 560, 110, 14, 0.4)):
        a.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#16234f" opacity="{op}"/>')
    sky_line = [(690, 810), (690, 738), (730, 738), (730, 712), (776, 712), (776, 742), (820, 742), (820, 690),
                (846, 690), (846, 670), (858, 670), (858, 690), (890, 690), (890, 730), (940, 730), (940, 700),
                (990, 700), (990, 745), (1050, 745), (1050, 810)]
    a.raw('<path d="M' + " L".join(f"{x},{y}" for x, y in sky_line) + ' Z" fill="#080c1c"/>')
    for (wx, wy) in ((750, 730), (800, 738), (866, 700), (960, 722), (1010, 730)):
        a.raw(f'<rect x="{wx}" y="{wy}" width="6" height="8" fill="#ffcf7a"/>')
    for k in range(5):                                       # faint glass reflections
        a.raw(f'<path d="M{760 + k * 55},{y0} l-90,{h}" stroke="#fff" stroke-width="10" opacity="0.045"/>')
    return "sky", a, dict(par=0.4, depth=3.4, emissive=True)


def window_layer():
    x0, y0, w, h = 560, 190, 620, 760
    a = Ink(x0, y0, w, h, SEED + 4)
    outer = [(690, 250), (1050, 250), (1050, 800), (690, 800)]
    inner = [(722, 282), (1018, 282), (1018, 768), (722, 768)]
    a.raw('<path fill-rule="evenodd" fill="#e8e2d2" d="M690,250 L1050,250 L1050,800 L690,800 Z '
          'M722,282 L1018,282 L1018,768 L722,768 Z"/>')
    a.poly(outer, fill="none", sw=7, wobble=1.0)
    a.poly(inner, fill="none", sw=5, wobble=1.0)
    a.rect(863, 282, 14, 486, fill="#e8e2d2", sw=4, wobble=0.8)
    a.rect(722, 518, 296, 14, fill="#e8e2d2", sw=4, wobble=0.8)
    a.poly([(660, 800), (1090, 800), (1090, 842), (660, 842)], fill="#e0d9c8", sw=6, wobble=1.0)
    a.hatch([(668, 844), (1080, 844), (1080, 905), (668, 905)], 82, 8, 2.2, 0.55, gradient=(6, 24))
    a.line((596, 222), (1160, 222), sw=9, wobble=0.6)                  # curtain rod
    a.ellipse(596, 222, 13, 13, fill="#d6b25e", sw=4)
    a.ellipse(1160, 222, 13, 13, fill="#d6b25e", sw=4)
    # plant on the sill (life detail)
    a.poly([(724, 800), (784, 800), (774, 752), (734, 752)], fill="#b6704f", sw=5, wobble=0.8)
    for (dx, dy, ang) in ((0, -60, -24), (14, -78, 6), (28, -58, 30), (6, -44, -50), (22, -46, 52)):
        px, py = 754 + dx, 750
        a.ellipse(px + dx * 0.2, py + dy / 2, 11, abs(dy) / 2, fill="#6a8a5a", sw=3.5, rot=ang)
    return "window", a, dict(par=0.62, depth=3.0)


def _curtain(mirror):
    x0, y0, w, h = 590, 200, 590, 900
    a = Ink(x0, y0, w, h, SEED + (5 if not mirror else 6))
    m = (lambda x: 1740 - x) if mirror else (lambda x: x)
    left = [(618, 232), (650, 420), (652, 640), (634, 820), (606, 1010)]
    right = [(790, 232), (778, 420), (746, 640), (774, 820), (802, 1010)]
    outline = [(m(x), y) for x, y in left] + [(m(x), y) for x, y in reversed(right)]
    a.poly(outline, fill="#a86a66", sw=7, smooth=True, wobble=0.8)
    folds = 8
    for i in range(1, folds):
        t = i / folds
        pts = [(m(left[k][0] + (right[k][0] - left[k][0]) * t + a.rng.uniform(-3, 3)), left[k][1]) for k in range(5)]
        a.path(pts, sw=4.2, wobble=0.8, smooth=True, opacity=0.9)
    for i in range(0, folds, 2):                                   # shaded troughs
        t0, t1 = i / folds, (i + 1) / folds
        band = [(m(left[k][0] + (right[k][0] - left[k][0]) * t0), left[k][1]) for k in range(5)] + \
               [(m(left[k][0] + (right[k][0] - left[k][0]) * t1), left[k][1]) for k in range(4, -1, -1)]
        a.hatch(band, 84, 8, 2.0, 0.55, gradient=(6, 18))
    tx0, tx1 = sorted((m(652), m(746)))                      # tie-back band at the cinch
    a.rrect(tx0 - 6, 626, tx1 - tx0 + 12, 28, 8, fill="#d6b25e", sw=4)
    return a


def curtain_l_layer():
    return "curtain_l", _curtain(False), dict(par=0.9, depth=2.8, sway=1)


def curtain_r_layer():
    return "curtain_r", _curtain(True), dict(par=0.9, depth=2.8, sway=1)


def headboard_layer():
    a = Ink(-20, 560, 660, 900, SEED + 7)
    r = 90
    pts = [(20, 1430), (20, 590 + r)]
    for k in range(1, 8):
        ang = math.radians(180 + k * 90 / 8)
        pts.append((20 + r + r * math.cos(ang), 590 + r + r * math.sin(ang)))
    pts += [(610 - r, 590), ]
    for k in range(1, 8):
        ang = math.radians(270 + k * 90 / 8)
        pts.append((610 - r + r * math.cos(ang), 590 + r + r * math.sin(ang)))
    pts += [(610, 1430)]
    a.poly(pts, fill="#7d5c3b", sw=8, wobble=1.2, step=60)
    a.rect(62, 650, 506, 700, fill="#8b6743", sw=4.5, wobble=1.3)
    for x in range(146, 568, 84):
        a.path([(x, 654), (x + a.rng.uniform(-2, 2), 1346)], sw=3, wobble=1.5, step=80, opacity=0.55)
    a.hatch([(20, 600), (130, 600), (130, 1430), (20, 1430)], 88, 9, 2.4, 0.6, gradient=(6, 26))
    a.hatch([(62, 650), (568, 650), (568, 720), (62, 720)], 0, 9, 2.0, 0.45, gradient=(6, 22))
    return "headboard", a, dict(par=0.85, depth=2.2)


def pillows_layer():
    a = Ink(-120, 900, 960, 420, SEED + 8)

    def pillow(cx, cy, w, h, rot):
        rr = math.radians(rot)
        pts = []
        for k in range(28):
            t = 2 * math.pi * k / 28
            sx = math.copysign(abs(math.cos(t)) ** 0.55, math.cos(t)) * w / 2
            sy = math.copysign(abs(math.sin(t)) ** 0.7, math.sin(t)) * h / 2
            pts.append((cx + sx * math.cos(rr) - sy * math.sin(rr), cy + sx * math.sin(rr) + sy * math.cos(rr)))
        a.poly(pts, fill="#e9e3d6", sw=6.5, smooth=True, wobble=1.0, step=70)
        a.hatch(pts, 60, 9, 2.0, 0.5, gradient=(7, 28))
        for (fx, fy, fa) in ((-w * 0.42, -h * 0.28, 25), (w * 0.4, h * 0.25, -30), (-w * 0.3, h * 0.33, -10)):
            x1, y1 = cx + fx * math.cos(rr) - fy * math.sin(rr), cy + fx * math.sin(rr) + fy * math.cos(rr)
            a.line((x1, y1), (x1 + 34 * math.cos(math.radians(fa + rot)), y1 + 34 * math.sin(math.radians(fa + rot))),
                   sw=3.2, wobble=0.6)
    pillow(120, 1110, 340, 235, -8)
    pillow(690, 1150, 310, 215, 9)
    return "pillows", a, dict(par=0.92, depth=2.0)


def nightstand_layer():
    a = Ink(770, 900, 420, 780, SEED + 9)
    a.poly([(795, 1195), (1135, 1195), (1135, 1238), (795, 1238)], fill="#b08a5c", sw=6.5)
    a.rect(815, 1238, 300, 332, fill="#9c7852", sw=6.5)
    a.rect(845, 1276, 240, 156, fill="#a68259", sw=4.5)
    a.ellipse(965, 1352, 11, 11, fill="#d6b25e", sw=4)
    a.rect(845, 1456, 240, 96, fill="#a68259", sw=4.5)
    a.rect(830, 1570, 30, 42, fill="#8a6742", sw=5)
    a.rect(1070, 1570, 30, 42, fill="#8a6742", sw=5)
    a.hatch([(1030, 1240), (1115, 1240), (1115, 1570), (1030, 1570)], 88, 8, 2.2, 0.55, gradient=(6, 22))
    # lamp (off) — ceramic base, stem, shade
    a.poly([(925, 1195), (1005, 1195), (1020, 1160), (1010, 1110), (985, 1082), (945, 1082), (920, 1110), (910, 1160)],
           fill="#6d8fa0", sw=6, smooth=True, wobble=0.8)
    a.line((965, 1084), (965, 1040), sw=8, wobble=0.4)
    a.poly([(925, 940), (1005, 940), (1075, 1052), (855, 1052)], fill="#e6ce98", sw=6.5, wobble=0.9)
    a.ellipse(965, 940, 40, 8, fill="#d8bd82", sw=4)
    a.hatch([(925, 940), (1005, 940), (1075, 1052), (855, 1052)], 76, 8, 2.0, 0.45, gradient=(24, 7))
    # glass of water
    a.poly([(828, 1195), (872, 1195), (866, 1132), (834, 1132)], fill="#cfe0e6", sw=4.5, wobble=0.5)
    a.line((836, 1150), (864, 1150), sw=2.5, wobble=0.3)
    a.hatch([(795, 1612), (1135, 1612), (1150, 1660), (780, 1660)], 82, 9, 2.4, 0.55, gradient=(6, 22))
    return "nightstand", a, dict(par=0.95, depth=2.0)


# phone leaning against the lamp base: the practical light that makes the "interruption" an on-screen event
STAND_PHONE = [(1032, 1196), (1110, 1190), (1098, 1076), (1026, 1084)]
STAND_SCREEN = [(1042, 1184), (1100, 1180), (1090, 1090), (1036, 1096)]


def stand_phone_layer():
    a = Ink(1000, 1050, 140, 170, SEED + 20)
    a.poly(STAND_PHONE, fill="#20222d", sw=5.5, wobble=0.35, step=60)
    a.poly(STAND_SCREEN, fill="#05060b", sw=0, wobble=0)               # dark glass while idle
    a.line((1052, 1088), (1080, 1086), sw=2.4, wobble=0.1, stroke="#3a3f52")
    return "stand_phone", a, dict(par=0.95, depth=1.95)


def stand_screen_layer():
    a = Ink(1000, 1050, 140, 170, SEED + 21)
    a.defs.append('<linearGradient id="scr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dff6ff"/>'
                  '<stop offset="1" stop-color="#7fcdf0"/></linearGradient>')
    a.raw('<path d="M' + " L".join(f"{x},{y}" for x, y in STAND_SCREEN) + ' Z" fill="url(#scr)"/>')
    a.raw('<rect x="1046" y="1118" width="46" height="16" rx="5" fill="#ffffff" opacity="0.85"/>')     # banner
    a.raw('<rect x="1046" y="1142" width="34" height="8" rx="3" fill="#ffffff" opacity="0.55"/>')
    return "stand_screen", a, dict(par=0.95, depth=1.94, emissive=True, opacity=0.0)


def clouds_layer():
    a = Ink(690, 250, 360, 560, SEED + 22)
    for (cx, cy, rx, ry, op) in ((830, 400, 70, 12, 0.5), (925, 470, 56, 10, 0.42), (800, 560, 64, 11, 0.36)):
        a.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#8fa4d8" opacity="{op}"/>')
    return "clouds", a, dict(par=0.4, depth=3.35, emissive=True)


def _blanket_edge(x_from, x_to, base, amp, seed):
    r = random.Random(seed)
    pts = []
    x = x_from
    while x <= x_to:
        pts.append((x, base + amp * math.sin(x / 78.0) + r.uniform(-6, 6)))
        x += 46
    return pts


def blanket_mid_layer():
    a = Ink(-140, 1240, 1020, 720, SEED + 10)
    top = _blanket_edge(-100, 740, 1335, 20, SEED + 11)
    body = [(-100, 2000)] + [(-100, top[0][1])] + top + [(800, 1352), (838, 1420), (846, 1560), (836, 1760), (800, 2000)]
    a.poly(body, fill="#6f86a8", sw=8, wobble=1.2, step=44)
    cid = a.clip_poly(body)
    for k in range(-6, 24):                                           # quilting
        x = -100 + k * 90
        a.raw(f'<g clip-path="url(#{cid})"><path d="M{x},1380 l700,700" stroke="{INK}" stroke-width="2" opacity="0.2"/>'
              f'<path d="M{x + 700},1380 l-700,700" stroke="{INK}" stroke-width="2" opacity="0.2"/></g>')
    band = [(x, y) for x, y in top] + [(x, y + 62 + 6 * math.sin(x / 61.0)) for x, y in reversed(top)]
    a.poly(band, fill="#e4ddce", sw=5.5, wobble=1.0, step=44)
    a.hatch(band, 70, 9, 1.8, 0.4, gradient=(7, 22))
    folds = [[(120, 1470), (210, 1560), (260, 1700), (250, 1840)],
             [(420, 1440), (500, 1560), (520, 1700), (480, 1900)],
             [(640, 1450), (700, 1580), (718, 1720)],
             [(-40, 1480), (30, 1600), (60, 1740)]]
    for f in folds:
        a.path(f, sw=5.5, wobble=1.0, smooth=True)
    a.hatch([(-100, 1700), (830, 1700), (836, 2000), (-100, 2000)], 38, 12, 2.4, 0.6, gradient=(30, 9))
    a.hatch([(-100, 1700), (830, 1700), (836, 2000), (-100, 2000)], 112, 14, 2.2, 0.45, gradient=(34, 12))
    return "blanket_mid", a, dict(par=1.05, depth=1.4)


def blanket_fg_layer():
    a = Ink(-200, 1560, 1500, 700, SEED + 12)
    left = [(-200, 2260), (-200, 1760), (-100, 1700), (60, 1690), (240, 1730), (360, 1800), (420, 1900), (430, 2260)]
    right = [(640, 2260), (660, 2010), (760, 1940), (900, 1925), (1060, 1950), (1300, 2010), (1300, 2260)]
    for shape in (left, right):
        a.poly(shape, fill="#4f6283", sw=8, smooth=True, wobble=1.0, step=60)
        a.hatch(shape, 40, 11, 2.4, 0.6, gradient=(24, 8))
        a.path(shape[2:5], sw=5, smooth=True, wobble=0.8)
    return "blanket_fg", a, dict(par=1.5, depth=0.8)


LAYERS = [wall_layer, decor_layer, sky_layer, clouds_layer, window_layer, curtain_l_layer, curtain_r_layer,
          headboard_layer, pillows_layer, nightstand_layer, stand_phone_layer, stand_screen_layer, blanket_mid_layer, blanket_fg_layer]


def build():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for fn in LAYERS:
        name, ink, meta = fn()
        path = os.path.join(OUT, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(ink.svg())
        manifest[name] = dict(meta, svg=os.path.relpath(path, ROOT), world=[ink.x0, ink.y0, ink.w, ink.h])
    with open(os.path.join(OUT, "layers.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    m = build()
    print("wrote", len(m), "layers to", OUT)
