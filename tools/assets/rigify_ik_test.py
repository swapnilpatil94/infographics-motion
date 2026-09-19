"""IK/face test for a Rigify-generated rig (controls, not internal MCH bones): run  blender -b --disable-autoexec <file> -P rigify_ik_test.py -- <out_dir> <id> <armature>.
Sets the IK/FK switches to IK, drives foot_ik / hand_ik controls in world space and measures the DEF- (deforming) bones."""
import json
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector

OUT, AID, ARM = sys.argv[sys.argv.index("--") + 1:][:3]
ob = bpy.data.objects[ARM]
sc = bpy.context.scene
R = dict(id=AID, armature=ARM, blender=bpy.app.version_string)


def upd():
    bpy.context.view_layer.update()


def ev_pb(n):
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return e, e.pose.bones[n]


def tail(n):
    e, p = ev_pb(n)
    return e.matrix_world @ p.tail


def head(n):
    e, p = ev_pb(n)
    return e.matrix_world @ p.head


def put(n, world):
    pb = ob.pose.bones[n]
    M = pb.matrix.copy()
    M.translation = ob.matrix_world.inverted() @ Vector(world)
    pb.matrix = M
    upd()


names = set(ob.pose.bones.keys())
R["controls_found"] = {k: (k in names) for k in ("foot_ik.L", "foot_ik.R", "hand_ik.L", "hand_ik.R", "thigh_parent.L", "upper_arm_parent.L", "torso", "eye.L", "eye.R", "jaw_master", "head", "chest", "hips")}
for n in ("thigh_parent.L", "thigh_parent.R", "upper_arm_parent.L", "upper_arm_parent.R"):
    if n in names and "IK_FK" in ob.pose.bones[n].keys():
        ob.pose.bones[n]["IK_FK"] = 0.0
upd()
res = {}
try:
    up = Vector((0, 0, 1))
    f0 = {s: head(f"foot_ik.{s}") for s in "LR"}
    lat = (f0["L"] - f0["R"])
    lat.z = 0
    lat.normalize()
    fwd = up.cross(lat)
    leg_len = (head("DEF-thigh.L") - tail("DEF-shin.L")).length
    stride, lift = 0.22 * leg_len, 0.12 * leg_len
    errs, tf, tz = [], {"L": [], "R": []}, {"L": [], "R": []}
    for i in range(24):
        ph = i / 24 * 2 * math.pi
        for k, s in enumerate("LR"):
            p = ph + k * math.pi
            put(f"foot_ik.{s}", f0[s] + fwd * (stride * math.sin(p)) + up * (lift * max(0, math.cos(p))))
        for s in "LR":
            t = tail(f"DEF-foot.{s}") if f"DEF-foot.{s}" in names else tail(f"DEF-shin.{s}")
            tf[s].append(t.dot(fwd))
            tz[s].append(t.z)
            errs.append((head(f"foot_ik.{s}") - head(f"DEF-foot.{s}")).length * 100)
    res["walk"] = dict(stride=round(max(tf["L"]) - min(tf["L"]), 3), lift=round(max(tz["L"]) - min(tz["L"]), 3), foot_to_control_err_cm_max=round(max(errs), 2), alternating=abs(sum(1 for a, b in zip(tf["L"], tf["R"]) if a > b) - 12) < 8,
                       pass_ik_walk=(max(errs) < 1.5 and (max(tf["L"]) - min(tf["L"])) > 0.1 * leg_len))
    for s in "LR":
        put(f"foot_ik.{s}", f0[s])
    # sit: foot control forward by thigh length, hips lowered is done with torso control
    th = (head("DEF-thigh.L") - tail("DEF-thigh.L")).length
    hipw = head("DEF-thigh.L")
    sit = []
    for s in "LR":
        hp = head(f"DEF-thigh.{s}")
        put(f"foot_ik.{s}", hp + fwd * th - up * (leg_len - th))
        kn, ft = tail(f"DEF-thigh.{s}"), tail(f"DEF-shin.{s}")
        sit.append(round(math.degrees((hp - kn).angle(ft - kn)), 1))
    res["sit"] = dict(knee_deg=sit, pass_seated_pose=all(70 < a < 115 for a in sit))
    for s in "LR":
        put(f"foot_ik.{s}", f0[s])
    # reach
    h0 = head("hand_ik.L")
    sh = head("DEF-upper_arm.L")
    arm_len = (sh - tail("DEF-forearm.L")).length
    reach = []
    for lab, off in (("0.5L_fwd", fwd * 0.5 * arm_len), ("0.9L_fwd", fwd * 0.9 * arm_len), ("0.9L_up", up * 0.9 * arm_len)):
        put("hand_ik.L", sh + off)
        reach.append(dict(target=lab, err_cm=round((tail("DEF-forearm.L") - (sh + off)).length * 100, 2)))
    res["reach"] = dict(trials=reach, pass_reach=all(r["err_cm"] < 3.0 for r in reach))
    put("hand_ik.L", h0)
    # face
    eyes = {}
    for n in ("eye.L", "eye.R", "jaw_master"):
        if n in names:
            pb = ob.pose.bones[n]
            pb.rotation_mode = "XYZ"
    res["face"] = dict(face_control_bones=sum(1 for n in names if not n.startswith(("DEF-", "MCH-", "ORG-")) and any(k in n for k in ("brow", "lid", "lip", "eye", "cheek", "nose", "jaw", "teeth", "tongue", "ear"))), brow_controls=sum(1 for n in names if "brow" in n and not n.startswith(("DEF-", "MCH-", "ORG-"))))
    base = [v.co.copy() for m in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Human"] for v in m.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh().vertices]
    def mesh_delta():
        m = bpy.data.objects["Human"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = m.to_mesh()
        cur = [v.co.copy() for v in me.vertices]
        m.to_mesh_clear()
        return max((a - b).length for a, b in zip(base, cur))
    eye_pb = ob.pose.bones.get("eye.L")
    if eye_pb:
        best = 0
        for ax in range(3):
            old = eye_pb.rotation_euler.copy()
            e = old.copy()
            e[ax] += math.radians(30)
            eye_pb.rotation_euler = e
            upd()
            best = max(best, mesh_delta())
            eye_pb.rotation_euler = old
        upd()
        res["face"]["eye_rotation_moves_mesh"] = best > 1e-4
        res["face"]["eye_max_disp"] = round(best, 4)
    jaw = ob.pose.bones.get("jaw_master")
    if jaw:
        best = 0
        for ax in range(3):
            old = jaw.rotation_euler.copy()
            e = old.copy()
            e[ax] += math.radians(20)
            jaw.rotation_euler = e
            upd()
            best = max(best, mesh_delta())
            jaw.rotation_euler = old
        upd()
        res["face"]["jaw_rotation_moves_mesh"] = best > 1e-4
except Exception:
    res["error"] = traceback.format_exc()[-500:]
R["tests"] = res
json.dump(R, open(os.path.join(OUT, AID + "_rigify_tests.json"), "w"), indent=1, default=str)
print("RIGIFY_OK", json.dumps(res)[:1500])
