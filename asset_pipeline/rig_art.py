"""Vector art for the LAYERED performer (torso, sleeves, hands, phone, face features).

Everything is drawn in bust-CANVAS coordinates (the frame the Open Peeps heads/bodies share; see
cast_builder.py) so the head, torso and every limb line up exactly. Style = Open Peeps: pure black
ink outline (~9px), flat white fill, hand-drawn wobble, speckled sweater. Limbs are drawn along their
REST pose; engine/shorts/rig2.py moves them as rigid parts with real joints.

Outlined-stroke trick: a thick black stroke under a thinner white stroke gives an inked capsule with
round joins - used for sleeves and fingers, so overlaps read as ink lines exactly like the source art.
"""
import math
import random
import re

OUT_W = 9.0
FACE_ORIGIN = (531.0, 366.0)          # canvas position of the Open Peeps face-group origin
CANVAS = (1500, 1650)
INK = "#000000"


def _svg(body, defs=""):
    w, h = CANVAS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<defs>{defs}</defs>{body}</svg>')


def _jit(rng, pts, amp):
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)) for x, y in pts]


def _d(pts, closed=False):
    """Catmull-Rom -> cubic Bezier path through pts."""
    n = len(pts)
    P = lambda i: pts[(i % n)] if closed else pts[max(0, min(n - 1, i))]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = P(i - 1), P(i), P(i + 1), P(i + 2)
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + (" Z" if closed else "")


def capsule_line(p0, p1, width, fill="#fff", ow=OUT_W):
    """Inked capsule from p0 to p1: black stroke under white stroke."""
    return (f'<path d="M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f}" stroke="{INK}" stroke-width="{width + 2 * ow}" '
            f'stroke-linecap="round" fill="none"/>'
            f'<path d="M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f}" stroke="{fill}" stroke-width="{width}" '
            f'stroke-linecap="round" fill="none"/>')


def seeds(rng, x0, x1, y0, y1, n, rot0=0.0):
    """Speckled-sweater seeds: short slanted black ellipses (the Device/Sweater bodies' pattern)."""
    out = []
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        a = rot0 + rng.uniform(-70, 70)
        out.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rng.uniform(5.5, 7.5):.1f}" ry="{rng.uniform(14, 19):.1f}" '
                   f'transform="rotate({a:.0f} {x:.1f} {y:.1f})" fill="{INK}"/>')
    return "".join(out)


# ------------------------------------------------------------------ torso
def torso(seed=3):
    """Chest + shoulders + crew collar (no arms; sleeves are separate parts). Canvas coords."""
    r = random.Random(seed)
    outline = [(470, 712), (405, 738), (330, 776), (268, 830), (232, 900), (236, 990), (262, 1120), (270, 1400),
               (620, 1420), (880, 1400), (884, 1120), (900, 990), (896, 900), (858, 830), (800, 782), (742, 742), (708, 720)]
    body = f'<path d="{_d(outline, True)}" fill="#fff" stroke="{INK}" stroke-width="{OUT_W}" stroke-linejoin="round"/>'
    body += seeds(r, 320, 830, 930, 1380, 22)
    body += (f'<path d="{_d([(520, 640), (508, 690), (480, 726)])}" fill="none" stroke="{INK}" stroke-width="{OUT_W}" stroke-linecap="round"/>'
             f'<path d="{_d([(690, 662), (716, 700), (744, 728)])}" fill="none" stroke="{INK}" stroke-width="{OUT_W}" stroke-linecap="round"/>')
    # ribbed crew collar: two arcs + ribs (drawn OVER the neck column of the head, which ends ~y=720)
    collar = [(462, 716), (520, 780), (610, 806), (700, 782), (752, 722)]
    body += f'<path d="{_d(collar)}" fill="none" stroke="{INK}" stroke-width="{OUT_W + 6}" stroke-linecap="round"/>'
    inner = [(478, 728), (528, 786), (610, 810), (694, 790), (742, 734)]
    body += f'<path d="{_d(inner)}" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round" opacity="0.8"/>'
    for i in range(1, 9):
        t = i / 9
        cx = collar[0][0] + (collar[-1][0] - collar[0][0]) * t
        cy = 716 + 96 * math.sin(math.pi * t) * 0.95
        body += f'<line x1="{cx:.1f}" y1="{cy - 6:.1f}" x2="{cx:.1f}" y2="{cy + 20:.1f}" stroke="{INK}" stroke-width="4" opacity="0.7"/>'
    return _svg(body)


# ------------------------------------------------------------------ sleeves
def sleeve(pivot, length, width, angle_deg, seed, cuff=False, rest_end_width=None):
    """A sleeve tube drawn from `pivot` along `angle_deg` for `length`. Pivot = the joint it rotates about."""
    r = random.Random(seed)
    g = (f'<g transform="rotate({angle_deg} {pivot[0]} {pivot[1]})">'
         + capsule_line(pivot, (pivot[0] + length, pivot[1]), width)
         + seeds(r, pivot[0] + 26, pivot[0] + length - (60 if cuff else 30), pivot[1] - width / 2 + 20, pivot[1] + width / 2 - 20, max(3, int(length / 78))))
    if cuff:                                            # ribbed cuff band at the wrist end
        cx = pivot[0] + length - 18
        for k in range(4):
            g += (f'<line x1="{cx - 42 + k * 12:.1f}" y1="{pivot[1] - width / 2 + 2:.1f}" x2="{cx - 42 + k * 12:.1f}" '
                  f'y2="{pivot[1] + width / 2 - 2:.1f}" stroke="{INK}" stroke-width="4.5"/>')
        g += (f'<line x1="{cx + 10:.1f}" y1="{pivot[1] - width / 2 - 1:.1f}" x2="{cx + 10:.1f}" y2="{pivot[1] + width / 2 + 1:.1f}" '
              f'stroke="{INK}" stroke-width="{OUT_W}"/>')
    g += "</g>"
    return _svg(g)


# ------------------------------------------------------------------ hand
def hand(wrist, angle_deg, curl=0.0, spread=0.35, thumb=0.5, grip=False):
    """Inked hand pointing along angle_deg from the wrist. curl 0 (open) .. 1 (fist); thumb 0 (tucked) .. 1 (out)."""
    fingers = []
    base_x, palm_w, palm_h = 8.0, 74.0, 78.0
    for i, (dy, ln) in enumerate(((-27, 52), (-9, 60), (9, 58), (27, 46))):
        seg1 = 0.55 * ln
        seg2 = 0.45 * ln
        bend = math.radians(115 * curl)
        spr = math.radians((i - 1.5) * 9 * spread)
        p0 = (base_x + palm_w - 6, dy)
        p1 = (p0[0] + seg1 * math.cos(spr) * (1 - 0.35 * curl), p0[1] + seg1 * math.sin(spr) + 14 * curl * (1 if dy > 0 else 0.6))
        a2 = spr + bend
        p2 = (p1[0] + seg2 * math.cos(a2), p1[1] + seg2 * math.sin(a2))
        fingers.append(f'<path d="M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f}" stroke="{INK}" '
                       f'stroke-width="{21 + 2 * 7}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>')
    fill_fingers = "".join(f.replace(f'stroke="{INK}"', 'stroke="#fff"').replace(f'stroke-width="{21 + 14}"', 'stroke-width="21"') for f in fingers)
    palm = (f'<rect x="{base_x}" y="{-palm_h / 2}" width="{palm_w}" height="{palm_h}" rx="24" fill="#fff" stroke="{INK}" stroke-width="{OUT_W}"/>')
    ta = math.radians(-58 + 30 * (1 - thumb))
    t0 = (base_x + 24, -palm_h / 2 + 8)
    t1 = (t0[0] + 38 * math.cos(ta) * (1 - 0.3 * curl), t0[1] + 38 * math.sin(ta))
    t2 = (t1[0] + 30 * math.cos(ta + 0.45 * curl), t1[1] + 30 * math.sin(ta + 0.45 * curl))
    th = (f'<path d="M{t0[0]:.1f},{t0[1]:.1f} L{t1[0]:.1f},{t1[1]:.1f} L{t2[0]:.1f},{t2[1]:.1f}" stroke="{INK}" stroke-width="{22 + 14}" '
          f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
          f'<path d="M{t0[0]:.1f},{t0[1]:.1f} L{t1[0]:.1f},{t1[1]:.1f} L{t2[0]:.1f},{t2[1]:.1f}" stroke="#fff" stroke-width="22" '
          f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>')
    inner = "".join(fingers) + fill_fingers + palm + th
    return _svg(f'<g transform="translate({wrist[0]} {wrist[1]}) rotate({angle_deg}) scale(1.18)">{inner}</g>')


# ------------------------------------------------------------------ phone
PHONE_W, PHONE_H = 112.0, 226.0


def phone_body(center, tilt_deg=0.0):
    """Inked phone slab (screen area left transparent-dark; the dynamic emissive screen is a separate layer)."""
    cx, cy = center
    w, h = PHONE_W, PHONE_H
    g = (f'<g transform="rotate({tilt_deg} {cx} {cy})">'
         f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="20" fill="#20222d" stroke="{INK}" stroke-width="{OUT_W}"/>'
         f'<rect x="{cx - w / 2 + 8}" y="{cy - h / 2 + 8}" width="{w - 16}" height="{h - 16}" rx="13" fill="#05060b"/>'
         f'<rect x="{cx - 14}" y="{cy - h / 2 + 12}" width="28" height="7" rx="3.5" fill="#000"/></g>')
    return _svg(g)


def phone_screen_rect(center):
    cx, cy = center
    return (cx - PHONE_W / 2 + 8, cy - PHONE_H / 2 + 8, PHONE_W - 16, PHONE_H - 16)


# ------------------------------------------------------------------ face features (face-local coords)
EYE_L, EYE_R = (92.0, 112.0), (210.0, 110.0)
BROW_L, BROW_R = (86.0, 72.0), (210.0, 67.0)
MOUTH_C = (165.0, 228.0)


FACE_REGION = (470, 330, 420, 340)          # canvas rect the face features live in (small viewBox = fast per-frame raster)


def _face_wrap(inner):
    ox, oy = FACE_ORIGIN
    rx, ry, rw, rh = FACE_REGION
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{rw}" height="{rh}" viewBox="{rx} {ry} {rw} {rh}">'
            f'<g transform="translate({ox} {oy})">{inner}</g></svg>')


def eyes_svg(open_=1.0, gaze=(0.0, 0.0), conv=0.0, lid=0.0):
    """Two ink eyes. open_ 0..1 (blink), gaze in [-1,1]^2 (shifts the eyes inside the socket), conv = convergence
    (near focus), lid = heavy-lid amount (tired)."""
    out = ""
    for k, (cx, cy) in enumerate((EYE_L, EYE_R)):
        gx = gaze[0] * 8.5 + (conv * 3.2 if k == 0 else -conv * 3.2)
        gy = gaze[1] * 6.0 + conv * 3.0
        ry = max(2.2, 19.0 * open_ * (1 - 0.42 * lid))
        rx = 10.8 + (1.5 if open_ < 0.5 else 0)
        if open_ > 1.08:                                            # wide eyes: inked eyeball + pupil (as in the Open Peeps 'Hectic' face)
            k = min(1.0, (open_ - 1.08) / 0.2)
            er = 15 + 13 * k
            out += (f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{er:.1f}" ry="{er * 1.08:.1f}" fill="#fff" stroke="{INK}" stroke-width="6.5"/>'
                    f'<ellipse cx="{cx + gx * 0.9:.1f}" cy="{cy + gy * 0.8:.1f}" rx="{6.5 + 2 * k:.1f}" ry="{7.5 + 2 * k:.1f}" fill="{INK}"/>')
            continue
        out += f'<ellipse cx="{cx + gx:.1f}" cy="{cy + gy + (19 - ry) * 0.35:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{INK}"/>'
        if lid > 0.05 or open_ < 0.6:                        # upper-lid line above the eye
            ly = cy + gy - ry - 3 + (19 - ry) * 0.35
            out += (f'<path d="M{cx - 17 + gx:.1f},{ly + 3:.1f} Q{cx + gx:.1f},{ly - 5 - 3 * lid:.1f} {cx + 17 + gx:.1f},{ly + 3:.1f}" '
                    f'fill="none" stroke="{INK}" stroke-width="5.5" stroke-linecap="round"/>')
    return _face_wrap(out)


def brows_svg(raise_=0.0, tilt=0.0, arch=0.0, asym=0.0):
    """Two ink brows. raise_ -1..1 (px*14), tilt -1..1 (+ = inner ends up = worry), arch -1..1, asym = left-right raise difference."""
    out = ""
    for k, (cx, cy) in enumerate((BROW_L, BROW_R)):
        side = -1 if k == 0 else 1
        y = cy - 19 * raise_ - (asym * 7 * side)
        ang = math.radians(-24 * tilt * side * -1)           # inner end (towards nose) rises for +tilt
        half = 32
        dx, dy = half * math.cos(ang), half * math.sin(ang) * side * -1
        p0, p2 = (cx - dx, y - dy), (cx + dx, y + dy)
        ctrl = (cx, y - 9 * arch - 3)
        out += (f'<path d="M{p0[0]:.1f},{p0[1]:.1f} Q{ctrl[0]:.1f},{ctrl[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="none" stroke="{INK}" '
                f'stroke-width="13" stroke-linecap="round"/>')
    return _face_wrap(out)


def mouth_svg(smile=0.0, open_=0.0, width=1.0, shift=0.0):
    """Ink mouth. smile -1 (frown) .. 1 (smile); open_ 0..1; width scale; shift = corner asymmetry."""
    cx, cy = MOUTH_C
    w = 62 * width
    x0, x1 = cx - w / 2, cx + w / 2
    yc = cy - 11 * smile
    ctrl = (cx, cy + 15 * smile - 2)
    if open_ < 0.04:
        return _face_wrap(f'<path d="M{x0:.1f},{yc + shift:.1f} Q{ctrl[0]:.1f},{ctrl[1]:.1f} {x1:.1f},{yc - shift:.1f}" fill="none" '
                          f'stroke="{INK}" stroke-width="9" stroke-linecap="round"/>')
    drop = 10 + 46 * open_
    d = (f'M{x0:.1f},{yc:.1f} Q{ctrl[0]:.1f},{ctrl[1]:.1f} {x1:.1f},{yc:.1f} '
         f'Q{cx:.1f},{ctrl[1] + drop * 1.7:.1f} {x0:.1f},{yc:.1f} Z')
    return _face_wrap(f'<path d="{d}" fill="{INK}" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>')


def nose_svg(atom_path):
    """Nose = subpath (138,138)-(213,212) of any Open Peeps face atom (identical across atoms)."""
    s = open(atom_path, encoding="utf-8").read()
    d = re.search(r'<path d="([^"]*)"', s).group(1)
    for part in re.split(r"(?=M)", d):
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", part)]
        if nums and abs(min(nums[0::2]) - 138) < 2 and abs(min(nums[1::2]) - 138) < 3:
            return _face_wrap(f'<path d="{part}" fill="{INK}"/>')
    raise ValueError("nose subpath not found")
