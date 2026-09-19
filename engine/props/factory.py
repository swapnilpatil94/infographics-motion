"""PROP factory (spec sec. 13): parametric ink props - recolour, scale, rotate, place, vary screens - registered as procedural assets.

    layer = make_layer("laptop", x=520, y=1395, scale=0.8, params={"color": "#8fa1c4", "screen": "#8fc0e8"}, seed=3, par=1.08, depth=0.9)
Local frame: origin = bottom-centre of the prop, x right, y up (negative). Same ink language as the sets. Deterministic in (kind, params, seed).
"""
import math
import random

import numpy as np

from asset_pipeline.ink import Ink, INK
from engine.shorts.layers import Layer
from engine.shorts.raster import rasterize

Z = 2.0


def _ink(w, h, seed):
    return Ink(-w / 2, -h, w, h, seed)


def _screen(a, x, y, w, h, color, lines=3, seed=0):
    a.rect(x, y, w, h, fill=color, sw=5, wobble=0.5)
    r = random.Random(seed)
    for k in range(lines):
        a.line((x + 14, y + 20 + k * (h - 30) / max(lines, 1)), (x + w - 14 - r.uniform(0, w * 0.4), y + 20 + k * (h - 30) / max(lines, 1)), sw=4, wobble=0.3, opacity=0.55, stroke="#ffffff")


def smartphone(p, s):
    a = _ink(90, 170, s); c = p.get("color", "#20222d")
    a.rrect(-38, -160, 76, 156, 14, fill=c, sw=6)
    a.rect(-30, -148, 60, 118, fill=p.get("screen", "#5fb4ff"), sw=0)
    return a, (90, 170)


def laptop(p, s):
    a = _ink(360, 250, s); c = p.get("color", "#b8c0d0")
    a.poly([(-150, -190), (150, -190), (166, -34), (-166, -34)], fill=c, sw=7, wobble=0.6)
    _screen(a, -132, -176, 264, 134, p.get("screen", "#8fc0e8"), 3, s)
    a.poly([(-180, -34), (180, -34), (200, -8), (-200, -8)], fill="#dfe3ec", sw=7, wobble=0.6)
    a.line((-40, -18), (40, -18), sw=5, wobble=0.3)
    return a, (400, 250)


def desktop(p, s):
    a = _ink(360, 330, s)
    a.rrect(-160, -300, 320, 220, 14, fill=p.get("color", "#2c2f38"), sw=8)
    _screen(a, -142, -282, 284, 184, p.get("screen", "#8fc0e8"), 4, s)
    a.rect(-24, -82, 48, 60, fill="#3a3f4a", sw=6)
    a.rrect(-80, -26, 160, 22, 6, fill="#3a3f4a", sw=6)
    return a, (360, 330)


def tablet(p, s):
    a = _ink(230, 300, s)
    a.rrect(-100, -280, 200, 270, 20, fill=p.get("color", "#2a2d36"), sw=7)
    _screen(a, -84, -262, 168, 234, p.get("screen", "#dbe7f7"), 4, s)
    return a, (230, 300)


def smartwatch(p, s):
    a = _ink(120, 220, s)
    a.rect(-22, -210, 44, 70, fill=p.get("strap", "#3a3f4a"), sw=5)
    a.rect(-22, -60, 44, 56, fill=p.get("strap", "#3a3f4a"), sw=5)
    a.rrect(-38, -150, 76, 92, 18, fill="#20222d", sw=6)
    a.rrect(-30, -142, 60, 76, 12, fill=p.get("screen", "#5fb4ff"), sw=0)
    return a, (120, 220)


def headphones(p, s):
    a = _ink(220, 200, s); c = p.get("color", "#3a3f4a")
    a.path([(-84, -80), (-84, -170), (0, -196), (84, -170), (84, -80)], sw=16, smooth=True, wobble=0.5, stroke=c)
    a.rrect(-108, -110, 48, 90, 18, fill=c, sw=7)
    a.rrect(60, -110, 48, 90, 18, fill=c, sw=7)
    return a, (220, 200)


def wallet(p, s):
    a = _ink(180, 130, s)
    a.rrect(-80, -110, 160, 104, 16, fill=p.get("color", "#8a5a36"), sw=7)
    a.rrect(-80, -110, 160, 40, 14, fill="#a06c44", sw=6)
    a.ellipse(56, -58, 10, 10, fill="#d9b24a", sw=4)
    return a, (180, 130)


def bank_card(p, s):
    a = _ink(200, 130, s)
    a.rrect(-92, -118, 184, 112, 12, fill=p.get("color", "#2f5fa8"), sw=6)
    a.rect(-92, -96, 184, 22, fill="#20222d", sw=0)
    a.rect(-70, -60, 40, 28, fill="#e2c46a", sw=4)
    for k in range(4):
        a.line((-70 + k * 42, -24), (-42 + k * 42, -24), sw=5, wobble=0.2, stroke="#ffffff")
    return a, (200, 130)


def cash(p, s):
    a = _ink(220, 130, s)
    for k in range(4):
        a.rect(-90 + k * 6, -110 + k * 22, 170, 44, fill=p.get("color", "#a9c99a"), sw=5)
        a.ellipse(-5 + k * 6, -88 + k * 22, 16, 16, fill="#e9f0dc", sw=3)
    return a, (220, 130)


def qr_code(p, s):
    a = _ink(180, 180, s); r = random.Random(s)
    a.rect(-84, -170, 168, 168, fill="#ffffff", sw=6)
    n, c0, cw = 17, -72, 144 / 17
    for i in range(n):
        for j in range(n):
            finder = (i < 5 and j < 5) or (i < 5 and j >= n - 5) or (i >= n - 5 and j < 5)
            on = finder and (i in (0, 4) or j in (0, 4) or j in (n - 1, n - 5) or i in (n - 1, n - 5) or (1 < i < 3 and 1 < j < 3) or (1 < i < 3 and n - 4 < j < n - 2) or (n - 4 < i < n - 2 and 1 < j < 3)) if finder else r.random() < 0.5
            if on:
                a.raw(f'<rect x="{c0 + j * cw:.1f}" y="{-160 + i * cw:.1f}" width="{cw:.1f}" height="{cw:.1f}" fill="{INK}"/>')
    return a, (180, 180)


def payment_terminal(p, s):
    a = _ink(150, 220, s)
    a.poly([(-60, -200), (60, -200), (72, -8), (-72, -8)], fill=p.get("color", "#3a3f4a"), sw=7)
    a.rect(-46, -186, 92, 54, fill="#c9e6c0", sw=4)
    for i in range(3):
        for j in range(3):
            a.rrect(-46 + j * 32, -114 + i * 34, 26, 24, 5, fill="#d7dae2", sw=3)
    return a, (150, 220)


def _doc(a, w, h, color, title_lines, seed, stamp=None):
    a.rect(-w / 2, -h, w, h, fill=color, sw=6, wobble=0.8)
    r = random.Random(seed)
    a.rect(-w / 2 + 16, -h + 16, w * 0.5, 16, fill="#2f5fa8", sw=0)
    for k in range(title_lines):
        a.line((-w / 2 + 16, -h + 56 + k * 22), (w / 2 - 16 - r.uniform(0, w * 0.3), -h + 56 + k * 22), sw=3.5, wobble=0.4, opacity=0.7)
    if stamp:
        a.ellipse(w / 4, -34, 30, 30, fill="none", sw=5, stroke="#c0392b")


def receipt(p, s):
    a = _ink(110, 200, s); _doc(a, 96, 190, "#f5f2ea", 6, s); return a, (110, 200)


def bill(p, s):
    a = _ink(170, 220, s); _doc(a, 150, 206, "#f6efd8", 8, s, stamp=True); return a, (170, 220)


def cheque(p, s):
    a = _ink(280, 130, s); _doc(a, 260, 116, "#e6f0e2", 3, s); return a, (280, 130)


def bank_document(p, s):
    a = _ink(190, 250, s); _doc(a, 170, 236, "#f4f6fa", 9, s, stamp=True); return a, (190, 250)


def loan_document(p, s):
    a = _ink(190, 250, s); _doc(a, 170, 236, "#f2ede0", 10, s, stamp=True); return a, (190, 250)


def emi_document(p, s):
    a = _ink(190, 250, s); _doc(a, 170, 236, "#f1f0ee", 8, s); a.rect(-70, -70, 140, 40, fill="#e2b4a8", sw=4); return a, (190, 250)


def investment_document(p, s):
    a = _ink(190, 250, s); _doc(a, 170, 236, "#eef4ea", 7, s); a.path([(-60, -60), (-20, -90), (10, -70), (60, -110)], sw=7, wobble=0.6, stroke="#2f8f83"); return a, (190, 250)


def shopping_bags(p, s):
    a = _ink(300, 260, s); r = random.Random(s)
    for k, col in enumerate((p.get("color", "#d8493c"), "#3b6fb6", "#f0c65a")):
        x = -100 + k * 92
        a.poly([(x - 56, -200 + k * 8), (x + 56, -200 + k * 8), (x + 66, -6), (x - 66, -6)], fill=col, sw=7, wobble=0.8)
        a.path([(x - 26, -200 + k * 8), (x - 20, -250 + k * 6), (x + 20, -250 + k * 6), (x + 26, -200 + k * 8)], sw=6, smooth=True, wobble=0.4)
    return a, (300, 260)


def boxes(p, s):
    a = _ink(300, 260, s)
    for k, (x, y, w, h) in enumerate(((-120, 0, 140, 110), (30, 0, 120, 90), (-70, -110, 110, 90))):
        a.rect(x, y - h, w, h, fill=p.get("color", "#c9a878"), sw=7, wobble=0.8)
        a.line((x + w / 2, y - h), (x + w / 2, y), sw=5, wobble=0.3, opacity=0.6)
    return a, (300, 260)


def mug(p, s):
    a = _ink(120, 120, s)
    a.rrect(-38, -100, 76, 96, 12, fill=p.get("color", "#e8b34a"), sw=7)
    a.path([(38, -80), (64, -70), (64, -34), (38, -24)], sw=7, smooth=True, wobble=0.4)
    return a, (120, 120)


def pen_cup(p, s):
    a = _ink(110, 170, s)
    for k, ang in enumerate((-16, 0, 14)):
        a.line((k * 10 - 10, -70), (k * 10 - 10 + ang, -160), sw=8, wobble=0.3, stroke=("#2f5fa8", "#c0392b", "#20222d")[k])
    a.rect(-34, -80, 68, 74, fill="#7d93b8", sw=6)
    return a, (110, 170)


def lamp(p, s):
    a = _ink(150, 250, s)
    a.rect(-40, -20, 80, 16, fill="#3a3f4a", sw=5)
    a.line((0, -20), (20, -150), sw=8, wobble=0.3)
    a.poly([(-14, -196), (58, -196), (80, -140), (-36, -140)], fill=p.get("color", "#e6ce98"), sw=6)
    return a, (150, 250)


PROPS = dict(smartphone=smartphone, laptop=laptop, desktop=desktop, tablet=tablet, smartwatch=smartwatch, headphones=headphones, wallet=wallet, bank_card=bank_card, cash=cash,
             qr_code=qr_code, payment_terminal=payment_terminal, receipt=receipt, bill=bill, cheque=cheque, bank_document=bank_document, loan_document=loan_document,
             emi_document=emi_document, investment_document=investment_document, shopping_bags=shopping_bags, boxes=boxes, mug=mug, pen_cup=pen_cup, lamp=lamp)

SLOTS = {   # set -> named world positions (base-centre) where props can sit
    "office_day": dict(desk_left=(230, 1418), desk_center=(520, 1418), desk_right=(830, 1418)),
    "street_dusk": dict(parapet_left=(220, 1418), parapet_right=(850, 1418)),
    "night_bedroom": dict(nightstand=(960, 1195), lap=(560, 1290)),
    "bank_branch": dict(counter_left=(200, 1418), counter_right=(870, 1418)),
    "call_centre": dict(desk_left=(260, 1418), desk_right=(700, 1418)),
    "indian_living_room": dict(table_left=(240, 1418), table_right=(840, 1418)),
    "atm_area": dict(shelf_left=(260, 1418), shelf_right=(820, 1418))}


def make_layer(kind, x, y, scale=1.0, rotation=0.0, params=None, seed=0, par=1.08, depth=0.9, name=None):
    if kind not in PROPS:
        raise KeyError(f"unknown prop '{kind}' (have {sorted(PROPS)})")
    a, (w, h) = PROPS[kind](params or {}, seed)
    arr, (ox, oy) = rasterize(a.svg(), zoom=Z)
    res = Z / scale
    origin = (x - (w / 2) * scale + ox / res, y - h * scale + oy / res)
    L = Layer(name or f"prop_{kind}", arr, origin, res, par=par, depth=depth)
    if rotation:
        from engine.shorts.character import _R, _T
        L.world_xf = _T(x, y) @ _R(rotation) @ _T(-x, -y)
    return L


def place(scene, set_id, props, seed=0, after="@char"):
    """props: [{prop, at (slot name or [x,y]), scale?, rotation?, params?}] -> layers inserted into the scene order after `after`."""
    order = list(scene.order)
    i = order.index(after) + 1
    # props sit ON the foreground surface: draw them after the occluder layer (last in order)
    i = len(order)
    for k, pr in enumerate(props):
        pos = pr["at"] if isinstance(pr["at"], (list, tuple)) else SLOTS[set_id.split("_")[0] if set_id not in SLOTS else set_id][pr["at"]]
        L = make_layer(pr["prop"], pos[0], pos[1], pr.get("scale", 0.8), pr.get("rotation", 0.0), pr.get("params"), seed + k, name=f"prop{k}_{pr['prop']}")
        scene.room[L.name] = L
        order.append(L.name)
    scene.order = order
