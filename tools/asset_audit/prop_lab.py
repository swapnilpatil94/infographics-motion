"""PROP INTERACTION MATRIX: 10 props x 6 phases (REACH CONTACT GRAB HOLD USE RELEASE) through the SAME hand / arm / IK system. Prop art other than phone/card/money does not exist: TEST glyphs are drawn only so a
reviewer can see where the prop is. Contact error is measured by forward kinematics on the ACTUAL channels; IK error comes from Blender.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/prop_lab.py -> output/tests/prop_interaction_matrix.png, docs/asset_audit/prop_matrix.json
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, props4 as P4   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
WORK = os.path.join(OUT, "audit_work/props")
T0 = 0.4
PROP10 = [p_ for p_ in P4.PROPS if p_ not in P4.EXTRA]


def main():
    dna = LD.production_characters()["A"]
    specs, index = [], []
    for prop in PROP10:
        for ph in P4.PHASES:
            rec_box = {}

            def setup(a, prop=prop, rec_box=rec_box):
                an = a.man["hand_anchors"]
                recs = P4.perform(a.perf, an, prop, T0, "R", False)
                if prop in ("LAPTOP", "KEYBOARD"):
                    P4.perform(a.perf, an, prop, T0, "L", True)
                rec_box["recs"] = recs
                rec_box["an"] = an
            # phase arrival time = start of the NEXT phase (the phase's own target is reached at its end)
            t_phase = T0 + sum(P4.DUR[p] for p in P4.PHASES[:P4.PHASES.index(ph)]) + P4.DUR[ph] * 0.98
            specs.append(dict(label=f"{prop} {ph}", dna=dna, view="three_quarter", t=round(t_phase, 3), focus="torso", setup=setup, dx=150.0))
            index.append((prop, ph, rec_box, t_phase))
    ims, meta = lab.render_specs(specs, WORK, samples=8, batch=15, return_meta=True)
    cell = (250, 330)
    cells, rows = [], {}
    for k, ((prop, ph, box, t), im, m) in enumerate(zip(index, ims, meta)):
        actor = m["actor"]
        rec = next(r for r in box["recs"] if r["phase"] == ph)
        an = box["an"]
        d = P4.PROPS[prop]
        # forward kinematics on the ACTUAL channels
        if ph != "RELEASE":
            fk, Hdeg = P4.grip_point(actor.perf, an, rec["pose"], "tip" if d["anchor"] == "tip" and ph != "REACH" else "grip", t)
            err = math.dist(fk, rec["target"])
        else:
            fk, err = None, 0.0
        rec["fk_error_px"] = round(err, 2)
        rows.setdefault(prop, []).append(rec)
        # glyph placement (world = rig -> stage)
        img = Image.fromarray(im).convert("RGBA")
        # held or fixed?
        fixed = prop in ("LAPTOP", "KEYBOARD", "ATM", "DOOR")
        gpos = None
        if fixed or ph in ("REACH", "CONTACT"):
            c = next(r for r in box["recs"] if r["phase"] == "CONTACT")["target"]
            gpos = c
        elif ph in ("GRAB", "HOLD", "USE"):
            gpos = fk
        else:
            gpos = next(r for r in box["recs"] if r["phase"] == "USE")["target"]
        g = P4.glyph(prop)
        wx, wy = actor.rig_to_world(*gpos)
        sx, sy = (wx - m["cx"]) * m["zoom"] + 540, (wy - m["cy"]) * m["zoom"] + 960
        gs = g.resize((int(g.width * m["zoom"] * 0.5), int(g.height * m["zoom"] * 0.5)))
        under = Image.new("RGBA", img.size, (238, 235, 228, 255))
        under.alpha_composite(gs, (int(sx - gs.width / 2), int(sy - gs.height / 2)))
        under.alpha_composite(img)
        # crop around the working area
        cx0, cy0 = int(540 - 250), int(960 - 330)
        cells.append(np.asarray(under.crop((cx0 - 40, cy0, cx0 + 620, cy0 + 800)).convert("RGBA")))
    W, H = 224, 270
    S = Image.new("RGB", (6 * W + 160, 10 * H + 70), (30, 30, 34))
    dr = ImageDraw.Draw(S)
    dr.text((10, 8), "PROP INTERACTION MATRIX: same hand/arm/IK system, 10 props x 6 phases. Glyphs are TEST placeholders (no production art exists for CUP/DOCUMENT/LAPTOP/DOOR/ATM/KEYBOARD). err = FK contact error (px).", fill=(235, 235, 235), font=lab.font(15, True))
    for i, ph in enumerate(P4.PHASES):
        dr.text((160 + i * W + 8, 36), ph, fill=(255, 220, 120), font=lab.font(15, True))
    for r, prop in enumerate(PROP10):
        dr.text((8, 60 + r * H + H // 2), prop, fill=(255, 255, 255), font=lab.font(16, True))
        for c, ph in enumerate(P4.PHASES):
            im = Image.fromarray(cells[r * 6 + c]).convert("RGB")
            im.thumbnail((W - 4, H - 24))
            S.paste(im, (160 + c * W + 2, 56 + r * H))
            rec = rows[prop][c]
            colour = (120, 220, 130) if (rec["reachable"] and rec["fk_error_px"] <= 3.0) else (240, 120, 100)
            dr.text((160 + c * W + 4, 56 + r * H + H - 20), f"err {rec['fk_error_px']:.1f}px  {'ok' if rec['reachable'] else 'OUT OF REACH'}", fill=colour, font=lab.font(12))
    S.save(os.path.join(OUT, "prop_interaction_matrix.png"))
    # IK errors from Blender reports
    ik_max = 0.0
    for dp, _, fs in os.walk(WORK):
        for f in fs:
            if f == "report.json":
                rep = json.load(open(os.path.join(dp, f)))
                for e in rep.get("ik_error_px", []):
                    ik_max = max(ik_max, max(v for k, v in e.items() if k.startswith("IK")))
    summ = {}
    for prop, recs in rows.items():
        summ[prop] = dict(pose=P4.PROPS[prop]["pose"], anchor=P4.PROPS[prop]["anchor"], note=P4.PROPS[prop]["note"],
                          phases={r["phase"]: dict(fk_contact_error_px=r["fk_error_px"], reachable=bool(r["reachable"]), hand_angle=r["H"]) for r in recs},
                          all_phases_ok=all(r["reachable"] and r["fk_error_px"] <= 3.0 for r in recs), production_art=prop in ("PHONE", "CARD", "MONEY"))
    json.dump(dict(props=summ, ik_max_error_px_blender=round(ik_max, 2), solved_generically=[p for p, s in summ.items() if s["all_phases_ok"]]), open(os.path.join(ROOT, "docs/asset_audit/prop_matrix.json"), "w"), indent=1)
    print({p: s["all_phases_ok"] for p, s in summ.items()}, "IK max", round(ik_max, 2))


if __name__ == "__main__":
    main()
