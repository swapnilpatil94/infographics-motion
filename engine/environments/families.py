"""Environment families beyond the first three sets. Same ink language as asset_pipeline/set_art.py; each family is a stack of separable
layers (background / walls / furniture / midground / foreground occluder) with a '@char' slot, parametrised by a seeded VARIATION dict.

Every generator: gen(variation:dict, seed:int) -> (layers, order). Colours are albedo; time-of-day comes from the light rig in sets.py.
"""
import math
import random

from asset_pipeline.ink import Ink, INK
from asset_pipeline.set_art import FULL, _shift, FG_SHIFT

PALETTES = {  # variation -> named colour groups (walls/floor/accent)
    "bank_branch": [dict(wall="#e9e2cf", panel="#1f3f73", counter="#b98d5a"), dict(wall="#dfe8e4", panel="#7a2f3a", counter="#a4784e"), dict(wall="#efe6d6", panel="#22574f", counter="#9c7a52")],
    "call_centre": [dict(wall="#d5dbe6", partition="#7d93b8", desk="#c7a878"), dict(wall="#e2dccb", partition="#b0708a", desk="#b99a6a"), dict(wall="#d8e4dc", partition="#6c9c8c", desk="#c2a476")],
    "indian_living_room": [dict(wall="#efdcc0", sofa="#b8543f", rug="#7d3a2e"), dict(wall="#dfe6d3", sofa="#3f6f8c", rug="#2f4f63"), dict(wall="#f2e2c9", sofa="#8c6a3f", rug="#5a3d2a")],
    "atm_area": [dict(wall="#2b3342", glass="#5b7fa8", machine="#c9ccd4"), dict(wall="#33293a", glass="#7a6fa8", machine="#d4d0c9")],
}


def _pick(family, variation, seed):
    pal = PALETTES[family]
    return pal[int(variation.get("palette", seed)) % len(pal)]


def bank_branch(v, seed):
    c = _pick("bank_branch", v, seed)
    r = random.Random(seed)
    L = []
    a = Ink(*FULL, seed + 1)
    a.raw(f'<rect x="-160" y="-160" width="1400" height="2240" fill="{c["wall"]}"/>')
    a.rect(-160, 1300, 1400, 200, fill="#c9c0aa", sw=0, wobble=0)
    a.hatch([(-160, -160), (500, -160), (-160, 500)], 42, 11, 2.4, 0.4, gradient=(7, 34))
    for x in range(-100, 1240, 180):                                        # ceiling light panels
        a.rect(x, 90, 130, 24, fill="#fffbe8", sw=4, wobble=0.6)
    L.append(("wall", a, dict(par=0.6, depth=3.2)))
    a = Ink(80, 200, 700, 300, seed + 2)                                      # bank signage panel
    a.rect(100, 230, 660, 230, fill=c["panel"], sw=8)
    a.poly([(160, 400), (250, 300), (340, 400)], fill="#f4f1e6", sw=5)
    for k in range(4):
        a.rect(178 + k * 34, 372 - k * 0, 20, 34, fill="#f4f1e6", sw=3)
    a.rect(140, 410, 220, 22, fill="#f4f1e6", sw=4)
    for k in range(3):
        a.line((420, 290 + k * 46), (700 - k * 70, 290 + k * 46), sw=10, wobble=0.6, stroke="#f4f1e6")
    L.append(("sign", a, dict(par=0.62, depth=3.1)))
    a = Ink(560, 420, 560, 700, seed + 3)                                     # teller windows (glass + dark interior)
    for i in range(2):
        x = 580 + i * 260
        a.rect(x, 500, 220, 360, fill="#22303f", sw=8)
        a.poly([(x + 20, 520), (x + 120, 520), (x + 60, 840), (x + 20, 840)], fill="#5b7fa8", sw=0, opacity=0.35)
        a.rect(x + 40, 690, 140, 90, fill="#dfe6ee", sw=5)
    L.append(("windows", a, dict(par=0.7, depth=2.9)))
    a = Ink(-80, 900, 1240, 700, seed + 4)                                    # queue rope posts + rope
    xs = [40 + i * 230 for i in range(6)]
    for x in xs:
        a.rect(x - 8, 1050, 16, 300, fill="#3f3a4a", sw=4)
        a.ellipse(x, 1046, 20, 20, fill="#d9b24a", sw=4)
    for x0, x1 in zip(xs, xs[1:]):
        a.path([(x0, 1058), ((x0 + x1) / 2, 1110), (x1, 1058)], sw=9, smooth=True, wobble=0.5, stroke="#8a2f2f")
    L.append(("queue", a, dict(par=0.9, depth=2.3)))
    a = Ink(-200, 1440, 1500, 700, seed + 5)                                  # counter (foreground occluder)
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill=c["counter"], sw=8, wobble=1.2, step=70)
    a.poly([(-200, 1540), (1300, 1540), (1300, 1590), (-200, 1590)], fill="#e6d3ae", sw=6, wobble=1.0, step=70)
    a.hatch([(-200, 1610), (1300, 1610), (1300, 1780), (-200, 1780)], 84, 10, 2.4, 0.5, gradient=(7, 28))
    a.rrect(820, 1478, 150, 60, 10, fill="#2a2f3a", sw=5)                       # card machine
    a.rect(140, 1490, 200, 50, fill="#f5f2ea", sw=5)
    L.append(("counter_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return L, ["wall", "sign", "windows", "queue", "@char", "counter_fg"]


def call_centre(v, seed):
    c = _pick("call_centre", v, seed)
    r = random.Random(seed)
    L = []
    a = Ink(*FULL, seed + 1)
    a.raw(f'<rect x="-160" y="-160" width="1400" height="2240" fill="{c["wall"]}"/>')
    for x in range(-100, 1240, 130):
        a.rect(x, 60, 96, 20, fill="#fffbe8", sw=3, wobble=0.5)
    L.append(("wall", a, dict(par=0.55, depth=3.4)))
    a = Ink(-160, 520, 1400, 800, seed + 2)                                   # far rows of cubicles, monitors glowing
    for row, (y, s, col) in enumerate(((600, 0.55, "#9fb0cc"), (760, 0.75, c["partition"]))):
        for i in range(9):
            x = -100 + i * 165 * (1.0 if row else 0.8)
            a.rect(x, y, 140 * s / 0.75, 240 * s, fill=col, sw=5)
            a.rect(x + 22 * s, y + 40 * s, 90 * s, 62 * s, fill="#b8e0f5" if r.random() < 0.7 else "#33465e", sw=4)
            a.ellipse(x + 70 * s, y + 6 * s, 26 * s, 34 * s, fill="#30323c", sw=3)
    L.append(("cubicles", a, dict(par=0.72, depth=2.9)))
    a = Ink(-200, 1440, 1500, 700, seed + 3)                                  # foreground desk with monitor edge
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill=c["desk"], sw=8, wobble=1.2, step=70)
    a.poly([(-200, 1540), (1300, 1540), (1300, 1590), (-200, 1590)], fill="#e2caa0", sw=6, wobble=1.0, step=70)
    a.rrect(760, 1220, 300, 230, 16, fill="#2c2f38", sw=8)
    a.rect(778, 1238, 264, 176, fill="#8fc0e8", sw=4)
    a.rect(890, 1450, 40, 80, fill="#2c2f38", sw=5)
    L.append(("desk_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return L, ["wall", "cubicles", "@char", "desk_fg"]


def indian_living_room(v, seed):
    c = _pick("indian_living_room", v, seed)
    r = random.Random(seed)
    L = []
    a = Ink(*FULL, seed + 1)
    a.raw(f'<rect x="-160" y="-160" width="1400" height="2240" fill="{c["wall"]}"/>')
    a.rect(-160, 1380, 1400, 700, fill="#b88c5e", sw=0, wobble=0)
    for x in range(-160, 1240, 210):
        a.path([(x, 1380), (x + 40, 2080)], sw=3, wobble=1.2, step=80, opacity=0.5)
    a.hatch([(-160, -160), (520, -160), (-160, 520)], 42, 11, 2.4, 0.4, gradient=(7, 34))
    L.append(("wall", a, dict(par=0.6, depth=3.2)))
    a = Ink(60, 180, 760, 620, seed + 2)                                      # framed pictures + ceiling fan
    a.rect(90, 300, 210, 260, fill="#7a5a3a", sw=7)
    a.rect(106, 316, 178, 228, fill="#e8dfc8", sw=3)
    a.ellipse(195, 390, 44, 44, fill="#e7c56b", sw=3)
    a.poly([(112, 520), (160, 470), (200, 500), (250, 450), (280, 520)], fill="#8fae7a", sw=4)
    a.rect(360, 330, 150, 190, fill="#7a5a3a", sw=7)
    a.rect(374, 344, 122, 162, fill="#efe6d0", sw=3)
    for k in range(3):
        a.ellipse(435, 400 + k * 34, 30, 12, fill="#c4553f", sw=3)
    a.line((640, 190), (640, 250), sw=7, wobble=0.3)
    for ang in (0, 120, 240):
        a.ellipse(640 + 60 * math.cos(math.radians(ang)), 262 + 12 * math.sin(math.radians(ang)), 70, 12, fill="#d8c9a4", sw=5, rot=ang * 0.3)
    L.append(("decor", a, dict(par=0.62, depth=3.1)))
    a = Ink(660, 260, 460, 800, seed + 3)                                     # window with curtain
    a.rect(700, 300, 330, 470, fill="#a9d3ee", sw=8)
    a.line((865, 300), (865, 770), sw=7, wobble=0.5)
    a.line((700, 535), (1030, 535), sw=7, wobble=0.5)
    a.poly([(690, 290), (780, 290), (770, 800), (700, 780)], fill="#d9905a", sw=6, smooth=True, wobble=0.8)
    a.poly([(960, 290), (1060, 290), (1050, 800), (970, 780)], fill="#d9905a", sw=6, smooth=True, wobble=0.8)
    L.append(("window", a, dict(par=0.66, depth=3.0)))
    a = Ink(-120, 900, 1320, 560, seed + 4)                                   # sofa behind the character
    a.rrect(-60, 1010, 640, 330, 40, fill=c["sofa"], sw=8)
    a.rrect(600, 1010, 620, 330, 40, fill=c["sofa"], sw=8)
    a.rrect(-80, 1130, 200, 260, 36, fill=c["sofa"], sw=8)
    a.rrect(1030, 1130, 200, 260, 36, fill=c["sofa"], sw=8)
    a.hatch([(-40, 1030), (560, 1030), (560, 1330), (-40, 1330)], 62, 12, 2.3, 0.4, gradient=(8, 26))
    a.ellipse(140, 1120, 70, 70, fill="#e8c46a", sw=6)
    L.append(("sofa", a, dict(par=0.9, depth=2.2)))
    a = Ink(-200, 1440, 1500, 700, seed + 5)                                  # coffee-table edge (foreground occluder)
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill=c["rug"], sw=8, wobble=1.2, step=70)
    for k in range(4):
        a.line((-200 + k * 380, 1640), (-200 + k * 380 + 200, 2140), sw=4, wobble=1.0, opacity=0.5)
    a.poly([(-200, 1530), (1300, 1530), (1300, 1580), (-200, 1580)], fill="#8a5a36", sw=7, wobble=1.0, step=70)
    L.append(("table_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return L, ["wall", "decor", "window", "sofa", "@char", "table_fg"]


def atm_area(v, seed):
    c = _pick("atm_area", v, seed)
    L = []
    a = Ink(*FULL, seed + 1)
    a.raw(f'<rect x="-160" y="-160" width="1400" height="2240" fill="{c["wall"]}"/>')
    for x in range(-100, 1240, 220):
        a.rect(x, -100, 12, 1700, fill="#454e60", sw=0)
    L.append(("wall", a, dict(par=0.6, depth=3.2)))
    a = Ink(520, 240, 620, 1140, seed + 2)                                    # the ATM
    a.rrect(560, 300, 500, 1000, 30, fill=c["machine"], sw=9)
    a.rect(610, 360, 400, 300, fill="#152238", sw=7)
    a.rect(630, 380, 360, 260, fill="#5fb4ff", sw=0)
    for k in range(3):
        a.line((660, 430 + k * 60), (900 - k * 60, 430 + k * 60), sw=9, wobble=0.5, stroke="#eaf6ff")
    for i in range(3):
        for j in range(4):
            a.rrect(650 + j * 90, 720 + i * 70, 64, 48, 8, fill="#8d93a0", sw=4)
    a.rect(660, 1020, 320, 46, fill="#22262f", sw=6)
    a.rect(720, 1110, 200, 60, fill="#22262f", sw=6)
    L.append(("atm", a, dict(par=0.8, depth=2.4)))
    a = Ink(-160, 240, 700, 900, seed + 3)                                    # glass panel reflections
    a.poly([(-100, 260), (200, 260), (-20, 1100), (-100, 1100)], fill=c["glass"], sw=0, opacity=0.25)
    L.append(("glass", a, dict(par=0.9, depth=2.0, emissive=False)))
    a = Ink(-200, 1440, 1500, 700, seed + 4)
    a.poly([(-200, 1540), (1300, 1540), (1300, 2140), (-200, 2140)], fill="#3a4152", sw=8, wobble=1.2, step=70)
    a.poly([(-200, 1540), (1300, 1540), (1300, 1590), (-200, 1590)], fill="#59627a", sw=6, wobble=1.0, step=70)
    L.append(("shelf_fg", _shift(a, FG_SHIFT), dict(par=1.08, depth=0.9)))
    return L, ["wall", "atm", "glass", "@char", "shelf_fg"]


FAMILIES = {"bank_branch": bank_branch, "call_centre": call_centre, "indian_living_room": indian_living_room, "atm_area": atm_area}
