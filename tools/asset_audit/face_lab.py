"""FACE SYSTEM LAB: (1) inventory of the face system, (2) 8 eye x 8 brow x 8 mouth = 512 combinations through the real rig, (3) 8 target expressions: procedural face vs Open Peeps face-atom replacement drawings,
(4) head turn front -> 3/4 -> side -> 3/4 -> front with the existing view-sets.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/face_lab.py
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, motion as M, parts_art2 as PA2   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
WORK = os.path.join(OUT, "audit_work/face")
EYES = {"neutral": dict(lid=0.05), "wide": dict(wide=1.0), "narrow": dict(narrow=0.85), "half_lid": dict(lid=0.6), "closed": dict(blink=1.0), "squint": dict(narrow=0.55, lid=0.35),
        "glance_side": dict(gaze_x=-1.0, wide=0.2), "glance_up": dict(gaze_y=1.0, wide=0.5)}
BROWS = {"neutral": {}, "raised": dict(brow_raise=1.0), "lowered": dict(brow_raise=-0.8), "angry": dict(brow_raise=-0.7, brow_tilt=-1.0), "worried": dict(brow_raise=0.5, brow_tilt=1.0),
         "asym_up": dict(brow_asym=1.0, brow_raise=0.3), "flat_low": dict(brow_raise=-0.45), "sad": dict(brow_raise=-0.15, brow_tilt=1.0)}
MOUTHS = {"closed": {}, "smile": dict(mouth_smile=0.8), "grin": dict(mouth_smile=1.0, mouth_open=0.4), "frown": dict(mouth_smile=-0.8), "worried": dict(mouth_worried=1.0), "open_small": dict(mouth_open=0.3),
          "open_wide": dict(mouth_open=0.95, vis_A=1.0), "O_shape": dict(mouth_open=0.6, vis_O=1.0)}
TARGETS = {  # expression -> (procedural EMO name, Open Peeps face-atom emotion key)
    "neutral": ("neutral", "serious"), "happy": ("happy", "smile"), "fear": ("fear", "fear"), "confusion": ("confused", "worried"), "suspicion": ("suspicious", "suspicious"),
    "anger": ("anger", "anger"), "surprise": ("surprise", "surprise"), "realization": ("realization", "dread")}


def state_from_emo(name):
    e = M.EMO[name]
    return {M.FACE_MAP[k]: v for k, v in e.items() if k in M.FACE_MAP}


def crop_face(im, box=(200, 660, 880, 1280)):
    x0, y0, x1, y1 = box
    return im[y0:y1, x0:x1]


def main():
    os.makedirs(WORK, exist_ok=True)
    t0 = time.time()
    dna = LD.production_characters()["A"]
    # ---- 512 combinations (one character, 512 frames)
    states = []
    for m_ in MOUTHS.values():
        for b_ in BROWS.values():
            for e_ in EYES.values():
                states.append({**{"blink": 0.0, "wide": 0.0, "lid": 0.0, "narrow": 0.0, "brow_raise": 0.0, "brow_tilt": 0.0, "brow_asym": 0.0, "mouth_open": 0.0, "mouth_smile": 0.0, "mouth_worried": 0.0, "gaze_x": 0.0,
                                "gaze_y": 0.0, "vis_A": 0.0, "vis_O": 0.0}, **e_, **b_, **m_})
    ims = lab.render_states(dna, states, WORK + "/matrix", focus="head", zoom=3.4)
    crops = [Image.fromarray(crop_face(i)).resize((88, 88)) for i in ims]
    # layout: 8 blocks (mouth) of 8x8 (brow rows x eye columns)
    cell = 88
    S = Image.new("RGB", (4 * 8 * cell + 5 * 10, 2 * (8 * cell + 46) + 60), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), "FACE MATRIX: 8 eye states x 8 brow states x 8 mouth states = 512 combinations, one character, real rig.  Block = mouth state; row = brow state; column = eye state.", fill=(235, 235, 235), font=lab.font(16, True))
    for mi, mname in enumerate(MOUTHS):
        bx = (mi % 4) * (8 * cell + 10) + 10
        by = 40 + (mi // 4) * (8 * cell + 46)
        d.text((bx, by), f"mouth: {mname}", fill=(255, 220, 120), font=lab.font(15, True))
        for bi in range(8):
            for ei in range(8):
                k = mi * 64 + bi * 8 + ei
                bg = Image.new("RGB", (cell - 2, cell - 2), (238, 235, 228))
                c = crops[k].convert("RGBA")
                bg.paste(c.convert("RGB"), (0, 0), c.split()[3])
                S.paste(bg, (bx + ei * cell, by + 22 + bi * cell))
    S.save(os.path.join(OUT, "face_expression_matrix.png"))
    # ---- 8 target expressions: procedural vs face atom (same head, same lighting)
    keys = list(TARGETS)
    proc = [state_from_emo(TARGETS[k][0]) for k in keys]
    atom = [dict(face_atom_id=float(PA2.FACE_ATOM_IDS[TARGETS[k][1]])) for k in keys]
    atoms_needed = sorted({TARGETS[k][1] for k in keys})
    pims = lab.render_states(dna, proc, WORK + "/proc", focus="head", zoom=3.0, atoms=atoms_needed)
    aims = lab.render_states(dna, atom, WORK + "/atom", focus="head", zoom=3.0, atoms=atoms_needed)
    W, H = 330, 360
    T = Image.new("RGB", (8 * W, 2 * H + 90), (30, 30, 34))
    dt = ImageDraw.Draw(T)
    dt.text((10, 8), "8 target expressions.  TOP: our procedural face (eye/brow/mouth channels).  BOTTOM: Open Peeps face atoms as replacement drawings (same head, same rig).", fill=(235, 235, 235), font=lab.font(16, True))
    for i, k in enumerate(keys):
        for r, ims_ in enumerate((pims, aims)):
            im = Image.fromarray(crop_face(ims_[i], (100, 560, 980, 1400))).resize((W - 6, int((W - 6) * 840 / 880)))
            bg = Image.new("RGB", (W - 4, H - 4), (238, 235, 228))
            bg.paste(im.convert("RGB"), (0, 4), im.split()[3])
            T.paste(bg, (i * W + 2, 44 + r * H))
        dt.text((i * W + 8, 44 + 2 * H + 8), f"{k}  [procedural: {TARGETS[k][0]} | atom: {PA2.FACE_ATOMS[TARGETS[k][1]]}]", fill=(235, 235, 235), font=lab.font(12))
    T.save(os.path.join(OUT, "face_expression_atoms_vs_procedural.png"))
    # ---- head turn: FRONT -> 3/4 -> SIDE -> 3/4 -> FRONT using the view-sets that exist
    seq = [("front", "FRONT"), ("three_quarter", "3/4"), ("profile", "SIDE"), ("three_quarter", "3/4"), ("front", "FRONT")]
    heads = lab.render_specs([dict(label=l, dna=dna, view=v, focus="head") for v, l in seq] + [dict(label="back", dna=dna, view="back", focus="head")], WORK + "/turn", samples=8)
    lab.sheet(heads, [l for _, l in seq] + ["BACK"], os.path.join(OUT, "head_turn_existing_assets.png"), cols=6, cell=(330, 360), crop=False,
              title="HEAD TURN with the assets we have: front -> 3/4 -> side -> 3/4 -> front (+ back). Each frame is a different view-set swap, not an interpolated turn.")
    json.dump(dict(eye_states=list(EYES), brow_states=list(BROWS), mouth_states=list(MOUTHS), combos=len(states), targets=TARGETS, face_atoms_available=len(PA2.FACE_ATOMS), seconds=round(time.time() - t0, 1)),
              open(os.path.join(ROOT, "docs/asset_audit/face_lab.json"), "w"), indent=1)
    print("done", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
