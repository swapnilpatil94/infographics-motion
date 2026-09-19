"""Builds a bust-shot character rig from Open Peeps atoms: the pre-aligned
"a person/bust.svg" composite with its body slot swapped for a body atom
(e.g. Device = holding a phone), its hair slot swapped, and one head SVG
per face expression. The body and head are written as SEPARATE SVGs that
share the composite's canvas/coordinate frame, so they can be rasterized
independently (head rotates on a neck pivot) yet re-align exactly.

Why this replaced the seated-pose rig: the seated pose has no hands and no
phone; the bust+Device body draws a real hand holding a real phone, which
is what the story needs, and one body keeps wardrobe consistent across
every shot.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asset_pipeline import compose_character as cc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")


def _compose(face, hair, body):
    doc = open(os.path.join(ATOMS, "a person/bust.svg"), encoding="utf-8").read()
    doc = cc._replace_group(doc, "face/Smile", cc._read_atom_inner(os.path.join(ATOMS, "face", face + ".svg")))
    hair_id = re.search(r'<g id="(head/mono/[^"]+)"', doc).group(1)
    doc = cc._replace_group(doc, hair_id, cc._read_atom_inner(os.path.join(ATOMS, "head", hair + ".svg")))
    body_id = re.search(r'<g id="(body/mono/[^"]+)"', doc).group(1)
    doc = cc._replace_group(doc, body_id, cc._read_atom_inner(os.path.join(ATOMS, "body", body + ".svg")))
    return doc, hair_id, body_id


def build(character_id, hair, body, faces, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    spec = {"character_id": character_id, "hair": hair, "body": body, "faces": {}}
    for name, atom in faces.items():
        doc, hair_id, body_id = _compose(atom, hair, body)
        head_doc = cc._replace_group(doc, body_id, "")
        p = os.path.join(out_dir, f"{character_id}_head_{name}.svg")
        open(p, "w", encoding="utf-8").write(head_doc)
        spec["faces"][name] = {"atom": atom, "svg": os.path.relpath(p, ROOT)}
        if "body" not in spec:
            pass
    doc, hair_id, body_id = _compose(next(iter(faces.values())), hair, body)
    body_doc = cc._replace_group(cc._replace_group(doc, hair_id, ""), "face/Smile", "")
    bp = os.path.join(out_dir, f"{character_id}_body.svg")
    open(bp, "w", encoding="utf-8").write(body_doc)
    spec["body_svg"] = os.path.relpath(bp, ROOT)
    return spec


if __name__ == "__main__":
    out = os.path.join(ROOT, "assets/character/normalized/rahul_bust")
    spec = build(
        "rahul", hair="Flat Top", body="Device",
        faces={"tired": "Tired", "blank": "Blank", "serious": "Serious", "concerned": "Concerned",
               "uneasy": "Concerned Fear", "shock": "Hectic", "blink": "Eyes Closed", "calm": "Calm"},
        out_dir=out,
    )
    with open(os.path.join(out, "rahul_bust_spec.json"), "w") as f:
        json.dump(spec, f, indent=2)
    print("wrote", len(spec["faces"]), "head variants + body")
