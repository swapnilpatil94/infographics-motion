"""VISUAL STYLE TABLE: measured stroke ratio (rim / part size), tone count, gloss and palette size for every production asset family and every candidate, so 'do they look like one universe' is a measurement.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/style_table.py -> docs/asset_audit/style_table.json / style_table.md
"""
import io
import json
import os
import sys

import numpy as np
import resvg_py
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rgs_lab   # noqa: E402
from asset_pipeline import cast_builder as cb   # noqa: E402
from engine.skeleton import lab_dna as LD, parts_art2 as PA2, props4 as P4   # noqa: E402


def svg_img(txt, width=700):
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=txt, width=width)))).convert("RGBA")


def main():
    base = rgs_lab.unzip()
    dna = LD.production_characters()["A"]
    man = PA2.bake2(dna, "three_quarter", "full")
    load = lambda n: Image.open(os.path.join(ROOT, man["parts"][n]["png"])).convert("RGBA")
    doc, _, _ = cb._compose("Short 1", "* None", "* None", "Serious", "Tee 1")
    rows = {
        "Open Peeps head+face (composed bust)": (rgs_lab.stats(svg_img(doc)), "monochrome ink, flat white fill, closed contours, no shading; 3/4 orthographic"),
        "own torso (generated)": (rgs_lab.stats(load("torso")), "ink outline + flat tone + one shade + fold lines; orthographic side/3-4"),
        "own hand, procedural pose": (rgs_lab.stats(load("hand_R_relaxed")), "ink outline + flat skin + shade; orthographic"),
        "own hand, harvested Open Peeps (hold_phone)": (rgs_lab.stats(load("hand_R_hold_phone")), "real Open Peeps ink drawing recoloured to the DNA skin"),
        "own face atom baked (fear)": (rgs_lab.stats(Image.open(os.path.join(ROOT, PA2.bake_face_atoms(dna, "three_quarter", ["fear"])["parts"]["faceatom_fear"]["png"])).convert("RGBA")), "Open Peeps face atom: ink only"),
        "prop glyph (test placeholder)": (rgs_lab.stats(P4.glyph("CUP")), "flat fill + ink outline drawn with PIL (placeholder)"),
        "RGS head1 (raw)": (rgs_lab.stats(rgs_lab.part(base, "Heads/head1")), "thick black rim, 3-band cel shading, specular gloss (game-monster style)"),
        "RGS head1 (normalised by rgs_lab)": (rgs_lab.stats(rgs_lab.normalise(rgs_lab.part(base, "Heads/head1"))), "flattened + thin rim: matches our ink weight; loses all form"),
        "RGS hair1 (raw)": (rgs_lab.stats(rgs_lab.part(base, "Hairs/hair1")), "as above"),
    }
    gp = os.path.join(ROOT, "docs/blender_audit/gp_boyhead_gaze_center.png")
    if os.path.exists(gp):
        rows["Blender Studio 'Boy Head' GP render"] = (rgs_lab.stats(Image.open(gp).convert("RGBA")), "3D-head Grease Pencil: thin variable-width line, soft flat tones, highlights")
    L = ["| Asset family | part px | rim px | rim/part | tones | gloss | palette | note |", "|---|---|---|---|---|---|---|---|"]
    for k, (s, n) in rows.items():
        L.append(f"| {k} | {s['part_px']} | {s['rim_px']} | {s['rim_ratio']} | {s['tones']} | {'yes' if s['gloss'] else 'no'} | {s['colours']} | {n} |")
    open(os.path.join(ROOT, "docs/asset_audit/style_table.md"), "w").write("\n".join(L) + "\n")
    json.dump({k: dict(v[0], note=v[1]) for k, v in rows.items()}, open(os.path.join(ROOT, "docs/asset_audit/style_table.json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
