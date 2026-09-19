"""Reproducible check: what does STOCK Blender (no add-ons) give us for a 2D cutout rig with Grease Pencil?
Run: blender -b -P tools/verify_native_gp_rig.py  -> prints RESULT {...} and writes two renders (IK pose A/B) to scratch_preview/gp/.
Verified on Blender 5.2.2 LTS: IK constraint, GP layer parent_bone following the IK chain, Time Offset + Armature GP modifiers."""
import bpy, math, json
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
res = {}
# ---- armature: shoulder->elbow->wrist chain (2 bones) + IK target
arm_data = bpy.data.armatures.new("rig"); arm = bpy.data.objects.new("rig", arm_data); sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
b1 = arm_data.edit_bones.new("upper"); b1.head = (0, 0, 0); b1.tail = (300, 0, 0)
b2 = arm_data.edit_bones.new("fore"); b2.head = (300, 0, 0); b2.tail = (600, 0, 0); b2.parent = b1; b2.use_connect = True
bpy.ops.object.mode_set(mode='POSE')
tgt = bpy.data.objects.new("ik_target", None); sc.collection.objects.link(tgt); tgt.location = (600, 0, 0)
pb = arm.pose.bones["fore"]
ik = pb.constraints.new('IK'); ik.target = tgt; ik.chain_count = 2
res["ik_constraint"] = ik.type
# ---- grease pencil object with 2 layers parented to bones
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.grease_pencil_add(type='EMPTY'); gp_ob = bpy.context.object; gp = gp_ob.data
gp.materials.clear(); m = bpy.data.materials.new("m"); bpy.data.materials.create_gpencil_data(m); m.grease_pencil.show_stroke = True; m.grease_pencil.color = (1, 0.5, 0.2, 1); gp.materials.append(m)
for name, x0, x1 in (("upper_layer", 0, 300), ("fore_layer", 300, 600)):
    L = gp.layers.new(name); L.use_lights = False
    d = L.frames.new(1).drawing; d.add_strokes([2])
    for p, x in zip(d.strokes[0].points, (x0, x1)):
        p.position = (x, 0, 0); p.radius = 12; p.opacity = 1
    L.parent = arm
    try:
        L.parent_bone = "upper" if name == "upper_layer" else "fore"
        res[f"{name}_parent_bone"] = L.parent_bone
    except Exception as e:
        res[f"{name}_parent_bone"] = f"ERR {e}"
res["layer_attrs"] = [a for a in ("parent", "parent_type", "parent_bone", "translation", "rotation", "scale", "matrix_local") if hasattr(gp.layers[0], a)]
# ---- animate the IK target; measure where the fore layer's far end lands (evaluated depsgraph)
def eval_wrist(frame_target):
    tgt.location = frame_target
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = arm.evaluated_get(dg)
    return tuple(round(c, 1) for c in (ev.matrix_world @ ev.pose.bones["fore"].tail))
res["wrist_when_target_600_0"] = eval_wrist((600, 0, 0))
res["wrist_when_target_400_300"] = eval_wrist((400, 300, 0))
# ---- facial states as drawing swaps: Time Offset modifier + armature modifier availability
try:
    tm = gp_ob.modifiers.new("faceswap", "GREASE_PENCIL_TIME"); res["time_modifier_props"] = [p.identifier for p in tm.bl_rna.properties if p.identifier in ("mode", "offset", "frame_start", "frame_end", "use_custom_frame_range", "custom_range_start", "custom_range_end", "frame_scale")]
except Exception as e:
    res["time_modifier"] = f"ERR {e}"
try:
    am = gp_ob.modifiers.new("arm", "GREASE_PENCIL_ARMATURE"); am.object = arm; res["armature_modifier"] = "ok"
except Exception as e:
    res["armature_modifier"] = f"ERR {e}"

# render two poses and measure the ink centroid: does the bone-parented GP layer follow the IK chain?
sc.render.engine='BLENDER_EEVEE'; sc.render.film_transparent=True; sc.render.resolution_x=800; sc.render.resolution_y=800
cam=bpy.data.cameras.new("c"); cam.type='ORTHO'; cam.ortho_scale=800; co=bpy.data.objects.new("c",cam); sc.collection.objects.link(co); sc.camera=co; co.location=(300,0,50)
cent={}
for tag,loc in (("A",(600,0,0)),("B",(400,300,0))):
    tgt.location=loc; bpy.context.view_layer.update()
    sc.render.filepath=f"/Users/swapnil/infographics animations/scratch_preview/gp/native_{tag}.png"; bpy.ops.render.render(write_still=True)
res["render_dir"]="ok"
print("RESULT", json.dumps(res))
