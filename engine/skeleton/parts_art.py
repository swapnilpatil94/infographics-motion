"""Full-body modular character ART: a DNA -> one vector part per body part, each drawn in its own JOINT frame (pivot = the joint).

Nothing here is a whole-character picture. Parts are SVG (resvg-rasterised to PNG textures cached by content hash) and are rigged by
engine/blender/skeleton_scene.py. Sources: head/hair shell = Open Peeps (CC0, Pablo Stanley) split into a skin layer and an independent hair layer;
torso / pelvis / neck / limbs / hands / feet / phone = own work, generated from proportions + outfit + palette (so a new outfit or body type is data).
Style follows the Open Peeps ink language: flat fills, one black outline weight.
"""
import hashlib
import json
import math
import os
import random

import numpy as np
from PIL import Image

from asset_pipeline import rig_art as A
from engine.characters import dna as D
from engine.shorts.raster import ROOT, rasterize
from engine.skeleton import rig_def as R

TEX = 2.0                                                        # texture px per rig px
GEN = os.path.join(ROOT, "assets/character/skeleton/generated")
INK = "#000000"
OW = 7.0                                                         # outline (rig px)
M = 40.0                                                         # canvas margin around a part

SHORT_SLEEVE = {"tee_white", "polo_green", "polo_maroon", "stripes_orange", "top_mustard", "blouse_rose"}
TROUSERS = ["#3d4f78", "#464650", "#8b7b5a", "#5c6f8e", "#2f3b52", "#6b5a48", "#55606b"]
TROUSERS_F = ["#2d2f3b", "#3d4f78", "#6a4b5a", "#464650", "#2f5b57"]
SHOES = ["#26262c", "#7a4b2a", "#e6e6ea", "#3b3f4a"]
HAIR_COLORS = ["#000000", "#000000", "#000000", "#2b1a12", "#3a2416"]


def fullbody(dna):
    """Deterministic full-body extras derived from the DNA seed (bottoms, shoes, hair colour, sleeves, height jitter)."""
    r = random.Random(f"fullbody|{dna['id']}")
    fem = dna["gender"] == "female"
    return dict(bottom=r.choice(TROUSERS_F if fem else TROUSERS), shoes=r.choice(SHOES), hair_color="#8f8f95" if dna["age_group"] == "elder" else r.choice(HAIR_COLORS),
                short_sleeve=dna["clothing"]["top"] in SHORT_SLEEVE, long_top=dna["clothing"]["top"] in ("kurta_cream", "kurta_teal") or (fem and r.random() < 0.3),
                height_scale=float(dna.get("height_scale", round(r.uniform(0.97, 1.04), 3))))


def _svg(w, h, body, defs=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}"><defs>{defs}</defs>{body}</svg>'


def _capsule(len_, w0, w1, fill, x=M, y=M, extra="", stroke=OW):
    r0, r1 = w0 / 2, w1 / 2
    d = f"M{x - r0:.1f},{y:.1f} A{r0:.1f},{r0:.1f} 0 0 1 {x + r0:.1f},{y:.1f} L{x + r1:.1f},{y + len_:.1f} A{r1:.1f},{r1:.1f} 0 0 1 {x - r1:.1f},{y + len_:.1f} Z"
    return f'<path d="{d}" fill="{fill}" stroke="{INK}" stroke-width="{stroke}" stroke-linejoin="round"/>{extra}'


def _clip(id_, path_d):
    return f'<clipPath id="{id_}"><path d="{path_d}"/></clipPath>'


def _pattern(pattern, seed, x0, x1, y0, y1):
    if pattern == "plain":
        return ""
    n = int(max(8, (x1 - x0) * (y1 - y0) / 4200))
    return A.pattern_marks(random.Random(seed), pattern, x0, x1, y0, y1, n)


def _limb_part(len_, w0, w1, skin, sleeve, sleeve_len, pattern, seed, cuff=True):
    """Upper arm / forearm: skin capsule + a sleeve capsule over the first `sleeve_len` of it (0 = bare)."""
    W_, H_ = 2 * M + w0, 2 * M + len_
    body = _capsule(len_, w0, w1, skin)
    if sleeve_len > 0:
        sl = min(sleeve_len, len_)
        wl = w0 + (w1 - w0) * sl / len_
        r0, r1 = w0 / 2 + 1.5, wl / 2 + 1.5
        d = (f"M{M - r0:.1f},{M:.1f} A{r0:.1f},{r0:.1f} 0 0 1 {M + r0:.1f},{M:.1f} L{M + r1:.1f},{M + sl:.1f} L{M - r1:.1f},{M + sl:.1f} Z")
        body += (f'<g clip-path="url(#sc)"><path d="{d}" fill="{sleeve}" stroke="none"/>{_pattern(pattern, seed, M - w0, M + w0, M, M + sl)}</g>'
                 f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>')
        if cuff and sl < len_ - 2:
            body += f'<path d="M{M - r1 - 1:.1f},{M + sl:.1f} L{M + r1 + 1:.1f},{M + sl:.1f}" stroke="{INK}" stroke-width="{OW + 1}" stroke-linecap="round"/>'
        defs = _clip("sc", d)
    else:
        defs = ""
    return _svg(W_, H_, body, defs), (M, M)


def upperarm(P, dna, fb, side):
    o = D.outfit(dna)
    sl = P["upper_arm"] * (0.52 if fb["short_sleeve"] else 0.97)
    lim = P["limb"]
    return _limb_part(P["upper_arm"], lim * 1.08, lim * 0.9, D.SKIN[dna["skin"]], o["fill"], sl, o.get("pattern", "plain"), 7 + (side == "R"))


def forearm(P, dna, fb, side):
    o = D.outfit(dna)
    sl = 0.0 if fb["short_sleeve"] else P["forearm"] * 0.82
    lim = P["limb"]
    return _limb_part(P["forearm"], lim * 0.92, lim * 0.7, D.SKIN[dna["skin"]], o["fill"], sl, o.get("pattern", "plain"), 9 + (side == "R"))


def hand(P, dna, fb, side):
    skin, hl, k = D.SKIN[dna["skin"]], P["hand"], P["k"]
    hw = P["limb"] * 0.58
    W_, H_ = 2 * M + 2 * hw + 30, 2 * M + hl + 30
    cx = M + hw
    palm = (f'<path d="M{cx - hw * 0.62:.1f},{M - 4:.1f} C{cx - hw * 1.05:.1f},{M + hl * 0.35:.1f} {cx - hw * 0.85:.1f},{M + hl * 0.95:.1f} {cx:.1f},{M + hl:.1f} '
            f'C{cx + hw * 0.95:.1f},{M + hl * 0.95:.1f} {cx + hw * 1.05:.1f},{M + hl * 0.35:.1f} {cx + hw * 0.62:.1f},{M - 4:.1f} Z" fill="{skin}" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>')
    thumb = (f'<path d="M{cx + hw * 0.55:.1f},{M + hl * 0.12:.1f} C{cx + hw * 1.5:.1f},{M + hl * 0.25:.1f} {cx + hw * 1.55:.1f},{M + hl * 0.62:.1f} {cx + hw * 0.95:.1f},{M + hl * 0.66:.1f}" '
             f'fill="{skin}" stroke="{INK}" stroke-width="{OW}" stroke-linecap="round" stroke-linejoin="round"/>')
    lines = "".join(f'<path d="M{cx + dx:.1f},{M + hl * 0.62:.1f} L{cx + dx:.1f},{M + hl * 0.9:.1f}" stroke="{INK}" stroke-width="4.5" stroke-linecap="round"/>' for dx in (-hw * 0.22, hw * 0.18))
    return _svg(W_, H_, palm + thumb + lines), (cx, M)


def fingers(P, dna, fb):
    """The four fingertips that wrap over a held phone's front edge (shown only while gripping)."""
    skin, hw = D.SKIN[dna["skin"]], P["limb"] * 0.58
    W_, H_ = 2 * M + 2 * hw + 40, 2 * M + 60
    cx = M + hw
    body = "".join(f'<path d="M{cx - hw * 0.7:.1f},{M + 8 + 16 * i:.1f} L{cx + hw * 1.05:.1f},{M + 8 + 16 * i:.1f}" stroke="{INK}" stroke-width="{16 + OW * 1.6}" stroke-linecap="round"/>'
                   f'<path d="M{cx - hw * 0.7:.1f},{M + 8 + 16 * i:.1f} L{cx + hw * 1.05:.1f},{M + 8 + 16 * i:.1f}" stroke="{skin}" stroke-width="16" stroke-linecap="round"/>' for i in range(3))
    return _svg(W_, H_, body), (cx, M)


def thigh(P, dna, fb, side):
    lim = P["limb"]
    return _limb_part(P["thigh"], lim * 1.32, lim * 1.02, fb["bottom"], fb["bottom"], P["thigh"], "plain", 3, cuff=False)


def shin(P, dna, fb, side):
    lim = P["limb"]
    W_, H_ = 2 * M + lim * 1.1, 2 * M + P["shin"]
    body = _capsule(P["shin"], lim * 1.02, lim * 0.72, fb["bottom"])
    body += f'<path d="M{M - lim * 0.42:.1f},{M + P["shin"] - 26:.1f} L{M + lim * 0.42:.1f},{M + P["shin"] - 26:.1f}" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
    return _svg(W_, H_, body), (M, M)


def foot(P, dna, fb, side):
    k, fh, fl = P["k"], P["foot_h"], P["foot_len"]
    heel, toe = -34 * k, fl - 34 * k
    W_, H_ = 2 * M + fl + 40, 2 * M + fh + 30
    y0 = M                                                       # ankle level
    x0 = M + 34 * k + 12
    top = f"M{x0 - 32 * k:.1f},{y0 - 6:.1f} L{x0 + 26 * k:.1f},{y0 - 6:.1f} C{x0 + 34 * k:.1f},{y0 + 22:.1f} {x0 + 70 * k:.1f},{y0 + 26:.1f} {x0 + toe * 0.82:.1f},{y0 + 30:.1f}"
    top += f" C{x0 + toe + 8:.1f},{y0 + 32:.1f} {x0 + toe + 10:.1f},{y0 + fh + 4:.1f} {x0 + toe - 8:.1f},{y0 + fh + 6:.1f} L{x0 + heel + 6:.1f},{y0 + fh + 6:.1f} C{x0 + heel - 8:.1f},{y0 + fh + 4:.1f} {x0 + heel - 6:.1f},{y0 + 8:.1f} {x0 - 32 * k:.1f},{y0 - 6:.1f} Z"
    sole = f'<path d="M{x0 + heel + 6:.1f},{y0 + fh - 4:.1f} L{x0 + toe - 8:.1f},{y0 + fh - 4:.1f}" stroke="#f2f2f2" stroke-width="7" stroke-linecap="round"/>'
    return _svg(W_, H_, f'<path d="{top}" fill="{fb["shoes"]}" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>{sole}'), (x0, y0)


def pelvis(P, dna, fb):
    tw, k = P["torso_w"], P["k"]
    W_, H_ = 2 * M + tw, 2 * M + 130 * k
    x0, y0 = M + tw / 2, M + 44 * k
    body = f'<rect x="{x0 - tw / 2 * 0.98:.1f}" y="{y0 - 74 * k:.1f}" width="{tw * 0.98:.1f}" height="{130 * k:.1f}" rx="{40 * k:.1f}" fill="{fb["bottom"]}" stroke="{INK}" stroke-width="{OW}"/>'
    return _svg(W_, H_, body), (x0, y0)


def neck(P, dna, fb):
    skin, nw, nl = D.SKIN[dna["skin"]], 50 * P["k"], P["neck"] + 34 * P["k"]
    return _svg(2 * M + nw, 2 * M + nl, _capsule(nl, nw, nw * 0.92, skin, stroke=OW)), (M, M + nl)   # pivot = neck base (chest top); the capsule runs UP from it


def torso(P, dna, fb):
    """Side-view shirt from the hip (pivot, bottom) to the shoulders; chest bulges forward (+x), back curves."""
    o = D.outfit(dna)
    tw, Lt, k = P["torso_w"], P["torso"], P["k"]
    hem = (P["thigh"] * 0.34) if fb["long_top"] else 34 * k
    W_, H_ = 2 * M + tw + 40, 2 * M + Lt + hem + 40
    cx, hy = M + tw / 2 + 12, M + Lt + 20                         # hip pivot (canvas)
    back, front = cx - tw * 0.5, cx + tw * 0.52
    top = hy - Lt - 14 * k
    d = (f"M{back + 10:.1f},{top + 30:.1f} C{back - 6:.1f},{top + Lt * 0.35:.1f} {back - 10:.1f},{top + Lt * 0.75:.1f} {back + 2:.1f},{hy + hem:.1f} "
         f"L{front - 6:.1f},{hy + hem:.1f} C{front + 12:.1f},{hy + hem * 0.3:.1f} {front + 20:.1f},{top + Lt * 0.62:.1f} {front + 6:.1f},{top + Lt * 0.30:.1f} "
         f"C{front - 2:.1f},{top + 8:.1f} {cx + tw * 0.15:.1f},{top - 6:.1f} {cx - tw * 0.05:.1f},{top - 4:.1f} C{back + 26:.1f},{top:.1f} {back + 14:.1f},{top + 12:.1f} {back + 10:.1f},{top + 30:.1f} Z")
    pat = _pattern(o.get("pattern", "plain"), 5, back - 10, front + 20, top, hy + hem)
    col = o["collar"] if "collar" in o else "crew"
    coll = ""
    if col == "polo":
        coll = (f'<path d="M{cx + tw * 0.02:.1f},{top - 2:.1f} L{front - 4:.1f},{top + 42:.1f} L{cx + tw * 0.28:.1f},{top + 58:.1f} Z" fill="{o["fill"]}" stroke="{INK}" stroke-width="{OW - 1}" stroke-linejoin="round"/>')
    elif col == "kurta":
        coll = f'<path d="M{cx - tw * 0.08:.1f},{top + 2:.1f} L{front - 2:.1f},{top + 30:.1f}" stroke="{INK}" stroke-width="{OW}" stroke-linecap="round"/><path d="M{front - 30:.1f},{top + 30:.1f} L{front - 34:.1f},{top + 120:.1f}" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
    else:
        coll = f'<path d="M{cx - tw * 0.06:.1f},{top + 2:.1f} C{cx + tw * 0.2:.1f},{top + 16:.1f} {front - 6:.1f},{top + 22:.1f} {front + 4:.1f},{top + 30:.1f}" fill="none" stroke="{INK}" stroke-width="{OW + 1}" stroke-linecap="round"/>'
    extra = ""
    if o.get("badge"):
        extra += f'<rect x="{front - 34:.1f}" y="{top + Lt * 0.32:.1f}" width="22" height="30" rx="4" fill="#d9c25a" stroke="{INK}" stroke-width="4"/>'
    body = (f'<g clip-path="url(#tc)"><path d="{d}" fill="{o["fill"]}"/>{pat}</g><path d="{d}" fill="none" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>{coll}{extra}')
    return _svg(W_, H_, body, _clip("tc", d)), (cx, hy)


def phone(P, dna, fb):
    w, h = 62 * P["k"], 118 * P["k"]
    W_, H_ = 2 * M + w, 2 * M + h
    body = (f'<rect x="{M}" y="{M}" width="{w}" height="{h}" rx="10" fill="#15171c" stroke="{INK}" stroke-width="6"/>'
            f'<rect x="{M + 6}" y="{M + 10}" width="{w - 12}" height="{h - 20}" rx="5" fill="#2a3e58"/>'
            f'<rect x="{M + 12}" y="{M + 22}" width="{w - 24}" height="14" rx="4" fill="#d6e6ff" opacity="0.65"/><rect x="{M + 12}" y="{M + 44}" width="{(w - 24) * 0.7:.0f}" height="10" rx="4" fill="#9fb8dd" opacity="0.5"/>')
    return _svg(W_, H_, body), (M + w / 2, M + h / 2)               # pivot = phone centre


def head_layers(P, dna, fb):
    """Open Peeps head shell split into an independent SKIN layer and HAIR layer (fills split by colour)."""
    svg = open(os.path.join(ROOT, D.head_svg_path(dna)), encoding="utf-8").read()
    skin_hex = D.SKIN[dna["skin"]]
    skull = svg.replace('fill="#000000"', 'fill="none"')
    hair = svg.replace(f'fill="{skin_hex}"', 'fill="none"').replace('fill="#000000"', f'fill="{fb["hair_color"]}"')
    return skull, hair


def nose(P, dna):
    return A.nose_svg(A.__file__.rsplit("/asset_pipeline", 1)[0] + "/assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/face/Serious.svg").replace('fill="#000000"', f'fill="{D.SKIN[dna["skin"]]}"').replace(
        f'fill="{INK}"', f'fill="{INK}"')


# ------------------------------------------------------------------------------------------------------------------ bake
def _key(dna, fb, P):
    return hashlib.sha1(json.dumps([dna, fb, {k: round(v, 2) for k, v in P.items()}, "art-v3"], sort_keys=True, default=str).encode()).hexdigest()[:12]


def bake(dna, force=False):
    """-> dict(id, dir, P, fb, parts={name: dict(png, pivot(tex px in cropped image), size, res)}). PNGs cached under assets/character/skeleton/generated/<key>/."""
    fb = fullbody(dna)
    P = R.proportions(dna, fb["height_scale"])
    key = _key(dna, fb, P)
    d = os.path.join(GEN, key)
    man_path = os.path.join(d, "parts.json")
    if os.path.exists(man_path) and not force:
        return json.load(open(man_path))
    os.makedirs(d, exist_ok=True)
    parts = {}

    def save(name, svg, pivot, zoom=TEX):
        arr, (ox, oy) = rasterize(svg, zoom=zoom)
        Image.fromarray(arr).save(os.path.join(d, f"{name}.png"))
        parts[name] = dict(png=os.path.relpath(os.path.join(d, f"{name}.png"), ROOT), pivot=[pivot[0] * zoom - ox, pivot[1] * zoom - oy], size=[arr.shape[1], arr.shape[0]], res=TEX)

    for side in ("L", "R"):
        save(f"upperarm_{side}", *upperarm(P, dna, fb, side))
        save(f"forearm_{side}", *forearm(P, dna, fb, side))
        save(f"hand_{side}", *hand(P, dna, fb, side))
        save(f"thigh_{side}", *thigh(P, dna, fb, side))
        save(f"shin_{side}", *shin(P, dna, fb, side))
        save(f"foot_{side}", *foot(P, dna, fb, side))
    save("pelvis", *pelvis(P, dna, fb))
    save("torso", *torso(P, dna, fb))
    save("neck", *neck(P, dna, fb))
    save("phone", *phone(P, dna, fb))
    save("fingers", *fingers(P, dna, fb))
    skull, hair = head_layers(P, dna, fb)
    hz = TEX * P["hs"]
    save("skull", skull, R.NECK_PIVOT_CANVAS, zoom=hz)
    save("hair", hair, R.NECK_PIVOT_CANVAS, zoom=hz)
    ns = nose(P, dna)
    reg = A.FACE_REGION                                             # nose svg is drawn in region coords: viewBox origin = (reg[0], reg[1])
    save("nose", ns, (R.NECK_PIVOT_CANVAS[0] - reg[0], R.NECK_PIVOT_CANVAS[1] - reg[1]), zoom=hz)
    man = dict(id=key, dir=os.path.relpath(d, ROOT), P=P, fb=fb, parts=parts, dna_id=dna["id"], skin=D.SKIN[dna["skin"]],
               face_style=dict(ex=D.EYES[dna["eyes"]][0], ey=D.EYES[dna["eyes"]][1], brow=D.BROWS[dna["eyebrows"]], mouth=dna["mouth_width"]))
    json.dump(man, open(man_path, "w"), indent=1)
    return man
