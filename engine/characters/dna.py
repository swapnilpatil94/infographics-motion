"""CHARACTER DNA factory (spec sec. 4/17): a small curated part library -> many deterministic, coherent characters.

A DNA is plain data (JSON-serialisable); the same DNA always resolves to the same rig. Parts come from the canonical asset library
(Open Peeps heads/hair/faces, accessories, facial hair) + our own layered torso/limb/hand art (asset_pipeline/rig_art.py).
Variation is seeded:   dna = make("banker", seed=story_id + character_id)   -> identical every run; another seed -> a different person.
"""
import hashlib
import json
import os
import random

from asset_pipeline import cast_builder as cb, compose_character as cc
from engine.shorts.raster import ROOT

GEN_DIR = os.path.join(ROOT, "assets/character/generated")

SKIN = {"skin_01": "#f6dcc8", "skin_02": "#eecaa6", "skin_03": "#e2b487", "skin_04": "#d29d6d", "skin_05": "#bb8256", "skin_06": "#9e6842", "skin_07": "#7f4f33", "skin_08": "#603a29"}
INDIAN_SKIN = ["skin_03", "skin_04", "skin_05", "skin_06", "skin_07"]
BODY = {"slim": dict(torso_x=0.90, head=0.98, arm=0.88), "average": dict(torso_x=1.0, head=1.0, arm=1.0), "broad": dict(torso_x=1.12, head=1.02, arm=1.1), "heavy": dict(torso_x=1.24, head=1.03, arm=1.22)}
EYES = {"eyes_round": (1.0, 1.0), "eyes_narrow": (1.1, 0.78), "eyes_wide": (0.95, 1.15), "eyes_small": (0.85, 0.9)}
BROWS = {"brows_thin": 9, "brows_normal": 13, "brows_bold": 18}
OUTFITS = {   # id -> cloth. fill is albedo (the light-map does the rest)
    "tee_white": dict(fill="#ffffff", pattern="plain", collar="crew"), "sweater_speckled": dict(fill="#ffffff", pattern="seeds", collar="crew"),
    "blazer_navy": dict(fill="#7d8fc0", pattern="plain", collar="crew"), "shirt_blue": dict(fill="#9fc0e8", pattern="plain", collar="polo"),
    "shirt_check": dict(fill="#e9d6b8", pattern="check", collar="polo"), "polo_green": dict(fill="#8fc79a", pattern="plain", collar="polo"),
    "polo_maroon": dict(fill="#c98a92", pattern="plain", collar="polo"), "kurta_cream": dict(fill="#f1e4c3", pattern="plain", collar="kurta"),
    "kurta_teal": dict(fill="#8fc7c0", pattern="plain", collar="kurta"), "stripes_orange": dict(fill="#f1c79a", pattern="stripes", collar="crew"),
    "hoodie_grey": dict(fill="#c9ccd4", pattern="plain", collar="crew"), "uniform_khaki": dict(fill="#cdbb8b", pattern="plain", collar="polo", badge=True, epaulettes=True),
    "blouse_rose": dict(fill="#e6a8b4", pattern="plain", collar="crew"), "top_mustard": dict(fill="#e3c46a", pattern="plain", collar="crew"),
    "shirt_white_polo": dict(fill="#f4f4f4", pattern="plain", collar="polo")}
_F = {"male", "female"}
ARCHETYPES = {
    "young_man": dict(gender="male", age="young", hair=["Flat Top", "Short 1", "Short 2", "Short 3", "Pomp", "Mohawk"], outfits=["tee_white", "sweater_speckled", "hoodie_grey", "polo_green", "stripes_orange"], body=["slim", "average"], facial=["* None"] * 3 + ["Moustache 1"], acc=["* None"] * 3 + ["Glasses"]),
    "young_woman": dict(gender="female", age="young", hair=["Long", "Long Curly", "Bun", "Medium 1", "Long Bangs", "Medium Bangs"], outfits=["blouse_rose", "top_mustard", "kurta_teal", "stripes_orange", "blazer_navy"], body=["slim", "average"], facial=["* None"], acc=["* None"] * 3 + ["Glasses 2"]),
    "middle_aged_man": dict(gender="male", age="adult", hair=["Short 4", "Short 5", "Flat Top Long", "Shaved 1"], outfits=["shirt_blue", "shirt_check", "polo_maroon", "kurta_cream"], body=["average", "broad"], facial=["Moustache 2", "Full", "* None"], acc=["* None", "Glasses 3"]),
    "middle_aged_woman": dict(gender="female", age="adult", hair=["Medium 2", "Medium 3", "Bun 2", "Medium Straight"], outfits=["kurta_teal", "blouse_rose", "top_mustard", "blazer_navy"], body=["average", "broad"], facial=["* None"], acc=["* None", "Glasses 4"]),
    "elderly_man": dict(gender="male", age="elder", hair=["Gray Short", "Gray Medium", "No Hair 1"], outfits=["kurta_cream", "shirt_check", "sweater_speckled"], body=["slim", "average"], facial=["Moustache 1", "Full 2", "Chin"], acc=["Glasses", "Glasses 2"]),
    "elderly_woman": dict(gender="female", age="elder", hair=["Gray Bun", "Gray Medium"], outfits=["kurta_cream", "blouse_rose", "kurta_teal"], body=["average", "broad"], facial=["* None"], acc=["Glasses 3", "* None"]),
    "student": dict(gender="either", age="young", hair=["Short 2", "Bangs", "Bun", "Medium Bangs 2", "Pomp"], outfits=["hoodie_grey", "tee_white", "stripes_orange", "polo_green"], body=["slim"], facial=["* None"], acc=["* None", "Glasses 5"]),
    "office_worker": dict(gender="either", age="adult", hair=["Short 1", "Medium 1", "Bun", "Short 3", "Long"], outfits=["shirt_blue", "shirt_white_polo", "blazer_navy", "shirt_check"], body=["average"], facial=["* None"] * 2 + ["Moustache 3"], acc=["* None", "Glasses"]),
    "banker": dict(gender="either", age="adult", hair=["Short 4", "Bun 2", "Medium Straight", "Short 1"], outfits=["blazer_navy", "shirt_white_polo"], body=["average", "slim"], facial=["* None"], acc=["Glasses 2", "* None"]),
    "shopkeeper": dict(gender="male", age="adult", hair=["Short 5", "Shaved 2"], outfits=["kurta_cream", "polo_maroon", "shirt_check"], body=["broad", "heavy"], facial=["Moustache 2", "Full 3"], acc=["* None"]),
    "police_officer": dict(gender="either", age="adult", hair=["Short 1", "Bun 2"], outfits=["uniform_khaki"], body=["broad", "average"], facial=["Moustache 2", "* None"], acc=["* None"], extra=["cap"]),
    "call_centre_agent": dict(gender="either", age="young", hair=["Short 2", "Long", "Medium 1", "Bangs 2"], outfits=["polo_maroon", "shirt_blue", "top_mustard"], body=["average", "slim"], facial=["* None"], acc=["* None"], extra=["headset"]),
    "manager": dict(gender="either", age="adult", hair=["Short 4", "Medium Straight", "Bun 2"], outfits=["blazer_navy", "shirt_white_polo"], body=["average", "broad"], facial=["Moustache 3", "* None"], acc=["Glasses 3", "* None"]),
    "family_member": dict(gender="either", age="adult", hair=["Medium 2", "Short 4", "Gray Short", "Bun 2"], outfits=["kurta_cream", "kurta_teal", "sweater_speckled", "top_mustard"], body=["average", "heavy"], facial=["* None", "Moustache 1"], acc=["* None", "Glasses"]),
    "customer": dict(gender="either", age="adult", hair=["Short 3", "Long Curly", "Medium 3", "Flat Top", "Bun"], outfits=["tee_white", "hoodie_grey", "stripes_orange", "polo_green", "blouse_rose"], body=["slim", "average", "broad"], facial=["* None"] * 2 + ["Full 4"], acc=["* None", "Sunglasses"])}
FEMALE_HAIR = {"Long", "Long Curly", "Long Bangs", "Bun", "Bun 2", "Buns", "Medium 1", "Medium 2", "Medium 3", "Medium Bangs", "Medium Bangs 2", "Medium Bangs 3", "Medium Straight", "Gray Bun", "Bangs 2", "Bangs"}
MALE_HAIR = {"Flat Top", "Flat Top Long", "Short 1", "Short 2", "Short 3", "Short 4", "Short 5", "Mohawk", "Pomp", "Shaved 1", "Shaved 2", "Gray Short", "No Hair 1"}


def make(archetype, seed=0, overrides=None, gender=None):
    """Deterministic DNA from (archetype, seed). `gender` ('male'|'female') resolves 'either' archetypes and constrains hair."""
    a = ARCHETYPES[archetype]
    r = random.Random(f"{archetype}|{seed}")
    g = gender or (a["gender"] if a["gender"] in ("male", "female") else r.choice(["male", "female"]))
    strict = [h for h in a["hair"] if (h in (FEMALE_HAIR if g == "female" else MALE_HAIR))]         # gendered styles first; unclassified styles only as a last resort
    hairs = strict or [h for h in a["hair"] if h not in (MALE_HAIR if g == "female" else FEMALE_HAIR)] or a["hair"]
    dna = dict(archetype=archetype, gender=g, age_group=a["age"], body_type=r.choice(a["body"]), head="Flat Top", hair=r.choice(hairs), skin=r.choice(INDIAN_SKIN),
               eyes=r.choice(list(EYES)), eyebrows=r.choice(list(BROWS)), mouth_width=round(r.uniform(0.9, 1.1), 2), clothing=dict(top=r.choice(a["outfits"])),
               facial_hair=(r.choice(a["facial"]) if g == "male" else "* None"), glasses=r.choice(a["acc"]), extra=list(a.get("extra", [])), seed=seed)
    if overrides:
        dna.update(overrides)
    dna["id"] = "dna_" + hashlib.sha1(json.dumps({k: v for k, v in dna.items() if k != "id"}, sort_keys=True).encode()).hexdigest()[:10]
    return dna


def variations(base, seed, n):
    """n controlled variations of one archetype: different people, same social role."""
    return [make(base if isinstance(base, str) else base["archetype"], f"{seed}:{i}") for i in range(n)]


def head_svg_path(dna, face="Serious"):
    """Face-less head shell (hair + skull + neck) tinted with the DNA's skin, cached by DNA content."""
    os.makedirs(GEN_DIR, exist_ok=True)
    key = hashlib.sha1(json.dumps([dna["hair"], dna["facial_hair"], dna["glasses"], dna["skin"]]).encode()).hexdigest()[:12]
    path = os.path.join(GEN_DIR, f"head_{key}.svg")
    if not os.path.exists(path):
        doc, hair_id, body_id = cb._compose(dna["hair"], dna["facial_hair"], dna["glasses"], face, "Tee 1")
        base = cc._replace_group(cc._replace_group(doc, body_id, ""), "face/Smile", "")
        base = base.replace('fill="#FFFFFF"', f'fill="{SKIN[dna["skin"]]}"')
        open(path, "w", encoding="utf-8").write(base)
    return os.path.relpath(path, ROOT)


def outfit(dna):
    o = dict(OUTFITS[dna["clothing"]["top"]])
    o["seeds"] = o["pattern"] != "plain"
    return o


def describe(dna):
    return f"{dna['age_group']} {dna['gender']} {dna['archetype']}: {dna['hair']}, {dna['skin']}, {dna['clothing']['top']}, {dna['body_type']}"
