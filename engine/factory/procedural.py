"""Procedural financial / psychological visualisation: DATA in -> animated frame out. No bitmaps, no per-story art.

Every renderer is  f(data, u, t, seed) -> HxWx3 float image, where u in [0,1] is progress through the shot and t the local time.
Style: warm paper, black ink, one accent colour - the same language as the cards - so procedural shots sit in the same film as the
illustrated ones. New graphics = add a function to RENDERERS and its name to domains/<id>/domain.json ("procedural").
Example data (money_flow): {"amount": 450000, "currency": "INR", "from": "victim", "to": ["account_1", "account_2", "account_3"]}
"""
import math
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw

from engine.shorts import cards
from engine.shorts.captions import _font
from engine.shorts.layers import W, H
from engine.shorts.performance import ease

TONES = cards.TONES
INK = (0.075, 0.07, 0.10)
PAPER = cards.PAPER


def inr(n, symbol=True):
    """Indian digit grouping: 450000 -> ₹4,50,000."""
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1])
        s = head + "," + tail
    return ("₹" if symbol else "") + ("-" if n < 0 else "") + s


def rgb(hexcol):
    return tuple(int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


def base(seed=1, tint=None):
    c = np.tile(PAPER, (H, W, 1)).copy()
    c *= (1.05 - 0.10 * np.linspace(0, 1, H, dtype=np.float32)[:, None, None])
    if tint is not None:
        c = c * 0.8 + np.array(tint, np.float32) * 0.2
    cards._blit(c, cards._frame(seed), W / 2, H / 2)
    return c


def _draw(c):
    """PIL ImageDraw over a float canvas (via 8-bit RGBA layer) -> returns (draw, commit)."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def commit(opacity=1.0):
        a = np.asarray(lay).astype(np.float32) / 255.0
        al = a[:, :, 3:4] * opacity
        c[:] = c * (1 - al) + a[:, :, :3] * al
    return d, commit


def _col(x, a=255):
    return tuple(int(v * 255) for v in x) + (a,)


def text(c, s, xy, size, color=INK, opacity=1.0, maxw=900, scale=1.0):
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    lines = cards._wrap(s, _font(size), maxw, d)
    layer = cards._text_layer(lines, size, _col(color), maxw=maxw)
    cards._blit(c, layer, xy[0], xy[1], scale, opacity)
    return layer.shape[0]


def wline(d, p0, p1, color, w=6, seed=0, wob=3.0):
    r = random.Random(seed)
    n = max(3, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 60))
    pts = [(p0[0] + (p1[0] - p0[0]) * i / n + r.uniform(-wob, wob) * (0 < i < n), p0[1] + (p1[1] - p0[1]) * i / n + r.uniform(-wob, wob) * (0 < i < n)) for i in range(n + 1)]
    d.line(pts, fill=_col(color), width=w, joint="curve")


def person_icon(d, cx, cy, s=1.0, color=INK, fill=(1, 1, 1)):
    d.ellipse((cx - 26 * s, cy - 78 * s, cx + 26 * s, cy - 26 * s), fill=_col(fill), outline=_col(color), width=int(6 * s))
    d.rounded_rectangle((cx - 46 * s, cy - 16 * s, cx + 46 * s, cy + 52 * s), 26 * s, fill=_col(fill), outline=_col(color), width=int(6 * s))


def bank_icon(d, cx, cy, s=1.0, color=INK):
    d.polygon([(cx - 60 * s, cy - 24 * s), (cx, cy - 66 * s), (cx + 60 * s, cy - 24 * s)], fill=_col((1, 1, 1)), outline=_col(color))
    for k in (-40, -14, 14, 40):
        d.rectangle((cx + k * s - 7 * s, cy - 18 * s, cx + k * s + 7 * s, cy + 34 * s), fill=_col((1, 1, 1)), outline=_col(color), width=int(4 * s))
    d.rectangle((cx - 64 * s, cy + 34 * s, cx + 64 * s, cy + 50 * s), fill=_col((1, 1, 1)), outline=_col(color), width=int(5 * s))


# ----------------------------------------------------------------------------------------- renderers
def counter(data, u, t, seed=1):
    """Big animated rupee counter. data: {label, from, to, tone, sub?, currency?}"""
    c = base(seed)
    tone = rgb(TONES[data.get("tone", "alert")])
    v0, v1 = float(data.get("from", 0)), float(data["to"])
    e = ease("smooth", (u - 0.12) / 0.7)
    val = v0 + (v1 - v0) * e
    text(c, data.get("label", ""), (W / 2, 640), 68, INK, min(1, u * 5))
    op, sc = cards._pop(t, 0.1, 0.4)
    big = inr(val) if data.get("currency", "INR") == "INR" else f"{val:,.0f}"
    text(c, big, (W / 2, 980), 170 if len(big) < 10 else 140, tone, op, maxw=940, scale=sc)
    d, commit = _draw(c)
    wline(d, (180, 1120), (900, 1112), tone, 12, seed)
    commit(min(1, max(0, (u - 0.2) * 3)))
    if data.get("sub"):
        text(c, data["sub"], (W / 2, 1290), 62, INK, min(1, max(0, (u - 0.5) * 3)))
    return c


def money_flow(data, u, t, seed=1):
    """Money leaving the victim through accounts. data: {amount, from, to:[...], labels?:{}}"""
    c = base(seed)
    d, commit = _draw(c)
    to = data.get("to", ["account_1"])
    n = len(to)
    src = (300, 880)                                                   # v3.5: the graph ends above the caption band (a bank label used to sit under the captions)
    ys = [540 + i * (680 / max(n - 1, 1)) if n > 1 else 880 for i in range(n)]
    dst = [(800, y) for y in ys]
    amt = float(data["amount"])
    prog = ease("smooth", (u - 0.1) / 0.7)
    for i, (x, y) in enumerate(dst):
        pts = [(src[0] + 70, src[1]), ((src[0] + x) / 2, src[1] + (y - src[1]) * 0.15), ((src[0] + x) / 2 + 60, y), (x - 90, y)]
        bez = [(cv2_bez(pts, k / 30)) for k in range(31)]
        d.line(bez, fill=_col(INK, 90), width=5)
        # coins as dots travelling along the curve
        for j in range(6):
            k = ((prog * 1.6 + j / 6.0 + i * 0.13) % 1.0)
            if prog > 0.02 and k < min(1.0, prog * 1.4):
                px, py = bez[int(k * 30)]
                d.ellipse((px - 15, py - 15, px + 15, py + 15), fill=_col(rgb("#f0c65a")), outline=_col(INK), width=4)
        person_icon(d, 0, 0, 0)  # no-op keeps API symmetric
    person_icon(d, src[0], src[1] - 20, 1.7, fill=(0.94, 0.94, 1.0))
    for i, (x, y) in enumerate(dst):
        bank_icon(d, x, y - 10, 0.85)
    commit()
    text(c, inr(amt * prog), (W / 2, 330), 130, rgb(TONES["alert"]), min(1, u * 6))
    text(c, data.get("from_label", "आपका खाता"), (src[0], src[1] + 150), 52, INK)
    for i, (x, y) in enumerate(dst):
        text(c, data.get("labels", {}).get(to[i], to[i].replace("_", " ").title()), (x, y + 84), 44, INK, maxw=300)
    return c


def cv2_bez(pts, k):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    m = 1 - k
    return (m ** 3 * x0 + 3 * m * m * k * x1 + 3 * m * k * k * x2 + k ** 3 * x3, m ** 3 * y0 + 3 * m * m * k * y1 + 3 * m * k * k * y2 + k ** 3 * y3)


def countdown(data, u, t, seed=1):
    """Urgency dial. data: {total_seconds, label, to_seconds?}"""
    c = base(seed)
    total = float(data.get("total_seconds", 1800))
    end = float(data.get("to_seconds", total * 0.25))
    left = total - (total - end) * ease("smooth", u)
    frac = left / total
    cx, cy, R = W / 2, 900, 340
    d, commit = _draw(c)
    hot = rgb(TONES["alert"])
    col = tuple(a * (1 - (1 - frac)) + b * (1 - frac) for a, b in zip(rgb(TONES["calm"]), hot))
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=_col((1, 1, 1)), outline=_col(INK), width=10)
    d.pieslice((cx - R + 26, cy - R + 26, cx + R - 26, cy + R - 26), -90, -90 + 360 * frac, fill=_col(col, 230))
    d.ellipse((cx - R + 130, cy - R + 130, cx + R - 130, cy + R - 130), fill=_col((1, 1, 1)), outline=_col(INK), width=8)
    for k in range(60):
        a = math.radians(k * 6 - 90)
        r0 = R - (10 if k % 5 else 34)
        d.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * R, cy + math.sin(a) * R), fill=_col(INK), width=5 if k % 5 == 0 else 3)
    commit()
    m, s = int(left // 60), int(left % 60)
    pulse = 1.0 + 0.03 * math.sin(t * (4 + 6 * (1 - frac)))
    text(c, f"{m:02d}:{s:02d}", (cx, cy - 6), 150, hot if frac < 0.5 else INK, 1.0, scale=pulse)
    text(c, data.get("label", ""), (W / 2, 1400), 64, INK, min(1, u * 5))
    return c


def balance_chart(data, u, t, seed=1):
    """Bars stepping down as money leaves. data: {points:[{label, value}], unit?}"""
    c = base(seed)
    pts = data["points"]
    vmax = max(p["value"] for p in pts) or 1
    d, commit = _draw(c)
    n = len(pts)
    bw, gap, x0, base_y, top = 150, 40, (W - (n * 150 + (n - 1) * 40)) / 2, 1420, 640
    for i, p in enumerate(pts):
        grow = ease("out", (u * (n + 1) - i) / 1.0)
        h = (base_y - top) * (p["value"] / vmax) * min(1, max(0, grow))
        x = x0 + i * (bw + gap)
        col = rgb(TONES["alert"]) if i and p["value"] < pts[i - 1]["value"] else rgb(TONES["calm"])
        d.rectangle((x, base_y - h, x + bw, base_y), fill=_col(col, 235), outline=_col(INK), width=6)
    d.line((x0 - 30, base_y, x0 + n * (bw + gap), base_y), fill=_col(INK), width=8)
    commit()
    for i, p in enumerate(pts):
        grow = ease("out", (u * (n + 1) - i) / 1.0)
        if grow > 0.3:
            x = x0 + i * (bw + gap) + bw / 2
            h = (base_y - top) * (p["value"] / vmax) * min(1, grow)
            text(c, inr(p["value"]), (x, base_y - h - 46), 40, INK, min(1, grow), maxw=200)
            text(c, p["label"], (x, base_y + 62), 40, INK, min(1, grow), maxw=200)
    return c


def stack(data, u, t, seed=1):
    """Commitment / sunk cost: blocks pile up; the exit is blocked. data: {items:[{label, value}]}"""
    c = base(seed)
    items = data["items"]
    tot = sum(i["value"] for i in items)
    d, commit = _draw(c)
    y = 1500
    x0, w = 300, 480
    shown = []
    for i, it in enumerate(items):
        k = ease("out_back", (u * (len(items) + 1.2) - i) / 0.8)
        if k <= 0:
            continue
        h = 90 + 330 * it["value"] / tot
        y -= h
        off = (1 - min(1, k)) * -700
        d.rounded_rectangle((x0, y + off, x0 + w, y + h - 6 + off), 16, fill=_col(rgb("#f0c65a")), outline=_col(INK), width=7)
        shown.append((it, y + off, h))
    d.line((x0 - 60, 1500, x0 + w + 60, 1500), fill=_col(INK), width=10)
    if u > 0.8:                                                        # the way out is blocked
        ex = ease("out", (u - 0.8) / 0.2)
        wline(d, (860, 700), (940, 700 + 80 * ex), rgb(TONES["alert"]), 16, seed)
        wline(d, (940, 700), (860, 700 + 80 * ex), rgb(TONES["alert"]), 16, seed + 1)
    commit()
    for it, yy, h in shown:
        text(c, f"{it['label']}  {inr(it['value'])}", (x0 + w / 2, yy + h / 2 - 4), 44, INK, maxw=440)
    text(c, inr(sum(i["value"] for i in [s[0] for s in shown])), (W / 2, 560), 120, rgb(TONES["alert"]), min(1, u * 4))
    if u > 0.8:
        text(c, data.get("exit_label", "अब रुकें कैसे?"), (770, 900), 52, rgb(TONES["alert"]), 1.0, maxw=240)
    return c


def authority_ladder(data, u, t, seed=1):
    """Escalating authority. data: {levels:[{label}], victim?}"""
    c = base(seed)
    lv = data["levels"]
    d, commit = _draw(c)
    n = len(lv)
    for i, L in enumerate(lv):
        k = ease("out_back", (u * (n + 0.8) - i) / 0.8)
        if k <= 0:
            continue
        w = 300 + i * 150
        y = 1300 - i * 190
        d.rounded_rectangle((W / 2 - w / 2, y - 70, W / 2 + w / 2, y + 70), 22, fill=_col(rgb("#cfd8ea") if i < n - 1 else rgb("#f4b9b2")), outline=_col(INK), width=7)
    commit()
    for i, L in enumerate(lv):
        if ease("out_back", (u * (n + 0.8) - i) / 0.8) > 0.3:
            text(c, L["label"], (W / 2, 1300 - i * 190 - 4), 46, INK, 1.0, maxw=300 + i * 150 - 40)
    d, commit = _draw(c)
    person_icon(d, W / 2, 1560, 0.9 * (1 - 0.3 * u))
    commit()
    return c


def network_cut(data, u, t, seed=1):
    """Isolation: connections to other people are cut one by one. data: {center, nodes:[...]}"""
    c = base(seed)
    d, commit = _draw(c)
    nodes = data["nodes"]
    n = len(nodes)
    cx, cy = W / 2, 980
    ring = [(cx + math.cos(2 * math.pi * i / n - math.pi / 2) * 360, cy + math.sin(2 * math.pi * i / n - math.pi / 2) * 360) for i in range(n)]
    for i, p in enumerate(ring):
        cut = ease("out", (u * (n + 1) - 1 - i) / 0.6)
        if cut < 1:
            wline(d, (cx, cy), p, INK + (), 6, seed + i)
        else:
            mid = ((cx + p[0]) / 2, (cy + p[1]) / 2)
            wline(d, (cx, cy), (cx + (p[0] - cx) * 0.3, cy + (p[1] - cy) * 0.3), INK, 5, seed + i)
            wline(d, (mid[0] - 30, mid[1] - 30), (mid[0] + 30, mid[1] + 30), rgb(TONES["alert"]), 9, seed)
            wline(d, (mid[0] - 30, mid[1] + 30), (mid[0] + 30, mid[1] - 30), rgb(TONES["alert"]), 9, seed + 1)
        person_icon(d, p[0], p[1], 1.15, fill=(0.94, 0.94, 1.0) if cut < 1 else (0.86, 0.86, 0.88))
    person_icon(d, cx, cy, 1.8, fill=(1.0, 0.95, 0.85))
    commit()
    text(c, data.get("center", ""), (cx, cy + 170), 56, INK)
    for i, p in enumerate(ring):
        text(c, nodes[i], (p[0], p[1] + 110), 46, INK, maxw=260)
    return c


def tunnel(data, u, t, seed=1):
    """Fear narrows attention: the periphery closes in on one thing. data: {focus_label}"""
    c = base(seed, tint=(0.9, 0.85, 0.85))
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xs - W / 2) / (W / 2), (ys - 960) / (H / 2.4))
    closing = 1.05 - 0.78 * ease("smooth", u)
    dark = np.clip((r - closing) * 3.5, 0, 1)[:, :, None]
    c = c * (1 - dark * 0.93)
    d, commit = _draw(c)
    for k in range(3):
        rad = (closing * 360 * (1 + 0.6 * k)) + 30 * math.sin(t * 3 + k)
        d.ellipse((W / 2 - rad, 960 - rad, W / 2 + rad, 960 + rad), outline=_col(rgb(TONES["alert"]), int(200 / (k + 1))), width=8)
    d.ellipse((W / 2 - 110, 960 - 110, W / 2 + 110, 960 + 110), fill=_col((1, 1, 1)), outline=_col(INK), width=8)
    d.rectangle((W / 2 - 34, 960 - 60, W / 2 + 34, 960 + 60), fill=_col(rgb(TONES["alert"])), outline=_col(INK), width=6)
    commit()
    text(c, data.get("focus_label", ""), (W / 2, 1300), 60, (1, 1, 1), min(1, u * 4))
    return c


def checklist(data, u, t, seed=1):
    """Ink checklist with ticks drawn on. data: {title, items:[str]}"""
    c = base(seed)
    items = data["items"]
    text(c, data.get("title", ""), (W / 2, 580), 84, rgb(TONES["calm"]), min(1, u * 6), maxw=900)
    d, commit = _draw(c)
    for i, it in enumerate(items):
        k = ease("out", (u * (len(items) + 1) - 0.6 - i) / 0.9)
        y = 700 + i * 220
        d.rounded_rectangle((110, y - 46, 200, y + 44), 14, fill=_col((1, 1, 1)), outline=_col(INK), width=7)
        if k > 0:
            p = min(1, k)
            pts = [(128, y), (152, y + 26), (188, y - 34)]
            seg = [(pts[0], pts[1]), (pts[1], pts[2])]
            a, b = pts[0], pts[1]
            d.line((a[0], a[1], a[0] + (b[0] - a[0]) * min(1, p * 2), a[1] + (b[1] - a[1]) * min(1, p * 2)), fill=_col(rgb(TONES["calm"])), width=14)
            if p > 0.5:
                b2 = pts[2]
                q = (p - 0.5) * 2
                d.line((b[0], b[1], b[0] + (b2[0] - b[0]) * q, b[1] + (b2[1] - b[1]) * q), fill=_col(rgb(TONES["calm"])), width=14)
    commit()
    for i, it in enumerate(items):
        k = ease("out", (u * (len(items) + 1) - 0.6 - i) / 0.9)
        if k > 0:
            text(c, it, (610, 700 + i * 220 - 4), 52, INK, min(1, k * 2), maxw=720)
    return c


def timeline(data, u, t, seed=1):
    """Vertical timeline. data: {total_minutes, events:[{at, label}]}"""
    c = base(seed)
    ev = data["events"]
    tot = float(data.get("total_minutes", max(e["at"] for e in ev)))
    d, commit = _draw(c)
    x, y0, y1 = 360, 520, 1520
    d.line((x, y0, x, y0 + (y1 - y0) * ease("out", u * 1.4)), fill=_col(INK), width=10)
    for i, e in enumerate(ev):
        y = y0 + (y1 - y0) * e["at"] / tot
        if u * 1.4 > (y - y0) / (y1 - y0) + 0.02:
            d.ellipse((x - 24, y - 24, x + 24, y + 24), fill=_col(rgb(TONES["alert"]) if e.get("hot") else rgb("#f0c65a")), outline=_col(INK), width=7)
    commit()
    for i, e in enumerate(ev):
        y = y0 + (y1 - y0) * e["at"] / tot
        if u * 1.4 > (y - y0) / (y1 - y0) + 0.02:
            text(c, f"{int(e['at'])} मिनट", (200, y), 42, INK, maxw=180)
            text(c, e["label"], (700, y), 48, INK, maxw=520)
    return c


def crowd(data, u, t, seed=1):
    """Social proof / FOMO: one person, then a few, then a crowd; one figure is highlighted. data: {count, label}"""
    c = base(seed)
    d, commit = _draw(c)
    n = int(data.get("count", 30))
    r = random.Random(seed)
    cols = 6
    for i in range(n):
        k = ease("out", (u * (n + 6) - i * 0.9) / 3.0)
        if k <= 0:
            continue
        cx, cy = 200 + (i % cols) * 130 + r.uniform(-10, 10), 560 + (i // cols) * 170 + (1 - min(1, k)) * 60
        person_icon(d, cx, cy, 0.55 * min(1, k), fill=(0.9, 0.93, 1.0) if i else (1.0, 0.9, 0.7))
    commit()
    text(c, data.get("label", ""), (W / 2, 1620), 60, INK, min(1, u * 3))
    return c


RENDERERS = dict(counter=counter, money_flow=money_flow, countdown=countdown, balance_chart=balance_chart, stack=stack,
                 authority_ladder=authority_ladder, network_cut=network_cut, tunnel=tunnel, checklist=checklist, timeline=timeline, crowd=crowd)


def render(kind, data, u, t, seed=1):
    if kind not in RENDERERS:
        raise KeyError(f"procedural type '{kind}' not implemented (have: {sorted(RENDERERS)})")
    return RENDERERS[kind](data, min(1.0, max(0.0, u)), t, seed)
