#!/usr/bin/env python3
"""Index everything we already own into the canonical library (heads, faces, bodies, accessories, facial hair, environments + parts, fx, palettes,
procedural generators). Idempotent. Records carry sha256, license, tags; nothing is invented (files that do not exist are not registered)."""
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from engine.assets import library

NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
FEMALE = {"long", "long curly", "long bangs", "bun", "bun 2", "buns", "medium 1", "medium 2", "medium 3", "medium bangs", "medium bangs 2", "medium bangs 3", "medium straight",
          "twists", "twists 2", "hijab", "bangs", "bangs 2", "bantu knots", "cornrows", "cornrows 2"}
MALE = {"flat top", "flat top long", "short 1", "short 2", "short 3", "short 4", "short 5", "mohawk", "mohawk 2", "pomp", "shaved 1", "shaved 2", "shaved 3", "gray short", "no hair 1", "no hair 2", "no hair 3"}
ELDER = {"gray bun", "gray medium", "gray short"}
OWN = dict(source="hand-authored (this project)", author="infographics-animations project", license="CC0-1.0")
PEEPS = dict(source="Open Peeps", author="Pablo Stanley", license="CC0-1.0", source_url="https://www.openpeeps.com/", proof_url="https://www.openpeeps.com/",
             download_url="https://www.openpeeps.com/ (Gumroad pay-what-you-want bundle, downloaded once)")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def rec(id_, type_, path, tags, base, **kw):
    full = os.path.join(ROOT, path)
    return dict(id=id_, type=type_, path=path, tags=sorted(set(tags)), sha256=library.sha256_file(full), downloaded_at=NOW, style="ink-flat", status="REGISTERED", status_reason="ok",
                commercial_use=True, attribution_required=False, share_alike=False, modification_allowed=True, **base, **kw)


def main():
    lib = library.load()
    n = 0
    for group, typ in (("head", "head"), ("face", "face"), ("body", "body"), ("accessories", "accessory"), ("facial-hair", "facial_hair")):
        for f in sorted(glob.glob(os.path.join(ATOMS, group, "*.svg"))):
            name = os.path.basename(f)[:-4].replace("* ", "")
            key = name.lower()
            tags = [typ, "openpeeps", "svg", "layered"]
            if group == "head":
                tags += ["hair", "female" if key in FEMALE else "male" if key in MALE else "unisex"] + (["elder"] if key in ELDER else ["adult"])
                if "hat" in key or key in ("turban", "hijab"):
                    tags.append("headwear")
            if group == "body":
                tags += ["clothing_top", "arms"] + (["holds_phone"] if key == "device" else ["holds_mug"] if key == "coffee" else ["holds_laptop"] if key == "macbook" else ["holds_paper"] if key == "paper" else [])
            if group == "face":
                tags += ["expression"]
            lib, _ = library.add(rec(f"peeps_{typ}_{slug(name)}", typ, os.path.relpath(f, ROOT), tags, PEEPS), lib)
            n += 1
    for f in sorted(glob.glob(os.path.join(ATOMS, "a person", "*.svg"))):
        lib, _ = library.add(rec(f"peeps_character_{slug(os.path.basename(f)[:-4])}", "character", os.path.relpath(f, ROOT), ["character", "openpeeps", "composite"], PEEPS), lib)
        n += 1
    for f in sorted(glob.glob(os.path.join(ROOT, "assets/environment/generated/*/*.svg"))):
        set_id, part = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-4]
        tags = ["environment_part", set_id, part] + (["foreground"] if part.endswith("_fg") else [])
        lib, _ = library.add(rec(f"envpart_{set_id}_{part}", "environment_part", os.path.relpath(f, ROOT), tags, OWN, generator="asset_pipeline.set_art / room_art"), lib)
        n += 1
    for f in sorted(glob.glob(os.path.join(ROOT, "assets/character/cast/*.svg"))):
        lib, _ = library.add(rec(f"cast_{slug(os.path.basename(f)[:-4])}", "character", os.path.relpath(f, ROOT), ["character", "cast", "openpeeps-derived"], PEEPS,
                                 generator="asset_pipeline.cast_builder"), lib)
        n += 1
    # generator-backed (procedural / own) assets: hash the generator source file
    gens = [("procedural", "procedural_graphics", "engine/factory/procedural.py", ["procedural", "finance", "psychology"]),
            ("ui_screen", "ui_screens", "engine/factory/ui_screens.py", ["ui", "phone", "procedural"]),
            ("fx", "gp_fx_sprites", "engine/shorts/gp_strokes.py", ["fx", "grease_pencil", "procedural"]),
            ("character", "rig_art_layered", "asset_pipeline/rig_art.py", ["character", "layered", "torso", "arms", "hands", "face_features"])]
    for typ, name, path, tags in gens:
        lib, _ = library.add(rec(f"gen_{name}", typ, path, tags, OWN, generator=path.replace("/", ".")[:-3]), lib)
        n += 1
    library.save(lib)
    return n, lib


if __name__ == "__main__":
    n, lib = main()
    from collections import Counter
    print(n, "records processed; library now", len(lib["assets"]), dict(Counter(a["type"] for a in lib["assets"])))
    print("statuses", dict(Counter(a["status"] for a in lib["assets"])))
