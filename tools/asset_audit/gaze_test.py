"""GAZE TEST (Blender Studio 'Boy Head' idea): does a pupil that moves INSIDE a fixed eye white read better than the whole eyeball sliding across the face?
    PYTHONPATH=. .venv/bin/python tools/asset_audit/gaze_test.py  -> output/tests/gaze_pupil_in_sclera_test.png  (+ docs/asset_audit/gaze_test.json)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
DIRS = {"centre": (0, 0), "left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1), "up-left": (-0.8, 0.8), "down-right": (0.8, -0.8), "far right": (1.0, 0.3)}


def main():
    dna = LD.production_characters()["A"]
    states = [dict(gaze_x=x, gaze_y=y, wide=0.0, lid=0.05) for x, y in DIRS.values()]
    res = {}
    for mode in ("eye", "pupil"):
        res[mode] = lab.render_states(dna, states, os.path.join(OUT, f"audit_work/gaze_{mode}"), focus="head", zoom=5.2, gaze_mode=mode)
    W, H = 250, 210
    S = Image.new("RGB", (len(DIRS) * W, 2 * H + 100), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), "GAZE: top = whole eyeball slides (current production);  bottom = pupil moves inside a fixed eye white (Boy Head style)", fill=(235, 235, 235), font=lab.font(16, True))
    metrics = {}
    for r, mode in enumerate(("eye", "pupil")):
        for i, (name, _) in enumerate(DIRS.items()):
            im = Image.fromarray(res[mode][i][790:1130, 420:900]).resize((W - 4, int((W - 4) * 340 / 480)))
            bg = Image.new("RGB", (W - 2, H - 2), (238, 235, 228))
            bg.paste(im.convert("RGB"), (0, 8), im.split()[3])
            S.paste(bg, (i * W + 1, 44 + r * H))
            d.text((i * W + 6, 44 + 2 * H + 6 + 0), name, fill=(235, 235, 235), font=lab.font(13))
    S.save(os.path.join(OUT, "gaze_pupil_in_sclera_test.png"))
    # measured: how far does the eye WHITE move between centre and far-right? (eyeball slide) vs how far the pupil moves relative to the white
    def white_centroid(im):
        a = np.asarray(im)[790:1130, 420:900].astype(int)
        m = (a[..., 0] > 235) & (a[..., 1] > 235) & (a[..., 2] > 225) & (a[..., 3] > 200)
        ys, xs = np.where(m)
        return None if not len(xs) else (float(xs.mean()), float(ys.mean()))
    for mode in ("eye", "pupil"):
        c0, c1 = white_centroid(res[mode][0]), white_centroid(res[mode][DIRS and 2])
        metrics[mode] = dict(eye_white_shift_centre_to_right_px=None if not (c0 and c1) else round(((c1[0] - c0[0]) ** 2 + (c1[1] - c0[1]) ** 2) ** 0.5, 1))
    json.dump(metrics, open(os.path.join(ROOT, "docs/asset_audit/gaze_test.json"), "w"), indent=1)
    print(metrics)


if __name__ == "__main__":
    main()
