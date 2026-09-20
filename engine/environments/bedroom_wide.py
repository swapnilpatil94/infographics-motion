"""ENVIRONMENT FAMILY `bedroom_wide`: an Indian bedroom staged for FULL-BODY characters (floor line, seat-height bed edge, nightstand, doorway,
foreground occluders for a camera push through the layers).  Stage coordinates (world px, 1080x1920 canvas):
    FLOOR_Y = 1500   feet contact line          SEAT_Y = 1230  mattress top (seat height 270 above the floor)
    NIGHTSTAND top y = 1180, phone lies at (670, 1168)      DOORWAY x 850..1060 (a second character enters here)
Layers (back -> front, parallax): wall .6 | decor .62 | sky(emissive) .66 | window .66 | door .8 | floor .86 | nightstand .94 | phone_free .94 | bed 1.0
| [@char 1.0] | rug_fg 1.12 | plant_fg 1.3 | curtain_fg 1.22.  Same generator contract as engine/environments/families.py.
"""
import math
import random

from asset_pipeline.ink import Ink, INK
from asset_pipeline.set_art import FULL

FLOOR_Y = 1500
SEAT_Y = 1230
STAND_TOP = 1180
PHONE_POS = (670.0, 1166.0)
PALETTES = [dict(wall="#d6cfe0", wall2="#c3bbd4", floor="#b58a5e", bed="#7d6fae", blanket="#e0a56b", curtain="#8b4f74", door="#8a6a48"),
            dict(wall="#dcd6c6", wall2="#c9c2ad", floor="#a87d55", bed="#4f7c8c", blanket="#e8c07a", curtain="#3f6f7a", door="#7b5a3f"),
            dict(wall="#d3dcd6", wall2="#bccbc2", floor="#b08a60", bed="#a25a55", blanket="#e5d3a4", curtain="#c08a4a", door="#845f45")]


def bedroom_wide(v, seed):
    c = PALETTES[int(v.get("palette", seed)) % len(PALETTES)]
    r = random.Random(seed)
    L = []
    # ---- wall (far)
    a = Ink(*FULL, seed + 1)
    a.raw(f'<rect x="-160" y="-160" width="1400" height="{FLOOR_Y + 160}" fill="{c["wall"]}"/>')
    for x in range(-150, 1240, 96):
        a.path([(x, -160), (x + r.uniform(-2, 2), FLOOR_Y)], sw=1.6, wobble=1.2, step=90, opacity=0.09)
    a.raw(f'<rect x="-160" y="{FLOOR_Y - 46}" width="1400" height="46" fill="{c["wall2"]}" stroke="{INK}" stroke-width="6"/>')
    a.hatch([(-160, -160), (520, -160), (-160, 560)], 42, 11, 2.4, 0.4, gradient=(7, 34))
    a.hatch([(1240, -160), (760, -160), (1240, 380)], 138, 11, 2.4, 0.4, gradient=(7, 34))
    L.append(("wall", a, dict(par=0.6, depth=3.2)))
    # ---- decor: frames, shelf with books, clock
    a = Ink(-40, 220, 1000, 700, seed + 2)
    a.rect(20, 300, 200, 250, fill="#7a5a3a", sw=7)
    a.rect(36, 316, 168, 218, fill="#efe6d0", sw=3)
    a.poly([(50, 520), (100, 440), (140, 490), (180, 430), (196, 520)], fill="#7fa06f", sw=4)
    a.ellipse(150, 372, 30, 30, fill="#e7c56b", sw=3)
    a.rect(300, 340, 150, 180, fill="#5a4a6a", sw=7)
    a.rect(314, 354, 122, 152, fill="#e9dcc6", sw=3)
    a.rect(520, 260, 240, 26, fill="#8a5a36", sw=6)                              # shelf
    for i, col in enumerate(("#c4553f", "#3f6f8c", "#e0b45a", "#6b8f5a", "#8a5aa0")):
        a.rect(540 + i * 38, 190 + (i % 2) * 10, 30, 70 - (i % 2) * 10, fill=col, sw=4)
    a.ellipse(860, 330, 62, 62, fill="#f4f0e2", sw=7)                            # wall clock
    a.line((860, 330), (860, 292), sw=5)
    a.line((860, 330), (890, 344), sw=5)
    L.append(("decor", a, dict(par=0.62, depth=3.1)))
    # ---- window sky (emissive) + frame with curtains
    a = Ink(660, 300, 420, 560, seed + 3)
    day = v.get("time", "night") == "day"                                       # the window shows the sky of the scene's time of day (a day scene never gets a moon)
    a.raw(f'<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{"#6fb1e6" if day else "#1c2a55"}"/><stop offset="1" stop-color="{"#cfe7f8" if day else "#40507e"}"/></linearGradient></defs>')
    a.raw('<rect x="700" y="340" width="330" height="470" fill="url(#sg)"/>')
    if day:
        a.ellipse(950, 440, 44, 44, fill="#fff3b0", sw=0, wobble=0)               # sun
        for cx_, cy_, w_ in ((790, 470, 70), (900, 580, 90), (760, 690, 60)):
            a.ellipse(cx_, cy_, w_, w_ * 0.36, fill="#ffffff", sw=0, wobble=0)
            a.ellipse(cx_ + w_ * 0.5, cy_ + 6, w_ * 0.7, w_ * 0.3, fill="#ffffff", sw=0, wobble=0)
    else:
        a.ellipse(940, 430, 36, 36, fill="#f4f1dc", sw=0, wobble=0)
        for _ in range(14):
            a.ellipse(r.uniform(715, 1015), r.uniform(355, 640), 2.4, 2.4, fill="#fff", sw=0, wobble=0)
    L.append(("sky", a, dict(par=0.66, depth=3.0, emissive=True)))
    a = Ink(640, 280, 470, 620, seed + 4)
    a.rect(696, 336, 338, 478, fill="none", sw=9)
    a.line((865, 336), (865, 814), sw=8, wobble=0.5)
    a.line((696, 575), (1034, 575), sw=8, wobble=0.5)
    a.rect(680, 812, 372, 24, fill=c["wall2"], sw=7)
    a.poly([(672, 322), (742, 322), (760, 840), (690, 830)], fill=c["curtain"], sw=6, smooth=True, wobble=0.8)
    a.poly([(1000, 322), (1064, 322), (1050, 830), (984, 840)], fill=c["curtain"], sw=6, smooth=True, wobble=0.8)
    L.append(("window", a, dict(par=0.66, depth=3.0)))
    # ---- doorway on the right: warm hallway beyond
    a = Ink(800, 480, 300, 1100, seed + 5)
    a.raw(f'<rect x="850" y="560" width="210" height="{FLOOR_Y - 560}" fill="#e9d2a6"/>')
    a.hatch([(850, 560), (1060, 560), (1060, 900), (850, 900)], 60, 16, 2.0, 0.25, gradient=(6, 26))
    a.rect(840, 548, 232, FLOOR_Y - 548, fill="none", sw=12, wobble=0.6)
    a.poly([(840, 548), (1072, 548), (1072, 500), (840, 500)], fill=c["door"], sw=8)
    L.append(("door", a, dict(par=0.8, depth=2.6)))
    # ---- floor (ground plane)
    a = Ink(*FULL, seed + 6)
    a.raw(f'<rect x="-160" y="{FLOOR_Y}" width="1400" height="{2080 - FLOOR_Y}" fill="{c["floor"]}"/>')
    for k, x in enumerate(range(-160, 1240, 175)):
        a.path([(x, FLOOR_Y), (x - 60 + k * 6, 2080)], sw=3, wobble=1.0, step=80, opacity=0.5)
    for yy in range(FLOOR_Y + 90, 2080, 130):
        a.path([(-160, yy), (1240, yy + r.uniform(-4, 4))], sw=2, wobble=1.0, step=100, opacity=0.25)
    a.hatch([(-160, FLOOR_Y), (1240, FLOOR_Y), (1240, FLOOR_Y + 80), (-160, FLOOR_Y + 80)], 0, 12, 2.4, 0.4, gradient=(6, 30))
    L.append(("floor", a, dict(par=0.86, depth=2.4)))
    # ---- nightstand (against the back wall) with lamp (off)
    a = Ink(540, 1040, 300, 470, seed + 7)
    a.rrect(566, STAND_TOP, 226, 24, 8, fill="#8a5a36", sw=7)
    a.rect(580, STAND_TOP + 24, 198, 250, fill="#a06f44", sw=7)
    a.rect(596, STAND_TOP + 42, 166, 96, fill="#b58152", sw=5)
    a.ellipse(679, STAND_TOP + 90, 9, 9, fill="#e0c07a", sw=3)
    a.rect(596, STAND_TOP + 150, 166, 96, fill="#b58152", sw=5)
    a.ellipse(679, STAND_TOP + 198, 9, 9, fill="#e0c07a", sw=3)
    a.line((588, STAND_TOP + 274), (588, FLOOR_Y - 6), sw=8)
    a.line((770, STAND_TOP + 274), (770, FLOOR_Y - 6), sw=8)
    a.rect(596, STAND_TOP - 44, 22, 44, fill="#d8b070", sw=5)                     # lamp base
    a.poly([(566, STAND_TOP - 44), (648, STAND_TOP - 44), (630, STAND_TOP - 140), (584, STAND_TOP - 140)], fill="#f2e2b8", sw=6)
    L.append(("nightstand", a, dict(par=0.94, depth=2.0)))
    # ---- the phone lying on the nightstand (separate layer: it disappears when picked up)
    a = Ink(620, 1120, 120, 70, seed + 8)
    px, py = PHONE_POS
    a.poly([(px - 46, py + 8), (px + 42, py - 6), (px + 50, py + 6), (px - 38, py + 20)], fill="#15171c", sw=5)
    a.poly([(px - 40, py + 8), (px + 38, py - 3), (px + 42, py + 3), (px - 34, py + 14)], fill="#5b7fb0", sw=0, wobble=0)
    L.append(("phone_free", a, dict(par=0.94, depth=2.0)))
    # ---- bed in profile (headboard left, seat edge at x~500)
    a = Ink(-220, 940, 800, 580, seed + 9)
    a.rect(-200, 1000, 60, 470, fill="#5a3f2b", sw=8)                              # headboard
    a.rrect(-170, 1140, 260, 100, 44, fill="#f1ece0", sw=7)                        # pillow
    a.rrect(-200, SEAT_Y, 700, 62, 22, fill=c["bed"], sw=8)                        # mattress
    a.hatch([(-190, SEAT_Y + 8), (490, SEAT_Y + 8), (490, SEAT_Y + 56), (-190, SEAT_Y + 8)], 20, 16, 2.2, 0.4, gradient=(6, 24))
    a.poly([(-120, SEAT_Y - 4), (150, SEAT_Y - 44), (360, SEAT_Y - 30), (470, SEAT_Y - 2), (-120, SEAT_Y - 4)], fill=c["blanket"], sw=7, smooth=True, wobble=1.0)
    a.hatch([(-100, SEAT_Y - 8), (150, SEAT_Y - 40), (360, SEAT_Y - 26), (450, SEAT_Y - 6)], 70, 15, 2.2, 0.35, gradient=(6, 22))
    a.rect(-200, SEAT_Y + 62, 700, 150, fill="#6a4b34", sw=8)                      # frame
    a.line((-160, SEAT_Y + 212), (-160, FLOOR_Y - 4), sw=9)
    a.line((470, SEAT_Y + 212), (470, FLOOR_Y - 4), sw=9)
    L.append(("bed", a, dict(par=1.0, depth=1.7)))
    # ---- foreground occluders (camera push-through / depth cues)
    a = Ink(-200, 1720, 1500, 420, seed + 10)
    a.poly([(-200, 1800), (1300, 1780), (1300, 2140), (-200, 2140)], fill="#7d3a4e", sw=8, wobble=1.4, step=70)
    for k in range(6):
        a.line((-160 + k * 260, 1830), (-160 + k * 260 + 40, 2140), sw=4, wobble=1.0, opacity=0.5)
    L.append(("rug_fg", a, dict(par=1.12, depth=0.9)))
    a = Ink(860, 1160, 300, 940, seed + 11)                                         # potted plant, right edge
    a.poly([(930, 1780), (1130, 1780), (1100, 2040), (960, 2040)], fill="#b5613f", sw=8)
    for ang, ln in ((-70, 420), (-40, 520), (-10, 470), (20, 500), (55, 400), (-95, 360)):
        a.poly([(1030, 1780), (1030 + ln * math.sin(math.radians(ang)) * 0.55 - 40, 1780 - ln * math.cos(math.radians(ang))),
                (1030 + ln * math.sin(math.radians(ang)) * 0.55 + 40, 1780 - ln * math.cos(math.radians(ang)) * 0.96)], fill="#5f9a5a", sw=6, smooth=True, wobble=0.8)
    L.append(("plant_fg", a, dict(par=1.3, depth=0.7)))
    a = Ink(-220, 200, 300, 1900, seed + 12)                                        # curtain edge, left
    a.poly([(-220, 200), (30, 200), (60, 2000), (-220, 2000)], fill=c["curtain"], sw=8, smooth=True, wobble=1.0, step=70)
    for k in range(4):
        a.path([(-170 + k * 60, 220), (-160 + k * 60, 2000)], sw=4, wobble=1.4, step=100, opacity=0.45)
    L.append(("curtain_fg", a, dict(par=1.22, depth=0.8, opacity=0.9)))
    order = ["wall", "decor", "sky", "window", "door", "floor", "nightstand", "phone_free", "bed", "@char", "rug_fg", "curtain_fg", "plant_fg"]
    return L, order
