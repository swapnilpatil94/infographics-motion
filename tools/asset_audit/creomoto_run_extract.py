"""Extract ONE run cycle from the CC0 Creomoto stickman armature (20 frames) as joint positions relative to the hip, normalised by leg length -> assets/library/creomoto_run_cycle.json
(derived data, CC0). The cycle drives our own rig's `run` action (motion_v2.a_run): a running gait with a flight phase that the walk grammar could not produce."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
SRC = os.path.join(ROOT, "assets/raw/blender_audit/oga_stickman_fixed.blend")
BL = r'''
import bpy, json, sys
arm=[o for o in bpy.data.objects if o.type=="ARMATURE"][0]; sc=bpy.context.scene
act=[a for a in bpy.data.actions if "run" in a.name.lower()][0]
arm.animation_data_create(); arm.animation_data.action=act
out=[]
for f in range(1,21):
    sc.frame_set(f); bpy.context.view_layer.update()
    ev=arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    g=lambda n,end: [round(v,5) for v in (arm.matrix_world @ (ev.pose.bones[n].tail if end else ev.pose.bones[n].head))]
    out.append(dict(hip=g("Thigh_L",0), knee_L=g("Shin_L",0), ankle_L=g("Shin_L",1), knee_R=g("Shin_R",0), ankle_R=g("Shin_R",1), shoulder=g("Arm_L",0), elbow_L=g("Arm_L",1), wrist_L=g("Hand_L",1),
                    elbow_R=g("Arm_R",1), wrist_R=g("Hand_R",1), head_top=g("Head",1), neck=g("Neck",0), spine_base=g("Spine1",0)))
json.dump(out, open(sys.argv[sys.argv.index("--")+1],"w"))
'''


def main():
    tmp = os.path.join(ROOT, "output/tests/audit_work/creomoto/run_raw.json")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(os.path.join(os.path.dirname(tmp), "run_extract.py"), "w").write(BL)
    subprocess.run([BLENDER, "-b", "--disable-autoexec", SRC, "-P", os.path.join(os.path.dirname(tmp), "run_extract.py"), "--", tmp], capture_output=True, text=True, check=True)
    raw = json.load(open(tmp))
    # forward axis: the axis (x or y) along which the head is ahead of the hip on average
    import numpy as np
    hip = np.array([r["hip"] for r in raw])
    head = np.array([r["head_top"] for r in raw])
    d = (head - hip).mean(axis=0)
    ax = 0 if abs(d[0]) > abs(d[1]) else 1
    sg = 1.0 if d[ax] > 0 else -1.0
    leg = float(np.mean([np.linalg.norm(np.array(r["hip"]) - np.array(r["ankle_L"])) for r in raw]))
    leg_max = float(max(np.linalg.norm(np.array(r["hip"]) - np.array(r[k])) for r in raw for k in ("ankle_L", "ankle_R")))
    cyc = []
    for r in raw:
        h = np.array(r["hip"])
        rel = lambda k: [round(float((sg * (np.array(r[k])[ax] - h[ax])) / leg_max), 4), round(float((np.array(r[k])[2] - h[2]) / leg_max), 4)]
        cyc.append({k: rel(k) for k in ("ankle_L", "ankle_R", "knee_L", "knee_R", "shoulder", "elbow_L", "elbow_R", "wrist_L", "wrist_R", "head_top", "neck")} | dict(hip_z=round(float(h[2] / leg_max), 4)))
    # stance-foot backward speed (relative to hip) -> travel speed per cycle
    ankles = np.array([[c["ankle_L"][0], c["ankle_L"][1]] for c in cyc] + [[c["ankle_R"][0], c["ankle_R"][1]] for c in cyc])
    low = min(a[1] for a in ankles)
    stance_v = []
    for side in ("ankle_L", "ankle_R"):
        for i in range(len(cyc)):
            j = (i + 1) % len(cyc)
            if cyc[i][side][1] < low + 0.06 and cyc[j][side][1] < low + 0.06:
                stance_v.append(-(cyc[j][side][0] - cyc[i][side][0]) * 24.0)      # frames at 24 fps
    out = dict(source="assets/raw/blender_audit/oga_stickman_fixed.blend (OpenGameArt Creomoto stickman, CC0-1.0)", frames=len(cyc), fps=24, forward_axis="xy"[ax], leg_length_blender=round(leg_max, 4),
               stance_travel_speed_legs_per_s=round(float(np.median(stance_v)), 3) if stance_v else None, contact_frames_low=round(float(low), 4), cycle=cyc)
    os.makedirs(os.path.join(ROOT, "assets/library"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "assets/library/creomoto_run_cycle.json"), "w"))
    print(out["frames"], "frames; travel speed", out["stance_travel_speed_legs_per_s"], "legs/s; flight low ankle", out["contact_frames_low"])


if __name__ == "__main__":
    main()
