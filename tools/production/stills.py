"""Preview stills (one per shot midpoint + 0.6 s in) for a story plan -> contact sheet. Usage: stills.py <plan.json> <out_dir>"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

from engine.skeleton import short


def run(plan, out, per_shot=1, samples=6):
    times = []
    for s in plan["shots"]:
        for k in range(per_shot):
            times.append(round(s["t0"] + (s["t1"] - s["t0"]) * (0.5 if per_shot == 1 else (k + 1) / (per_shot + 1)), 2))
    r = short.render_stills(plan, out, times, samples=samples)
    ims = [Image.open(p).convert("RGB").resize((216, 384)) for p in r["paths"]]
    cols = 10
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 216, rows * 404), (12, 12, 14))
    dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * 216, (i // cols) * 404
        sheet.paste(im, (x, y + 20))
        dr.text((x + 4, y + 4), f"{r['meta'][i]['shot']} {plan['shots'][i // per_shot].get('act', '')}", fill=(230, 230, 230))
    sheet.save(os.path.join(out, "sheet.png"))
    return r


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1]))
    run(plan, sys.argv[2])
