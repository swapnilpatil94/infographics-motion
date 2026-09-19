"""Shorts-style burned-in Hindi captions (PIL + raqm, so conjuncts shape
correctly). Kept inside the vertical-video safe zone: clear of the bottom
~22% (channel/description UI) and the right ~12% (like/comment rail).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

FONT = "/System/Library/Fonts/Kohinoor.ttc"
BOLD_INDEX = 3
W, H = 1080, 1920
SAFE = dict(left=70, right=W - 130, top=260, bottom=int(H * 0.78))
_cache = {}


def _font(size):
    layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    return ImageFont.truetype(FONT, size, index=BOLD_INDEX, layout_engine=layout)


def render(text, size=76, center_y=1420):
    key = (text, size, center_y)
    if key in _cache:
        return _cache[key]
    font = _font(size)
    tmp = Image.new("RGBA", (W, 10))
    d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), text, font=font, stroke_width=8)
    tw, th = box[2] - box[0], box[3] - box[1]
    while tw > SAFE["right"] - SAFE["left"] and size > 40:
        size -= 4
        font = _font(size)
        box = d.textbbox((0, 0), text, font=font, stroke_width=8)
        tw, th = box[2] - box[0], box[3] - box[1]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = (SAFE["left"] + SAFE["right"]) // 2 - tw // 2 - box[0]
    y = center_y - th // 2 - box[1]
    d.text((x, y + 5), text, font=font, fill=(0, 0, 0, 120), stroke_width=9, stroke_fill=(0, 0, 0, 120))
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=(12, 10, 20, 255))
    arr = np.asarray(layer).astype(np.float32) / 255.0
    bbox = (x + box[0], y + box[1], x + box[2], y + box[3])
    _cache[key] = (arr, bbox)
    return arr, bbox


def overlay(frame, arr, opacity=1.0):
    a = arr[:, :, 3:4] * opacity
    return frame * (1 - a) + arr[:, :, :3] * a


def in_safe_zone(bbox):
    x0, y0, x1, y1 = bbox
    return x0 >= SAFE["left"] and x1 <= SAFE["right"] and y0 >= SAFE["top"] and y1 <= SAFE["bottom"]
