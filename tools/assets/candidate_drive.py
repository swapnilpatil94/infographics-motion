"""Drive an EXTERNAL candidate rig (IK controls) with the semantic channels sampled from OUR motion grammar and render a side-view frame strip.
blender -b --disable-autoexec <file> -P candidate_drive.py -- <out_dir> <id> <kind: stick|rigify> <armature> [flip]
This is the 'can it be converted to our pipeline' test: same script (walk -> reach -> hold), foot/hand targets + hip travel mapped by leg-length scale."""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT, AID, KIND, ARM = A[:4]
FLIP = len(A) > 4 and A[4] == "flip"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
C = json.load(open(os.path.join(ROOT, "output/tests/blender_audit/semantic_channels.json")))
ch, P, N = C["channels"], C["P"], C["frames"]
ob = bpy.data.objects[ARM]
sc = bpy.context.scene
os.makedirs(os.path.join(OUT, AID + "_drive"), exist_ok=True)
CFG = dict(stick=dict(foot="LegIK_{s}", hand="ArmIK_{s}", hip="Master", hipbone="Thigh_{s}", shin="Shin_{s}", forearm="Hand_{s}"),
           rigify=dict(foot="foot_ik.{s}", hand="hand_ik.{s}", hip="torso", hipbone="DEF-thigh.{s}", shin="DEF-foot.{s}", forearm="DEF-hand.{s}"))[KIND]
up = Vector((0, 0, 1))
if KIND == "rigify":
    for n in ("thigh_parent.L", "thigh_parent.R", "upper_arm_parent.L", "upper_arm_parent.R"):
        if n in ob.pose.bones and "IK_FK" in ob.pose.bones[n].keys():
            ob.pose.bones[n]["IK_FK"] = 0.0
# base pose: the file's own idle action frame (stashed), then the action is removed so OUR targets drive the rig
if ob.animation_data and ob.animation_data.action:
    acts = [a for a in bpy.data.actions if "idle" in a.name.lower()]
    if acts:
        ob.animation_data.action = acts[0]
        sc.frame_set(int(acts[0].frame_range[0]))
    stash = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy(), pb.scale.copy()) for pb in ob.pose.bones}
    ob.animation_data.action = None
    for pb in ob.pose.bones:
        pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = stash[pb.name]
else:
    for pb in ob.pose.bones:
        pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = (0, 0, 0), (1, 0, 0, 0), (0, 0, 0), (1, 1, 1)


def upd():
    bpy.context.view_layer.update()


def ev():
    return ob.evaluated_get(bpy.context.evaluated_depsgraph_get())


def head(n):
    e = ev()
    return e.matrix_world @ e.pose.bones[n].head


def tail(n):
    e = ev()
    return e.matrix_world @ e.pose.bones[n].tail


def put(n, world):
    pb = ob.pose.bones[n]
    M = pb.matrix.copy()
    M.translation = ob.matrix_world.inverted() @ Vector(world)
    pb.matrix = M
    upd()


upd()
c = {k: CFG[k].format(s="L") for k in ("hipbone",)}
ft = {s: head(CFG["foot"].format(s=s)) for s in "LR"}
hip_z = head(CFG["hipbone"].format(s="L")).z
hip_h = hip_z - min(v.z for v in ft.values())
hd = {s: head(CFG["hand"].format(s=s)) for s in "LR"}
hip0 = head(CFG["hip"])
lat = ft["L"] - ft["R"]
lat.z = 0
lat.normalize()
fwd = up.cross(lat).normalized()
if FLIP:
    fwd, lat = -fwd, -lat
s = hip_h / (P["hip_y"] - P["foot_h"])
R = dict(id=AID, kind=KIND, armature=ARM, scale=round(s, 4), frames=N, blender=bpy.app.version_string)
# render setup
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y = 360, 480
sc.display.shading.light = "STUDIO"
cd = bpy.data.cameras.new("_c")
cd.type = "ORTHO"
cd.ortho_scale = hip_h * 3.4
cd.clip_end = 1e5
cam = bpy.data.objects.new("_c", cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.rotation_euler = (-lat).to_track_quat("-Z", "Y").to_euler()
r0 = {k: ch[k][0] for k in ch}
err_f, err_h, planted = [], [], {"L": [], "R": []}
first_tail = {}
for f in range(N):
    dx = ch["root_x"][f] + ch["pelvis_dx"][f] - r0["root_x"] - r0["pelvis_dx"]
    dy = ch["root_y"][f] + ch["pelvis_dy"][f] - r0["root_y"] - r0["pelvis_dy"]
    put(CFG["hip"], hip0 + fwd * (s * dx) + up * (s * dy))
    for sd in "LR":
        tf = ft[sd] + fwd * (s * (ch[f"foot_{sd}_x"][f] - r0[f"foot_{sd}_x"])) + up * (s * (ch[f"foot_{sd}_y"][f] - r0[f"foot_{sd}_y"]))
        put(CFG["foot"].format(s=sd), tf)
        th = hd[sd] + fwd * (s * (ch[f"hand_{sd}_x"][f] - r0[f"hand_{sd}_x"])) + up * (s * (ch[f"hand_{sd}_y"][f] - r0[f"hand_{sd}_y"]))
        put(CFG["hand"].format(s=sd), th)
        endp = head if KIND == "rigify" else tail
        err_f.append((endp(CFG["shin"].format(s=sd)) - head(CFG["foot"].format(s=sd))).length / s)
        err_h.append((endp(CFG["forearm"].format(s=sd)) - head(CFG["hand"].format(s=sd))).length / s)
        if ch[f"foot_{sd}_y"][f] <= r0[f"foot_{sd}_y"] + 1.0:
            planted[sd].append((f, (head if KIND == "rigify" else tail)(CFG["shin"].format(s=sd)).dot(fwd)))
    cam.location = head(CFG["hip"]).copy() + lat * (hip_h * 12)
    cam.location.z = hip_z - hip_h * 0.05
    cam.location += fwd * 0.0
    sc.render.filepath = os.path.join(OUT, AID + "_drive", f"f{f:04d}.png")
    bpy.ops.render.render(write_still=True)
slip = []
for sd in "LR":
    runs, cur = [], []
    for (f, x) in planted[sd]:
        if cur and f != cur[-1][0] + 1:
            runs.append(cur)
            cur = []
        cur.append((f, x))
    if cur:
        runs.append(cur)
    slip += [max(x for _, x in r) - min(x for _, x in r) for r in runs if len(r) > 4]
R["foot_target_err_rigunits_max"] = round(max(err_f), 3)
R["foot_target_err_pct_of_hip_height_max"] = round(100 * max(err_f) * s / hip_h, 2)
R["planted_foot_slide_m_max"] = round(max(slip), 3) if slip else None
R["planted_foot_slide_pct_of_hip_height"] = round(100 * max(slip) / hip_h, 2) if slip else None
R["fwd_axis"] = [round(x, 3) for x in fwd]
R["hand_target_err_rigunits_max"] = round(max(err_h), 3)
R["hand_target_err_pct_of_hip_height_max"] = round(100 * max(err_h) * s / hip_h, 2)
R["frames_dir"] = os.path.join(OUT, AID + "_drive")
json.dump(R, open(os.path.join(OUT, AID + "_drive.json"), "w"), indent=1)
print("DRIVE_OK", json.dumps(R))
