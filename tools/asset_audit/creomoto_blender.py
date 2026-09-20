"""Creomoto stickman: (1) bone-chain proportions, (2) 8 silhouette frames of the RUN action and 6 of IDLE, side view, flat black on transparent.
blender -b --disable-autoexec oga_stickman_fixed.blend -P creomoto_blender.py -- <out_dir>"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
sc = bpy.context.scene
B = arm.data.bones
L = lambda n: round((B[n].tail_local - B[n].head_local).length, 4)
lens = dict(thigh=L("Thigh_L"), shin=L("Shin_L"), upper_arm=L("Arm_L"), forearm=L("Hand_L"), spine=sum(L(f"Spine{i}") for i in (1, 2, 3, 4)), neck=L("Neck"), head=L("Head"))
hip_h = B["Thigh_L"].head_local.z * 1.0
json.dump(dict(bone_lengths=lens, hip_height=round(hip_h, 4), n_bones=len(B)), open(os.path.join(OUT, "proportions.json"), "w"))
arm.animation_data_create()
skel = {}
for name, frames in (("run", [1, 4, 7, 10, 13, 16, 18, 20]), ("idle", [1, 20, 40, 60, 80, 100])):
    act = [a for a in bpy.data.actions if name in a.name.lower()][0]
    arm.animation_data.action = act
    for f in frames:
        sc.frame_set(f)
        bpy.context.view_layer.update()
        ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        skel[f"{name}_{f:03d}"] = {pb.name: [[round(v, 4) for v in (arm.matrix_world @ pb.head)], [round(v, 4) for v in (arm.matrix_world @ pb.tail)]] for pb in ev.pose.bones}
json.dump(skel, open(os.path.join(OUT, "skeleton_frames.json"), "w"))
