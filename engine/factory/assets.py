"""Asset completeness check BEFORE rendering.

Order (per the factory contract): registry/library first -> procedurally generated -> composed from existing assets ->
approved open source (recorded in asset_pipeline/discover.py; automatic download exists only where a source declares a direct
URL - none do yet, so acquisition plans are emitted for a human to approve) -> flagged MISSING with the shots that need it.
Never silently substitutes junk: a shot whose required asset is missing is listed with possible solutions.
"""
import json
import os

from asset_pipeline import discover
from engine.factory import procedural as PR, ui_screens
from engine.shorts import gp_strokes, sets
from engine.shorts.raster import ROOT

REG = os.path.join(ROOT, "assets/licenses/registry.json")


def check(dom, plan_shots, cast_ids, log=print):
    reg = {a["id"]: a for a in json.load(open(REG))["assets"]}
    need = {}
    add = lambda kind, name, shot: need.setdefault((kind, name), []).append(shot)
    for sh in plan_shots:
        if sh["treatment"] == "performance":
            add("environment", sh["location"], sh["id"])
            if sh.get("character_ref"):
                add("character_dna", sh["character_ref"], sh["id"])
            else:
                add("cast", sh["cast"], sh["id"])
                add("outfit", sh["outfit"], sh["id"])
            for pr in sh.get("props", []):
                add("prop", pr["prop"], sh["id"])
            if sh.get("crowd"):
                add("crowd", "ambient_crowd", sh["id"])
        elif sh["treatment"] == "insert_ui":
            add("ui_screen", sh["ui"]["screen"], sh["id"])
        elif sh["treatment"] == "procedural":
            add("procedural", sh["procedural"]["type"], sh["id"])
        for g in sh["gp"]:
            add("gp_effect", g["effect"], sh["id"])
    used, missing = [], []
    for (kind, name), shots in sorted(need.items(), key=lambda x: str(x)):
        status, how, lic = "available", "library", None
        if kind == "environment":
            e = dom["environments"].get(name)
            from engine.environments import factory as EF
            if not e or (e["set"] not in sets.SETS and e["set"] not in EF.available()):        # base sets or a buildable family
                status, how = "missing", "specialist environment art"
            else:
                lic = reg.get(f"set_{e['set']}", {}).get("license")
        elif kind == "cast":
            if not name:
                status, how = "missing", "on-screen character model"
            else:
                lic = reg.get("cast_open_peeps_v1", {}).get("license")
        elif kind == "character_dna":
            status, how = "available", "character DNA factory"
            lic = reg.get("cast_open_peeps_v1", {}).get("license")
        elif kind == "prop":
            from engine.props import factory as PF
            status, how = ("available", "prop factory (procedural)") if name in PF.PROPS else ("missing", "prop generator")
            lic = reg.get("procedural_ui_v1", {}).get("license")
        elif kind == "crowd":
            status, how = "available", "crowd factory (DNA sprites)"
            lic = reg.get("cast_open_peeps_v1", {}).get("license")
        elif kind == "outfit":
            lic = reg.get("rig_art_layered_v1", {}).get("license")
            if name not in dom["outfits"]:
                status, how = "missing", "outfit definition"
        elif kind == "ui_screen":
            status, how = ("available", "procedural UI") if name in ui_screens.SCREENS else ("missing", "UI template")
            lic = reg.get("procedural_ui_v1", {}).get("license")
        elif kind == "procedural":
            status, how = ("available", "procedural graphic") if name in PR.RENDERERS else ("missing", "procedural renderer")
            lic = reg.get("procedural_ui_v1", {}).get("license")
        elif kind == "gp_effect":
            status, how = ("available", "Blender Grease Pencil sprite bank") if name in gp_strokes.SPRITES else ("missing", "GP sprite generator")
        rec = dict(kind=kind, name=name, status=status, how=how, license=lic, required_for=shots)
        (used if status == "available" else missing).append(rec)
    reqs = []
    for m in missing:
        src = [k for k, v in discover.accepted_sources().items() if "icon" in v["verdict"].lower() or k in ("open_peeps", "humaaans")]
        reqs.append(dict(missing_asset=True, name=m["name"], kind=m["kind"], reason=m["how"], required_for=m["required_for"], priority="high",
                         possible_solutions=[f"procedurally generate ({m['kind']})", f"acquire from an approved source and register: {src}",
                                             "use a generic asset of the same kind (requires explicit --allow-fallbacks)", "add a specialist asset pack"]))
    unlicensed = [u for u in used if u["kind"] in ("environment", "cast", "outfit", "ui_screen", "procedural") and not u["license"]]
    return dict(used=used, missing=reqs, unlicensed=unlicensed, license_ok=not unlicensed)
