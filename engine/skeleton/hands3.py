"""Hand library v3: 20 poses per hand, both hands, in the Open Peeps ink language.

* `hold_phone` is a REAL Open Peeps drawing (CC0) harvested from the 'Device' body atom (tools/assets/harvest_openpeeps.py), recoloured to the DNA skin tone.
* every other pose is a parametric hand: tapered three-phalanx fingers with staggered lengths, a palm with a heel and a wrist taper, a two-segment thumb with a web, knuckle creases and
  finger-separation lines. Ink weight is normalised to the same value as the heads.
Local frame of every drawing: origin = wrist centre, +y = along the hand toward the fingertips (a hanging hand points down), +x = the front/palm side of the character.
Each pose also exposes semantic anchors (grip / tip / palm) in that frame so props can be gripped without floating (see props3.py).
"""
import math
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
HARV = os.path.join(ROOT, "assets/character/harvest")
HAND_INK_PX = 4.0                                                             # ink weight of small parts (large silhouettes use PA.OW = 6.0); measured by normalize.stroke_width_px

POSES = ["open", "closed", "point", "grab", "hold_phone", "hold_card", "hold_money", "gesture", "palm_up", "fist",                     # v2 ids stay stable
         "relaxed", "pinch", "hold_pen", "hold_cup", "type", "touch_screen", "push", "pull", "wave", "palm_down"]
BASIC = ["open", "closed", "gesture", "relaxed", "fist", "point"]
PROP_HELD = {"hold_phone": "phone", "hold_card": "card", "hold_money": "money"}

# per pose: finger flexion (3 joints, deg) for index/middle/ring/pinky, spread (deg between fingers), thumb (abduction, seg1 flex, seg2 flex), palm_first (draw palm over the fingers), grip anchor as (u, v) fractions
# of (hand length along y, palm width along x) measured from the wrist, tip = which fingertip is the semantic 'tip'
T = dict
TABLE = {
    "open": T(f=[(4, 4, 2), (2, 3, 2), (4, 4, 2), (8, 6, 4)], spread=9, th=(38, 8, 6), grip=(0.42, 0.10)),
    "relaxed": T(f=[(14, 22, 14), (20, 28, 18), (26, 34, 22), (32, 38, 24)], spread=4, th=(24, 14, 10), grip=(0.42, 0.10)),
    "closed": T(f=[(44, 62, 34), (48, 66, 36), (52, 70, 38), (56, 72, 40)], spread=2, th=(26, 30, 24), palm_first=False, grip=(0.40, 0.14)),
    "fist": T(f=[(88, 96, 56), (90, 98, 58), (92, 100, 58), (94, 100, 56)], spread=1, th=(10, 58, 44), palm_first=False, grip=(0.34, 0.10)),
    "point": T(f=[(2, 2, 0), (90, 100, 60), (92, 102, 60), (94, 100, 56)], spread=2, th=(16, 46, 30), tip=0, grip=(0.34, 0.10)),
    "grab": T(f=[(58, 70, 42), (62, 74, 44), (66, 76, 46), (70, 76, 46)], spread=5, th=(40, 28, 20), palm_first=False, grip=(0.36, 0.20)),
    "hold_phone": T(f=[(52, 62, 38), (56, 66, 40), (60, 70, 42), (64, 70, 42)], spread=3, th=(32, 20, 26), palm_first=False, grip=(0.38, 0.22)),
    "hold_card": T(f=[(20, 22, 12), (26, 26, 14), (56, 66, 40), (62, 68, 40)], spread=3, th=(42, 22, 18), grip=(0.62, 0.14)),
    "hold_money": T(f=[(26, 28, 14), (30, 30, 16), (34, 34, 18), (40, 38, 20)], spread=3, th=(44, 24, 20), grip=(0.60, 0.14)),
    "gesture": T(f=[(10, 14, 8), (14, 22, 12), (26, 34, 20), (34, 40, 24)], spread=8, th=(34, 10, 8), grip=(0.42, 0.10)),
    "palm_up": T(f=[(10, 8, 6), (8, 6, 4), (10, 8, 6), (14, 10, 6)], spread=11, th=(50, 6, 4), grip=(0.36, 0.06)),
    "palm_down": T(f=[(12, 10, 6), (10, 8, 4), (12, 10, 6), (16, 12, 6)], spread=6, th=(20, 10, 6), grip=(0.36, 0.06)),
    "pinch": T(f=[(36, 46, 26), (30, 42, 24), (46, 58, 34), (52, 62, 36)], spread=3, th=(44, 32, 26), tip=0, grip=(0.66, 0.12)),
    "hold_pen": T(f=[(30, 40, 22), (36, 46, 26), (70, 82, 46), (78, 86, 48)], spread=2, th=(44, 26, 22), tip=0, grip=(0.60, 0.12)),
    "hold_cup": T(f=[(34, 44, 26), (38, 48, 28), (42, 52, 30), (46, 54, 30)], spread=4, th=(48, 24, 20), grip=(0.44, 0.18)),
    "type": T(f=[(22, 32, 20), (24, 36, 22), (26, 38, 24), (30, 40, 26)], spread=7, th=(30, 14, 10), tip=0, grip=(0.50, 0.10)),
    "touch_screen": T(f=[(4, 8, 4), (84, 96, 56), (88, 98, 58), (92, 98, 56)], spread=2, th=(14, 44, 28), tip=0, grip=(0.66, 0.08)),
    "push": T(f=[(0, 0, 0), (0, 0, 0), (0, 2, 0), (2, 2, 0)], spread=2, th=(12, 6, 4), grip=(0.50, 0.08)),
    "pull": T(f=[(52, 60, 30), (56, 62, 32), (60, 64, 34), (62, 66, 34)], spread=2, th=(36, 30, 20), palm_first=False, grip=(0.40, 0.14)),
    "wave": T(f=[(2, 2, 0), (0, 0, 0), (2, 2, 0), (6, 4, 2)], spread=15, th=(50, 6, 4), grip=(0.50, 0.08)),
}


def _shade(hex_, f):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in (r, g, b))


def _finger_pts(base, ang0, flex, lens):
    """polyline of a finger: base + 3 phalanges. angle measured from +y (down), positive toward +x (the palm/front side)."""
    pts = [base]
    a = math.radians(ang0)
    x, y = base
    for fl, L in zip(flex, lens):
        a += math.radians(fl)
        x += math.sin(a) * L
        y += math.cos(a) * L
        pts.append((x, y))
    return pts


def _tapered(pts, w0, w1):
    """closed outline (list of points) around a polyline with linearly tapering width, round-ish tip."""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2.0
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    # rounded tip: a point beyond the last joint
    tx, ty = pts[-1]
    dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
    L = math.hypot(dx, dy) or 1.0
    cap = (tx + dx / L * w1 * 0.55, ty + dy / L * w1 * 0.55)
    return left + [cap] + right[::-1]


def _path(pts, close=True):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d + (" Z" if close else "")


def _smooth(pts):
    """closed Catmull-Rom -> cubic Bezier path through pts (soft organic outline)."""
    n = len(pts)
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + " Z"


def geometry(P, pose):
    """-> dict(fingers=[polyline pts], thumb=pts, palm=[pts], anchors={...}) in the local hand frame (wrist at origin, +y to the fingertips)."""
    tab = TABLE[pose]
    hl = P["forearm"] * 0.62                                                 # real hands are ~0.6-0.7 of the forearm (the HAND bone is only the wrist link)
    pw = P["limb"] * 0.86                                                    # palm width
    pl = hl * 0.46                                                           # palm length
    xs = [pw * 0.34, pw * 0.11, -pw * 0.12, -pw * 0.34]                      # knuckle positions: index (front) .. pinky
    ln = [0.88, 1.0, 0.92, 0.72]
    fingers = []
    for i, (fl, x) in enumerate(zip(tab["f"], xs)):
        L = hl * 0.60 * ln[i]
        lens = [L * 0.44, L * 0.30, L * 0.26]
        sp = (1.5 - i) * tab["spread"] * 0.45
        fingers.append(_finger_pts((x, pl - 1.0), sp * 0.6, list(fl), lens))
    ab, f1, f2 = tab["th"]
    tb = (pw * 0.46, pl * 0.30)
    tl = hl * 0.27
    thumb = _finger_pts(tb, 20 + ab * 0.55, [0.0, f1, f2], [tl * 0.55, tl * 0.5, tl * 0.4])
    # palm: soft blob with heel; slightly narrower at the wrist
    palm = [(-pw * 0.30, -4), (pw * 0.30, -4), (pw * 0.52, pl * 0.20), (pw * 0.56, pl * 0.62), (pw * 0.46, pl * 1.02), (0, pl * 1.08), (-pw * 0.46, pl * 1.02), (-pw * 0.56, pl * 0.60), (-pw * 0.50, pl * 0.20)]
    gu, gv = tab["grip"]
    tip_i = tab.get("tip", 0)
    anchors = dict(wrist=(0.0, 0.0), palm=(pw * 0.05, pl * 0.55), grip=(gv * pw * 1.6 * 0.5, gu * hl), tip=fingers[tip_i][-1], thumb_tip=thumb[-1], length=hl, width=pw)
    return dict(fingers=fingers, thumb=thumb, palm=palm, anchors=anchors, tab=tab)


def hand_svg(k, pose, mirror=False):
    """procedural pose -> (svg_text, pivot_xy, anchors). pivot = wrist centre; drawn with +y toward the fingertips."""
    from engine.skeleton import parts_art2 as PA
    P = k.P
    g = geometry(P, pose)
    tab = g["tab"]
    skin, sh = k.skin, _shade(k.skin, 0.80)
    ink = PA.INK
    ow = PA.OW * 0.66                                                        # ink weight: matched to the head atoms (3.7 px @ rig scale)
    fw0 = max(8.0, P["limb"] * 0.19)
    body = ""

    def limb(pts, w0, w1):
        out = _tapered(pts, w0, w1)
        return (f'<path d="{_smooth(out)}" fill="{ink}" stroke="{ink}" stroke-width="{ow * 2:.1f}" stroke-linejoin="round"/>'
                f'<path d="{_smooth(out)}" fill="{skin}" stroke="none"/>')

    order = [3, 2, 1, 0]                                                     # pinky first (furthest), index last (front)
    palm_first = tab.get("palm_first", True)
    palm = (f'<path d="{_smooth(g["palm"])}" fill="{ink}" stroke="{ink}" stroke-width="{ow * 2:.1f}" stroke-linejoin="round"/>'
            f'<path d="{_smooth(g["palm"])}" fill="{skin}"/>'
            f'<path d="M{-P["limb"] * 0.34:.1f},{g["anchors"]["length"] * 0.28:.1f} Q0,{g["anchors"]["length"] * 0.36:.1f} {P["limb"] * 0.36:.1f},{g["anchors"]["length"] * 0.27:.1f}" fill="none" stroke="{sh}" stroke-width="2.4" stroke-linecap="round"/>')
    fingers = ""
    for i in order:
        w0 = fw0 * (1.0 if i != 3 else 0.86)
        fingers += limb(g["fingers"][i], w0, w0 * 0.68)
        j = g["fingers"][i]
        fingers += f'<path d="M{j[1][0] - w0 * 0.22:.1f},{j[1][1]:.1f} L{j[1][0] + w0 * 0.22:.1f},{j[1][1]:.1f}" stroke="{sh}" stroke-width="1.8" stroke-linecap="round"/>'
    thumb = limb(g["thumb"], fw0 * 1.12, fw0 * 0.8)
    body = (palm + fingers + thumb) if palm_first else (fingers + palm + thumb)
    # wrist stub so the hand never shows a hard edge against the cuff
    body = f'<rect x="{-P["limb"] * 0.30:.1f}" y="-12" width="{P["limb"] * 0.60:.1f}" height="22" fill="{skin}"/>' + body
    xs = [x for f in g["fingers"] for x, _ in f] + [x for x, _ in g["thumb"]] + [x for x, _ in g["palm"]]
    ys = [y for f in g["fingers"] for _, y in f] + [y for _, y in g["thumb"]] + [y for _, y in g["palm"]]
    pad = 20.0
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    w, h = x1 - x0, y1 - y0
    if mirror:                                                               # mirrored about the wrist axis (3/4 and front views)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" viewBox="{-x1:.1f} {y0:.1f} {w:.1f} {h:.1f}"><g transform="scale(-1,1)">{body}</g></svg>')
        return svg, (x1, -y0), g["anchors"]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}">{body}</svg>'
    return svg, (-x0, -y0), g["anchors"]


# ---------------------------------------------------------------------------------------------- harvested real drawing
HARVEST = {"hold_phone": dict(name="openpeeps_device_hand", zoom=2.0, wrist=(10.0, 340.0), tip=(536.0, 160.0), grip=(0.30, 0.10), crop_origin=(430.0, 270.0),
                             phone_centre_atom=(680.0, 292.0), phone_up_atom=(0.386, -0.922))}


def harvested_png(k, pose, mirror, tex):
    """-> (PIL RGBA image, pivot_px, anchors) rotated so the wrist->fingertip axis points +y, scaled so the hand has the DNA hand length, recoloured with the DNA skin tone."""
    import cv2
    meta = HARVEST[pose]
    fill = np.load(os.path.join(HARV, meta["name"] + ".fill.npy"))
    ink = np.load(os.path.join(HARV, meta["name"] + ".ink.npy"))
    h = k.skin.lstrip("#")
    skin = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    shade = tuple(int(c * 0.86) for c in skin)
    rgba = np.zeros(fill.shape + (4,), np.uint8)
    rgba[..., :3] = skin
    rgba[..., 3] = fill
    yy, xx = np.mgrid[0:fill.shape[0], 0:fill.shape[1]]
    wx, wy = meta["wrist"]
    tx, ty = meta["tip"]
    axis = np.array([tx - wx, ty - wy], float)
    length = float(np.hypot(*axis))
    under = (fill > 0) & (((xx - wx) * axis[0] + (yy - wy) * axis[1]) / (length * length) < 0.18)      # gentle shade toward the wrist end
    rgba[under, :3] = shade
    inkm = ink > 0
    rgba[inkm, :3] = (12, 8, 8)
    rgba[inkm, 3] = 255
    P = k.P
    hl = P["forearm"] * 0.62
    s = hl * tex / length
    theta = math.atan2(axis[1], axis[0])
    phi = math.pi / 2 - theta
    c_, s_ = math.cos(phi), math.sin(phi)
    Hh, Ww = fill.shape
    corners = np.array([[0, 0], [Ww, 0], [Ww, Hh], [0, Hh]], float) - np.array([wx, wy])
    rot = np.array([[c_, -s_], [s_, c_]])
    rc = (corners @ rot.T) * s
    mnx, mny = rc.min(axis=0)
    mxx, mxy = rc.max(axis=0)
    outw, outh = int(math.ceil(mxx - mnx)) + 2, int(math.ceil(mxy - mny)) + 2
    A = np.zeros((2, 3), float)
    A[:, :2] = rot * s
    A[:, 2] = -np.array([wx, wy]) @ (rot * s).T - np.array([mnx, mny]) + 1
    out = cv2.warpAffine(rgba, A, (outw, outh), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    from engine.skeleton import normalize as N                                                    # style normalisers: one ink language for every part
    out = N.stroke_cap_normalizer(N.stroke_join_normalizer(N.line_weight_normalizer(out, HAND_INK_PX, tex)))
    pivot = (-mnx + 1, -mny + 1)
    pivot_raw = pivot
    if mirror:
        out = out[:, ::-1].copy()
        pivot = (outw - pivot[0], pivot[1])
    grip = meta["grip"]
    anchors = dict(wrist=(0.0, 0.0), palm=(0.0, hl * 0.4), grip=(grip[1] * hl, grip[0] * hl), tip=(0.0, hl), thumb_tip=(0.0, hl * 0.5), length=hl, width=P["limb"])
    if "phone_centre_atom" in meta:                                            # where the Open Peeps phone sits relative to this hand, in the hand's local frame (rig px) + its tilt
        ox, oy = meta["crop_origin"]
        pc = np.array([(meta["phone_centre_atom"][0] - ox) * meta["zoom"], (meta["phone_centre_atom"][1] - oy) * meta["zoom"], 1.0])
        q = A @ pc                                                             # output px
        lx, ly = (q[0] - pivot_raw[0]) / tex, (q[1] - pivot_raw[1]) / tex
        uv = (rot @ np.array(meta["phone_up_atom"], float))
        th = math.degrees(math.atan2(uv[0], -uv[1]))
        if mirror:
            lx, th = -lx, -th
        anchors["prop_phone"] = [float(lx), float(ly), float(th)]
    return Image.fromarray(out, "RGBA"), pivot, anchors


def phone_anchor(P, mirror=False):
    """(lx, ly, th) of the held phone's centre in the hold_phone hand's local frame (rig px; x forward, y along the hand toward the fingertips) and the phone's tilt th (deg, clockwise
    from the hand's 'up'). Pure geometry from the harvest metadata - no rasterisation."""
    meta = HARVEST["hold_phone"]
    wx, wy = meta["wrist"]
    tx, ty = meta["tip"]
    axis = np.array([tx - wx, ty - wy], float)
    length = float(np.hypot(*axis))
    phi = math.pi / 2 - math.atan2(axis[1], axis[0])
    rot = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
    hl = P["forearm"] * 0.62
    ox, oy = meta["crop_origin"]
    v = np.array([(meta["phone_centre_atom"][0] - ox) * meta["zoom"] - wx, (meta["phone_centre_atom"][1] - oy) * meta["zoom"] - wy])
    lx, ly = (rot @ v) * hl / length
    uv = rot @ np.array(meta["phone_up_atom"], float)
    th = math.degrees(math.atan2(uv[0], -uv[1]))
    if mirror:
        lx, th = -lx, -th
    return float(lx), float(ly), float(th)
