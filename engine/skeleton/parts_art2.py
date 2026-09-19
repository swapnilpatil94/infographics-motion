"""CHARACTER ART v2: CharacterDNA v2 -> reusable vector PARTS per body part, per VIEW (profile / three_quarter / front), in a restrained editorial ink language
(thin black outline, flat muted fills, one shade tone, a few fold lines - after the Open Peeps illustrations). Nothing is baked into one picture.

Wardrobe (all recolourable via the DNA palette): tops tee/shirt/polo/hoodie/kurta/sweater/jacket - bottoms jeans/trousers/shorts/skirt/salwar - shoes sneakers/sandals/formal/slippers -
accessories glasses(Open Peeps atom)/watch/bag/backpack/earrings/cap. Hands: 10 reusable poses attached to the wrist bone.
Heads, hair, nose and the ink style: Open Peeps (CC0). Everything else is own-work generated art.
"""
import hashlib
import json
import re
import math
import os
import random

from PIL import Image

from asset_pipeline import rig_art as A
from engine.characters import dna as D1
from engine.shorts.raster import ROOT, rasterize
from engine.skeleton import dna2, parts_art as PA, rig_def as R

TEX = 2.0
GEN = os.path.join(ROOT, "assets/character/skeleton/generated_v2")
INK = "#000000"
OW = 6.0
M = 44.0
from engine.skeleton import hands3 as H3   # noqa: E402
HAND_POSES = list(H3.POSES)                                                          # 20 poses per hand (v3); the first ten keep their v2 ids
BASIC_POSES = list(H3.BASIC)
PROP_HELD = {"hold_phone": "phone", "hold_card": "card", "hold_money": "money"}

TOP_STYLE = {
    "tee": dict(sleeve=0.50, hem=0.03, collar="crew", baggy=1.00, seam=True), "shirt": dict(sleeve=1.0, hem=0.09, collar="shirt", buttons=True, pocket=True, baggy=1.03, cuff="button"),
    "polo": dict(sleeve=0.55, hem=0.05, collar="polo", placket=True, baggy=1.0), "hoodie": dict(sleeve=1.0, hem=0.10, collar="hood", kangaroo=True, baggy=1.13, cuff="rib"),
    "kurta": dict(sleeve=1.0, hem=0.40, collar="band", placket=True, slit=True, baggy=1.06, cuff="plain"), "sweater": dict(sleeve=1.0, hem=0.07, collar="crew_rib", rib=True, baggy=1.09, cuff="rib"),
    "jacket": dict(sleeve=1.0, hem=0.12, collar="lapel", zip=True, opening=True, baggy=1.07, cuff="plain")}
BOTTOM_STYLE = {"jeans": dict(cover=1.0, seam="stitch", baggy=1.0), "trousers": dict(cover=1.0, seam="crease", baggy=1.0), "shorts": dict(cover=0.58, lower="skin", baggy=1.04),
                "skirt": dict(cover=0.0, lower="tights", baggy=1.0), "salwar": dict(cover=1.0, baggy=1.5, gather=True)}


def shade(hex_, f):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in (r, g, b))


class Kit:
    """Everything the part generators need, derived from (DNA, view)."""

    def __init__(self, d2, view):
        self.d2, self.view = d2, view
        self.P = R.proportions_v2(d2, view)
        w = d2["wardrobe"]
        self.top, self.bottom, self.shoes = w["top"], w["bottom"], w["shoes"]
        self.ts, self.bs = TOP_STYLE[self.top], BOTTOM_STYLE[self.bottom]
        self.skin = d2["skin"]["hex"]
        self.top_c, self.bot_c, self.shoe_c, self.accent = w["top_color"], w["bottom_color"], w["shoe_color"], w["accent"]
        self.pattern = w["pattern"] if self.top not in ("jacket",) else "plain"
        self.acc = set(w["accessories"])
        self.rng = random.Random(d2["id"])
        self.lower_c = self.skin if self.bs.get("lower") == "skin" else (shade(self.bot_c, 0.9) if self.bs.get("lower") == "tights" else self.bot_c)


def _svg(w, h, body, defs=""):
    return PA._svg(w, h, body, defs)


def _fold(x0, y0, x1, y1, bend=8, op=0.55):
    mx, my = (x0 + x1) / 2 + bend, (y0 + y1) / 2
    return f'<path d="M{x0:.1f},{y0:.1f} Q{mx:.1f},{my:.1f} {x1:.1f},{y1:.1f}" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round" opacity="{op}"/>'


def _limb(len_, w0, w1, base, cover, cover_len, pattern, seed, cuff=None, seam=None, shade_c=None, extra_tail="", knee=False, skin_c=None):
    """Tapered capsule limb: `base` colour over the whole length, a `cover` garment colour over the first `cover_len` (0=none), cuff / seam / shading / folds."""
    W_, H_ = 2 * M + max(w0, w1) * 1.3, 2 * M + len_
    cx = M + max(w0, w1) * 0.65
    r0, r1 = w0 / 2, w1 / 2
    d = f"M{cx - r0:.1f},{M:.1f} A{r0:.1f},{r0:.1f} 0 0 1 {cx + r0:.1f},{M:.1f} L{cx + r1:.1f},{M + len_:.1f} A{r1:.1f},{r1:.1f} 0 0 1 {cx - r1:.1f},{M + len_:.1f} Z"
    defs = f'<clipPath id="lc"><path d="{d}"/></clipPath>'
    body = f'<path d="{d}" fill="{base}" stroke="none"/>'
    if cover and cover_len > 0:
        cl = min(cover_len, len_ + r1)
        body += f'<g clip-path="url(#lc)"><rect x="0" y="0" width="{W_}" height="{M + cl:.1f}" fill="{cover}"/>' + (PA._pattern(pattern, seed, 0, W_, M, M + cl) if pattern != "plain" else "") + '</g>'
        if cl < len_ - 2:
            body += f'<path d="M{cx - r1 - 8:.1f},{M + cl:.1f} L{cx + r1 + 8:.1f},{M + cl:.1f}" stroke="{INK}" stroke-width="{OW + 0.5}" stroke-linecap="round"/>'
            if cuff == "rib":
                for k in range(1, 4):
                    body += f'<path d="M{cx - r1 - 2:.1f},{M + cl - 7 * k:.1f} L{cx + r1 + 2:.1f},{M + cl - 7 * k:.1f}" stroke="{INK}" stroke-width="1.8" opacity="0.55"/>'
            elif cuff == "button":
                body += f'<circle cx="{cx + r1 * 0.55:.1f}" cy="{M + cl - 12:.1f}" r="3.2" fill="{INK}"/>'
    sc = shade_c or shade(cover or base, 0.80)
    body += f'<g clip-path="url(#lc)"><rect x="{cx + r0 * 0.15:.1f}" y="{M - 4:.1f}" width="{W_}" height="{len_ + 10:.1f}" fill="{sc}" opacity="0.30"/></g>'
    body += _fold(cx - r0 * 0.55, M + len_ * 0.5, cx + r0 * 0.15, M + len_ * 0.52, 6) if knee else _fold(cx - r0 * 0.5, M + len_ * 0.48, cx + r0 * 0.3, M + len_ * 0.5, 5, 0.4)
    if seam == "stitch":
        body += f'<path d="M{cx + r0 * 0.62:.1f},{M + 12:.1f} L{cx + r1 * 0.6:.1f},{M + len_ - 10:.1f}" stroke="{INK}" stroke-width="2" stroke-dasharray="7 5" opacity="0.55"/>'
    elif seam == "crease":
        body += f'<path d="M{cx:.1f},{M + 14:.1f} L{cx:.1f},{M + len_ - 12:.1f}" stroke="{INK}" stroke-width="2" opacity="0.4"/>'
    body += f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>' + extra_tail
    return _svg(W_, H_, body, defs), (cx, M)


# ------------------------------------------------------------------------------------------------------------------ limbs / body parts
def upperarm(k, side):
    P, ts = k.P, k.ts
    sl = P["upper_arm"] * (ts["sleeve"] if ts["sleeve"] < 1 else 0.98)
    return _limb(P["upper_arm"], P["limb"] * 1.08, P["limb"] * 0.9, k.skin, k.top_c, sl, k.pattern, 7 + (side == "R"), cuff=ts.get("cuff") if ts["sleeve"] < 1 else None,
                 shade_c=shade(k.top_c, 0.8))


def forearm(k, side):
    P, ts = k.P, k.ts
    sl = 0.0 if ts["sleeve"] < 1 else P["forearm"] * 0.86
    extra = ""
    if "watch" in k.acc and side == "R":
        cx = M + P["limb"] * 0.6
        y = M + P["forearm"] * 0.84
        extra = (f'<rect x="{cx - P["limb"] * 0.42:.1f}" y="{y:.1f}" width="{P["limb"] * 0.84:.1f}" height="11" rx="3" fill="{k.accent}" stroke="{INK}" stroke-width="3"/>'
                 f'<rect x="{cx + P["limb"] * 0.08:.1f}" y="{y - 3:.1f}" width="{P["limb"] * 0.4:.1f}" height="17" rx="4" fill="#d8d6cf" stroke="{INK}" stroke-width="2.6"/>')
    return _limb(P["forearm"], P["limb"] * 0.92, P["limb"] * 0.7, k.skin, k.top_c, sl, k.pattern, 9 + (side == "R"), cuff=ts.get("cuff"), shade_c=shade(k.top_c, 0.8), extra_tail=extra)


def thigh(k, side):
    P, bs = k.P, k.bs
    wmul = bs["baggy"]
    cover = k.bot_c if bs["cover"] > 0 else None
    base = k.lower_c if bs["cover"] < 1 else k.bot_c
    return _limb(P["thigh"], P["limb"] * 1.32 * wmul, P["limb"] * 1.02 * wmul, base, cover, P["thigh"] * bs["cover"], "plain", 3, seam=bs.get("seam"), shade_c=shade(k.bot_c, 0.8), knee=True)


def shin(k, side):
    P, bs = k.P, k.bs
    wmul = bs["baggy"] if not bs.get("gather") else 1.25
    cover = k.bot_c if bs["cover"] >= 1.0 else None
    base = k.lower_c
    svg, piv = _limb(P["shin"], P["limb"] * 1.02 * wmul, P["limb"] * (0.72 if not bs.get("gather") else 0.66) * (1.0 if bs["cover"] >= 1 else 1.0), base, cover, P["shin"] if cover else 0, "plain", 4,
                     seam=bs.get("seam"), shade_c=shade(k.bot_c, 0.8), knee=True)
    if bs.get("gather"):                                                            # salwar cuff gathered at the ankle
        cx = piv[0]
        y = M + P["shin"] - 22
        svg = svg.replace("</svg>", f'<path d="M{cx - P["limb"] * 0.5:.1f},{y:.1f} L{cx + P["limb"] * 0.5:.1f},{y:.1f}" stroke="{INK}" stroke-width="4"/></svg>')
    return svg, piv


def pelvis(k, side=None):
    P = k.P
    tw, kk = P["torso_w"] * (1.0 if k.view == "profile" else 1.2 if k.view == "three_quarter" else 1.4), P["k"]
    W_, H_ = 2 * M + tw + 40, 2 * M + 150 * kk
    x0, y0 = M + tw / 2 + 20, M + 48 * kk
    fill = k.bot_c if k.bs["cover"] > 0 else shade(k.bot_c, 0.95)
    body = (f'<rect x="{x0 - tw / 2 * 0.98:.1f}" y="{y0 - 76 * kk:.1f}" width="{tw * 0.98:.1f}" height="{136 * kk:.1f}" rx="{42 * kk:.1f}" fill="{fill}" stroke="{INK}" stroke-width="{OW}"/>'
            f'<rect x="{x0 - tw / 2 * 0.98:.1f}" y="{y0 - 76 * kk:.1f}" width="{tw * 0.98:.1f}" height="14" rx="6" fill="{shade(fill, 0.78)}" opacity="0.7"/>')
    if k.view != "profile" and k.bs["cover"] > 0:
        body += f'<path d="M{x0:.1f},{y0 - 60 * kk:.1f} L{x0:.1f},{y0 + 10 * kk:.1f}" stroke="{INK}" stroke-width="2.4" opacity="0.6"/>'
    if k.bottom in ("jeans", "trousers") and k.view == "profile":
        body += f'<path d="M{x0 - tw * 0.25:.1f},{y0 - 60 * kk:.1f} Q{x0 - tw * 0.1:.1f},{y0 - 30 * kk:.1f} {x0 - tw * 0.3:.1f},{y0 - 8 * kk:.1f}" fill="none" stroke="{INK}" stroke-width="2" opacity="0.5"/>'
    return _svg(W_, H_, body), (x0, y0)


def skirt(k):
    P = k.P
    tw, kk = P["torso_w"] * (1.0 if k.view == "profile" else 1.25 if k.view == "three_quarter" else 1.5), P["k"]
    L = P["thigh"] * 0.82
    W_, H_ = 2 * M + tw * 1.9, 2 * M + L + 70
    cx, y0 = M + tw * 0.95, M + 30
    d = f"M{cx - tw * 0.48:.1f},{y0:.1f} C{cx - tw * 0.7:.1f},{y0 + L * 0.4:.1f} {cx - tw * 0.85:.1f},{y0 + L * 0.8:.1f} {cx - tw * 0.9:.1f},{y0 + L:.1f} L{cx + tw * 0.9:.1f},{y0 + L:.1f} C{cx + tw * 0.85:.1f},{y0 + L * 0.8:.1f} {cx + tw * 0.7:.1f},{y0 + L * 0.4:.1f} {cx + tw * 0.48:.1f},{y0:.1f} Z"
    body = (f'<defs><clipPath id="sk"><path d="{d}"/></clipPath></defs><path d="{d}" fill="{k.bot_c}"/>'
            f'<g clip-path="url(#sk)"><rect x="{cx + tw * 0.1:.1f}" y="{y0}" width="{tw}" height="{L}" fill="{shade(k.bot_c, 0.78)}" opacity="0.4"/>' +
            "".join(f'<path d="M{cx + dx:.1f},{y0 + 20:.1f} Q{cx + dx * 1.25:.1f},{y0 + L * 0.5:.1f} {cx + dx * 1.5:.1f},{y0 + L:.1f}" stroke="{INK}" stroke-width="2" fill="none" opacity="0.45"/>' for dx in (-tw * 0.3, 0, tw * 0.3)) +
            f'</g><path d="{d}" fill="none" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>')
    return _svg(W_, H_, body), (cx, y0)


def neck(k):
    P = k.P
    nw, nl = 50 * P["k"] * k.d2["body"]["neck"], P["neck"] + 34 * P["k"]
    body = PA._capsule(nl, nw, nw * 0.92, k.skin, stroke=OW) + f'<path d="M{M - nw * 0.1:.1f},{M + 6:.1f} L{M - nw * 0.1:.1f},{M + nl * 0.6:.1f}" stroke="{shade(k.skin, 0.8)}" stroke-width="{nw * 0.3:.1f}" opacity="0.5"/>'
    return _svg(2 * M + nw, 2 * M + nl, body), (M, M + nl)


def torso(k):
    """Profile: side-on shirt with forward chest bulge. Three-quarter / front: wider, symmetric shirt block. All tops share the outline builder; details come from TOP_STYLE."""
    P, ts = k.P, dict(k.ts)
    back = k.view == "back"
    if back:                                                                       # seen from behind: no placket, buttons, pocket, zip, collar opening
        ts.update(collar="band", buttons=False, placket=False, pocket=False, zip=False, kangaroo=False, opening=False)
    kk, Lt = P["k"], P["torso"]
    tw = P["torso_w"] * (ts["baggy"] ** 0.6)
    if k.view == "profile":
        wv = tw
    elif k.view == "three_quarter":
        wv = tw * 1.20 * P.get("shoulder_k", 1.0)
    else:
        wv = tw * 1.50 * P.get("shoulder_k", 1.0)
    hem = P["thigh"] * ts["hem"] + 30 * kk
    W_, H_ = 2 * M + wv + 70, 2 * M + Lt + hem + 60
    cx, hy = M + wv / 2 + 30, M + Lt + 30
    top = hy - Lt - 14 * kk
    yh = hy + hem
    if k.view == "profile":
        back, front = cx - wv * 0.5, cx + wv * 0.52
        yw = top + Lt * 0.72                                                          # waist
        d = (f"M{cx - wv * 0.10:.1f},{top - 2:.1f} C{back + 34:.1f},{top - 2:.1f} {back + 12:.1f},{top + 8:.1f} {back + 5:.1f},{top + 36:.1f} "
             f"C{back - 8:.1f},{top + Lt * 0.30:.1f} {back - 8:.1f},{top + Lt * 0.55:.1f} {back - 1:.1f},{yw:.1f} "
             f"C{back + 4:.1f},{hy + hem * 0.2:.1f} {back + 2:.1f},{yh - 16:.1f} {back + 12:.1f},{yh - 3:.1f} Q{back + 18:.1f},{yh:.1f} {back + 30:.1f},{yh:.1f} "
             f"L{front - 20:.1f},{yh:.1f} Q{front - 2:.1f},{yh:.1f} {front + 2:.1f},{yh - 14:.1f} C{front + 6:.1f},{hy + hem * 0.1:.1f} {front + 3:.1f},{yw + 6:.1f} {front + 2:.1f},{yw - 4:.1f} "
             f"C{front - 4:.1f},{top + Lt * 0.52:.1f} {front + 22:.1f},{top + Lt * 0.42:.1f} {front + 9:.1f},{top + Lt * 0.22:.1f} "
             f"C{front + 2:.1f},{top + 10:.1f} {cx + wv * 0.18:.1f},{top - 2:.1f} {cx - wv * 0.10:.1f},{top - 2:.1f} Z")
        neck_x = cx + wv * 0.02
    else:
        half = wv / 2
        wr = min(0.90, max(0.66, (0.80 if k.view == "front" else 0.84) + (ts["baggy"] - 1.0) * 0.9))
        waist = half * wr
        hipw = waist * (1.05 + 0.14 * min(1.0, ts["hem"] * 3))
        nk = min(half * 0.36, 30.0)
        yw = top + Lt * 0.70

        def side(sg):
            X = lambda dx: f"{cx + sg * dx:.1f}"
            return (f"C{X(half + 4)},{top + Lt * 0.20:.1f} {X(half * 0.95)},{top + Lt * 0.42:.1f} {X(waist + 2)},{top + Lt * 0.62:.1f} "
                    f"C{X(waist - 1)},{top + Lt * 0.70:.1f} {X(hipw + 5)},{hy + hem * 0.30:.1f} {X(hipw)},{yh - 12:.1f}")
        d = (f"M{cx - nk:.1f},{top - 6:.1f} C{cx - nk - 22:.1f},{top - 4:.1f} {cx - half * 0.80:.1f},{top + 2:.1f} {cx - half:.1f},{top + 40:.1f} " + side(-1) +
             f" Q{cx - hipw + 1:.1f},{yh:.1f} {cx - hipw + 14:.1f},{yh:.1f} L{cx + hipw - 14:.1f},{yh:.1f} Q{cx + hipw - 1:.1f},{yh:.1f} {cx + hipw:.1f},{yh - 12:.1f} "
             f"C{cx + hipw + 5:.1f},{hy + hem * 0.30:.1f} {cx + waist - 1:.1f},{top + Lt * 0.70:.1f} {cx + waist + 2:.1f},{top + Lt * 0.62:.1f} "
             f"C{cx + half * 0.95:.1f},{top + Lt * 0.42:.1f} {cx + half + 4:.1f},{top + Lt * 0.20:.1f} {cx + half:.1f},{top + 40:.1f} "
             f"C{cx + half * 0.80:.1f},{top + 2:.1f} {cx + nk + 22:.1f},{top - 4:.1f} {cx + nk:.1f},{top - 6:.1f} Z")
        neck_x = cx
        front = cx + half
        back = cx - half
    fill = k.top_c
    det = ""
    sh_x = (cx + wv * 0.05) if k.view == "profile" else (cx + wv * 0.12)
    det += f'<rect x="{sh_x:.1f}" y="{top - 8:.1f}" width="{wv}" height="{Lt + hem + 40:.1f}" fill="{shade(fill, 0.78)}" opacity="0.28"/>'
    if k.pattern != "plain":
        det += PA._pattern(k.pattern, 5, back - 10, cx + wv * 0.6, top, hy + hem)
    # collar / neckline
    col = ts["collar"]
    nx, ny = neck_x, top
    if col in ("crew", "crew_rib"):
        det += f'<path d="M{nx - 34:.1f},{ny + 4:.1f} Q{nx:.1f},{ny + 36:.1f} {nx + 34:.1f},{ny + 4:.1f}" fill="{shade(fill, 0.9)}" stroke="{INK}" stroke-width="{OW - 1}" stroke-linecap="round"/>'
        if col == "crew_rib":
            det += f'<path d="M{nx - 30:.1f},{ny + 12:.1f} Q{nx:.1f},{ny + 40:.1f} {nx + 30:.1f},{ny + 12:.1f}" fill="none" stroke="{INK}" stroke-width="1.8" opacity="0.5"/>'
    elif col in ("shirt", "polo"):
        det += (f'<path d="M{nx - 8:.1f},{ny}  L{nx + 36:.1f},{ny + 52:.1f} L{nx + 8:.1f},{ny + 62:.1f} Z" fill="{fill}" stroke="{INK}" stroke-width="{OW - 1}" stroke-linejoin="round"/>'
                f'<path d="M{nx - 40:.1f},{ny + 2:.1f} L{nx - 4:.1f},{ny + 58:.1f} L{nx - 18:.1f},{ny + 64:.1f} Z" fill="{shade(fill, 0.93)}" stroke="{INK}" stroke-width="{OW - 1}" stroke-linejoin="round"/>')
    elif col == "hood":
        det += f'<path d="M{nx - 44:.1f},{ny + 10:.1f} Q{nx:.1f},{ny + 52:.1f} {nx + 44:.1f},{ny + 10:.1f}" fill="{shade(fill, 0.85)}" stroke="{INK}" stroke-width="{OW}" stroke-linecap="round"/>'
    elif col == "band":
        det += f'<path d="M{nx - 30:.1f},{ny + 4:.1f} L{nx + 30:.1f},{ny + 4:.1f}" stroke="{INK}" stroke-width="{OW}" stroke-linecap="round"/>'
    elif col == "lapel":
        det += (f'<path d="M{nx - 10:.1f},{ny} L{nx + 46:.1f},{ny + 70:.1f} L{nx + 12:.1f},{ny + 84:.1f} Z" fill="{shade(fill, 1.08)}" stroke="{INK}" stroke-width="{OW - 1}" stroke-linejoin="round"/>')
    line_x = nx + (10 if k.view == "profile" else 0)
    if ts.get("buttons") or ts.get("placket"):
        det += f'<path d="M{line_x:.1f},{ny + 60:.1f} L{line_x + (8 if k.view == "profile" else 0):.1f},{hy + hem - 6:.1f}" stroke="{INK}" stroke-width="2.4" opacity="0.7"/>'
        for j in range(5):
            det += f'<circle cx="{line_x + 3 + (j * 1.6 if k.view == "profile" else 0):.1f}" cy="{ny + 86 + j * (Lt - 60) / 5:.1f}" r="3.3" fill="{INK}"/>'
    if ts.get("zip"):
        det += f'<path d="M{line_x + 4:.1f},{ny + 58:.1f} L{line_x + 10:.1f},{hy + hem - 4:.1f}" stroke="{INK}" stroke-width="3" stroke-dasharray="4 3"/>'
    if ts.get("pocket"):
        px = (front - 46) if k.view == "profile" else cx + wv * 0.22
        det += f'<path d="M{px:.1f},{top + Lt * 0.32:.1f} l30,0 l0,34 l-15,8 l-15,-8 Z" fill="none" stroke="{INK}" stroke-width="2.6" opacity="0.75"/>'
    if ts.get("kangaroo"):
        det += f'<path d="M{cx - wv * 0.28:.1f},{hy - Lt * 0.22:.1f} L{cx + wv * 0.34:.1f},{hy - Lt * 0.22:.1f} L{cx + wv * 0.4:.1f},{hy + hem * 0.2:.1f} L{cx - wv * 0.34:.1f},{hy + hem * 0.2:.1f} Z" fill="none" stroke="{INK}" stroke-width="2.6" opacity="0.7"/>'
    if ts.get("rib"):
        for j in range(3):
            det += f'<path d="M{back + 4:.1f},{hy + hem - 6 - 6 * j:.1f} L{front - 4:.1f},{hy + hem - 6 - 6 * j:.1f}" stroke="{INK}" stroke-width="1.8" opacity="0.5"/>'
    if ts.get("slit"):
        det += f'<path d="M{cx - wv * 0.28:.1f},{hy + hem * 0.35:.1f} L{cx - wv * 0.28:.1f},{hy + hem:.1f} M{cx + wv * 0.3:.1f},{hy + hem * 0.35:.1f} L{cx + wv * 0.3:.1f},{hy + hem:.1f}" stroke="{INK}" stroke-width="2.4" opacity="0.7"/>'
    det += _fold(cx - wv * 0.2, hy - Lt * 0.3, cx + wv * 0.1, hy - Lt * 0.05, 5, 0.45) + _fold(cx - wv * 0.3, hy - Lt * 0.62, cx - wv * 0.05, hy - Lt * 0.5, 4, 0.35)
    body = f'<defs><clipPath id="tc"><path d="{d}"/></clipPath></defs><path d="{d}" fill="{fill}"/><g clip-path="url(#tc)">{det}</g><path d="{d}" fill="none" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>'
    if ts.get("opening"):
        body += f'<path d="M{line_x:.1f},{ny + 60:.1f} L{line_x + 6:.1f},{hy + hem:.1f}" stroke="{INK}" stroke-width="{OW - 1}"/>'
    return _svg(W_, H_, body), (cx, hy)


def foot(k, side):
    P = k.P
    kk, fh, fl = P["k"], P["foot_h"], P["foot_len"]
    st, col = k.shoes, k.shoe_c
    if k.view == "front":                                                             # shoe seen from the front: rounded toe cap
        W_, H_ = 2 * M + 110 * kk, 2 * M + fh + 40
        cx, y0 = M + 55 * kk, M + 4
        base = k.skin if st == "sandals" else col
        body = (f'<path d="M{cx - 34 * kk:.1f},{y0 - 6:.1f} L{cx + 34 * kk:.1f},{y0 - 6:.1f} C{cx + 44 * kk:.1f},{y0 + 16:.1f} {cx + 46 * kk:.1f},{y0 + fh + 8:.1f} {cx:.1f},{y0 + fh + 10:.1f} '
                f'C{cx - 46 * kk:.1f},{y0 + fh + 8:.1f} {cx - 44 * kk:.1f},{y0 + 16:.1f} {cx - 34 * kk:.1f},{y0 - 6:.1f} Z" fill="{base}" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>'
                f'<path d="M{cx - 34 * kk:.1f},{y0 + fh + 4:.1f} L{cx + 34 * kk:.1f},{y0 + fh + 4:.1f}" stroke="#f2f2f2" stroke-width="6" stroke-linecap="round"/>')
        return _svg(W_, H_, body), (cx, y0)
    heel, toe = -34 * kk, fl - 34 * kk
    W_, H_ = 2 * M + fl + 50, 2 * M + fh + 36
    y0 = M
    x0 = M + 34 * kk + 14
    top = (f"M{x0 - 32 * kk:.1f},{y0 - 6:.1f} L{x0 + 26 * kk:.1f},{y0 - 6:.1f} C{x0 + 34 * kk:.1f},{y0 + 22:.1f} {x0 + 70 * kk:.1f},{y0 + 26:.1f} {x0 + toe * 0.82:.1f},{y0 + 30:.1f}"
           f" C{x0 + toe + 8:.1f},{y0 + 32:.1f} {x0 + toe + 10:.1f},{y0 + fh + 4:.1f} {x0 + toe - 8:.1f},{y0 + fh + 6:.1f} L{x0 + heel + 6:.1f},{y0 + fh + 6:.1f} C{x0 + heel - 8:.1f},{y0 + fh + 4:.1f} {x0 + heel - 6:.1f},{y0 + 8:.1f} {x0 - 32 * kk:.1f},{y0 - 6:.1f} Z")
    if st == "formal":
        top = top.replace(f"{x0 + toe + 8:.1f},{y0 + 32:.1f}", f"{x0 + toe + 26:.1f},{y0 + fh * 0.7:.1f}")
    body = ""
    if st == "sandals":
        body += f'<path d="{top}" fill="{k.skin}" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>'
        body += "".join(f'<path d="M{x0 + a_:.1f},{y0 + 4:.1f} L{x0 + a_ + 26:.1f},{y0 + fh + 2:.1f}" stroke="{col}" stroke-width="9" stroke-linecap="round"/>' for a_ in (10 * kk, 48 * kk))
        body += f'<path d="M{x0 + heel:.1f},{y0 + fh + 5:.1f} L{x0 + toe - 6:.1f},{y0 + fh + 5:.1f}" stroke="{col}" stroke-width="9" stroke-linecap="round"/>'
    else:
        fillc = col if st != "slippers" else shade(k.accent, 0.9)
        body += f'<path d="{top}" fill="{fillc}" stroke="{INK}" stroke-width="{OW}" stroke-linejoin="round"/>'
        if st == "sneakers":
            body += f'<path d="M{x0 + heel + 4:.1f},{y0 + fh - 2:.1f} L{x0 + toe - 6:.1f},{y0 + fh - 2:.1f}" stroke="#f4f4f2" stroke-width="9" stroke-linecap="round"/>'
            body += "".join(f'<path d="M{x0 + a_:.1f},{y0 + 6:.1f} l14,8" stroke="#f4f4f2" stroke-width="3.4" stroke-linecap="round"/>' for a_ in (30 * kk, 46 * kk, 62 * kk))
            body += f'<path d="M{x0 + toe * 0.55:.1f},{y0 + 30:.1f} Q{x0 + toe * 0.7:.1f},{y0 + fh:.1f} {x0 + toe - 10:.1f},{y0 + fh:.1f}" fill="none" stroke="{INK}" stroke-width="2.4" opacity="0.55"/>'
        elif st == "formal":
            body += f'<path d="M{x0 + 20 * kk:.1f},{y0 + 14:.1f} Q{x0 + toe * 0.5:.1f},{y0 + 18:.1f} {x0 + toe * 0.8:.1f},{y0 + 26:.1f}" fill="none" stroke="#ffffff" stroke-width="3.2" opacity="0.55" stroke-linecap="round"/>'
            body += f'<path d="M{x0 + heel + 6:.1f},{y0 + fh + 1:.1f} L{x0 + toe - 8:.1f},{y0 + fh + 1:.1f}" stroke="#1a1a1e" stroke-width="7" stroke-linecap="round"/>'
        else:
            body += f'<path d="M{x0 + 6 * kk:.1f},{y0 + 22:.1f} Q{x0 + toe * 0.5:.1f},{y0 + 8:.1f} {x0 + toe * 0.8:.1f},{y0 + 28:.1f}" fill="none" stroke="{INK}" stroke-width="3" opacity="0.6"/>'
    return _svg(W_, H_, body), (x0, y0)


# ------------------------------------------------------------------------------------------------------------------ hands (10 reusable poses)
# per finger (curl1, curl2) degrees, thumb (curl1, curl2, out); positive curl = fingers close toward +x
POSE_TABLE = {
    "open": dict(f=[(4, 4), (0, 0), (-2, -2), (-6, -4)], t=(25, 10, 34), spread=9), "closed": dict(f=[(34, 46), (38, 50), (42, 52), (44, 54)], t=(30, 22, 10), spread=3),
    "point": dict(f=[(0, 0), (82, 88), (86, 90), (88, 92)], t=(40, 30, 8), spread=4), "grab": dict(f=[(52, 60), (56, 64), (58, 66), (58, 66)], t=(34, 40, 22), spread=5),
    "hold_phone": dict(f=[(58, 70), (62, 74), (64, 76), (64, 76)], t=(30, 22, 30), spread=3), "hold_card": dict(f=[(30, 36), (70, 78), (74, 82), (78, 84)], t=(38, 30, 26), spread=3),
    "hold_money": dict(f=[(34, 40), (66, 74), (72, 80), (76, 82)], t=(40, 34, 28), spread=3), "gesture": dict(f=[(12, 12), (16, 22), (34, 40), (46, 54)], t=(20, 14, 28), spread=8),
    "palm_up": dict(f=[(14, 10), (10, 8), (8, 6), (6, 4)], t=(18, 6, 52), spread=12), "fist": dict(f=[(82, 92), (86, 94), (88, 96), (88, 96)], t=(64, 52, 0), spread=2)}


def hand_pose(k, pose, side):
    P = k.P
    hl, hw = P["hand"], P["limb"] * 0.6
    fw = max(9.0, P["limb"] * 0.19)
    W_, H_ = 2 * M + hw * 4 + 50, 2 * M + hl * 1.9 + 30
    cx = M + hw * 2
    tab = POSE_TABLE[pose]
    skin, sh = k.skin, shade(k.skin, 0.84)
    palm_h = hl * 0.52
    seg = [hl * 0.30, hl * 0.26]
    body = ""
    xs = [-hw * 0.50, -hw * 0.17, hw * 0.16, hw * 0.48]
    lens = [1.0, 1.08, 1.0, 0.82]
    for i, ((c1, c2), fx) in enumerate(zip(tab["f"], xs)):
        sp = (i - 1.5) * tab["spread"] * 0.3
        pts = [(cx + fx, M + palm_h - 2)]
        a1, a2 = math.radians(c1 + sp), math.radians(c1 + c2 + sp)
        p1 = (pts[0][0] + math.sin(a1) * seg[0] * lens[i] * 1.25, pts[0][1] + math.cos(a1) * seg[0] * lens[i] * 1.25)
        p2 = (p1[0] + math.sin(a2) * seg[1] * lens[i] * 1.25, p1[1] + math.cos(a2) * seg[1] * lens[i] * 1.25)
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} L{p1[0]:.1f},{p1[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f}"
        body += (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{fw + 2 * OW * 0.75:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
                 f'<path d="{d}" fill="none" stroke="{skin}" stroke-width="{fw:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    palm = (f'<path d="M{cx - hw * 0.72:.1f},{M - 6:.1f} C{cx - hw * 1.0:.1f},{M + palm_h * 0.5:.1f} {cx - hw * 0.8:.1f},{M + palm_h + 4:.1f} {cx - hw * 0.4:.1f},{M + palm_h + 4:.1f} '
            f'L{cx + hw * 0.62:.1f},{M + palm_h + 4:.1f} C{cx + hw * 0.92:.1f},{M + palm_h:.1f} {cx + hw * 0.98:.1f},{M + palm_h * 0.4:.1f} {cx + hw * 0.7:.1f},{M - 6:.1f} Z" fill="{skin}" stroke="{INK}" stroke-width="{OW * 0.85}" stroke-linejoin="round"/>'
            f'<path d="M{cx - hw * 0.5:.1f},{M + palm_h * 0.15:.1f} Q{cx:.1f},{M + palm_h * 0.7:.1f} {cx + hw * 0.4:.1f},{M + palm_h * 0.2:.1f}" fill="none" stroke="{sh}" stroke-width="3" opacity="0.6"/>')
    t1, t2, out = tab["t"]
    base = (cx + hw * 0.62, M + palm_h * 0.28)
    ta, tb = math.radians(out + t1 * 0.6), math.radians(out + t1 + t2)
    tp1 = (base[0] + math.sin(ta + 0.9) * hl * 0.30, base[1] + math.cos(ta + 0.9) * hl * 0.34)
    tp2 = (tp1[0] + math.sin(tb + 0.5) * hl * 0.26, tp1[1] + math.cos(tb + 0.5) * hl * 0.26)
    td = f"M{base[0]:.1f},{base[1]:.1f} L{tp1[0]:.1f},{tp1[1]:.1f} L{tp2[0]:.1f},{tp2[1]:.1f}"
    thumb = (f'<path d="{td}" fill="none" stroke="{INK}" stroke-width="{fw * 1.15 + 2 * OW * 0.75:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
             f'<path d="{td}" fill="none" stroke="{skin}" stroke-width="{fw * 1.15:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    return _svg(W_, H_, body + palm + thumb), (cx, M)


def fingers_overlay(k, pose):
    """Fingertips that wrap OVER a held prop (drawn above phone/card/money)."""
    P = k.P
    hw, fw = P["limb"] * 0.6, max(9.0, P["limb"] * 0.19)
    W_, H_ = 2 * M + hw * 4 + 40, 2 * M + 60
    cx = M + hw * 2
    body = "".join(f'<path d="M{cx - hw * 0.6:.1f},{M + 8 + 17 * i:.1f} L{cx + hw * 1.0:.1f},{M + 8 + 17 * i:.1f}" stroke="{INK}" stroke-width="{fw + 2 * OW * 0.7:.1f}" stroke-linecap="round"/>'
                   f'<path d="M{cx - hw * 0.6:.1f},{M + 8 + 17 * i:.1f} L{cx + hw * 1.0:.1f},{M + 8 + 17 * i:.1f}" stroke="{k.skin}" stroke-width="{fw:.1f}" stroke-linecap="round"/>' for i in range(3))
    return _svg(W_, H_, body), (cx, M)


def prop_card(k):
    W_, H_ = 2 * M + 96, 2 * M + 64
    body = (f'<rect x="{M}" y="{M}" width="92" height="60" rx="8" fill="{k.accent}" stroke="{INK}" stroke-width="5"/><rect x="{M}" y="{M + 12}" width="92" height="12" fill="#2a2a30"/>'
            f'<rect x="{M + 8}" y="{M + 38}" width="34" height="8" rx="3" fill="#f4f0e4"/><circle cx="{M + 74}" cy="{M + 44}" r="8" fill="#f2c55a" stroke="{INK}" stroke-width="2.4"/>')
    return _svg(W_, H_, body), (M + 46, M + 30)


def prop_money(k):
    W_, H_ = 2 * M + 110, 2 * M + 70
    body = "".join(f'<g transform="rotate({a} {M + 55} {M + 35})"><rect x="{M + 6}" y="{M + 8}" width="98" height="54" rx="4" fill="{c}" stroke="{INK}" stroke-width="4"/>'
                   f'<circle cx="{M + 55}" cy="{M + 35}" r="11" fill="none" stroke="{INK}" stroke-width="2.4" opacity="0.6"/></g>' for a, c in ((-9, "#b7c6a0"), (0, "#a9bd93"), (8, "#c4d1ad")))
    return _svg(W_, H_, body), (M + 55, M + 35)


def bag(k):
    P = k.P
    kk = P["k"]
    W_, H_ = 2 * M + 260, 2 * M + P["torso"] + 160
    cx, hy = M + 130, M + P["torso"] + 40
    body = (f'<path d="M{cx - 50:.1f},{hy - P["torso"] * 0.9:.1f} L{cx + 62:.1f},{hy - 20:.1f}" stroke="{INK}" stroke-width="{OW + 8}" stroke-linecap="round"/>'
            f'<path d="M{cx - 50:.1f},{hy - P["torso"] * 0.9:.1f} L{cx + 62:.1f},{hy - 20:.1f}" stroke="{k.accent}" stroke-width="8" stroke-linecap="round"/>'
            f'<rect x="{cx + 30:.1f}" y="{hy - 36:.1f}" width="104" height="82" rx="14" fill="{shade(k.accent, 0.95)}" stroke="{INK}" stroke-width="{OW}"/>'
            f'<path d="M{cx + 30:.1f},{hy - 6:.1f} L{cx + 134:.1f},{hy - 6:.1f}" stroke="{INK}" stroke-width="3"/><circle cx="{cx + 82:.1f}" cy="{hy + 8:.1f}" r="5" fill="{INK}"/>')
    return _svg(W_, H_, body), (cx, hy)


def backpack(k):
    P = k.P
    W_, H_ = 2 * M + 300, 2 * M + P["torso"] + 120
    cx, hy = M + 170, M + P["torso"] + 40
    body = (f'<rect x="{cx - 138:.1f}" y="{hy - P["torso"] * 0.92:.1f}" width="92" height="{P["torso"] * 0.86:.1f}" rx="26" fill="{k.accent}" stroke="{INK}" stroke-width="{OW}"/>'
            f'<rect x="{cx - 128:.1f}" y="{hy - P["torso"] * 0.42:.1f}" width="72" height="{P["torso"] * 0.26:.1f}" rx="12" fill="{shade(k.accent, 0.85)}" stroke="{INK}" stroke-width="3.4"/>')
    return _svg(W_, H_, body), (cx, hy)


# ------------------------------------------------------------------------------------------------------------------ head
def head_layers(k):
    """Open Peeps shell -> independent skin + hair layers; cap / earrings are drawn into these layers; nose is scaled by the DNA."""
    d2 = k.d2
    v1 = dna2.peeps_view(d2)
    svg = open(os.path.join(ROOT, D1.head_svg_path(v1)), encoding="utf-8").read()
    skin_hex = d2["skin"]["hex"]
    skull = svg.replace('fill="#000000"', 'fill="none"')
    if k.view == "back":                                                          # the back of the head is hair-coloured all over
        skull = re.sub(r'fill="(#[0-9a-fA-F]{6})"', lambda m: 'fill="none"' if m.group(1).lower() == "#000000" else f'fill="{d2["hair"]["color"]}"', svg)   # every non-ink fill (skin, white) -> hair
    hair = svg.replace(f'fill="{skin_hex}"', 'fill="none"').replace('fill="#000000"', f'fill="{d2["hair"]["color"]}"')
    ear = ""
    if "earrings" in k.acc:
        ear = f'<g><circle cx="452" cy="600" r="11" fill="{k.accent}" stroke="{INK}" stroke-width="4"/><circle cx="452" cy="623" r="7" fill="{k.accent}" stroke="{INK}" stroke-width="3"/></g>'
    cap = ""
    if "cap" in k.acc:
        cc = k.top_c if k.top_c not in ("#eeeeea", "#eadfc6") else k.accent
        cap = (f'<g><path d="M{432},{372} C{436},{268} {520},{226} {612},{228} C{700},{230} {770},{280} {782},{372} L{432},{372} Z" fill="{cc}" stroke="{INK}" stroke-width="10" stroke-linejoin="round"/>'
               f'<path d="M{772},{368} C{820},{362} {880},{372} {900},{392} C{860},{398} {800},{392} {772},{384} Z" fill="{shade(cc, 0.82)}" stroke="{INK}" stroke-width="9" stroke-linejoin="round"/>'
               f'<path d="M{612},{232} L{612},{300}" stroke="{INK}" stroke-width="5" opacity="0.5"/></g>')
    inner = lambda s: s[:s.rindex("</svg>")] + ear + cap + "</svg>" if (ear or cap) else s
    return skull, inner(hair)


def nose(k):
    src = A.__file__.rsplit("/asset_pipeline", 1)[0] + "/assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/face/Serious.svg"
    s = A.nose_svg(src).replace('fill="#000000"', f'fill="{k.skin}"')
    sc = k.d2["nose"]
    if abs(sc - 1.0) < 1e-3:
        return s
    return s.replace('<g transform="', f'<g transform="translate(236 211) scale({sc:.3f}) translate(-236 -211) ', 1)


# ------------------------------------------------------------------------------------------------------------------ bake
ART_VERSION = "art-v3.4"                                                             # bump whenever any part art changes (bake cache key)


def _key(d2, view, hand_set):
    return hashlib.sha1(json.dumps([d2, view, hand_set, ART_VERSION], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def bake2(d2, view="profile", hand_set="full"):
    """-> manifest dict (version 2). PNGs cached under assets/character/skeleton/generated_v2/<key>/. Same DNA + view -> identical files."""
    key = _key(d2, view, hand_set)
    d = os.path.join(GEN, key)
    man_path = os.path.join(d, "parts.json")
    if os.path.exists(man_path):
        return json.load(open(man_path))
    os.makedirs(d, exist_ok=True)
    k = Kit(d2, view)
    P = k.P
    parts = {}

    def save(name, svg_pivot, zoom=TEX, alias=None):
        svg, pivot = svg_pivot
        arr, (ox, oy) = rasterize(svg, zoom=zoom)
        Image.fromarray(arr).save(os.path.join(d, f"{name}.png"))
        parts[name] = dict(png=os.path.relpath(os.path.join(d, f"{name}.png"), ROOT), pivot=[pivot[0] * zoom - ox, pivot[1] * zoom - oy], size=[arr.shape[1], arr.shape[0]], res=TEX)

    for side in ("L", "R"):
        save(f"upperarm_{side}", upperarm(k, side))
        save(f"forearm_{side}", forearm(k, side))
        save(f"thigh_{side}", thigh(k, side))
        save(f"shin_{side}", shin(k, side))
        save(f"foot_{side}", foot(k, side))
    save("pelvis", pelvis(k))
    save("torso", torso(k))
    save("neck", neck(k))
    if k.bottom == "skirt":
        save("skirt", skirt(k))
    if "backpack" in k.acc:
        save("backpack", backpack(k))
    if "bag" in k.acc:
        save("bag", bag(k))
    poses = HAND_POSES if hand_set == "full" else BASIC_POSES
    anchors = {}
    for pose in poses:
        for side in ("L", "R"):
            mirror = (side == "L" and view != "profile")                              # profile: both thumbs face forward; 3/4 and front: true left/right hands
            if pose in H3.HARVEST:
                im, pv, an = H3.harvested_png(k, pose, mirror, TEX)
                name = f"hand_{side}_{pose}"
                im.save(os.path.join(d, name + ".png"))
                parts[name] = dict(png=os.path.relpath(os.path.join(d, name + ".png"), ROOT), pivot=[float(pv[0]), float(pv[1])], size=[im.width, im.height], res=TEX)
            else:
                svg, pv, an = H3.hand_svg(k, pose, mirror)
                save(f"hand_{side}_{pose}", (svg, pv))
            anchors[pose] = an
    save("phone", PA.phone(P, None, dict(bottom=k.bot_c)))
    save("card", prop_card(k))
    save("money", prop_money(k))
    skull, hair = head_layers(k)
    hz = TEX * P["hs"]
    save("skull", (skull, R.NECK_PIVOT_CANVAS), zoom=hz)
    save("hair", (hair, R.NECK_PIVOT_CANVAS), zoom=hz)
    reg = A.FACE_REGION
    save("nose", (nose(k), (R.NECK_PIVOT_CANVAS[0] - reg[0], R.NECK_PIVOT_CANVAS[1] - reg[1])), zoom=hz)
    et, bt, mt = dna2.EYE_TYPES[d2["eyes"]], dna2.BROW_TYPES[d2["eyebrows"]], dna2.MOUTH_TYPES[d2["mouth"]]
    man = dict(version=2, id=key, dir=os.path.relpath(d, ROOT), view=view, P=P, parts=parts, dna_id=d2["id"], skin=d2["skin"]["hex"], hand_poses=poses,
               hand_anchors={p_: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in a_.items()} for p_, a_ in anchors.items()},
               face_style=dict(ex=et[0], ey=et[1], tilt=et[2], lash=et[3], brow=bt[0], arch=bt[1], mouth=mt[0], lip=mt[1]),
               wardrobe=dict(d2["wardrobe"]), fb=dict(height_scale=d2["body"]["height"]))
    json.dump(man, open(man_path, "w"), indent=1)
    return man


REQUIRED_PARTS = ["upperarm_L", "forearm_L", "thigh_L", "shin_L", "foot_L", "upperarm_R", "forearm_R", "thigh_R", "shin_R", "foot_R", "pelvis", "torso", "neck", "skull", "hair", "nose", "phone", "card", "money"]


def verify(man):
    """Missing-asset detection: [(part, reason)] for every required part / hand pose whose PNG is missing, unreadable or fully transparent."""
    bad = []
    names = REQUIRED_PARTS + [f"hand_{s}_{p}" for s in ("L", "R") for p in man.get("hand_poses", [])]
    for n in names:
        p = man["parts"].get(n)
        if p is None:
            bad.append((n, "not in manifest"))
            continue
        f = os.path.join(ROOT, p["png"])
        if not os.path.exists(f):
            bad.append((n, "file missing"))
            continue
        try:
            a = Image.open(f).convert("RGBA")
            if a.getchannel("A").getextrema()[1] == 0:
                bad.append((n, "fully transparent"))
        except Exception as e:
            bad.append((n, f"unreadable: {e}"))
    return bad
