"""Registry of story SETS: the closed vocabulary of locations the planner may choose from.

Each entry couples the art (layers on disk) with its light rig, so choosing a set also
chooses its time-of-day look. The planner sees `catalog()` (generated from this table), and
the validator rejects anything not in it - adding a set here (plus its art) is the only
step needed for the planner to be able to use it.
"""
import math
import os

import numpy as np

from engine.shorts.character import c2w, PHONE_CENTER
from engine.shorts.lighting import Light
from engine.shorts.scene import load_room_layers, ROOM_ORDER

GEN = "assets/environment/generated"
_layer_cache = {}


def _bedroom_lights(ctx):
    return [
        Light("shaft", (0.29, 0.33, 0.57), lambda t: 0.96 + 0.04 * math.sin(0.5 * t), reach=(2.05, 3.4), attach_par=0.85,
              poly=[(722, 290), (1018, 290), (500, 1250), (-60, 1250)], axis=[(870, 290), (220, 1250)], feather=46, fade_end=0.3),
        Light("radial", (0.10, 0.11, 0.22), 1.0, reach=(0, 3.4), attach_par=0.7, center=(870, 520), radius=760, power=1.6),
        Light("radial", (0.26, 0.33, 0.52), 0.55, reach=(1.5, 1.7), attach_par=1.0, center=c2w((800, 470)), radius=330, power=1.5),
    ]


def _office_lights(ctx):
    return [
        Light("shaft", (0.62, 0.50, 0.30), lambda t: 0.95 + 0.05 * math.sin(0.4 * t), reach=(0.5, 3.4), attach_par=0.85,
              poly=[(700, 230), (1100, 230), (620, 1420), (-80, 1420)], axis=[(900, 230), (270, 1420)], feather=60, fade_end=0.25),
        Light("radial", (0.30, 0.26, 0.18), 0.8, reach=(1.5, 1.7), attach_par=1.0, center=c2w((820, 480)), radius=420, power=1.5),
    ]


def _street_lights(ctx):
    return [
        Light("radial", (0.85, 0.52, 0.22), 1.0, reach=(0, 4.1), attach_par=0.7, center=(120, 900), radius=1100, power=1.4),
        Light("radial", (0.62, 0.36, 0.14), 0.9, reach=(1.5, 1.7), attach_par=1.0, center=c2w((150, 520)), radius=520, power=1.3),
    ]


SETS = {
    "night_bedroom": dict(
        dir=f"{GEN}/night_bedroom", order=ROOM_ORDER, lights=_bedroom_lights, ambient=(0.18, 0.19, 0.32), bloom=0.55,
        time="night", mood="lonely, quiet, anxious, intimate",
        desc="Dim bedroom at night, moonlit window, character sitting up in bed under a blanket.",
        good_for="insomnia, late-night phone use, anxiety, loneliness, secrets, sudden bad/good news, regrets, sleep habits"),
    "office_day": dict(
        dir=f"{GEN}/office_day", order=None, lights=_office_lights, ambient=(0.62, 0.64, 0.66), bloom=0.30,
        time="day", mood="busy, pressured, routine, professional",
        desc="Bright office: character at a desk, window with city skyline, wall clock, corkboard of notes, plant.",
        good_for="work stress, deadlines, productivity, careers, salary, money at work, meetings, procrastination, laptops, burnout"),
    "street_dusk": dict(
        dir=f"{GEN}/street_dusk", order=None, lights=_street_lights, ambient=(0.55, 0.47, 0.56), bloom=0.45,
        time="dusk", mood="reflective, transitional, hopeful or wistful",
        desc="City street at golden-hour dusk: skyline, buildings with lit windows, lamp post, character behind a low wall.",
        good_for="commuting, spending in the market, city life, decisions, reflection, change, ending-of-day, walking, shopping, relationships"),
}


def layers_for(set_id):
    if set_id not in _layer_cache:
        import json
        spec = SETS[set_id]
        _layer_cache[set_id] = load_room_layers(spec["dir"])
    return _layer_cache[set_id]


def order_for(set_id):
    spec = SETS[set_id]
    if spec["order"]:
        return spec["order"]
    import json
    from engine.shorts.raster import ROOT
    return json.load(open(os.path.join(ROOT, spec["dir"], "layers.json")))["order"]


def catalog():
    return {k: dict(time=v["time"], mood=v["mood"], desc=v["desc"], good_for=v["good_for"]) for k, v in SETS.items()}
