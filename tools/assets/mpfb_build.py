"""Use the MPFB2 add-on (GPL-3.0 code, CC0 assets/output) purely as an EXTERNAL generator inside Blender 5.2.2 - no MPFB code is copied into this repo.
Builds humans with different macro details, attaches the builtin rigs, optionally adds IK constraints (our own construction) and saves blends for the audit tests.
run: BLENDER_USER_EXTENSIONS=$PWD/.blender_ext blender -b --factory-startup -P mpfb_build.py -- <out_dir>
(the env var keeps the GPL add-on OUT of the user's Blender profile; it is installed from assets/raw/blender_audit/mpfb_2.0.17.zip on first run)"""
import json
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
ZIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "raw", "blender_audit", "mpfb_2.0.17.zip")


def enable_mpfb():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
    except Exception:
        pass
    if "bl_ext.user_default.mpfb" not in bpy.context.preferences.addons:                # first run: install into the (project-local) extensions repo
        bpy.ops.extensions.package_install_files(filepath=os.path.abspath(ZIP), repo="user_default", enable_on_install=True, overwrite=True)


enable_mpfb()
from bl_ext.user_default.mpfb.services.humanservice import HumanService   # noqa: E402
from bl_ext.user_default.mpfb.services.rigservice import RigService       # noqa: E402

res = dict(blender=bpy.app.version_string, humans=[], rigs={})


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    enable_mpfb()


def height(obj):
    z = [(obj.matrix_world @ Vector(c)).z for c in obj.bound_box]
    return max(z) - min(z)


def macro(**kw):
    d = dict(gender=0.5, age=0.5, muscle=0.5, weight=0.5, proportions=0.5, height=0.5, cupsize=0.5, firmness=0.5, race=dict(asian=0.33, caucasian=0.33, african=0.33))
    d.update(kw)
    return d


VARIANTS = [("young_slim_male", macro(gender=1.0, age=0.4, weight=0.3, height=0.5)), ("tall_heavy_male", macro(gender=1.0, age=0.5, weight=0.9, height=0.95)),
            ("short_female", macro(gender=0.0, age=0.5, weight=0.4, height=0.1)), ("elder_female", macro(gender=0.0, age=1.0, weight=0.6, height=0.4)), ("child", macro(gender=0.5, age=0.05, weight=0.4, height=0.5))]
# 1) parametric proportions
for nm, md in VARIANTS:
    try:
        clear()
        bm = HumanService.create_human(macro_detail_dict=md, scale=1.0)
        res["humans"].append(dict(name=nm, macro=md, height_m=round(height(bm), 3), verts=len(bm.data.vertices), shape_keys=len(bm.data.shape_keys.key_blocks) if bm.data.shape_keys else 0))
    except Exception:
        res["humans"].append(dict(name=nm, error=traceback.format_exc()[-300:]))

# 2) rigs
for rig_name in ("default", "default_no_toes", "game_engine"):
    try:
        clear()
        bm = HumanService.create_human(macro_detail_dict=macro(gender=0.0, age=0.5, height=0.5), scale=1.0)
        rig = HumanService.add_builtin_rig(bm, rig_name, import_weights=True)
        res["rigs"][rig_name] = dict(bones=len(rig.data.bones), name=rig.name, bone_sample=[b.name for b in rig.data.bones][:20])
        path = os.path.join(OUT, f"mpfb_{rig_name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        res["rigs"][rig_name]["file"] = path
        if rig_name == "default":                                                       # our own IK constraints on top (MPFB's default rig is FK)
            pbs = rig.pose.bones
            def find(pat):
                return next((p for p in pbs if p.name.lower() == pat), None)
            made = []
            for side in ("l", "r"):
                for tip, chain in ((f"lowerleg02.{side}", 2), (f"lowerarm02.{side}", 2)):
                    pb = find(tip) or find(tip.replace("02", "01"))
                    if pb is None:
                        made.append((tip, "missing"))
                        continue
                    wpos = rig.matrix_world @ pb.tail
                    e = bpy.data.objects.new(f"IKT_{pb.name}", None)
                    e.location = wpos
                    bpy.context.scene.collection.objects.link(e)
                    c = pb.constraints.new("IK")
                    c.target, c.chain_count, c.use_tail = e, chain, True
                    made.append((pb.name, "ok"))
            res["rigs"][rig_name]["ik_added"] = made
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "mpfb_default_ik.blend"))
    except Exception:
        res["rigs"][rig_name] = dict(error=traceback.format_exc()[-500:])

# 3) rigify (Blender's own add-on) path
try:
    clear()
    bpy.ops.preferences.addon_enable(module="rigify")
    bm = HumanService.create_human(macro_detail_dict=macro(gender=1.0, age=0.5, height=0.5), scale=1.0)
    meta = HumanService.add_builtin_rig(bm, "rigify.human_toes", import_weights=True)
    res["rigs"]["rigify.human_meta"] = dict(bones=len(meta.data.bones))
    try:
        gen = RigService.generate_rigify_rig(meta) if hasattr(RigService, "generate_rigify_rig") else None
        res["rigs"]["rigify.human_meta"]["generated"] = bool(gen)
        res["rigs"]["rigify.human_meta"]["generated_bones"] = len(gen.data.bones) if gen else None
    except Exception:
        res["rigs"]["rigify.human_meta"]["generate_error"] = traceback.format_exc()[-400:]
    hum = next(o for o in bpy.data.objects if o.type == "MESH" and o.name == "Human")
    res["rigs"]["rigify.human_meta"]["vertex_groups"] = len(hum.vertex_groups)
    res["rigs"]["rigify.human_meta"]["def_groups"] = sum(1 for g in hum.vertex_groups if g.name.startswith("DEF-"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "mpfb_rigify.blend"))
except Exception:
    res["rigs"]["rigify.human_meta"] = dict(error=traceback.format_exc()[-500:])

json.dump(res, open(os.path.join(OUT, "mpfb_build.json"), "w"), indent=1)
print("MPFB_OK")
