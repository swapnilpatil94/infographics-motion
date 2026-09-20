"""ASSET CATALOG: every environment / character / prop / effect the renderer can use, semantic and machine-readable. The built-in part is GENERATED from the renderer's registries (so it can never list something the code
cannot draw); the library part (`assets/library/kathaya/<id>/asset.json`) holds assets created through the request -> reference -> approval -> build flow and grows over time."""
import hashlib
import json
import os

from engine.environments import locations as LOC
from engine.skeleton import lab_dna as LD, props4
from kathaya import schemas
from kathaya.renderer import manifest as MF

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIBRARY = os.path.join(ROOT, "assets/library/kathaya")
ENV_SUBJECTS = {"bedroom": ["bedroom", "bed room"], "study": ["study", "study room"], "living_room": ["living room", "drawing room", "hall"], "office": ["office", "workplace"], "classroom": ["classroom"],
                "cafe": ["cafe", "restaurant", "tea shop"], "bank": ["bank", "bank branch", "bank counter"], "shop": ["shop", "store"], "police": ["police station", "police", "cyber cell"], "atm": ["atm", "atm booth", "cash machine"],
                "call_center": ["call centre", "call center"], "street": ["street", "road", "lane"]}
PROP_SUBJECTS = {"phone": ["phone", "mobile", "smartphone", "cell phone"], "card": ["card", "debit card", "credit card", "atm card"], "money": ["money", "cash", "notes", "currency"], "document": ["document", "paper", "form", "slip", "letter"],
                 "cup": ["cup", "tea cup", "glass"], "laptop": ["laptop", "computer"], "door": ["door"], "atm": ["atm machine", "atm"], "keyboard": ["keyboard"], "bag": ["bag"], "food": ["food", "snack"], "pen": ["pen"]}


def norm(s):
    return " ".join((s or "").lower().replace("_", " ").replace("-", " ").split())


def _gender(archetype):
    a = archetype.lower()
    return "female" if ("woman" in a or "female" in a) else ("male" if ("man" in a or "shopkeeper" in a or "guard" in a) else "either")


def builtin():
    out = []
    for n, (family, times, default, _lay, aliases) in list(LOC.LOCATIONS.items()):
        if n in LOC.EXTRA or n not in ENV_SUBJECTS:                                        # library environments come from their own asset.json
            continue
        out.append(dict(id=f"env_{n}", type="environment", name=n.replace("_", " "), tags=sorted({norm(a) for a in aliases} | {family, "generic", *times}), subjects=sorted({norm(x) for x in ENV_SUBJECTS[n]} | {norm(n)}),
                        source="kathaya_procedural", license="original work (Kathaya, drawn in code)", local_path="engine/environments", status="production_ready", supports=dict(time_of_day=list(times), default_time=default, kind="generic"),
                        anchors=dict(A_stop=_lay["A_stop"], D_stop=_lay["D_stop"], handover=list(_lay["handover"])), capabilities=["stand", "walk", "sit" if _lay.get("sit") or _lay.get("D_sit_x") else "stand", "hand_over"], binding=dict(location=n)))
    for a in sorted(LD.ARCHETYPES):
        out.append(dict(id="char_" + a.replace(" ", "_").replace("-", "_"), type="character", name=a, tags=sorted(set(a.replace("-", " ").split()) | {_gender(a)}), subjects=[norm(a)], source="Open Peeps (CC0) + Kathaya rig", license="CC0-1.0 art, original rig",
                        local_path="assets/character/skeleton", status="production_ready", supports=dict(gender=_gender(a)), anchors={}, capabilities=[c["id"] for c in MF.build()["characters"]["capabilities"]][:0] or ["walk", "sit", "stand", "look_at", "talk", "reach", "hold", "hand_over", "phone_use"],
                        binding=dict(archetype=a)))
    for p in sorted(k.lower() for k in props4.PROPS):
        out.append(dict(id=f"prop_{p}", type="prop", name=p, tags=[p, "prop"], subjects=sorted({norm(x) for x in PROP_SUBJECTS.get(p, [p])} | {p}), source="kathaya_procedural", license="original work (Kathaya, drawn in code)", local_path="engine/skeleton/props4.py",
                        status="production_ready", supports={}, anchors=dict(props4.PROPS[p.upper()]) and {"grip": True}, capabilities=["hold", "use"], binding=dict(prop=p)))
    for e in MF.effects():
        out.append(dict(id="fx_" + e["id"].replace("@", "_"), type="effect", name=e["id"], tags=[e["effect"], e["anchor"]], subjects=[e["id"]], source="kathaya_procedural", license="original work (Kathaya, Grease Pencil)", local_path="engine/skeleton/scene_director.py",
                        status="production_ready", supports={}, anchors={}, capabilities=[], binding=dict(effect=e["id"])))
    return out


def library():
    out = []
    if os.path.isdir(LIBRARY):
        for d in sorted(os.listdir(LIBRARY)):
            f = os.path.join(LIBRARY, d, "asset.json")
            if os.path.exists(f):
                out.append(json.load(open(f, encoding="utf-8")))
    return out


def load():
    from kathaya.assets import library_env
    library_env.register_all()                                                             # library environments become renderable locations
    cat = dict(schema=f"kathaya.asset_catalog/{schemas.VERSION}", renderer_version=MF.renderer_version(), assets=builtin() + library())
    bad = schemas.validate("AssetCatalog", cat)
    if bad:
        raise ValueError(f"asset catalog invalid: {bad[:3]}")
    cat["catalog_hash"] = hashlib.sha1(json.dumps(cat["assets"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    return cat


def index(cat):
    return {a["id"]: a for a in cat["assets"]}


def compact(cat):
    """the catalog as the creative director reads it"""
    envs = [dict(id=a["id"], name=a["name"], subjects=a["subjects"], time_of_day=a["supports"].get("time_of_day"), kind=a["supports"].get("kind", "generic"), landmark=a.get("landmark")) for a in cat["assets"] if a["type"] == "environment" and a["status"] == "production_ready"]
    return dict(environments=envs, characters=[dict(id=a["id"], archetype=a["binding"]["archetype"], gender=a["supports"].get("gender")) for a in cat["assets"] if a["type"] == "character"],
                props=[dict(id=a["id"], name=a["name"], aliases=a["subjects"]) for a in cat["assets"] if a["type"] == "prop"])
