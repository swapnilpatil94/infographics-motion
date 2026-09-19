"""Small ink icons (300x300) for concept cards, in the same linework as the sets.
Closed vocabulary: the planner picks a name; unknown names fall back to 'question'."""
import math

from asset_pipeline.ink import Ink, INK

S = 300


def _new(seed):
    return Ink(0, 0, S, S, seed)


def clock(a, c):
    a.ellipse(150, 150, 118, 118, fill="#f4f0e4", sw=9)
    for k in range(12):
        ang = math.radians(k * 30)
        a.line((150 + 98 * math.sin(ang), 150 - 98 * math.cos(ang)), (150 + 84 * math.sin(ang), 150 - 84 * math.cos(ang)), sw=5, wobble=0.2)
    a.line((150, 150), (150, 84), sw=9, wobble=0.3, stroke=c)
    a.line((150, 150), (200, 176), sw=7, wobble=0.3)


def phone(a, c):
    a.rrect(85, 20, 130, 260, 22, fill="#f4f0e4", sw=9)
    a.rrect(97, 48, 106, 200, 8, fill=c, sw=5)
    a.line((135, 34), (165, 34), sw=5, wobble=0.2)
    a.line((112, 88), (188, 88), sw=6, wobble=0.3, stroke="#fff")
    a.line((112, 118), (170, 118), sw=6, wobble=0.3, stroke="#fff")


def coin(a, c):
    a.ellipse(150, 150, 120, 120, fill="#f0c65a", sw=9)
    a.ellipse(150, 150, 92, 92, fill="none", sw=5)
    a.path([(112, 110), (192, 110)], sw=9, wobble=0.3)
    a.path([(112, 140), (192, 140)], sw=9, wobble=0.3)
    a.path([(118, 108), (170, 108), (188, 126), (170, 144), (118, 144), (190, 210)], sw=10, smooth=False, wobble=0.4)


def moon(a, c):
    a.raw('<path d="M190,26 A128,128 0 1 0 262,200 A100,100 0 1 1 190,26 Z" fill="#f2e8b8" stroke="#13121a" '
          'stroke-width="9" stroke-linejoin="round"/>')
    for (x, y, r) in ((225, 90, 7), (250, 160, 5), (215, 215, 6)):
        a.ellipse(x, y, r, r, fill="#f2e8b8", sw=3)


def heart(a, c):
    pts = [(150, 265), (60, 170), (40, 110), (75, 62), (125, 66), (150, 110), (175, 66), (225, 62), (260, 110), (240, 170)]
    a.poly(pts, fill=c, sw=9, smooth=True, wobble=0.7)


def warning(a, c):
    a.poly([(150, 30), (272, 250), (28, 250)], fill="#f0c65a", sw=10, wobble=0.6)
    a.line((150, 100), (150, 180), sw=16, wobble=0.3)
    a.ellipse(150, 218, 9, 9, fill=INK, sw=0)


def bulb(a, c):
    a.ellipse(150, 120, 80, 88, fill="#f6e28a", sw=9)
    a.rect(118, 198, 64, 44, fill="#d9d4c4", sw=8, wobble=0.6)
    a.line((124, 224), (176, 224), sw=5, wobble=0.2)
    a.path([(126, 130), (150, 96), (174, 130)], sw=6, smooth=True, wobble=0.3)
    for ang in (-60, -30, 0, 30, 60):
        r = math.radians(ang - 90)
        a.line((150 + 112 * math.cos(r), 118 + 112 * math.sin(r)), (150 + 138 * math.cos(r), 118 + 138 * math.sin(r)), sw=6, wobble=0.2)


def calendar(a, c):
    a.rrect(34, 50, 232, 216, 16, fill="#f4f0e4", sw=9)
    a.rrect(34, 50, 232, 62, 16, fill=c, sw=9)
    for x in (94, 206):
        a.line((x, 30), (x, 74), sw=12, wobble=0.2)
    for r in range(3):
        for k in range(4):
            a.rect(56 + k * 52, 134 + r * 42, 32, 26, fill="#fff" if (r, k) != (1, 2) else c, sw=3.5, wobble=0.5)


def _chart(a, c, down):
    a.line((40, 260), (40, 40), sw=8, wobble=0.3)
    a.line((40, 260), (270, 260), sw=8, wobble=0.3)
    pts = [(60, 80), (120, 120), (170, 110), (220, 190), (262, 230)] if down else [(60, 230), (120, 190), (170, 200), (220, 120), (262, 70)]
    a.path(pts, sw=13, wobble=0.5, stroke=c, smooth=False)
    e = pts[-1]
    a.poly([(e[0] + 10, e[1] + (18 if down else -18)), (e[0] - 22, e[1] + (2 if down else -2)), (e[0] + 16, e[1] - (10 if down else -10))], fill=c, sw=6)


def chart_down(a, c):
    _chart(a, c, True)


def chart_up(a, c):
    _chart(a, c, False)


def hourglass(a, c):
    a.poly([(70, 30), (230, 30), (150, 140), (230, 270), (70, 270), (150, 160)], fill="#f4f0e4", sw=9, wobble=0.6)
    a.poly([(105, 250), (195, 250), (150, 200)], fill="#e2b04a", sw=4)
    a.poly([(100, 46), (200, 46), (150, 100)], fill="#e2b04a", sw=4)
    a.line((56, 30), (244, 30), sw=13, wobble=0.2)
    a.line((56, 270), (244, 270), sw=13, wobble=0.2)


def question(a, c):
    a.path([(96, 100), (110, 50), (172, 38), (216, 76), (196, 128), (156, 156), (150, 196)], sw=24, smooth=True, wobble=0.8, stroke=c)
    a.ellipse(150, 248, 15, 15, fill=INK, sw=0)


def eye(a, c):
    a.poly([(20, 150), (90, 80), (210, 80), (280, 150), (210, 220), (90, 220)], fill="#f4f0e4", sw=9, smooth=True, wobble=0.6)
    a.ellipse(150, 150, 52, 52, fill=c, sw=8)
    a.ellipse(150, 150, 22, 22, fill=INK, sw=0)


def lock(a, c):
    a.path([(96, 130), (96, 80), (120, 48), (180, 48), (204, 80), (204, 130)], sw=16, smooth=True, wobble=0.4)
    a.rrect(60, 126, 180, 140, 18, fill="#e2b04a", sw=9)
    a.ellipse(150, 190, 15, 15, fill=INK, sw=0)
    a.line((150, 200), (150, 232), sw=10, wobble=0.2)


ICONS = dict(clock=clock, phone=phone, coin=coin, moon=moon, heart=heart, warning=warning, bulb=bulb, calendar=calendar,
             chart_down=chart_down, chart_up=chart_up, hourglass=hourglass, question=question, eye=eye, lock=lock)


def svg(name, color="#d8493c", seed=7):
    a = _new(seed)
    ICONS.get(name, question)(a, color)
    return a.svg()
