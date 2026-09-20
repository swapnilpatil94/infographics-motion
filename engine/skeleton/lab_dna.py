"""COMBINATION MATRIX for the character factory: HEAD x HAIR x FACE x BODY x TOP x BOTTOM x SHOES x ACCESSORY x AGE, drawn from EVERY atom the audit found reachable (all 46 Open Peeps heads/hats, 17 facial hairs,
8 glasses, 20 own-work part styles) - with coherence rules so that only plausible people come out - plus the 15 archetypes and the 3 production characters.

    pool(n, seed)          -> n coherent random DNAs (unfiltered)
    select_distinct(pool)  -> a subset chosen by farthest-point sampling on STRUCTURAL features (never colour)
"""
import hashlib
import random

from engine.skeleton import dna2

AXES = ("head", "hair", "facial", "glasses", "face", "body", "top", "bottom", "shoes", "accessories", "age", "hat")


def features(d):
    """Structural descriptor of a DNA (what a viewer perceives as 'a different person'), colour-free."""
    b = d["body"]
    hair = d["hair"]["style"]
    return dict(
        head=(hair, d["gender_presentation"]),
        hair=(dna2.HAIR_LEN.get(hair, dna2.EXTRA_HAIR_LEN.get(hair, "medium")),),
        facial=d["facial_hair"],
        glasses=d["glasses"] if d.get("glasses") else "* None",
        face=(d["eyes"], d["eyebrows"], d["mouth"]),
        body=(d["silhouette"], round(b["height"] / 0.06), round(b["width"] / 0.15), round(b["shoulder"] / 0.15), round(b["neck"] / 0.25)),
        top=(d["wardrobe"]["top"], d["wardrobe"]["pattern"] if d["wardrobe"]["pattern"] != "plain" else ""),
        bottom=d["wardrobe"]["bottom"], shoes=d["wardrobe"]["shoes"],
        accessories=tuple(sorted(a for a in d["wardrobe"]["accessories"] if a != "glasses")),
        age=d["age_group"], hat=hair in ("Turban", "hat-beanie", "hat-hip") or "cap" in d["wardrobe"]["accessories"])


def distance(f1, f2):
    """number of structural axes (of 12) on which two characters differ; colour never counts"""
    return sum(1 for k in AXES if f1[k] != f2[k])


def _custom(seed, role, extra=None):
    r = random.Random(f"labpool|{seed}")
    fem = role in ("young_woman", "middle_aged_woman", "elderly_woman") or (role in ("office_worker", "banker", "teacher", "parent", "customer", "student") and r.random() < 0.5)
    base = dna2.make(seed, role)
    ov = {}
    age = base["age"]
    # ---- head / hair (every atom reachable, gendered and age-coherent)
    if age > 58:
        pool = ["Gray Bun", "Gray Medium", "Bun 2"] if fem else ["Gray Short", "No Hair 1", "No Hair 2", "Short 4", "Turban"]
    elif fem:
        pool = sorted(dna2.FEM_HAIR | dna2.EXTRA_HAIR_FEM | {"Gray Medium"} - {"Gray Bun"})
    else:
        pool = sorted((dna2.MASC_HAIR | dna2.EXTRA_HAIR_MASC) - {"Gray Short"})
    hair = r.choice(pool)
    ov["hair.style"] = hair
    ov["hair.length"] = dna2.HAIR_LEN.get(hair, dna2.EXTRA_HAIR_LEN.get(hair, "medium"))
    if hair in ("Turban", "hat-beanie", "hat-hip"):
        ov["hair.color"] = base["hair"]["color"]
    # ---- facial hair (all 17), men only; older men more
    if not fem:
        ov["facial_hair"] = r.choice(list(dna2.ALL_FACIAL) if age > 30 else ["* None", "* None", "Moustache 1", "Moustache 3", "Goatee 1"])
    # ---- glasses: 8 atoms
    ov["glasses"] = r.choice(["* None", "* None", "* None"] + [g for g in dna2.ALL_GLASSES if g != "* None"] if age > 25 else ["* None", "* None", "Glasses", "Glasses 5"])
    acc = [a for a in base["wardrobe"]["accessories"] if a != "glasses"]
    if ov["glasses"] != "* None":
        acc.append("glasses")
    if "cap" in acc and (hair not in dna2.CAP_OK):
        acc.remove("cap")
    ov["wardrobe.accessories"] = sorted(set(acc))
    # ---- wardrobe (independent axes, coherence: skirts/salwar for feminine, kurta anywhere)
    ov["wardrobe.top"] = r.choice(list(dna2.TOPS))
    ov["wardrobe.bottom"] = r.choice([b for b in dna2.BOTTOMS if not (b == "skirt" and not fem)])
    ov["wardrobe.shoes"] = r.choice(list(dna2.SHOES))
    ov["wardrobe.pattern"] = r.choice(list(dna2.PATTERNS))
    ov["wardrobe.palette"] = r.choice(sorted({**dna2.PALETTES, **dna2.EXTRA_PALETTES}))
    # ---- body proportions: wide ranges (the base draw is narrow), silhouette derived
    body = dict(height=round(r.uniform(0.86, 1.08) * (0.96 if fem else 1.0), 3), width=round(r.uniform(0.78, 1.36), 3), shoulder=round(r.uniform(0.82, 1.28) * (0.94 if fem else 1.0), 3),
                head_size=round(r.uniform(0.92, 1.12), 3), neck=round(r.uniform(0.75, 1.35), 3), leg_ratio=round(r.uniform(0.92, 1.08), 3))
    body["build"] = "slim" if body["width"] < 0.95 else "heavy" if body["width"] > 1.2 else "broad" if body["width"] > 1.08 else "average"
    ov["body"] = body
    ov["silhouette"] = dna2.silhouette_name(body)
    ov["eyes"] = r.choice(sorted(dna2.EYE_TYPES))
    ov["eyebrows"] = r.choice(sorted(dna2.BROW_TYPES))
    ov["mouth"] = r.choice(sorted(dna2.MOUTH_TYPES))
    ov["posture"] = r.choice(["upright", "confident", "slouched", "hunched"] if age > 50 else ["upright", "confident", "slouched"])
    ov.update(extra or {})
    return dna2.make(seed, role, ov)


ROLE_CYCLE = ["young_man", "young_woman", "middle_aged_man", "middle_aged_woman", "elderly_man", "elderly_woman", "office_worker", "student", "shopkeeper", "banker", "delivery_worker", "security_guard", "teacher",
              "parent", "customer"]


def pool(n, seed="lab"):
    return [_custom(f"{seed}:{i}", ROLE_CYCLE[i % len(ROLE_CYCLE)]) for i in range(n)]


def select_distinct(cands, k, min_axes=4):
    """Farthest-point sampling on structural features. Every chosen pair differs on >= min_axes of the 12 axes (colour-only variants can never be picked). -> (chosen, report)"""
    feats = [features(d) for d in cands]
    chosen = [0]
    dist = [distance(feats[0], f) for f in feats]
    while len(chosen) < k:
        best = max((i for i in range(len(cands)) if i not in chosen), key=lambda i: (dist[i], hashlib.sha1(cands[i]["id"].encode()).hexdigest()))
        if dist[best] < min_axes:
            break
        chosen.append(best)
        dist = [min(dist[i], distance(feats[best], feats[i])) for i in range(len(cands))]
    pairs = [distance(feats[a], feats[b]) for ai, a in enumerate(chosen) for b in chosen[ai + 1:]]
    rep = dict(chosen=len(chosen), min_axes_differing=min(pairs) if pairs else None, mean_axes_differing=round(sum(pairs) / max(len(pairs), 1), 2),
               pairs_with_lt6_axes=sum(1 for p in pairs if p < 6), distinct_heads=len({feats[i]["head"] for i in chosen}), distinct_body_bins=len({feats[i]["body"] for i in chosen}),
               distinct_tops=len({feats[i]["top"] for i in chosen}))
    return [cands[i] for i in chosen], rep


# ---------------------------------------------------------------------------------------------------------- 15 archetypes on the SAME rig
ARCHETYPES = {
    "young man": ("young_man", {}),
    "young woman": ("young_woman", {}),
    "middle-aged man": ("middle_aged_man", {}),
    "middle-aged woman": ("middle_aged_woman", {}),
    "older man": ("elderly_man", {"glasses": "Glasses 2", "wardrobe.accessories": ["glasses"]}),
    "older woman": ("elderly_woman", {"glasses": "Glasses 4", "wardrobe.accessories": ["glasses", "earrings"]}),
    "office worker": ("office_worker", {"wardrobe.top": "shirt", "wardrobe.bottom": "trousers", "wardrobe.shoes": "formal", "wardrobe.palette": "grey_blue", "wardrobe.pattern": "plain", "wardrobe.accessories": ["bag", "watch"]}),
    "student": ("student", {"wardrobe.top": "hoodie", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "teal", "wardrobe.pattern": "plain", "wardrobe.accessories": ["backpack"], "hair.style": "Short 2"}),
    "shopkeeper": ("shopkeeper", {"wardrobe.top": "kurta", "wardrobe.bottom": "trousers", "wardrobe.shoes": "sandals", "wardrobe.palette": "cream", "wardrobe.pattern": "plain", "facial_hair": "Moustache 2", "wardrobe.accessories": ["watch"]}),
    "bank employee": ("banker", {"wardrobe.top": "jacket", "wardrobe.bottom": "trousers", "wardrobe.shoes": "formal", "wardrobe.palette": "navy", "wardrobe.pattern": "plain", "glasses": "Glasses 3", "wardrobe.accessories": ["glasses", "watch"]}),
    "delivery worker": ("delivery_worker", {"wardrobe.top": "tee", "wardrobe.bottom": "trousers", "wardrobe.shoes": "sneakers", "wardrobe.palette": "saffron", "wardrobe.pattern": "plain", "hair.style": "Short 2", "wardrobe.accessories": ["backpack", "cap"]}),
    "parent": ("parent", {"wardrobe.top": "sweater", "wardrobe.bottom": "trousers", "wardrobe.shoes": "slippers", "wardrobe.palette": "maroon", "wardrobe.pattern": "plain", "wardrobe.accessories": ["bag"]}),
    "teacher": ("teacher", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals", "wardrobe.palette": "sage", "wardrobe.pattern": "plain", "glasses": "Glasses 4", "wardrobe.accessories": ["glasses", "bag"]}),
    "customer": ("customer", {"wardrobe.top": "polo", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "rust", "wardrobe.pattern": "plain", "wardrobe.accessories": ["bag"]}),
    "security guard": ("security_guard", {"wardrobe.top": "shirt", "wardrobe.bottom": "trousers", "wardrobe.shoes": "formal", "wardrobe.palette": "khaki", "wardrobe.pattern": "plain", "facial_hair": "Moustache 2", "hair.style": "Short 5",
                                           "wardrobe.accessories": ["cap", "watch"]}),
}


def archetype(name, seed="arch"):
    role, ov = ARCHETYPES[name]
    return dna2.make(f"{seed}:{name}", role, ov)


# ---------------------------------------------------------------------------------------------------------- 3 production characters (same rig, same grammar, visibly different art)
def production_characters():
    A = dna2.make("prod:A", "young_man", {"hair.style": "Short 4", "hair.length": "short", "facial_hair": "* None", "glasses": "* None", "wardrobe.top": "hoodie", "wardrobe.bottom": "trousers", "wardrobe.shoes": "sneakers",
                                          "wardrobe.palette": "ink_blue", "wardrobe.pattern": "plain", "wardrobe.accessories": [], "posture": "slouched", "personality": "anxious", "eyes": "round", "eyebrows": "normal",
                                          "age": 22, "age_group": "young"})
    B = dna2.make("prod:B", "middle_aged_woman", {"hair.style": "Bun 2", "hair.length": "long", "glasses": "Glasses 4", "wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals",
                                                  "wardrobe.palette": "terracotta", "wardrobe.pattern": "plain", "wardrobe.accessories": ["earrings", "glasses"], "posture": "upright", "personality": "calm",
                                                  "eyes": "almond", "eyebrows": "arched", "age": 47, "age_group": "adult"})
    C = dna2.make("prod:C", "young_woman", {"hair.style": "Long Curly", "hair.length": "long", "glasses": "* None", "wardrobe.top": "sweater", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers",
                                            "wardrobe.palette": "plum", "wardrobe.pattern": "plain", "wardrobe.accessories": ["earrings", "bag"], "posture": "confident", "personality": "cheerful", "eyes": "lashed",
                                            "eyebrows": "bold", "age": 25, "age_group": "young"})
    return dict(A=A, B=B, C=C)
