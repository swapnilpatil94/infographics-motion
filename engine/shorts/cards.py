"""Concept cards: the topic-agnostic beat type.

A character scene can only show what the set/pose library covers; a card can carry ANY idea
(a number, a claim, a contrast, a short list) with an icon from a closed vocabulary, drawn in
the same ink language and animated (pop-in, ink underline draw-on, slow push). The planner
supplies only text + icon + tone; layout and motion are deterministic.
"""
import numpy as np
from PIL import Image, ImageDraw

from asset_pipeline import icons
from asset_pipeline.ink import Ink
from engine.shorts.captions import _font
from engine.shorts.layers import W, H
from engine.shorts.performance import ease
from engine.shorts.raster import rasterize

TONES = {"alert": "#d8493c", "calm": "#2f8f83", "gold": "#d9a13b", "info": "#3b6fb6"}
PAPER = np.array((0.93, 0.89, 0.80), np.float32)
INKC = (19, 18, 26, 255)
_cache = {}


def _wrap(text, font, maxw, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_layer(lines, size, color, maxw=880, line_gap=1.28):
    """-> RGBA float image (tight) for centred multi-line text; shrinks to fit maxw."""
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    while True:
        font = _font(size)
        widest = max((d.textlength(l, font=font) for l in lines), default=0)
        if widest <= maxw or size <= 34:
            break
        size -= 4
    lh = int(size * line_gap)
    im = Image.new("RGBA", (int(widest) + 40, lh * len(lines) + 30), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        x = (im.width - d.textlength(l, font=font)) / 2
        dr.text((x, i * lh + 6), l, font=font, fill=color)
    return np.asarray(im).astype(np.float32) / 255.0


def _blit(canvas, rgba, cx, cy, scale=1.0, opacity=1.0):
    if opacity <= 0.001:
        return
    h, w = rgba.shape[:2]
    if abs(scale - 1.0) > 0.003:
        import cv2
        rgba = cv2.resize(rgba, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        h, w = rgba.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(W, x0 + w), min(H, y0 + h)
    if xe <= xs or ye <= ys:
        return
    p = rgba[ys - y0:ye - y0, xs - x0:xe - x0]
    a = p[:, :, 3:4] * opacity
    canvas[ys:ye, xs:xe] = canvas[ys:ye, xs:xe] * (1 - a) + p[:, :, :3] * a


def _icon(name, tone, size):
    key = ("icon", name, tone, size)
    if key not in _cache:
        arr, _ = rasterize(icons.svg(name, TONES.get(tone, TONES["alert"])), zoom=size * 1.7 / 300.0)
        _cache[key] = arr.astype(np.float32) / 255.0
    return _cache[key]


def _underline(width, tone, seed):
    key = ("ul", width, tone, seed)
    if key not in _cache:
        a = Ink(0, 0, width, 40, seed)
        a.path([(8, 22), (width * 0.3, 14), (width * 0.62, 26), (width - 8, 16)], sw=14, smooth=True, wobble=1.6,
               stroke=TONES.get(tone, TONES["alert"]))
        arr, _ = rasterize(a.svg(), zoom=1.0)
        _cache[key] = arr.astype(np.float32) / 255.0
    return _cache[key]


def _frame(seed):
    key = ("frame", seed)
    if key not in _cache:
        a = Ink(0, 0, W, H, seed)
        a.path([(46, 46), (W - 46, 50), (W - 50, H - 46), (50, H - 50)], sw=9, closed=True, wobble=2.6, step=70, smooth=False)
        a.path([(66, 66), (W - 68, 68), (W - 66, H - 66), (68, H - 68)], sw=3, closed=True, wobble=2.0, step=70, opacity=0.5)
        arr, _ = rasterize(a.svg(), zoom=1.0, crop=False)
        _cache[key] = arr.astype(np.float32) / 255.0
    return _cache[key]


def _pop(t, t0, dur=0.42):
    u = (t - t0) / dur
    if u <= 0:
        return 0.0, 0.0
    return min(1.0, u * 2.2), 0.6 + 0.4 * ease("out_back", u)


def render(card, t, dur, seed=1):
    """-> HxWx3 float image of the card at local time t (0..dur)."""
    style, tone = card.get("style", "title"), card.get("tone", "alert")
    canvas = np.tile(PAPER, (H, W, 1)).copy()
    ys = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    canvas *= (1.05 - 0.10 * ys)                                   # soft top-to-bottom wash
    fr = _frame(seed)
    _blit(canvas, fr, W / 2, H / 2)
    push = 1.0 + 0.035 * ease("smooth", t / max(dur, 1e-6))        # slow push over the whole card
    ic = card.get("icon", "question")
    accent = tuple(int(TONES.get(tone, TONES["alert"])[i:i + 2], 16) for i in (1, 3, 5)) + (255,)

    if style == "stat":
        op, sc = _pop(t, 0.05)
        _blit(canvas, _icon(ic, tone, 360), W / 2, 560, sc * push, op)
        big = _text_layer([card["big"]], 210, accent, maxw=900)
        op, sc = _pop(t, 0.30)
        _blit(canvas, big, W / 2, 1000, sc * push, op)
        u = ease("out", (t - 0.7) / 0.5)
        ul = _underline(min(860, big.shape[1]), tone, seed + 3)
        if u > 0:
            cut = ul[:, :max(1, int(ul.shape[1] * u))]
            _blit(canvas, cut, W / 2 - (ul.shape[1] - cut.shape[1]) / 2, 1000 + big.shape[0] / 2 + 12, push, 1.0)
        lab = _text_layer(_wrap(card.get("small", ""), _font(70), 860, ImageDraw.Draw(Image.new("RGBA", (4, 4)))), 70, INKC)
        op, sc = _pop(t, 0.55)
        _blit(canvas, lab, W / 2, 1300, sc * push, op)
    elif style == "versus":
        for i, key in enumerate(("left", "right")):
            cx = W * (0.27 if i == 0 else 0.73)
            op, sc = _pop(t, 0.1 + 0.35 * i)
            col = accent if i == 1 else (60, 60, 70, 255)
            _blit(canvas, _icon(card.get(f"icon_{key}", ic), tone if i else "calm", 250), cx, 700, sc * push, op)
            lines = _wrap(card[key], _font(80), 400, ImageDraw.Draw(Image.new("RGBA", (4, 4))))
            _blit(canvas, _text_layer(lines, 80, col, maxw=420), cx, 1010, sc * push, op)
        op, sc = _pop(t, 0.3)
        _blit(canvas, _text_layer(["VS"], 90, INKC, maxw=200), W / 2, 850, sc * push, op)
        if card.get("small"):
            op, sc = _pop(t, 0.95)
            _blit(canvas, _text_layer(_wrap(card["small"], _font(64), 860, ImageDraw.Draw(Image.new("RGBA", (4, 4)))), 64, INKC), W / 2, 1360, sc * push, op)
    elif style == "list":
        op, sc = _pop(t, 0.05)
        _blit(canvas, _icon(ic, tone, 260), W / 2, 470, sc * push, op)
        if card.get("title"):
            _blit(canvas, _text_layer(_wrap(card["title"], _font(84), 880, ImageDraw.Draw(Image.new("RGBA", (4, 4)))), 84, accent), W / 2, 740, sc * push, op)
        for i, item in enumerate(card.get("items", [])[:4]):
            op, sc = _pop(t, 0.5 + 0.55 * i)
            lines = _wrap(f"{i + 1}. {item}", _font(70), 820, ImageDraw.Draw(Image.new("RGBA", (4, 4))))
            _blit(canvas, _text_layer(lines, 70, INKC, maxw=840), W / 2, 960 + i * 190, sc * push, op)
    else:  # title
        op, sc = _pop(t, 0.05)
        _blit(canvas, _icon(ic, tone, 400), W / 2, 620, sc * push, op)
        lines = _wrap(card.get("big", ""), _font(120), 880, ImageDraw.Draw(Image.new("RGBA", (4, 4))))
        big = _text_layer(lines, 120, INKC, maxw=900)
        op, sc = _pop(t, 0.30)
        _blit(canvas, big, W / 2, 1090, sc * push, op)
        u = ease("out", (t - 0.75) / 0.5)
        ul = _underline(min(820, big.shape[1]), tone, seed + 5)
        if u > 0:
            cut = ul[:, :max(1, int(ul.shape[1] * u))]
            _blit(canvas, cut, W / 2 - (ul.shape[1] - cut.shape[1]) / 2, 1090 + big.shape[0] / 2 + 10, push, 1.0)
        if card.get("small"):
            op, sc = _pop(t, 0.6)
            _blit(canvas, _text_layer(_wrap(card["small"], _font(64), 860, ImageDraw.Draw(Image.new("RGBA", (4, 4)))), 64, INKC), W / 2, 1420, sc * push, op)
    return canvas
