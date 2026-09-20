"""FULL-BODY STAGES: every location the story engine can name, built for the skeleton actors (floor y = 1500, seat height 270, character ~1000 px tall), with day / night variants where the place has a sky.

Two kinds of stage:
  * the ORIGINAL families re-issued without the bust-scale foreground shift (the counter / desk / parapet used to start at y~1360 and hide the legs) -> living_room, bank, atm, call_center;
  * NEW families composed from the same ink primitives: office, cafe, classroom (table scenes: chair + table, decor differs), shop, police (counter scenes), street (sky + city + pavement).
Generator contract (same as engine/environments/families.py): gen(variation, seed) -> (layers, order).  variation = {"palette": n, "time": "day" | "night" | "dusk"}.
A window/sky NEVER contradicts `time` (day = blue sky + sun, night = navy + moon/stars, dusk = warm gradient); windowless places take their light from the lighting rig only.
"""
import math
import random

from asset_pipeline.ink import Ink, INK
from asset_pipeline.set_art import FULL
from engine.environments import bedroom_wide as BW, families as F, study_room as SR

FLOOR = BW.FLOOR_Y
SEAT = BW.SEAT_Y
SKY = dict(day=("#6fb1e6", "#cfe7f8"), night=("#1c2a55", "#40507e"), dusk=("#e8905a", "#f6cf8a"))


def _fullbody(gen):
    """the original generator with `_shift` disabled: foreground occluders start below the floor line instead of ~180 px above it"""
    def g(v, seed):
        old = F._shift
        F._shift = lambda ink, dy: ink
        try:
            return gen(v, seed)
        finally:
            F._shift = old
    return g


def _sky(a, x, y, w, h, time, seed, sun=True):
    """a window's sky, consistent with the scene's time"""
    top, bot = SKY[time]
    a.raw(f'<defs><linearGradient id="sk{seed}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient></defs>')
    a.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#sk{seed})"/>')
    r = random.Random(seed)
    if time == "day" and sun:
        a.ellipse(x + w * 0.75, y + h * 0.2, 34, 34, fill="#fff3b0", sw=0, wobble=0)
        a.ellipse(x + w * 0.3, y + h * 0.35, 60, 20, fill="#ffffff", sw=0, wobble=0)
    elif time == "night":
        a.ellipse(x + w * 0.75, y + h * 0.18, 26, 26, fill="#f4f1dc", sw=0, wobble=0)
        for _ in range(9):
            a.ellipse(r.uniform(x + 10, x + w - 10), r.uniform(y + 10, y + h * 0.7), 2.2, 2.2, fill="#fff", sw=0, wobble=0)
    elif time == "dusk":
        a.ellipse(x + w * 0.5, y + h * 0.78, 40, 40, fill="#fff0c0", sw=0, wobble=0)


def _table_scene(kind):
    """chair + table stage (study_room geometry: chair seat y=1230 at x 180..440, table top y=1060 at x 560..980) with the decor of an office / cafe / classroom"""
    def gen(v, seed):
        time = v.get("time", "night" if kind == "study" else "day")
        L, order = SR.study_room(dict(v, time=time), seed)
        r = random.Random(seed + 7)
        L = [l for l in L if l[0] != "decor"]
        a = Ink(-40, 160, 1000, 760, seed + 31)
        if kind == "office":
            a.rect(20, 260, 300, 200, fill="#c9b48a", sw=7)                                      # notice board with pinned notes
            for i, col in enumerate(("#f3e08a", "#9fd0e8", "#f0a6b0", "#b7e0a0", "#f3e08a", "#9fd0e8")):
                a.rect(46 + (i % 3) * 92, 284 + (i // 3) * 84, 70, 60, fill=col, sw=3)
            a.rect(420, 250, 210, 160, fill="#e9e2cf", sw=6)                                     # wall chart
            a.poly([(440, 380), (500, 320), (540, 350), (610, 280)], fill="none", sw=6)
            a.ellipse(760, 300, 56, 56, fill="#f4f0e2", sw=7)                                     # clock
            a.line((760, 300), (760, 264), sw=5)
            a.line((760, 300), (786, 314), sw=5)
            a.rect(20, 520, 260, 30, fill="#8a5a36", sw=6)                                        # shelf with folders
            for i, col in enumerate(("#3f6f8c", "#c4553f", "#e0b45a", "#6b8f5a", "#5a4a6a")):
                a.rect(36 + i * 46, 430, 38, 90, fill=col, sw=4)
        elif kind == "cafe":
            a.rect(40, 250, 330, 230, fill="#2f3b34", sw=8)                                       # chalk menu board
            for i in range(5):
                a.line((70, 290 + i * 36), (330 - i * 30, 290 + i * 36), sw=6, wobble=0.6, stroke="#f2efe2")
            for x in (520, 700, 880):                                                             # pendant lamps
                a.line((x, 160), (x, 300), sw=4)
                a.poly([(x - 46, 360), (x + 46, 360), (x + 24, 300), (x - 24, 300)], fill="#e6b45a", sw=6)
            a.rect(420, 540, 200, 26, fill="#8a5a36", sw=6)                                       # shelf with jars
            for i in range(4):
                a.rect(436 + i * 46, 470, 34, 70, fill="#e8dcc0", sw=4)
        else:                                                                                     # classroom
            a.rect(20, 240, 560, 300, fill="#2e4a3e", sw=10)                                      # blackboard
            for i in range(4):
                a.line((60, 300 + i * 56), (500 - i * 60 + r.uniform(-20, 20), 300 + i * 56), sw=5, wobble=1.2, stroke="#eef2e8")
            a.rect(20, 540, 560, 16, fill="#8a5a36", sw=5)
            a.rect(660, 250, 220, 160, fill="#e9e2cf", sw=6)                                      # map poster
            a.ellipse(760, 330, 52, 52, fill="#6fa0c8", sw=5)
            a.rect(660, 430, 220, 24, fill="#c9b48a", sw=5)
        L.append(("decor", a, dict(par=0.62, depth=3.1)))
        if kind == "cafe":                                                                        # a second chair opposite: two people can sit at the table
            b = Ink(960, 1000, 320, 560, seed + 32)
            b.rect(1030, 1230, 220, 30, fill="#8a5a36", sw=7)
            b.rect(1210, 900, 30, 350, fill="#7a4d2c", sw=7)
            b.rect(1050, 1258, 22, 236, fill="#6a4426", sw=6)
            b.rect(1200, 1258, 22, 236, fill="#6a4426", sw=6)
            L.append(("chair2", b, dict(par=1.0, depth=1.75)))
            order = [o for o in order]
            order.insert(order.index("furniture") + 1 if "furniture" in order else 0, "chair2")
        if kind in ("office", "classroom"):                                                       # laptop / books on the table
            c = Ink(560, 940, 440, 130, seed + 33)
            if kind == "office":
                c.poly([(700, 1052), (860, 1052), (880, 1036), (720, 1036)], fill="#b9bdc8", sw=5)
                c.poly([(730, 1036), (850, 1036), (846, 950), (726, 950)], fill="#8fb4de", sw=5)
            else:
                for i, col in enumerate(("#c4553f", "#3f6f8c", "#e0b45a")):
                    c.rect(690 + i * 4, 1044 - i * 16, 150, 16, fill=col, sw=4)
            L.append(("tabletop", c, dict(par=1.0, depth=1.68)))
            order.insert(order.index("furniture") + 1 if "furniture" in order else 0, "tabletop")
        return L, order
    return gen


def _counter_scene(kind):
    """service-counter stage: the visitor stands on the left, the clerk / officer behind a waist-high counter on the right (the counter hides only the clerk's lower body)"""
    def gen(v, seed):
        time = v.get("time", "day")
        pal = dict(bank=("#e9e2cf", "#1f3f73", "#b98d5a"), shop=("#f0e2c4", "#b8543f", "#a4784e"), police=("#d9dee6", "#274a7a", "#8f7a5a"))[kind]
        r = random.Random(seed)
        L = []
        a = Ink(*FULL, seed + 1)
        a.raw(f'<rect x="-160" y="-160" width="1400" height="2240" fill="{pal[0]}"/>')
        a.rect(-160, FLOOR - 60, 1400, 600, fill="#c9c0aa" if kind != "shop" else "#b39a72", sw=0, wobble=0)
        for x in range(-100, 1240, 180):
            a.rect(x, 90, 130, 24, fill="#fffbe8", sw=4, wobble=0.6)
        a.hatch([(-160, -160), (500, -160), (-160, 500)], 42, 11, 2.4, 0.4, gradient=(7, 34))
        L.append(("wall", a, dict(par=0.6, depth=3.2)))
        b = Ink(60, 200, 1100, 700, seed + 2)
        if kind == "bank":
            b.rect(80, 230, 560, 190, fill=pal[1], sw=8)
            b.poly([(130, 390), (200, 300), (270, 390)], fill="#f4f1e6", sw=5)
            for k in range(3):
                b.line((330, 280 + k * 44), (600 - k * 60, 280 + k * 44), sw=9, wobble=0.6, stroke="#f4f1e6")
            b.rect(720, 300, 280, 420, fill="#22303f", sw=8)                                    # teller glass
            b.poly([(740, 320), (860, 320), (790, 700), (740, 700)], fill="#5b7fa8", sw=0, opacity=0.35)
        elif kind == "shop":
            for row in range(3):                                                                   # shelves with goods
                b.rect(60, 320 + row * 150, 620, 18, fill="#8a5a36", sw=6)
                for i in range(9):
                    b.rect(80 + i * 66, 250 + row * 150, 48, 70, fill=("#c4553f", "#3f6f8c", "#e0b45a", "#6b8f5a", "#8a5aa0")[(i + row) % 5], sw=4)
            b.rect(760, 240, 300, 120, fill=pal[1], sw=8)
            b.line((790, 300), (1030, 300), sw=12, wobble=0.6, stroke="#f6eed6")
        else:                                                                                      # police
            b.rect(80, 240, 330, 220, fill="#e9e2cf", sw=8)
            b.rect(110, 270, 270, 60, fill=pal[1], sw=5)
            b.line((140, 300), (350, 300), sw=10, wobble=0.6, stroke="#f6eed6")
            b.rect(470, 250, 20, 320, fill="#5a4a3a", sw=6)                                        # flag pole
            b.poly([(490, 260), (640, 280), (490, 340)], fill="#e0863c", sw=5)
            b.rect(760, 300, 280, 160, fill="#e9e2cf", sw=7)                                        # board of notices
        L.append(("signage", b, dict(par=0.7, depth=2.9)))
        c = Ink(660, 1080, 640, 470, seed + 3)                                                      # the counter (midground, behind the visitor's plane)
        c.poly([(680, 1140), (1260, 1140), (1260, FLOOR + 40), (680, FLOOR + 40)], fill=pal[2], sw=8, wobble=1.0, step=70)
        c.poly([(660, 1120), (1280, 1120), (1280, 1160), (660, 1160)], fill="#e6d3ae", sw=6, wobble=1.0, step=70)
        c.hatch([(700, 1190), (1240, 1190), (1240, 1460), (700, 1460)], 64, 12, 2.3, 0.4, gradient=(7, 26))
        if kind == "bank":
            c.rrect(840, 1078, 150, 44, 8, fill="#2a2f3a", sw=5)                                    # card machine
        elif kind == "shop":
            c.rect(1000, 1070, 130, 50, fill="#d9b24a", sw=5)                                       # till
        else:
            c.rect(880, 1078, 110, 42, fill="#f5f2ea", sw=5)                                        # register book
        L.append(("counter", c, dict(par=1.0, depth=1.7)))
        d = Ink(-200, 1500, 1500, 640, seed + 4)
        d.poly([(-200, 1560), (1300, 1560), (1300, 2140), (-200, 2140)], fill="#a9946c" if kind == "shop" else "#8f8a7a", sw=8, wobble=1.2, step=70)
        L.append(("floor_fg", d, dict(par=1.08, depth=0.9)))
        return L, ["wall", "signage", "counter", "@char", "floor_fg"]
    return gen


def _street(v, seed):
    time = v.get("time", "dusk")
    r = random.Random(seed)
    L = []
    a = Ink(*FULL, seed + 1)
    top, bot = SKY[time]
    a.raw(f'<defs><linearGradient id="st{seed}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient></defs>')
    a.raw(f'<rect x="-160" y="-160" width="1400" height="{FLOOR + 160}" fill="url(#st{seed})"/>')
    if time == "night":
        for _ in range(40):
            a.ellipse(r.uniform(-140, 1220), r.uniform(-100, 700), 2.4, 2.4, fill="#fff", sw=0, wobble=0)
        a.ellipse(880, 190, 40, 40, fill="#f4f1dc", sw=0, wobble=0)
    elif time == "day":
        a.ellipse(860, 220, 52, 52, fill="#fff3b0", sw=0, wobble=0)
        for cx_, cy_ in ((200, 260), (560, 180), (980, 330)):
            a.ellipse(cx_, cy_, 90, 30, fill="#ffffff", sw=0, wobble=0)
    L.append(("sky", a, dict(par=0.4, depth=3.6, emissive=True)))
    b = Ink(-160, 300, 1400, 1250, seed + 2)
    col = dict(day=("#8a99b8", "#a9b6cf", "#c9d3e6"), dusk=("#5a4a6a", "#7d5f7a", "#9a7488"), night=("#1d2540", "#27304f", "#323c60"))[time]
    x = -140
    while x < 1240:
        w = r.choice((150, 190, 230))
        h = r.choice((520, 680, 820, 940))
        b.rect(x, FLOOR - h, w, h, fill=col[r.randrange(3)], sw=6)
        for wy in range(FLOOR - h + 40, FLOOR - 120, 90):
            for wx in range(int(x) + 24, int(x + w) - 40, 60):
                lit = time != "day" and r.random() < (0.5 if time == "night" else 0.25)
                b.rect(wx, wy, 34, 46, fill="#f2d27a" if lit else ("#dbe8f5" if time == "day" else "#3a4468"), sw=3)
        x += w + r.choice((0, 10, 30))
    L.append(("buildings", b, dict(par=0.62, depth=3.0)))
    c = Ink(-160, 1000, 1400, 600, seed + 3)
    c.rect(300, 860, 14, FLOOR - 860, fill="#3a3f4c", sw=5)                                       # lamp post
    c.poly([(240, 850), (380, 850), (350, 800), (270, 800)], fill="#3a3f4c", sw=5)
    c.ellipse(310, 872, 26, 12, fill="#ffe9a0" if time != "day" else "#e9e6dc", sw=3)
    c.rect(900, 1120, 12, FLOOR - 1120, fill="#5a4a3a", sw=6)                                     # tree trunk + crown
    for tx_, ty_, tr_ in ((850, 1000, 84), (960, 990, 92), (905, 900, 88)):                       # a round crown from three overlapping discs
        c.ellipse(tx_, ty_, tr_, tr_, fill="#4f8a55" if time != "night" else "#2b4a3a", sw=7)
    c.rect(-160, FLOOR - 30, 1400, 40, fill="#c9c2b4", sw=5)                                      # kerb
    L.append(("street_props", c, dict(par=0.95, depth=2.0)))
    d = Ink(-160, FLOOR, 1400, 640, seed + 4)
    d.rect(-160, FLOOR, 1400, 600, fill="#8b8a92" if time != "night" else "#4b4b57", sw=0)
    for k in range(9):
        d.path([(-160 + k * 180, FLOOR + 8), (-200 + k * 190, 2100)], sw=3, wobble=1.0, opacity=0.4)
    L.append(("pavement", d, dict(par=0.9, depth=2.3)))
    return L, ["sky", "buildings", "street_props", "pavement", "@char"]


def _living_room(v, seed):
    L, order = _fullbody(F.indian_living_room)(v, seed)
    time = v.get("time", "day")
    for i, (n, ink, m) in enumerate(L):                                                          # the window pane shows the scene's sky
        if n == "window":
            top, bot = SKY[time]
            ink.body = [s.replace("#a9d3ee", bot if time != "night" else top) for s in ink.body]
    return L, order


FAMILIES = {
    "living_room": _living_room, "bank": _fullbody(F.bank_branch), "atm": _fullbody(F.atm_area), "call_center": _fullbody(F.call_centre),
    "office": _table_scene("office"), "cafe": _table_scene("cafe"), "classroom": _table_scene("classroom"), "study": _table_scene("study"),
    "shop": _counter_scene("shop"), "police": _counter_scene("police"), "bank_counter": _counter_scene("bank"), "street": _street,
}
