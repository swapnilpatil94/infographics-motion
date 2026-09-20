"""CREOMOTO: what can the CC0 stickman give us beyond 'reference'?  proportions vs our rig, gait silhouettes, a background stickman CROWD composited behind one of our characters.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/creomoto_test.py -> output/tests/creomoto_test.png, docs/asset_audit/creomoto_test.json
"""
import glob
import json
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, rig_def as R, dna2   # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
SRC = os.path.join(ROOT, "assets/raw/blender_audit/oga_stickman_fixed.blend")
WORK = os.path.join(ROOT, "output/tests/audit_work/creomoto")


def main():
    os.makedirs(WORK, exist_ok=True)
    subprocess.run([BLENDER, "-b", "--disable-autoexec", SRC, "-P", os.path.join(ROOT, "tools/asset_audit/creomoto_blender.py"), "--", WORK], capture_output=True, text=True)
    pr = json.load(open(os.path.join(WORK, "proportions.json")))
    b = pr["bone_lengths"]
    leg = b["thigh"] + b["shin"]
    P = R.proportions_v2(dna2.make("cm:1", "young_man"), "profile")
    ours_leg = P["thigh"] + P["shin"]
    rat = lambda x, ref: round(x / ref, 3)
    table = dict(
        creomoto=dict(thigh_over_leg=rat(b["thigh"], leg), shin_over_leg=rat(b["shin"], leg), upper_arm_over_leg=rat(b["upper_arm"], leg), forearm_over_leg=rat(b["forearm"], leg), spine_over_leg=rat(b["spine"], leg), head_over_leg=rat(b["head"], leg)),
        ours=dict(thigh_over_leg=rat(P["thigh"], ours_leg), shin_over_leg=rat(P["shin"], ours_leg), upper_arm_over_leg=rat(P["upper_arm"], ours_leg), forearm_over_leg=rat(P["forearm"], ours_leg), spine_over_leg=rat(P["torso"], ours_leg),
                  head_over_leg=rat(P["head"], ours_leg)))
    # crowd behind one of our characters
    dna = LD.production_characters()["A"]
    fg = lab.render_specs([dict(label="fg", dna=dna, focus="body")], os.path.join(WORK, "fg"), samples=8)[0]
    rng = random.Random(4)
    frames = json.load(open(os.path.join(WORK, "skeleton_frames.json")))
    CHAINS = [("Thigh_L", "Shin_L"), ("Thigh_R", "Shin_R"), ("Spine1", "Spine2", "Spine3", "Spine4"), ("Shoulder_L", "Arm_L", "Hand_L"), ("Shoulder_R", "Arm_R", "Hand_R"), ("Neck", "Head")]

    def stick(key, h=420):
        """side view (y = depth ignored): draw the bone chains as thick strokes + a head disc -> RGBA sprite"""
        bones = frames[key]
        pts = [(p[0][1], p[0][2]) for p in bones.values()] + [(p[1][1], p[1][2]) for p in bones.values()]
        xs, zs = [p[0] for p in pts], [p[1] for p in pts]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        sc_ = h / max(z1 - z0, 1e-6)
        im = Image.new("RGBA", (int((x1 - x0) * sc_) + 90, h + 60), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        tp = lambda v: (45 + (v[1] - x0) * sc_, 30 + (z1 - v[2]) * sc_)
        for ch in CHAINS:
            line = []
            for n in ch:
                if n in bones:
                    line += [tp(bones[n][0]), tp(bones[n][1])]
            dd.line(line, fill=(20, 20, 24, 255), width=max(6, h // 40), joint="curve")
        hd = tp(bones["Head"][1])
        dd.ellipse((hd[0] - h * 0.06, hd[1] - h * 0.06, hd[0] + h * 0.06, hd[1] + h * 0.06), fill=(20, 20, 24, 255))
        return im

    runs = [k for k in frames if k.startswith("run")]
    idles = [k for k in frames if k.startswith("idle")]
    canvas = Image.new("RGBA", (1080, 1920), (226, 222, 214, 255))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 1500, 1080, 1920), fill=(206, 200, 188, 255))
    for i in range(14):
        src = stick(rng.choice(runs if i % 2 else idles))
        src = src.crop(src.getbbox())
        h = rng.choice([420, 480, 540])
        s = src.resize((int(src.width * h / src.height), h), Image.LANCZOS)
        if rng.random() < 0.5:
            s = s.transpose(Image.FLIP_LEFT_RIGHT)
        alpha = s.split()[3].point(lambda v: int(v * 0.55))
        tint = Image.new("RGBA", s.size, (86, 88, 104, 255))
        tint.putalpha(alpha)
        canvas.alpha_composite(tint, (int(rng.uniform(-40, 960)), 1480 - h + int(rng.uniform(-10, 30))))
    canvas.alpha_composite(Image.fromarray(fg))
    # sheet: gait strip + crowd
    S = Image.new("RGB", (8 * 150 + 560, 640), (30, 30, 34))
    dr = ImageDraw.Draw(S)
    dr.text((10, 8), "CREOMOTO stickman (CC0): RUN gait silhouettes (top strip) and a 14-figure background crowd behind one of our characters (right).", fill=(235, 235, 235), font=lab.font(15, True))
    for row, keys in enumerate((runs[:8], idles[:6])):
        for i, k in enumerate(keys):
            im = stick(k, 380)
            bg = Image.new("RGBA", im.size, (238, 235, 228, 255))
            bg.alpha_composite(im)
            bg.thumbnail((148, 208))
            S.paste(bg.convert("RGB"), (i * 150, 40 + row * 220))
    cr = canvas.convert("RGB").crop((0, 620, 1080, 1620)).resize((540, 500))
    S.paste(cr, (8 * 150 + 10, 40))
    dr.text((10, 490), "proportions (ratio to leg length)  creomoto: " + json.dumps(table["creomoto"]), fill=(220, 220, 220), font=lab.font(13))
    dr.text((10, 512), "                                    ours: " + json.dumps(table["ours"]), fill=(220, 220, 220), font=lab.font(13))
    S.save(os.path.join(ROOT, "output/tests/creomoto_test.png"))
    json.dump(dict(proportions=table, bones=pr["n_bones"], actions=["idle (111 frames)", "run (20 frames)"], verdict="the .blend is a 27-bone ARMATURE with 8 IK constraints and 2 actions (the visible 'Cube' mesh is a bone-shape widget: it renders as a grey block, there is no stickman geometry) -> skeleton/gait reference; a stick-figure crowd has to be DRAWN from the bone positions (done here, 2D)"),
              open(os.path.join(ROOT, "docs/asset_audit/creomoto_test.json"), "w"), indent=1)
    print(json.dumps(table))


if __name__ == "__main__":
    main()
