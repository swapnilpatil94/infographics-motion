"""ENVIRONMENT FAMILY `study_room`: bedroom_wide's walls / window / door / floor / foreground layers with a CHAIR and a TABLE in the character plane instead of the bed (interaction tests).
Stage coordinates: floor y=1500, chair seat y=1230 (seat height 270), table top y=1060, phone lies on the table at (720, 1050), door x 850..1060."""
from asset_pipeline.ink import Ink, INK
from engine.environments import bedroom_wide as BW

TABLE_TOP = 1060
PHONE_POS = (720.0, 1050.0)


def study_room(v, seed):
    layers, order = BW.bedroom_wide(v, seed)
    keep = [(n, a, m) for (n, a, m) in layers if n not in ("bed", "nightstand", "phone_free")]
    L = list(keep)
    a = Ink(80, 900, 1000, 640, seed + 21)
    a.rect(180, 1230, 260, 30, fill="#8a5a36", sw=7)                                # chair seat
    a.rect(170, 900, 30, 350, fill="#7a4d2c", sw=7)                                 # chair back
    a.rect(190, 1258, 22, 236, fill="#6a4426", sw=6)
    a.rect(408, 1258, 22, 236, fill="#6a4426", sw=6)
    a.rrect(560, TABLE_TOP, 420, 34, 8, fill="#a06f44", sw=7)                       # table top
    a.rect(590, TABLE_TOP + 34, 26, 406, fill="#8a5a36", sw=7)
    a.rect(924, TABLE_TOP + 34, 26, 406, fill="#8a5a36", sw=7)
    a.rect(616, TABLE_TOP + 60, 308, 24, fill="#8f6238", sw=5)
    a.rect(690, TABLE_TOP - 52, 22, 52, fill="#d8b070", sw=5)                       # lamp on the table
    a.poly([(660, TABLE_TOP - 52), (742, TABLE_TOP - 52), (724, TABLE_TOP - 150), (678, TABLE_TOP - 150)], fill="#f2e2b8", sw=6)
    L.append(("furniture", a, dict(par=1.0, depth=1.7)))
    b = Ink(760, 1000, 130, 80, seed + 22)
    px, py = PHONE_POS
    b.poly([(px + 60 - 46, py + 8), (px + 60 + 42, py - 6), (px + 60 + 50, py + 6), (px + 60 - 38, py + 20)], fill="#15171c", sw=5)
    b.poly([(px + 60 - 40, py + 8), (px + 60 + 38, py - 3), (px + 60 + 42, py + 3), (px + 60 - 34, py + 14)], fill="#5b7fb0", sw=0, wobble=0)
    L.append(("phone_free", b, dict(par=1.0, depth=1.65)))
    order2 = []
    for n in order:
        if n in ("bed", "nightstand", "phone_free"):
            if n == "bed":
                order2 += ["furniture", "phone_free"]
            continue
        order2.append(n)
    return L, order2
