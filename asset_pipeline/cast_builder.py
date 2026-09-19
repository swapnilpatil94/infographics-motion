"""Builds the CAST: every (character x body x face) SVG the film planner may pick.

All parts are Open Peeps (CC0) atoms composited into the pre-aligned bust
frame (see bust_rig.py), so any head sits correctly on any body. A character
is (hair, facial hair, accessory); bodies are shared gesture/prop poses
("holding a phone", "pointing up", "arms crossed"...). Heads are rendered per
character x face; bodies per character x body (only differs by nothing but
file path - bodies carry no character identity - so they are shared).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asset_pipeline import compose_character as cc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
OUT = os.path.join(ROOT, "assets/character/cast")

# semantic name -> Open Peeps atom
BODIES = {"device": "Device", "coffee": "Coffee", "explaining": "Explaining", "laptop": "Macbook",
          "paper": "Paper", "pointing": "Pointing Up", "crossed": "Tee Arms Crossed", "shrug": "Whatever",
          "gaming": "Gaming", "neutral": "Tee 1", "hoodie": "Hoodie", "hug": "Sweater"}
FACES = {"calm": "Calm", "smile": "Smile", "happy": "Smile Big", "tired": "Tired", "blank": "Blank",
         "serious": "Serious", "concerned": "Concerned", "uneasy": "Concerned Fear", "shock": "Hectic",
         "fear": "Fear", "awe": "Awe", "angry": "Very Angry", "suspicious": "Suspicious", "contempt": "Contempt",
         "driven": "Driven", "explaining": "Explaining", "solemn": "Solemn", "cheeky": "Cheeky",
         "blink": "Eyes Closed"}
CHARACTERS = {
    "rahul": dict(hair="Flat Top", facial="* None", acc="* None", desc="young man, short flat-top hair"),
    "priya": dict(hair="Long", facial="* None", acc="* None", desc="young woman, long hair"),
    "uncle": dict(hair="Gray Short", facial="Moustache 1", acc="Glasses", desc="middle-aged man, grey hair, moustache, glasses"),
}


def _inner(path):
    return cc._read_atom_inner(path)


def _compose(hair, facial, acc, face, body):
    doc = open(os.path.join(ATOMS, "a person/bust.svg"), encoding="utf-8").read()
    doc = cc._replace_group(doc, "face/Smile", _inner(os.path.join(ATOMS, "face", face + ".svg")))
    hair_id = re.search(r'<g id="(head/mono/[^"]+)"', doc).group(1)
    doc = cc._replace_group(doc, hair_id, _inner(os.path.join(ATOMS, "head", hair + ".svg")))
    body_id = re.search(r'<g id="(body/mono/[^"]+)"', doc).group(1)
    doc = cc._replace_group(doc, body_id, _inner(os.path.join(ATOMS, "body", body + ".svg")))
    doc = cc._replace_group(doc, "facial-hair/*-None", _inner(os.path.join(ATOMS, "facial-hair", facial + ".svg")))
    doc = cc._replace_group(doc, "accessories/*-None", _inner(os.path.join(ATOMS, "accessories", acc + ".svg")))
    return doc, hair_id, body_id


def build_all():
    os.makedirs(OUT, exist_ok=True)
    spec = {"bodies": {}, "characters": {}}
    for name, atom in BODIES.items():        # bodies: head-less, identical for every character
        doc, hair_id, body_id = _compose("Short 1", "* None", "* None", "Calm", atom)
        for gid in (hair_id, "face/Smile" if False else None):
            pass
        body_doc = cc._replace_group(doc, hair_id, "")
        body_doc = cc._replace_group(body_doc, "face/Smile", "")
        body_doc = cc._replace_group(body_doc, "facial-hair/*-None", "")
        body_doc = cc._replace_group(body_doc, "accessories/*-None", "")
        p = os.path.join(OUT, f"body_{name}.svg")
        open(p, "w", encoding="utf-8").write(body_doc)
        spec["bodies"][name] = os.path.relpath(p, ROOT)
    for cid, c in CHARACTERS.items():
        heads = {}
        for fname, atom in FACES.items():
            doc, hair_id, body_id = _compose(c["hair"], c["facial"], c["acc"], atom, "Tee 1")
            head_doc = cc._replace_group(doc, body_id, "")
            p = os.path.join(OUT, f"{cid}_head_{fname}.svg")
            open(p, "w", encoding="utf-8").write(head_doc)
            heads[fname] = os.path.relpath(p, ROOT)
        doc, hair_id, body_id = _compose(c["hair"], c["facial"], c["acc"], "Serious", "Tee 1")   # head shell WITHOUT face features (layered rig)
        base = cc._replace_group(cc._replace_group(doc, body_id, ""), "face/Smile", "")
        bp = os.path.join(OUT, f"{cid}_head_base.svg")
        open(bp, "w", encoding="utf-8").write(base)
        spec["characters"][cid] = dict(desc=c["desc"], heads=heads, head_base=os.path.relpath(bp, ROOT))
    with open(os.path.join(OUT, "cast.json"), "w") as f:
        json.dump(spec, f, indent=2)
    return spec


if __name__ == "__main__":
    s = build_all()
    print(len(s["bodies"]), "bodies;", {k: len(v["heads"]) for k, v in s["characters"].items()}, "heads")
