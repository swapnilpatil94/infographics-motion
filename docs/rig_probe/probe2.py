import bpy, sys, json, importlib, os
res = {}
sys.path.insert(0, "/tmp/rigresearch/Tiny-2D-Rig-Tools"); sys.path.insert(0, "/tmp/rigresearch/coa_tools2")
import tiny_2d_rig_tools, coa_tools2
tiny_2d_rig_tools.register(); coa_tools2.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.tiny2drig.create_2d_armature()
arm = bpy.context.object
try:
    r = bpy.ops.tiny2drig.initialize_rig()
    res["tiny_initialize_rig"] = str(r)
except Exception as e:
    res["tiny_initialize_rig"] = "FAILED %s: %s" % (type(e).__name__, str(e)[:300])
res["tiny_ik_constraints"] = [(pb.name, [c.type for c in pb.constraints]) for pb in arm.pose.bones if pb.constraints]
res["tiny_drivers"] = len(arm.animation_data.drivers) if arm.animation_data else 0
# COA Tools 2: create a sprite object from a real PNG
png = "/Users/swapnil/infographics animations/assets/character/generated"
pngs = [f for f in os.listdir(png) if f.endswith(".png")][:1] if os.path.isdir(png) else []
res["coa_ops"] = [o for o in dir(bpy.ops.coa_tools2) if not o.startswith("_")][:40]
try:
    bpy.ops.coa_tools2.create_ortho_cam()
    res["coa_create_ortho_cam"] = "ok"
except Exception as e:
    res["coa_create_ortho_cam"] = "FAILED %s: %s" % (type(e).__name__, str(e)[:200])
try:
    bpy.ops.coa_tools2.create_sprite_object()
    res["coa_create_sprite_object"] = "ok"
except Exception as e:
    res["coa_create_sprite_object"] = "FAILED %s: %s" % (type(e).__name__, str(e)[:200])
res["coa_objects"] = [(o.name, o.type) for o in bpy.data.objects]
print("PROBE2", json.dumps(res, default=str))
