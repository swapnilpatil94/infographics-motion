"""MPFB2 + Rigify as a POSE / TURNAROUND REFERENCE GENERATOR: our semantic channels (stand, sit, walk, reach, hold phone, turn) drive the Rigify IK controls of an MPFB human; 4 orthographic views are rendered per pose.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/mpfb_pose_reference.py -> output/tests/mpfb_pose_reference.png, docs/asset_audit/mpfb_pose_reference.json
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import dna2, motion as M, rig_def as R, lab   # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
SRC = os.path.join(ROOT, "assets/raw/blender_audit/mpfb_out/mpfb_rigify.blend")
OUT = os.path.join(ROOT, "output/tests/audit_work/mpfb_pose")
KEEP = ["root_x", "root_y", "pelvis_dx", "pelvis_dy", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y", "hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y"]


def poses():
    d = dna2.make("mpfb_ref", "young_man")
    P = R.proportions_v2(d, "profile")

    def perf(start):
        p = M.Performance(P, seed=3, world=dict(seat_h=270), facing=1, origin=(300.0, 1500.0), resolver=lambda tid, t: (300.0 + 480.0, 1500.0 - 560.0))
        (M.pose_stand if start == "stand" else M.pose_sit)(p, -1.0, 0.0) if start == "stand" else M.pose_sit(p, -1.0, seat=270)
        return p

    snaps = {}
    p = perf("stand")
    M.perform(p, "breathe", 0.0, 4.0, "neutral", 0.5)
    snaps["stand"] = {k: p.v(k, 0.1) for k in KEEP}
    p = perf("sit")
    M.perform(p, "breathe", 0.0, 4.0, "neutral", 0.5)
    snaps["sit"] = {k: p.v(k, 0.1) for k in KEEP}
    p = perf("stand")
    M.perform(p, "walk", 0.2, 2.0, "neutral", 0.6, speed=200)
    snaps["walk"] = {k: p.v(k, 0.95) for k in KEEP}
    p = perf("stand")
    M.perform(p, "reach", 0.2, 1.2, "curious", 0.7, target="PHONE", grip="grab")
    snaps["reach"] = {k: p.v(k, 1.45) for k in KEEP}
    p = perf("stand")
    M.perform(p, "hold_phone", 0.2, 1.0, "neutral", 0.5, pos="chest")
    snaps["hold_phone"] = {k: p.v(k, 1.3) for k in KEEP}
    p = perf("stand")
    snaps["turn"] = dict(snaps["stand"], yaw=60.0)
    return dict(P={k: P[k] for k in ("hip_y", "thigh", "shin", "upper_arm", "forearm", "foot_h", "torso", "k")}, poses=snaps)


def main():
    os.makedirs(OUT, exist_ok=True)
    pj = os.path.join(OUT, "poses.json")
    data = poses()
    json.dump(data, open(pj, "w"))
    arms = subprocess.run([BLENDER, "-b", "--disable-autoexec", SRC, "--python-expr", "import bpy;print('ARMS',[o.name for o in bpy.data.objects if o.type=='ARMATURE'])"], capture_output=True, text=True).stdout
    line = [l for l in arms.splitlines() if l.startswith("ARMS")][0]
    names = eval(line[5:])
    print("armatures", names)
    rigify = [n for n in names if n.endswith(".rigify")][0]
    r = subprocess.run([BLENDER, "-b", "--disable-autoexec", SRC, "-P", os.path.join(ROOT, "tools/asset_audit/mpfb_pose_reference_blender.py"), "--", OUT, pj, rigify], capture_output=True, text=True)
    if not os.path.exists(os.path.join(OUT, "stand_front.png")):
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("blender failed")
    views = ["front", "three_quarter", "side", "back"]
    pose_names = list(data["poses"])
    cw, ch = 300, 460
    S = Image.new("RGB", (len(views) * cw, len(pose_names) * ch + 60), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), "MPFB2 + Rigify as a reference generator: our semantic channels drive the Rigify IK; 4 views per pose (front / 3/4 / side / back). Workbench render: REFERENCE only, not the film's look.", fill=(235, 235, 235), font=lab.font(15, True))
    for r_, pn in enumerate(pose_names):
        for c_, v in enumerate(views):
            im = Image.open(os.path.join(OUT, f"{pn}_{v}.png")).convert("RGB")
            S.paste(im, (c_ * cw, 40 + r_ * ch))
            d.text((c_ * cw + 8, 44 + r_ * ch), f"{pn} / {v}", fill=(20, 20, 20), font=lab.font(14))
    S.save(os.path.join(ROOT, "output/tests/mpfb_pose_reference.png"))
    err = json.load(open(os.path.join(OUT, "ik_error_ref_units.json")))
    json.dump(dict(armature=rigify, poses=pose_names, views=views, ik_end_effector_error_rig_px=err), open(os.path.join(ROOT, "docs/asset_audit/mpfb_pose_reference.json"), "w"), indent=1)
    print("ok", err)


if __name__ == "__main__":
    main()
