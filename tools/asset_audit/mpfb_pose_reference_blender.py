"""Blender side of the MPFB2+Rigify pose-reference test: pose the generated Rigify human with IK targets taken from OUR semantic channels (one snapshot per pose), render 4 camera angles.
blender -b --disable-autoexec mpfb_rigify.blend -P mpfb_pose_reference_blender.py -- <out_dir> <poses.json> <armature-name>"""
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

OUT, POSES, ARM = sys.argv[sys.argv.index("--") + 1:][:3]
ob = bpy.data.objects[ARM]
sc = bpy.context.scene
os.makedirs(OUT, exist_ok=True)
D = json.load(open(POSES))
P = D["P"]
up = Vector((0, 0, 1))
for n in ("thigh_parent.L", "thigh_parent.R", "upper_arm_parent.L", "upper_arm_parent.R"):
    if n in ob.pose.bones and "IK_FK" in ob.pose.bones[n].keys():
        ob.pose.bones[n]["IK_FK"] = 0.0
if ob.animation_data:
    ob.animation_data.action = None
for pb in ob.pose.bones:
    pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = (0, 0, 0), (1, 0, 0, 0), (0, 0, 0), (1, 1, 1)
# hide every other object except this human's meshes
mine = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == ob for m in o.modifiers)]
for o in bpy.data.objects:
    if o.type in ("MESH", "ARMATURE") and o not in mine and o != ob:
        o.hide_render = True
        o.hide_viewport = True
ob.hide_render = True


def upd():
    bpy.context.view_layer.update()


def ev():
    return ob.evaluated_get(bpy.context.evaluated_depsgraph_get())


def head(n):
    e = ev()
    return e.matrix_world @ e.pose.bones[n].head


def put(n, world):
    pb = ob.pose.bones[n]
    M = pb.matrix.copy()
    M.translation = ob.matrix_world.inverted() @ Vector(world)
    pb.matrix = M
    upd()


upd()
ft = {s: head(f"foot_ik.{s}") for s in "LR"}
hip_z = head("DEF-thigh.L").z
hip_h = hip_z - min(v.z for v in ft.values())
hd = {s: head(f"hand_ik.{s}") for s in "LR"}
hip0 = head("torso")
lat = ft["L"] - ft["R"]
lat.z = 0
lat.normalize()
fwd = up.cross(lat).normalized()
s = hip_h / (P["hip_y"] - P["foot_h"])
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y = 300, 460
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "OBJECT"
cd = bpy.data.cameras.new("_c")
cd.type = "ORTHO"
cd.ortho_scale = hip_h * 2.7
cd.clip_end = 1e5
cam = bpy.data.objects.new("_c", cd)
sc.collection.objects.link(cam)
sc.camera = cam
r0 = D["poses"]["stand"]
report = {}
for pname, ch in D["poses"].items():
    upd()
    dx = ch["root_x"] + ch["pelvis_dx"] - r0["root_x"] - r0["pelvis_dx"]
    dy = ch["root_y"] + ch["pelvis_dy"] - r0["root_y"] - r0["pelvis_dy"]
    put("torso", hip0 + fwd * (s * dx) + up * (s * dy))
    for sd in "LR":
        put(f"foot_ik.{sd}", ft[sd] + fwd * (s * (ch[f"foot_{sd}_x"] - r0[f"foot_{sd}_x"])) + up * (s * (ch[f"foot_{sd}_y"] - r0[f"foot_{sd}_y"])))
        put(f"hand_ik.{sd}", hd[sd] + fwd * (s * (ch[f"hand_{sd}_x"] - r0[f"hand_{sd}_x"])) + up * (s * (ch[f"hand_{sd}_y"] - r0[f"hand_{sd}_y"])))
    tb = ob.pose.bones["torso"]
    yaw = ch.get("yaw", 0.0)
    if yaw:
        tb.rotation_mode = "XYZ"
        tb.rotation_euler = (0, 0, math.radians(yaw))
        upd()
    e = {}
    for sd in "LR":
        e[f"hand_{sd}"] = round(((head(f"DEF-hand.{sd}") - head(f"hand_ik.{sd}")).length) / s, 2)
        e[f"foot_{sd}"] = round(((head(f"DEF-foot.{sd}") - head(f"foot_ik.{sd}")).length) / s, 2)
    report[pname] = e
    centre = head("torso")
    for vname, ang in (("front", 180), ("three_quarter", 135), ("side", 90), ("back", 0)):     # fwd is the +x of our rig: the camera at +fwd sees the BACK
        a = math.radians(ang)
        direction = (fwd * math.cos(a) + lat * math.sin(a))
        cam.location = centre + direction * (hip_h * 12)
        cam.location.z = hip_z - hip_h * 0.02
        cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, f"{pname}_{vname}.png")
        bpy.ops.render.render(write_still=True)
    if yaw:
        tb.rotation_euler = (0, 0, 0)
        upd()
json.dump(report, open(os.path.join(OUT, "ik_error_ref_units.json"), "w"), indent=1)
