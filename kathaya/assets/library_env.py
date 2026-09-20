"""Registers Kathaya LIBRARY environments (assets created through the request -> approval -> build flow) with the physical renderer: a location entry (stage layout), the `photo_backdrop` environment family
(a stylised backdrop layer + a ground plane, characters stand in front of it) and its lights. Idempotent; call before anything renders."""
import base64
import json
import os

from asset_pipeline.ink import Ink
from asset_pipeline.set_art import FULL
from engine.environments import factory, families, locations as LOC
from engine.shorts.lighting import Light
from engine.shorts.raster import ROOT

LIBRARY = os.path.join(ROOT, "assets/library/kathaya")
TOP, FLOOR_Y = -160, 1500


def photo_backdrop(v, seed):
    """layers: the stylised backdrop (far), the ground plane (near); '@char' between them and in front of the backdrop"""
    path = v["backdrop"] if os.path.isabs(v["backdrop"]) else os.path.join(ROOT, v["backdrop"])
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    a = Ink(*FULL, seed + 1)
    a.raw(f'<image x="-160" y="{TOP}" width="1400" height="{FLOOR_Y - TOP + 40}" preserveAspectRatio="none" href="data:image/png;base64,{b64}"/>')
    g = Ink(-160, FLOOR_Y - 20, 1400, 700, seed + 2)
    col = v.get("floor", "#5b5d66")
    r, gg, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
    lo = "#%02x%02x%02x" % (int(r * 0.45), int(gg * 0.45), int(b * 0.45))
    hi = "#%02x%02x%02x" % (min(255, int(r * 1.35) + 8), min(255, int(gg * 1.35) + 8), min(255, int(b * 1.35) + 8))
    g.defs.append(f'<linearGradient id="fl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hi}"/><stop offset="1" stop-color="{lo}"/></linearGradient>')
    g.raw(f'<rect x="-160" y="{FLOOR_Y}" width="1400" height="700" fill="url(#fl)"/>')
    for k in range(-4, 5):                                                                 # pavement seams converging to the vanishing point
        g.raw(f'<line x1="{540 + k * 90}" y1="{FLOOR_Y}" x2="{540 + k * 330}" y2="{FLOOR_Y + 700}" stroke="#13121a" stroke-width="3" opacity="0.28"/>')
    for k in range(1, 5):
        yy = FLOOR_Y + 40 * k * k
        g.raw(f'<line x1="-160" y1="{yy}" x2="1240" y2="{yy}" stroke="#13121a" stroke-width="2.5" opacity="0.22"/>')
    g.raw(f'<rect x="-160" y="{FLOOR_Y}" width="1400" height="10" fill="#13121a" opacity="0.8"/>')
    return [("wall", a, dict(par=0.6, depth=3.2)), ("floor", g, dict(par=0.9, depth=2.0))], ["wall", "floor", "@char"]


def register_all():
    families.FAMILIES["photo_backdrop"] = photo_backdrop
    factory.LIGHTS.setdefault("photo_backdrop", ((0.62, 0.62, 0.64), 0.30, "day", "as photographed", "Stylised backdrop built from an approved reference photograph", "real places"))
    n = 0
    if os.path.isdir(LIBRARY):
        for d in sorted(os.listdir(LIBRARY)):
            f = os.path.join(LIBRARY, d, "asset.json")
            if not os.path.exists(f):
                continue
            a = json.load(open(f, encoding="utf-8"))
            b = a.get("binding") or {}
            if a["type"] != "environment" or b.get("family") != "photo_backdrop":
                continue
            loc = b["location"]
            lay = dict(LOC.LOCATIONS["street"][3])
            LOC.LOCATIONS[loc] = ("photo_backdrop", tuple(a["supports"]["time_of_day"]), a["supports"]["time_of_day"][0], lay, [loc])
            if loc not in LOC.ALL:
                LOC.ALL.append(loc)
            LOC.EXTRA[loc] = dict(backdrop=b["backdrop"], floor=b.get("floor", "#5b5d66"))
            n += 1
    return n
