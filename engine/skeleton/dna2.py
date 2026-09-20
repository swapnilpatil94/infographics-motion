"""CHARACTER DNA v2 (schema `kathaya.character_dna/2`): a STRUCTURED, deterministic description of one person. The same skeleton supports every value.

    make(seed, role="office_worker", overrides={...}) -> dict        # same (seed, role) -> byte-identical DNA

Fields: age, gender_presentation, body{height,width,shoulder,head_size,neck,leg_ratio,build}, skin{id,hex}, hair{style,length,color}, facial_hair, eyebrows, eyes, nose, mouth,
expression, wardrobe{top,bottom,shoes,accessories,palette,pattern}, posture, silhouette, personality, palette. Heads/hair/faces come from Open Peeps (CC0) atoms;
everything below the neck is generated art in the same ink language (engine/skeleton/parts_art2.py).
"""
import hashlib
import json
import random

from engine.characters import dna as D1

SCHEMA = "kathaya.character_dna/2"
PRESENTATIONS = ("masculine", "feminine", "androgynous")
TOPS = ("tee", "shirt", "polo", "hoodie", "kurta", "sweater", "jacket")
BOTTOMS = ("jeans", "trousers", "shorts", "skirt", "salwar")
SHOES = ("sneakers", "sandals", "formal", "slippers")
ACCESSORIES = ("glasses", "watch", "bag", "backpack", "earrings", "cap")
EYE_TYPES = {"round": (1.0, 1.0, 0.0, False), "almond": (1.12, 0.85, 6.0, False), "narrow": (1.1, 0.72, 0.0, False), "wide": (0.95, 1.15, 0.0, False), "small": (0.85, 0.9, 0.0, False),
             "droopy": (1.0, 0.95, -8.0, False), "lashed": (1.0, 1.0, 3.0, True)}
BROW_TYPES = {"thin": (9, 0.0), "normal": (13, 0.3), "bold": (18, 0.2), "arched": (12, 1.0), "straight": (13, 0.0)}
MOUTH_TYPES = {"thin": (0.95, 3.6), "full": (1.0, 6.0), "wide": (1.2, 4.5), "small": (0.8, 4.5)}
PERSONALITIES = {"calm": dict(amp=0.8, speed=0.9, expr="calm"), "anxious": dict(amp=1.05, speed=1.1, expr="uneasy"), "confident": dict(amp=1.15, speed=1.1, expr="determined"),
                 "tired": dict(amp=0.7, speed=0.8, expr="tired"), "cheerful": dict(amp=1.1, speed=1.05, expr="smile"), "stern": dict(amp=0.9, speed=0.95, expr="serious")}
POSTURES = {"upright": dict(spine=0.0, head=0.0), "slouched": dict(spine=5.0, head=6.0), "confident": dict(spine=-2.0, head=-2.0), "hunched": dict(spine=9.0, head=8.0)}
# muted editorial palettes: (top, bottom, shoes, accent)
PALETTES = {
    "ink_blue": ("#5f7fae", "#2f3b55", "#23262f", "#c8a96a"), "sage": ("#8fae9c", "#4c5b56", "#3b3f47", "#d9c9a3"), "terracotta": ("#c98466", "#4a4d5a", "#2b2a2e", "#e4d2b0"),
    "mustard": ("#d3b45a", "#3d4658", "#302d2a", "#8a3f3a"), "plum": ("#8b6b99", "#3b3948", "#25232b", "#e6d4bd"), "charcoal": ("#5d6168", "#2c2f38", "#1f2026", "#c9a86a"),
    "cream": ("#eadfc6", "#5b6172", "#4a3a2c", "#6f8fb3"), "rust": ("#b0623f", "#39445a", "#2b2624", "#dcc7a0"), "teal": ("#5c9a97", "#33404d", "#262a30", "#e0c98f"),
    "rose": ("#c78d99", "#4b4c5e", "#2e2b31", "#e8dcc4"), "olive": ("#8a8f5a", "#43483b", "#2f2b24", "#d8c7a0"), "white": ("#eeeeea", "#3a4460", "#e6e6e0", "#4a6fa5")}
PATTERNS = ("plain", "plain", "plain", "stripes", "check", "seeds")

ROLES = {   # role -> (age range, presentation weights, tops, bottoms, shoes, accessory odds)
    "young_man": ((17, 29), "masculine", ("tee", "hoodie", "polo", "shirt"), ("jeans", "trousers", "shorts"), ("sneakers", "sneakers", "formal"), dict(watch=.3, backpack=.3, cap=.25, glasses=.2)),
    "young_woman": ((17, 29), "feminine", ("tee", "kurta", "hoodie", "shirt", "sweater"), ("jeans", "skirt", "salwar", "trousers"), ("sneakers", "sandals", "slippers"), dict(earrings=.6, bag=.4, glasses=.25)),
    "middle_aged_man": ((36, 54), "masculine", ("shirt", "polo", "sweater", "jacket", "kurta"), ("trousers", "jeans"), ("formal", "sneakers", "sandals"), dict(watch=.5, glasses=.4, bag=.25)),
    "middle_aged_woman": ((36, 54), "feminine", ("kurta", "shirt", "sweater", "jacket"), ("salwar", "trousers", "skirt", "jeans"), ("sandals", "slippers", "formal"), dict(earrings=.7, bag=.5, glasses=.3)),
    "elderly_man": ((60, 78), "masculine", ("kurta", "shirt", "sweater", "jacket"), ("trousers", "salwar"), ("slippers", "formal", "sandals"), dict(glasses=.6, watch=.4, cap=.15)),
    "elderly_woman": ((60, 78), "feminine", ("kurta", "sweater", "shirt"), ("salwar", "skirt", "trousers"), ("slippers", "sandals"), dict(glasses=.5, earrings=.6, bag=.3)),
    "office_worker": ((24, 45), "any", ("shirt", "polo", "jacket", "tee"), ("trousers", "jeans", "skirt"), ("formal", "sneakers"), dict(watch=.4, bag=.4, glasses=.3)),
    "student": ((16, 24), "any", ("tee", "hoodie", "sweater", "shirt"), ("jeans", "shorts", "trousers"), ("sneakers", "sneakers", "sandals"), dict(backpack=.6, cap=.2, glasses=.2)),
    "shopkeeper": ((30, 60), "masculine", ("kurta", "shirt", "polo"), ("trousers", "salwar"), ("sandals", "formal", "slippers"), dict(watch=.3, glasses=.2)),
    "banker": ((28, 56), "any", ("shirt", "jacket"), ("trousers", "skirt"), ("formal",), dict(watch=.6, glasses=.4)),
    # v3.6 (asset audit): roles the factory was asked for but did not have. Appended: the seeded streams of the roles above are untouched (stream key = seed + role name).
    "delivery_worker": ((20, 42), "masculine", ("tee", "polo", "jacket"), ("trousers", "jeans"), ("sneakers",), dict(backpack=.85, cap=.6, watch=.2)),
    "security_guard": ((30, 58), "masculine", ("shirt", "jacket"), ("trousers",), ("formal",), dict(cap=.75, watch=.3)),
    "teacher": ((28, 58), "any", ("kurta", "shirt", "sweater"), ("trousers", "salwar"), ("formal", "sandals"), dict(glasses=.6, bag=.6, watch=.3)),
    "parent": ((34, 54), "any", ("kurta", "shirt", "sweater", "polo"), ("trousers", "salwar", "jeans"), ("sandals", "slippers", "formal"), dict(bag=.5, glasses=.3, earrings=.4)),
    "customer": ((20, 62), "any", ("tee", "shirt", "kurta", "hoodie", "polo"), ("jeans", "trousers", "salwar", "skirt"), ("sneakers", "sandals", "formal"), dict(bag=.5, backpack=.2, glasses=.25)),
}

# Open Peeps atoms the factory could not reach before the audit. They are NOT in the seeded pools above (that would change every existing character); they are used through `overrides` / lab_dna.
EXTRA_HAIR_MASC = {"Turban", "Mohawk 2", "Shaved 3", "No Hair 2", "No Hair 3", "hat-beanie", "hat-hip"}
EXTRA_HAIR_FEM = {"Twists", "Twists 2"}
NOVELTY_HAIR = {"Bear"}                                   # a bear costume head: never used for documentary casts
ALL_FACIAL = ("* None", "Chin", "Full", "Full 2", "Full 3", "Full 4", "Goatee 1", "Goatee 2", "Moustache 1", "Moustache 2", "Moustache 3", "Moustache 4", "Moustache 5", "Moustache 6", "Moustache 7", "Moustache 8", "Moustache 9")
ALL_GLASSES = ("* None", "Glasses", "Glasses 2", "Glasses 3", "Glasses 4", "Glasses 5", "Sunglasses", "Sunglasses 2")
EXTRA_HAIR_LEN = {"Turban": "covered", "hat-beanie": "covered", "hat-hip": "covered", "Mohawk 2": "short", "Shaved 3": "buzz", "No Hair 2": "bald", "No Hair 3": "bald", "Twists": "medium", "Twists 2": "long"}
EXTRA_PALETTES = {"khaki": ("#c2b280", "#5b5a48", "#2b2a26", "#8a3f3a"), "navy": ("#3f5a8a", "#252d44", "#1f2026", "#d9c9a3"), "maroon": ("#8a3f4a", "#3b3948", "#25232b", "#e6d4bd"),
                  "saffron": ("#e08a2e", "#4a4d5a", "#2b2a2e", "#f0e4c8"), "grey_blue": ("#7f95ad", "#3a4460", "#26282e", "#d8c7a0")}

FEM_HAIR = {"Long", "Long Curly", "Long Bangs", "Bun", "Bun 2", "Buns", "Medium 1", "Medium 2", "Medium 3", "Medium Bangs", "Medium Bangs 2", "Medium Bangs 3", "Medium Straight", "Gray Bun", "Bangs 2", "Bangs",
            "Bantu Knots", "Long Afro", "Cornrows 2", "Hijab"}
MASC_HAIR = {"Flat Top", "Flat Top Long", "Short 1", "Short 2", "Short 3", "Short 4", "Short 5", "Mohawk", "Pomp", "Shaved 1", "Shaved 2", "Gray Short", "No Hair 1", "Afro", "Cornrows"}
HAIR_LEN = {"Shaved 1": "buzz", "Shaved 2": "buzz", "No Hair 1": "bald", "Flat Top": "short", "Short 1": "short", "Short 2": "short", "Short 3": "short", "Short 4": "short", "Short 5": "short", "Pomp": "short",
            "Mohawk": "short", "Gray Short": "short", "Afro": "medium", "Cornrows": "medium", "Flat Top Long": "medium", "Bangs": "medium", "Bangs 2": "medium", "Medium 1": "medium", "Medium 2": "medium",
            "Medium 3": "medium", "Medium Bangs": "medium", "Medium Bangs 2": "medium", "Medium Bangs 3": "medium", "Medium Straight": "medium", "Bun": "long", "Bun 2": "long", "Buns": "long", "Gray Bun": "long",
            "Long": "long", "Long Curly": "long", "Long Bangs": "long", "Long Afro": "long", "Bantu Knots": "medium", "Cornrows 2": "long", "Hijab": "covered"}
HAIR_COLORS = ["#000000", "#000000", "#000000", "#2b1a12", "#3a2416", "#5a3a22"]
CAP_OK = {"Short 1", "Short 2", "Short 3", "Short 4", "Short 5", "Shaved 1", "Shaved 2", "Pomp", "Flat Top", "Gray Short", "No Hair 1"}


def _canon(d):
    return json.dumps({k: v for k, v in d.items() if k != "id"}, sort_keys=True, ensure_ascii=False)


def silhouette_name(b):
    if b["height"] > 1.04 and b["width"] < 0.95:
        return "lanky"
    if b["width"] > 1.15:
        return "stocky"
    if b["shoulder"] > 1.12 and b["width"] < 1.1:
        return "athletic"
    if b["shoulder"] < 0.95 and b["width"] > 1.0:
        return "pear"
    if b["height"] < 0.93:
        return "petite"
    return "standard"


def make(seed, role="office_worker", overrides=None):
    """Deterministic CharacterDNA v2. `overrides` may replace any top-level field (or nested via dotted keys, e.g. {"wardrobe.top": "kurta"})."""
    r = random.Random(f"dna2|{seed}|{role}")
    (a0, a1), pres, tops, bottoms, shoes, acc = ROLES[role]
    age = r.randint(a0, a1)
    if pres == "any":
        pres = r.choice(PRESENTATIONS[:2])
    fem = pres == "feminine"
    body = dict(height=round(r.uniform(0.88, 1.06) * (0.96 if fem else 1.0), 3), width=round(r.uniform(0.82, 1.28), 3), shoulder=round(r.uniform(0.86, 1.22) * (0.94 if fem else 1.0), 3),
                head_size=round(r.uniform(0.94, 1.10), 3), neck=round(r.uniform(0.8, 1.3), 3), leg_ratio=round(r.uniform(0.94, 1.06), 3))
    body["build"] = "slim" if body["width"] < 0.95 else "heavy" if body["width"] > 1.2 else "broad" if body["width"] > 1.08 else "average"
    skin = r.choice(D1.INDIAN_SKIN)
    hair_pool = [h for h in (FEM_HAIR if fem else MASC_HAIR)]
    if age > 58:
        hair_pool = ["Gray Bun", "Gray Medium", "Bun 2"] if fem else ["Gray Short", "No Hair 1", "Short 4"]
    hair = r.choice(sorted(hair_pool))
    hair_color = "#8f8f95" if age > 58 else r.choice(HAIR_COLORS)
    pal_name = r.choice(sorted(PALETTES))
    accessories = sorted({a for a, p in acc.items() if r.random() < p})
    if "cap" in accessories and hair not in CAP_OK:
        accessories.remove("cap")
    if "bag" in accessories and "backpack" in accessories:
        accessories.remove("bag")
    d = dict(schema=SCHEMA, seed=str(seed), role=role, age=age, age_group="elder" if age > 58 else "young" if age < 30 else "adult", gender_presentation=pres, body=body,
             skin=dict(id=skin, hex=D1.SKIN[skin]), hair=dict(style=hair, length=HAIR_LEN.get(hair, "medium"), color=hair_color),
             facial_hair=("* None" if fem else r.choice(["* None", "* None", "Moustache 1", "Moustache 2", "Full", "Chin"] if age > 30 else ["* None", "* None", "* None", "Moustache 1"])),
             eyebrows=r.choice(sorted(BROW_TYPES)), eyes=r.choice(sorted(EYE_TYPES) if not fem else sorted(EYE_TYPES)), nose=round(r.uniform(0.86, 1.2), 3), mouth=r.choice(sorted(MOUTH_TYPES)),
             wardrobe=dict(top=r.choice(tops), bottom=r.choice(bottoms), shoes=r.choice(shoes), accessories=accessories, palette=pal_name, pattern=r.choice(PATTERNS),
                           top_color=PALETTES[pal_name][0], bottom_color=PALETTES[pal_name][1], shoe_color=PALETTES[pal_name][2], accent=PALETTES[pal_name][3]),
             posture=r.choice(["upright", "upright", "confident", "slouched", "hunched"] if age > 50 else ["upright", "upright", "confident", "slouched"]), personality=r.choice(sorted(PERSONALITIES)))
    d["glasses"] = "Glasses" if "glasses" in accessories else "* None"
    d["silhouette"] = silhouette_name(body)
    d["palette"] = dict(name=pal_name, top=d["wardrobe"]["top_color"], bottom=d["wardrobe"]["bottom_color"], shoes=d["wardrobe"]["shoe_color"], accent=d["wardrobe"]["accent"], skin=d["skin"]["hex"])
    if d["wardrobe"]["bottom"] == "skirt" and not fem:
        d["wardrobe"]["bottom"] = "trousers"
    for k, v in (overrides or {}).items():
        cur = d
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur[p]
        cur[parts[-1]] = v
    if "wardrobe.palette" in (overrides or {}):
        pn = d["wardrobe"]["palette"]
        pal = {**PALETTES, **EXTRA_PALETTES}[pn]
        d["wardrobe"].update(top_color=pal[0], bottom_color=pal[1], shoe_color=pal[2], accent=pal[3])
    d["id"] = "cdna_" + hashlib.sha1(_canon(d).encode()).hexdigest()[:10]
    return d


def peeps_view(d):
    """The v1-style dict the Open Peeps head-shell builder needs."""
    return dict(id=d["id"], archetype=d["role"], gender="female" if d["gender_presentation"] == "feminine" else "male", age_group=d["age_group"], hair=d["hair"]["style"], facial_hair=d["facial_hair"],
                glasses=(d["glasses"] if d.get("glasses", "* None") in ALL_GLASSES and d["glasses"] != "* None" else "Glasses" if "glasses" in d["wardrobe"]["accessories"] else "* None"), skin=d["skin"]["id"], extra=[])


def validate(d):
    errs = []
    for k in ("schema", "age", "gender_presentation", "body", "skin", "hair", "eyebrows", "eyes", "nose", "mouth", "wardrobe", "posture", "silhouette", "personality", "palette"):
        if k not in d:
            errs.append(f"missing {k}")
    if errs:
        return errs
    w = d["wardrobe"]
    for val, allowed, name in ((w["top"], TOPS, "top"), (w["bottom"], BOTTOMS, "bottom"), (w["shoes"], SHOES, "shoes")):
        if val not in allowed:
            errs.append(f"{name} '{val}' not in {allowed}")
    for a in w["accessories"]:
        if a not in ACCESSORIES:
            errs.append(f"accessory '{a}' unknown")
    if d["eyes"] not in EYE_TYPES or d["eyebrows"] not in BROW_TYPES or d["mouth"] not in MOUTH_TYPES:
        errs.append("face type unknown")
    if d["posture"] not in POSTURES or d["personality"] not in PERSONALITIES:
        errs.append("posture/personality unknown")
    if d["gender_presentation"] not in PRESENTATIONS:
        errs.append("gender_presentation")
    return errs
