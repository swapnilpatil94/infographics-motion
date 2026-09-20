"""PROP ART TEST: the in-hand production props (phone, card, money, document, cup, bag) at the HOLD phase of the interaction cycle, close on the hand, through the real rig; plus the laptop stage prop.
    PYTHONPATH=. .venv/bin/python tools/production/prop_art_test.py -> output/production/prop_art.png
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, motion as M, props4 as P4   # noqa: E402

OUT = os.path.join(ROOT, "output/production")
PROPS = [("PHONE", "hold_phone"), ("CARD", "hold_card"), ("MONEY", "hold_money"), ("DOCUMENT", "pinch"), ("CUP", "hold_cup"), ("BAG", "grab")]


def main():
    os.makedirs(OUT, exist_ok=True)
    dna = LD.production_characters()["A"]
    specs = []
    for prop, _ in PROPS:
        for ph_i, ph in enumerate(("HOLD", "USE")):
            def setup(a, prop=prop):
                M.perform(a.perf, "prop_cycle", 0.2, 3.0, "neutral", 0.5, prop=prop, hand="R")
            t = 0.2 + {"HOLD": 0.6 + 0.3 + 0.2 + 0.45, "USE": 0.6 + 0.3 + 0.2 + 0.6 + 0.6}[ph]
            specs.append(dict(label=f"{prop} {ph}", dna=dna, view="three_quarter", t=round(t, 3), focus="torso", setup=setup, dx=110.0))
    ims = lab.render_specs(specs, os.path.join(OUT, "work_props"), samples=10, batch=12)
    crops = [Image.fromarray(im).crop((160, 360, 920, 1290)).convert("RGBA") for im in ims]
    lab.sheet([np.asarray(c) for c in crops], [s["label"] for s in specs], os.path.join(OUT, "prop_art.png"), cols=4, cell=(300, 420), crop=False, title="In-hand prop art at HOLD / USE (real rig, real hand drawings + prop parts)")


if __name__ == "__main__":
    main()
