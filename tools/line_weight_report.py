"""Measured ink stroke width (rig px) of every character part + the harvested/procedural hands -> output/tests/line_weight_report.json. Big silhouettes = 6 px, small parts (hands) = 4 px."""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.skeleton import dna2, normalize as N, parts_art2 as PA2   # noqa: E402

rows = {}
for role in ("young_man", "middle_aged_woman", "elderly_man"):
    d = dna2.make("lw:" + role, role, {"wardrobe.top": "shirt"})
    for view in ("profile", "three_quarter"):
        man = PA2.bake2(d, view, "full")
        for part in ("hand_R_hold_phone", "hand_R_open", "hand_R_fist", "hand_R_point", "hand_L_relaxed", "forearm_R", "upperarm_R", "thigh_R", "shin_R", "torso", "neck", "pelvis"):
            p = man["parts"][part]
            im = np.asarray(Image.open(os.path.join(ROOT, p["png"])).convert("RGBA"))
            w = N.stroke_width_px(im, p["res"])
            rows.setdefault(part, []).append(None if w is None else round(w, 2))
summary = {k: dict(values=v, median=float(np.median([x for x in v if x is not None]))) for k, v in rows.items()}
big = ["forearm_R", "upperarm_R", "thigh_R", "shin_R", "torso", "neck", "pelvis"]
small = [k for k in rows if k.startswith("hand")]
res = dict(parts=summary, big_target_px=6.0, small_target_px=4.0,
           big_ok=all(abs(summary[k]["median"] - 6.0) <= 1.0 for k in big), hands_ok=all(abs(summary[k]["median"] - 4.0) <= 1.2 for k in small),
           hands_vs_limbs_ratio=round(float(np.median([summary[k]["median"] for k in small])) / float(np.median([summary[k]["median"] for k in big])), 2))
os.makedirs(os.path.join(ROOT, "output/tests"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "output/tests/line_weight_report.json"), "w"), indent=1)
print(json.dumps({k: v["median"] for k, v in summary.items()}), res["big_ok"], res["hands_ok"])
