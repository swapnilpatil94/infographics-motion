"""ENVIRONMENT factory: (family, variation, seed) -> a registered, renderable set.

    set_id = build("bank_branch", {"palette": 1}, seed=story_id)     # deterministic: same inputs -> byte-identical layers
Families = the three original sets (recolourable) + engine.environments.families (bank, call centre, living room, ATM area).
Variation = palette swap (walls/floor/accent), clutter and time-of-day light; extra families plug in by adding a generator.
"""
import hashlib
import json
import math
import os

from asset_pipeline import set_art
from engine.environments import families
from engine.shorts import sets
from engine.shorts.lighting import Light
from engine.shorts.raster import ROOT

GEN = os.path.join(ROOT, "assets/environment/generated")

LIGHTS = {   # family -> (ambient, bloom, time, mood, description, good_for, light builder)
    "bank_branch": ((0.66, 0.66, 0.64), 0.28, "day", "formal, official, orderly", "Bank branch: teller windows, queue posts, signage, counter in front", "bank visits, official processes, queues, loans, KYC, fraud reports"),
    "call_centre": ((0.60, 0.62, 0.68), 0.32, "day", "busy, impersonal, pressured", "Call centre floor: rows of glowing cubicles, headset desk in front", "support calls, scam call centres, customer service, sales pressure"),
    "indian_living_room": ((0.64, 0.58, 0.50), 0.35, "day", "warm, familial, domestic", "Indian living room: sofa, framed pictures, ceiling fan, curtained window", "family conversations, home life, evenings, TV, festivals"),
    "atm_area": ((0.36, 0.40, 0.52), 0.55, "night", "isolated, transactional, tense", "ATM kiosk at night: glowing machine screen, glass panels", "cash withdrawal, ATM fraud, night errands, card skimming"),
}


def _lights(family):
    if family == "atm_area":
        return lambda ctx: [Light("radial", (0.30, 0.55, 0.85), 1.0, reach=(0, 3.4), attach_par=0.8, center=(820, 560), radius=900, power=1.5),
                            Light("radial", (0.30, 0.50, 0.70), 0.8, reach=(1.5, 1.7), attach_par=1.0, center=(560, 640), radius=520, power=1.4)]
    if family == "call_centre":
        return lambda ctx: [Light("radial", (0.30, 0.34, 0.42), 1.0, reach=(0, 3.4), attach_par=0.7, center=(620, 500), radius=1300, power=1.3)]
    return lambda ctx: [Light("radial", (0.34, 0.30, 0.22), 0.9, reach=(0, 3.4), attach_par=0.8, center=(760, 500), radius=1200, power=1.4),
                        Light("radial", (0.24, 0.20, 0.14), 0.7, reach=(1.5, 1.7), attach_par=1.0, center=(520, 760), radius=520, power=1.5)]


def build(family, variation=None, seed=0):
    variation = variation or {}
    key = hashlib.sha1(json.dumps([family, variation, seed], sort_keys=True).encode()).hexdigest()[:8]
    set_id = f"{family}_{key}"
    if set_id in sets.SETS:
        return set_id
    if family not in families.FAMILIES:
        raise KeyError(f"unknown environment family '{family}' (have {sorted(families.FAMILIES)} + base sets {['night_bedroom', 'office_day', 'street_dusk']})")
    layers, order = families.FAMILIES[family](variation, seed)
    set_art._write(set_id, layers, order)
    amb, bloom, time, mood, desc, good = LIGHTS[family]
    sets.SETS[set_id] = dict(dir=f"assets/environment/generated/{set_id}", order=None, lights=_lights(family), ambient=amb, bloom=bloom, time=time, mood=mood, desc=desc, good_for=good,
                             family=family, variation=variation, seed=seed)
    return set_id


def available():
    return sorted(set(families.FAMILIES) | {"night_bedroom", "office_day", "street_dusk"})


# ------------------------------------------------------------------------------------------ recolour (variation of the base sets)
import colorsys
import re

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")


def _shift(m, deg, sat):
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.12 or v < 0.16:                    # ink, greys and whites keep their identity
        return m.group(0)
    h = (h + deg / 360.0) % 1.0
    s = min(1.0, s * sat)
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h, s, v))


def recolor(base_set, hue_deg, sat=1.0):
    """A hue-shifted copy of a base set (walls, furniture, accents): 'same room, different film'. Deterministic; cached on disk by (set, hue, sat)."""
    if not hue_deg and sat == 1.0:
        return base_set
    set_id = f"{base_set}_h{int(hue_deg)}_s{int(sat * 100)}"
    if set_id in sets.SETS:
        return set_id
    src = os.path.join(ROOT, sets.SETS[base_set]["dir"])
    dst = os.path.join(GEN, set_id)
    os.makedirs(dst, exist_ok=True)
    man = json.load(open(os.path.join(src, "layers.json")))
    layers = man.get("layers", man)
    for name, meta in layers.items():
        txt = open(os.path.join(ROOT, meta["svg"]), encoding="utf-8").read()
        txt = _HEX.sub(lambda m: _shift(m, hue_deg, sat), txt)
        out = os.path.join(dst, f"{name}.svg")
        open(out, "w", encoding="utf-8").write(txt)
        meta["svg"] = os.path.relpath(out, ROOT)
    json.dump(man, open(os.path.join(dst, "layers.json"), "w"), indent=1)
    spec = dict(sets.SETS[base_set])
    spec["dir"] = f"assets/environment/generated/{set_id}"
    sets.SETS[set_id] = spec
    return set_id


def resolve(env):
    """Plan environment -> registered set id. env = {"family": ..., "variation": {"hue": deg, "sat": s, "palette": n}, "seed": n}."""
    fam, var, seed = env["family"], env.get("variation", {}), env.get("seed", 0)
    if fam in families.FAMILIES:
        return build(fam, var, seed)
    if fam in sets.SETS:
        return recolor(fam, var.get("hue", 0), var.get("sat", 1.0))
    raise KeyError(f"unknown environment family '{fam}'")
