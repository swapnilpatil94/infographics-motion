"""Additional story SETS (locations), authored in the same ink language as
room_art.py so every set matches the Open Peeps cast. Each set is a stack of
separable layers (own parallax + depth) with an "@char" slot; the bust
character stands at a fixed world position in every set, and each set ends
with a foreground occluder (desk / parapet / blanket) that hides the bust's
cut-off edge - the standard trick for chest-up staging.

Colours are ALBEDO; time-of-day comes from the per-set light rig in
engine/shorts/sets.py. Seeded => byte-identical SVG for the same seed.
"""
import json
import math
import os

from asset_pipeline.ink import Ink, INK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "assets/environment/generated")
FULL = (-160, -160, 1400, 2240)


def _shift(ink, dy):
    """Move a finished layer vertically (all body shapes + viewBox origin)."""
    ink.body = [f'<g transform="translate(0,{dy})">'] + ink.body + ["</g>"]
    ink.y0 += dy
    return ink


FG_SHIFT = -180   # bust bodies end at world y~1390-1420; foreground occluders must start above that


def _write(set_id, layers, order):
    out = os.path.join(GEN, set_id)
    os.makedirs(out, exist_ok=True)
    man = {}
    for name, ink, meta in layers:
        p = os.path.join(out, f"{name}.svg")
        open(p, "w", encoding="utf-8").write(ink.svg())
        man[name] = dict(meta, svg=os.path.relpath(p, ROOT), world=[ink.x0, ink.y0, ink.w, ink.h])
    json.dump(dict(order=order, layers=man), open(os.path.join(out, "layers.json"), "w"), indent=2)
    return man


# =============================================================== office (day)
def office_day():
    S = 4100
    layers = []
    a = Ink(*FULL, S + 1)
    a.raw('<rect x="-160" y="-160" width="1400" height="2240" fill="#cbd7cf"/>')
    for x in range(-150, 1240, 90):
        a.path([(x, -160), (x + a.rng.uniform(-2, 2), 1500)], sw=1.8, wobble=1.2, step=90, opacity=0.10)
    a.rect(-160, 1380, 1400, 60, fill="#dfe6df", sw=5, wobble=1.0)                # skirting
    a.hatch([(-160, -160), (480, -160), (-160, 560)], 42, 11, 2.4, 0.42, gradient=(7, 34))
    a.hatch([(1240, -160), (760, -160), (1240, 300)], 138, 11, 2.4, 0.42, gradient=(7, 34))
    layers.append(("wall", a, dict(par=0.6, depth=3.2)))

    # clock + corkboard with notes
    a = Ink(60, 200, 620, 460, S + 2)
    cx, cy, r = 150, 300, 74
    a.ellipse(cx, cy, r, r, fill="#f4f0e4", sw=7)
    for k in range(12):
        ang = math.radians(k * 30)
        a.line((cx + (r - 12) * math.sin(ang), cy - (r - 12) * math.cos(ang)),
               (cx + (r - 22) * math.sin(ang), cy - (r - 22) * math.cos(ang)), sw=3.5, wobble=0.3)
    hh, mm = math.radians((10 + 10 / 60) * 30), math.radians(60)
    a.line((cx, cy), (cx + 36 * math.sin(hh), cy - 36 * math.cos(hh)), sw=7, wobble=0.3)
    a.line((cx, cy), (cx + 54 * math.sin(mm), cy - 54 * math.cos(mm)), sw=4.5, wobble=0.3)
    a.ellipse(cx, cy, 5, 5, fill=INK, sw=0)
    a.rect(280, 230, 360, 270, fill="#c9a26b", sw=8)                                 # cork frame
    a.rect(294, 244, 332, 242, fill="#dcc08e", sw=3)
    cols = ["#f2d35b", "#f0a6a0", "#9fd0e6", "#b8dc9b"]
    for i, (nx, ny, rot) in enumerate(((310, 262, -4), (410, 270, 3), (510, 258, -2), (330, 372, 4), (440, 380, -3), (536, 366, 5))):
        a.rect(nx, ny, 84, 84, fill=cols[i % 4], sw=3.5, wobble=0.8)
        for k in range(3):
            a.line((nx + 12, ny + 26 + k * 18), (nx + 70 - a.rng.uniform(0, 26), ny + 26 + k * 18), sw=2.4, wobble=0.6, opacity=0.6)
        a.ellipse(nx + 42, ny + 8, 5, 5, fill="#c0392b", sw=2)
    layers.append(("decor", a, dict(par=0.6, depth=3.1)))

    # window (sky is a separate emissive layer behind the frame)
    x0, y0, w, h = 690, 210, 420, 640
    a = Ink(x0, y0, w, h, S + 3)
    a.defs.append('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6fb4e8"/>'
                  '<stop offset="1" stop-color="#d6ecf7"/></linearGradient>')
    a.raw(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="url(#sky)"/>')
    for (sx, sy, sw_, sh) in ((760, 300, 120, 22), (920, 360, 150, 26), (800, 470, 100, 18)):
        a.raw(f'<ellipse cx="{sx}" cy="{sy}" rx="{sw_}" ry="{sh}" fill="#fff" opacity="0.85"/>')
    sk = [(x0, 850), (x0, 700), (740, 700), (740, 640), (800, 640), (800, 690), (850, 690), (850, 590), (900, 590),
          (900, 660), (960, 660), (960, 610), (1010, 610), (1010, 700), (x0 + w, 700), (x0 + w, 850)]
    a.raw('<path d="M' + " L".join(f"{x},{y}" for x, y in sk) + ' Z" fill="#7d93ad"/>')
    a.raw('<path d="M690,850 L690,760 L780,760 L780,720 L840,720 L840,780 L930,780 L930,740 L1010,740 L1010,800 L1110,800 L1110,850 Z" fill="#5d7590"/>')
    layers.append(("sky", a, dict(par=0.4, depth=3.4, emissive=True)))
    a = Ink(660, 180, 480, 720, S + 4)
    a.raw('<path fill-rule="evenodd" fill="#f1efe6" d="M680,200 L1120,200 L1120,860 L680,860 Z M710,230 L1090,230 L1090,830 L710,830 Z"/>')
    a.poly([(680, 200), (1120, 200), (1120, 860), (680, 860)], fill="none", sw=8, wobble=1.0)
    a.poly([(710, 230), (1090, 230), (1090, 830), (710, 830)], fill="none", sw=5, wobble=1.0)
    a.rect(893, 230, 14, 600, fill="#f1efe6", sw=4, wobble=0.8)
    a.rect(710, 500, 380, 14, fill="#f1efe6", sw=4, wobble=0.8)
    a.poly([(660, 860), (1140, 860), (1140, 894), (660, 894)], fill="#e7e2d3", sw=6, wobble=1.0)
    a.poly([(730, 860), (790, 860), (782, 810), (738, 810)], fill="#c46f4d", sw=5, wobble=0.8)           # pot on sill
    for (dx, dy, rot) in ((-10, -50, -25), (10, -58, 10), (24, -42, 40), (-24, -36, -50)):
        a.ellipse(760 + dx, 812 + dy, 12, 30, fill="#79ae62", sw=4, rot=rot)
    layers.append(("window", a, dict(par=0.62, depth=3.0)))

    # blinds (light-catching slats, partly raised) - separates window from wall
    a = Ink(700, 220, 400, 130, S + 5)
    for k in range(7):
        y = 224 + k * 17
        a.rect(712, y, 376, 13, fill="#f3f0e6", sw=3, wobble=0.6)
    a.line((760, 224), (760, 340), sw=2.5, wobble=0.4)
    layers.append(("blinds", a, dict(par=0.66, depth=2.9)))

    # tall plant (behind character, right)
    a = Ink(780, 1000, 420, 620, S + 6)
    a.poly([(900, 1500), (1080, 1500), (1060, 1380), (920, 1380)], fill="#b5654a", sw=6, wobble=0.9)
    a.hatch([(900, 1500), (1080, 1500), (1060, 1380), (920, 1380)], 70, 9, 2.2, 0.5)
    for (ang, ln) in ((-70, 300), (-45, 360), (-15, 380), (15, 370), (42, 340), (68, 280)):
        ex, ey = 990 + ln * math.sin(math.radians(ang)) * 0.55, 1380 - ln * math.cos(math.radians(ang))
        a.path([(990, 1385), ((990 + ex) / 2 + 20 * math.copysign(1, ang), (1385 + ey) / 2), (ex, ey)], sw=4, smooth=True, wobble=0.6)
        a.ellipse(ex, ey, 34, 74, fill="#6fa55d", sw=5, rot=ang, wobble=0.9)
    layers.append(("plant", a, dict(par=0.95, depth=2.2)))

    # desk foreground: top edge y=1540, laptop lid back, mug, papers
    a = Ink(-200, 1440, 1500, 700, S + 7)
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill="#c4915c", sw=8, wobble=1.2, step=70)
    a.poly([(-200, 1540), (1300, 1540), (1300, 1600), (-200, 1600)], fill="#d8a874", sw=6, wobble=1.0, step=70)
    a.hatch([(-200, 1610), (1300, 1610), (1300, 1780), (-200, 1780)], 84, 10, 2.4, 0.5, gradient=(7, 28))
    for gx in (-40, 430, 900):
        a.path([(gx, 1640), (gx + 6, 2140)], sw=3, wobble=1.2, step=80, opacity=0.5)
    a.poly([(70, 1500), (330, 1490), (352, 1544), (60, 1548)], fill="#f5f2ea", sw=5, wobble=0.9)         # papers
    a.poly([(90, 1480), (340, 1470), (350, 1500), (84, 1508)], fill="#e9ecf1", sw=5, wobble=0.9)
    a.rrect(870, 1470, 92, 78, 12, fill="#e8b34a", sw=6)                                                    # mug
    a.path([(962, 1490), (992, 1496), (992, 1524), (962, 1530)], sw=6, smooth=True, wobble=0.5)
    for k in range(2):
        a.path([(900 + k * 26, 1454), (890 + k * 26, 1428), (908 + k * 26, 1406)], sw=3, smooth=True, wobble=1.0, opacity=0.6)
    layers.append(("desk_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return "office_day", layers, ["wall", "decor", "sky", "window", "blinds", "plant", "@char", "desk_fg"]


# ============================================================ street (dusk)
def street_dusk():
    S = 5200
    layers = []
    a = Ink(*FULL, S + 1)
    a.defs.append('<linearGradient id="dusk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b4b8a"/>'
                  '<stop offset="0.38" stop-color="#d8708a"/><stop offset="0.68" stop-color="#f4a25f"/>'
                  '<stop offset="1" stop-color="#f8d58e"/></linearGradient>'
                  '<radialGradient id="sunh"><stop offset="0" stop-color="#fff2c8" stop-opacity="0.9"/>'
                  '<stop offset="1" stop-color="#fff2c8" stop-opacity="0"/></radialGradient>')
    a.raw('<rect x="-160" y="-160" width="1400" height="2240" fill="url(#dusk)"/>')
    a.raw('<circle cx="180" cy="1080" r="330" fill="url(#sunh)"/>')
    a.raw('<circle cx="180" cy="1080" r="70" fill="#fff0b8"/>')
    for (cx, cy, rx, ry, op) in ((720, 300, 210, 22, 0.55), (300, 460, 170, 18, 0.5), (900, 640, 190, 20, 0.45), (560, 820, 230, 16, 0.4)):
        a.raw(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#f9c3b0" opacity="{op}"/>')
    layers.append(("sky", a, dict(par=0.3, depth=4.0, emissive=True)))

    a = Ink(-160, 820, 1400, 760, S + 2)                                   # far skyline
    x = -160
    while x < 1240:
        bw, bh = a.rng.randint(70, 150), a.rng.randint(160, 420)
        a.rect(x, 1500 - bh, bw, bh + 60, fill="#8c789e", sw=4, wobble=0.8)
        for wy in range(1500 - bh + 20, 1480, 34):
            for wx in range(int(x) + 12, int(x + bw) - 14, 26):
                if a.rng.random() < 0.28:
                    a.rect(wx, wy, 11, 15, fill="#ffd486", sw=0, wobble=0)
        x += bw - 6
    layers.append(("far_city", a, dict(par=0.45, depth=3.6)))

    a = Ink(-160, 420, 1400, 1160, S + 3)                                  # mid buildings, off-centre
    for (bx, bw, top, col) in ((-150, 330, 700, "#b07f78"), (760, 480, 520, "#c99a72")):
        a.rect(bx, top, bw, 1580 - top, fill=col, sw=7, wobble=1.0)
        a.hatch([(bx, top), (bx + bw, top), (bx + bw, 1580), (bx, 1580)], 62, 12, 2.3, 0.35, gradient=(8, 30))
        for wy in range(top + 50, 1400, 150):
            for wx in range(int(bx) + 34, int(bx + bw) - 90, 120):
                lit = a.rng.random() < 0.45
                a.rect(wx, wy, 78, 96, fill="#ffd486" if lit else "#6b5a78", sw=5, wobble=0.7)
                a.line((wx + 39, wy), (wx + 39, wy + 96), sw=3, wobble=0.3)
                a.line((wx, wy + 48), (wx + 78, wy + 48), sw=3, wobble=0.3)
        a.rect(bx - 12, top - 22, bw + 24, 30, fill="#e8d3b0", sw=6, wobble=0.9)              # cornice
    a.poly([(800, 1180), (1230, 1180), (1230, 1250), (800, 1250)], fill="#d8493c", sw=6, wobble=0.8)   # shop awning
    for k in range(7):
        a.line((800 + k * 62, 1182), (800 + k * 62 + 8, 1250), sw=3, wobble=0.4, opacity=0.6)
    layers.append(("mid_buildings", a, dict(par=0.6, depth=3.0)))

    a = Ink(-160, 300, 1400, 1300, S + 4)                                  # lamp post + wires + tree
    a.rect(930, 560, 26, 1000, fill="#3f3a4a", sw=6, wobble=0.8)
    a.path([(943, 570), (943, 520), (860, 500)], sw=9, smooth=True, wobble=0.5)
    a.ellipse(846, 506, 30, 18, fill="#fff2c2", sw=6)
    for i, (y0_, sag) in enumerate(((430, 60), (470, 48), (395, 70))):
        pts = [(-160 + t * 1400 / 12, y0_ + sag * math.sin(math.pi * (t / 12)) + (t * 14 if False else 0)) for t in range(13)]
        a.path(pts, sw=3.2, smooth=True, wobble=0.5)
    a.path([(60, 1500), (58, 1260), (70, 1050)], sw=30, smooth=True, wobble=1.2)                   # trunk
    for (tx, ty, rx, ry) in ((30, 900, 170, 130), (170, 980, 150, 110), (-30, 1040, 160, 110), (110, 830, 130, 100)):
        a.ellipse(tx, ty, rx, ry, fill="#6d8f5a", sw=6, wobble=1.6)
    a.hatch([(-140, 780), (300, 780), (300, 1150), (-140, 1150)], 50, 10, 2.2, 0.35, gradient=(8, 26))
    layers.append(("lamp_tree", a, dict(par=0.8, depth=2.4)))

    a = Ink(-200, 1440, 1500, 700, S + 5)                                  # parapet fg, top edge y=1540
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill="#b9805f", sw=8, wobble=1.2, step=70)
    a.poly([(-200, 1520), (1300, 1520), (1300, 1590), (-200, 1590)], fill="#d9a888", sw=7, wobble=1.0, step=70)     # coping
    for row, y in enumerate(range(1600, 2140, 64)):
        off = 70 * (row % 2)
        a.line((-200, y), (1300, y), sw=3.2, wobble=1.2, step=80, opacity=0.65)
        for bx in range(-200 + off, 1300, 140):
            a.line((bx, y), (bx + 4, y + 64), sw=3, wobble=1.0, step=60, opacity=0.6)
    a.hatch([(-200, 1600), (1300, 1600), (1300, 1780), (-200, 1780)], 82, 10, 2.3, 0.45, gradient=(7, 26))
    layers.append(("parapet_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return "street_dusk", layers, ["sky", "far_city", "mid_buildings", "lamp_tree", "@char", "parapet_fg"]


def build():
    out = {}
    for fn in (office_day, street_dusk):
        set_id, layers, order = fn()
        out[set_id] = len(_write(set_id, layers, order))
    return out


if __name__ == "__main__":
    print(build())
