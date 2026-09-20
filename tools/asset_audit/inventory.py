"""ASSET INVENTORY: every source/asset record we hold (registry v2 + the older library index + files on disk that no registry lists), with the fields the utilisation audit needs. Registry status is NOT trusted:
'production use' is decided from the runtime usage trace (docs/asset_audit/usage_trace.json), the atlas (openpeeps_atoms.json) and the plans of the films we actually rendered.

    PYTHONPATH=. .venv/bin/python tools/asset_audit/inventory.py  -> docs/asset_audit/inventory.json, docs/asset_audit/inventory_table.md
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

CLASSES = ["FOUNDATION", "COMPONENT", "REPLACEMENT", "RIG", "MOTION", "FACE", "HAND", "HAIR", "CLOTHING", "PROP", "ENVIRONMENT", "GREASE_PENCIL", "FX", "REFERENCE ONLY", "UNUSABLE"]

# per registry id: (classes, kind, blender, grease_pencil, rig, modifiable_note, production, reason_unused_or_note)
A = {
    "kenney_platformer_characters_v1": (["REFERENCE ONLY"], "raster PNG", "as image planes", "no", "own bone rig in a test only: one-segment limbs, baked face", "yes (CC0)", "TESTED-NOT-USED", "chibi proportions + baked face; style is a game sprite, arm/leg are one segment -> cannot carry our IK"),
    "kenney_modular_characters_v1": (["REFERENCE ONLY", "CLOTHING"], "raster PNG", "as image planes", "no", "front-view chibi wardrobe, no limb split", "yes (CC0)", "TESTED-NOT-USED", "wrong scale/style for an editorial film; wardrobe pieces are pre-shaded raster"),
    "open_peeps_flat_v1": (["FOUNDATION", "HAIR", "FACE", "COMPONENT"], "vector SVG (Sketch export)", "textured planes / SVG import", "no (SVG import -> mesh possible)", "heads/hair/facial hair/glasses -> HEAD slot (used)", "yes (CC0)", "USED (partly)", "USED: 2 of 46 heads in the trace (36 reachable in the vocabulary); the 30 face atoms, 30 bodies, 34 poses are unused - see the atlas"),
    "humaaans_site": (["COMPONENT", "CLOTHING", "REPLACEMENT"], "vector SVG-in-JS (mirror jktzes/humaaans, MIT code / CC0 art) - NOT ON DISK", "would import as textured planes", "no", "heads/hair 17, torsos 10 (with arms), legs 8 standing + 4 sitting; no separate arms", "yes", "NOT DOWNLOADED", "never downloaded (only evaluated on the web). Read via the GitHub tree: fills only (no ink), hard-coded colours, legs are separate paths -> harvestable as replacement drawings (running legs, lab coat, trench coat, wheelchair). Needs a download approval."),
    "coa_tools2": (["REFERENCE ONLY"], "code (GPL-3)", "-", "-", "architecture reference", "no (GPL)", "REFERENCE", "GPL-3: never vendored"),
    "tiny_2d_rig_tools": (["REFERENCE ONLY"], "code (no licence)", "-", "-", "-", "no", "REFERENCE", "no licence -> quarantined"),
    "puppet_mode": (["REFERENCE ONLY"], "code (no licence)", "-", "-", "-", "no", "REFERENCE", "no licence -> quarantined"),
    "skeleton_rig_frycz": (["REFERENCE ONLY"], "code (no licence)", "-", "-", "data-model idea", "no", "REFERENCE", "no licence -> quarantined"),
    "oga_creomoto_stickman_fixed_v1": (["REFERENCE ONLY", "RIG", "MOTION"], "Blender 2.71 .blend, armature + IK", "opens (converted)", "own rig replaces it", "proportions / IK pole layout / idle+run action curves as reference", "yes (CC0)", "TESTED-NOT-USED", "stickman limbs are lines; we use its proportions and gait curves only as reference (see creomoto_test)"),
    "oga_lowpoly_rigged_man_v1": (["REFERENCE ONLY"], "Blender .blend", "no", "no", "leg IK 6 cm off in our walk test", "yes (CC0)", "TESTED-NOT-USED", "fails our IK gate; blocky 3D"),
    "oga_old_lady_rigged_v1": (["REFERENCE ONLY", "RIG"], "Blender .blend, 84 bones", "opens", "no", "finger + eye/brow bone layout reference", "yes (CC0)", "TESTED-NOT-USED", "fixed sculpted dress/hair; reference for a hand/face bone layout"),
    "oga_puppet_base_rigged_v1": (["REFERENCE ONLY"], "Blender .blend (7z)", "opens", "no", "eye bones move the mesh", "yes (CC0)", "TESTED-NOT-USED", "no IK/actions"),
    "blenderstudio_gp_cutout_pepe_v1": (["GREASE_PENCIL", "FACE", "REFERENCE ONLY"], "Blender GP cutout (GPv2 -> GPv3 auto-convert)", "yes", "yes", "separate GP layers per face part + pupil layers", "yes (CC-BY-4.0, attribution)", "TESTED-NOT-USED", "pupil-in-eye technique ADOPTED (gaze_pupil_in_sclera_test); the drawings themselves are a different (3D-head GP) style"),
    "blenderstudio_gp_cutout_cowboy_v1": (["GREASE_PENCIL", "FACE", "REFERENCE ONLY"], "Blender GP cutout", "yes", "yes", "as Pepe", "yes (CC-BY-4.0)", "TESTED-NOT-USED", "as Pepe; hat/face parts are character-specific"),
    "blenderstudio_gp_cutout_boyhead282_v1": (["GREASE_PENCIL", "FACE", "REFERENCE ONLY"], "Blender GP cutout", "yes", "yes", "pupil layers + eyelid layers", "yes (CC-BY-4.0)", "TESTED (technique adopted)", "the source of the pupil-in-sclera gaze now in production (gaze_mode 'pupil')"),
    "blenderstudio_gp_brush_pack_v2": (["GREASE_PENCIL", "FX"], "Blender asset .blend (brushes/materials)", "yes", "yes", "-", "yes (CC-BY-4.0)", "TESTED-NOT-USED", "brushes need a live Blender GP session; our compositor draws GP-style FX procedurally (deterministic)"),
    "artell_mike_rig_v1": (["REFERENCE ONLY", "RIG"], "Blender .blend, 956 bones, 371 drivers", "opens only with autoexec", "no", "face/finger bone layout", "yes (CC0)", "TESTED-NOT-USED", "needs script drivers (autoexec) -> against our deterministic policy"),
    "blender_human_base_meshes_v1_4_1": (["REFERENCE ONLY"], "Blender .blend, 17 unrigged meshes", "yes", "no", "no", "yes (CC0)", "TESTED-NOT-USED", "sculpting bases; usable as pose/anatomy reference renders"),
    "mpfb2_extension_2_0_17": (["REFERENCE ONLY"], "Blender extension (GPL-3.0 code; CC0 outputs)", "yes", "no", "Rigify", "outputs CC0", "EXTERNAL TOOL", "used only as an external generator; see mpfb_pose_reference"),
    "mpfb2_generated_humans_cc0": (["REFERENCE ONLY", "RIG"], "Blender .blend (Rigify 1090 bones)", "yes", "no", "Rigify", "yes (CC0)", "TESTED (reference generator)", "reference poses/turnarounds, not the final look"),
    "blendswap_stickman_basic_rig_30507": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (login)", "Blend Swap needs an account"),
    "blendswap_2d_stickman_rig_v2_15217": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (login)", "Blend Swap needs an account"),
    "gumroad_gp_spider_rig_dantti": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (checkout)", "e-mail checkout; licence unverified"),
    "gumroad_super_stickman_ahmad": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (checkout)", "e-mail checkout; licence unverified"),
    "gumroad_gp_character_rigs_yadoob": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (checkout)", "licence unknown"),
    "quaternius_universal_base_characters": (["UNUSABLE"], "not downloaded", "-", "-", "-", "-", "BLOCKED (gated)", "itch/Patreon gate"),
    "stickman_v4gp_2d": (["UNUSABLE"], "not found", "-", "-", "-", "-", "NOT FOUND", "no such asset located"),
    "blenderstudio_gp_cutout_suzanno_v1": (["UNUSABLE"], "Blender GP cutout", "opens", "yes", "-", "NO (no licence stated)", "QUARANTINED", "downloaded for inspection only"),
    "blenderstudio_gp_cutout_simplehead_v1": (["UNUSABLE"], "Blender GP cutout", "opens", "yes", "-", "NO (no licence stated)", "QUARANTINED", "downloaded for inspection only"),
    "blenderstudio_gp_cutout_eye282_v1": (["UNUSABLE"], "Blender GP cutout", "opens", "yes", "-", "NO (no licence stated)", "QUARANTINED", "downloaded for inspection only"),
    "rgs_cc0_modular_animated_vector_characters": (["REFERENCE ONLY"], "raster PNG sprites 2048 px (42 frames per part)", "as image planes", "no", "registered parts (canvas-aligned) but game-monster style", "yes (CC0)", "TESTED-NOT-USED", "see rgs_combination_test: thick rims + cel gloss; normalising leaves generic shapes"),
    "openpeeps_device_hand_harvest_v1": (["HAND", "REPLACEMENT"], "raster masks (npy) from an Open Peeps atom", "textured plane", "hand bone", "yes (CC0)", "yes", "USED", "the real hand drawing under hold_phone"),
}
EXTRA = [
    # (id, source, url, license, local_path, classes, kind, blender, gp, rig, modifiable, production, reason)
    ("openpeeps_face_atoms_30", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/face", ["FACE", "REPLACEMENT"], "vector SVG (1 filled path each)", "textured plane", "-", "head slot: same canvas as the head shell", "yes", "TESTED -> ADOPTED AS A TEST (face_atom action)", "before this audit: only 'Serious' was read (as the composition base); 29 expression drawings were thrown away"),
    ("openpeeps_bodies_30", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/body", ["REFERENCE ONLY", "HAND"], "vector SVG (Background + Ink groups)", "textured plane", "-", "none: torso+arms+hands are one silhouette", "yes", "UNUSED (1 hand harvested)", "one hand harvested (Device); the rest need raster hand harvesting per atom"),
    ("openpeeps_poses_34", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/pose", ["REFERENCE ONLY"], "vector SVG (whole figure)", "textured plane", "-", "none", "yes", "UNUSED", "whole standing/sitting illustrations: pose REFERENCE only"),
    ("openpeeps_templates_189", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Templates", ["REFERENCE ONLY"], "vector SVG + PNG", "textured plane", "-", "none", "yes", "PARTLY (bust.svg = composition base)", "105 bust / 30 standing / 18 sitting / 36 covid templates: unused apart from the bust base"),
    ("openpeeps_head_hair_46", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/head", ["HAIR", "COMPONENT"], "vector SVG", "textured plane", "-", "HEAD slot", "yes", "USED (36 reachable, 10 unreachable)", "10 unreachable atoms include Turban, beanie, hip hat, Twists: reachable now via dna2 overrides (lab_dna)"),
    ("openpeeps_facial_hair_17", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/facial-hair", ["COMPONENT"], "vector SVG", "textured plane", "-", "HEAD slot", "yes", "USED (5 of 17 reachable)", "dna2 picks only None / Moustache 1 / Moustache 2 / Full / Chin"),
    ("openpeeps_accessories_9", "Open Peeps", "https://www.openpeeps.com/", "CC0-1.0", "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms/accessories", ["COMPONENT"], "vector SVG", "textured plane", "-", "HEAD slot", "yes", "USED (Glasses only)", "Glasses 2-5 and Sunglasses were unreachable"),
    ("own_parts_v2", "hand-authored (this project)", "-", "CC0-1.0", "engine/skeleton/parts_art2.py + hands3.py -> assets/character/skeleton/generated_v2", ["COMPONENT", "CLOTHING", "HAND"], "generated vector -> PNG (2x)", "textured planes", "-", "26-bone rig", "yes", "USED", "torso/limbs/hands/shoes/clothing (7 tops, 5 bottoms, 4 shoes, 6 accessories): the whole body below the neck is own-work"),
    ("own_environment_sets", "hand-authored (this project)", "-", "CC0-1.0", "assets/environment/generated (+ engine/environments)", ["ENVIRONMENT"], "generated SVG layers", "planes", "-", "-", "yes", "USED (bedroom_wide only for skeleton films)", "8 families exist; only bedroom_wide is scaled for full-body actors (study_room partly); the others are bust-scale"),
    ("openmoji_icons_30", "OpenMoji", "https://openmoji.org/", "CC-BY-SA-4.0", "assets/props/icons + assets/raw/openmoji", ["PROP", "FX"], "vector SVG", "planes", "-", "-", "yes (share-alike + attribution)", "USED by legacy pipeline (concept cards)", "not used by skeleton films"),
    ("noto_sans_devanagari", "Google Fonts", "https://fonts.google.com/noto/specimen/Noto+Sans+Devanagari", "OFL-1.1", "assets/typography/NotoSansDevanagari-VF.ttf", ["FX"], "variable font", "-", "-", "-", "yes", "USED (captions, UI)", "-"),
]


def dims(path):
    """(kind, n_files, size_mb, dimension summary) for a file or directory"""
    p = os.path.join(ROOT, path) if path and not os.path.isabs(path) else path
    if not p or not os.path.exists(p):
        return None, 0, 0.0, None
    files = [p] if os.path.isfile(p) else [os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs if not f.startswith(".")]
    size = sum(os.path.getsize(f) for f in files) / 1e6
    ext = {}
    for f in files:
        ext[os.path.splitext(f)[1].lower()] = ext.get(os.path.splitext(f)[1].lower(), 0) + 1
    dm = None
    for f in files[:40]:
        if f.lower().endswith(".png"):
            from PIL import Image
            try:
                dm = "x".join(map(str, Image.open(f).size)) + " px (first png)"
                break
            except Exception:
                pass
        if f.lower().endswith(".svg"):
            import re
            m = re.search(r'viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"', open(f, encoding="utf-8", errors="ignore").read(2000))
            if m:
                dm = f"{m.group(1)}x{m.group(2)} svg units (first svg)"
                break
    return ext, len(files), round(size, 1), dm


def films_used_atoms():
    """Open Peeps atoms actually present in the CAST of the films we rendered (from their plan.json)"""
    heads, fh, gl = set(), set(), set()
    plans = glob.glob(os.path.join(ROOT, "output/shorts/*/plan.json")) + glob.glob(os.path.join(ROOT, "output/shorts/topic/*/plan.json")) + glob.glob(os.path.join(ROOT, "docs/topic_evidence/*/plan.json")) + glob.glob(os.path.join(ROOT, "docs/v3_evidence/plan.json"))
    for pth in plans:
        try:
            pl = json.load(open(pth))
        except Exception:
            continue
        for c in pl.get("characters", {}).values():
            d = c.get("dna", {})
            if d.get("schema") and isinstance(d.get("hair"), dict):
                heads.add(d["hair"]["style"])
                fh.add(d.get("facial_hair", "* None"))
                gl.add(d.get("glasses", "* None"))
    return sorted(heads), sorted(fh), sorted(gl), len(plans)


def main():
    reg = json.load(open(os.path.join(ROOT, "assets/registry/asset_registry.json")))["assets"]
    rows = []
    for r in reg:
        cls, kind, blender, gp, rig, mod, prod, why = A[r["asset_id"]]
        ext, n, mb, dm = dims(r.get("local_path"))
        rows.append(dict(id=r["asset_id"], source=r["source"], url=r.get("source_url"), license=r.get("license"), local_path=r.get("local_path"), file_types=ext, n_files=n, size_mb=mb, dimensions=dm,
                         vector_or_raster=kind, blender_compat=blender, grease_pencil_compat=gp, rig_compat=rig, modifiable=mod, commercial_use=r.get("commercial_use"), classes=cls, registry_status=r.get("status"),
                         production_use=prod, reason_unused=why, downloaded=bool(r.get("local_path") and os.path.exists(os.path.join(ROOT, r["local_path"])))))
    for (i, src, url, lic, path, cls, kind, blender, gp, rig, mod, prod, why) in EXTRA:
        ext, n, mb, dm = dims(path.split(" + ")[0])
        rows.append(dict(id=i, source=src, url=url, license=lic, local_path=path, file_types=ext, n_files=n, size_mb=mb, dimensions=dm, vector_or_raster=kind, blender_compat=blender, grease_pencil_compat=gp, rig_compat=rig,
                         modifiable=mod, commercial_use=True, classes=cls, registry_status="(library index / not a registry v2 record)", production_use=prod, reason_unused=why, downloaded=True))
    trace = json.load(open(os.path.join(ROOT, "docs/asset_audit/usage_trace.json")))
    heads, fh, gl, nplans = films_used_atoms()
    out = dict(records=rows, runtime_trace_files=trace["files"], trace_scenario=trace["scenario"], films_scanned=nplans, film_atoms_used=dict(heads=heads, facial_hair=fh, glasses=gl))
    json.dump(out, open(os.path.join(ROOT, "docs/asset_audit/inventory.json"), "w"), ensure_ascii=False, indent=1)
    # markdown table
    L = ["| # | Asset / source | Source URL | Licence | Local path | Type | Size (files, MB) | Dimensions | Blender | GP | Rig | Modifiable | Commercial | Class | Production use | Why unused / note |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | `{r['id']}` | {r['url'] or '-'} | {r['license']} | `{r['local_path'] or '(not on disk)'}` | {r['vector_or_raster']} | {r['n_files']} f / {r['size_mb']} MB | {r['dimensions'] or '-'} | {r['blender_compat']} | {r['grease_pencil_compat']} | {r['rig_compat']} | "
                 f"{r['modifiable']} | {'yes' if r['commercial_use'] else 'NO'} | {', '.join(r['classes'])} | **{r['production_use']}** | {r['reason_unused']} |")
    open(os.path.join(ROOT, "docs/asset_audit/inventory_table.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(len(rows), "records; film atoms:", heads, fh, gl)


if __name__ == "__main__":
    main()
