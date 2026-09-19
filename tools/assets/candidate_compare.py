"""3-up comparison video: OUR generated character | Creomoto stickman (CC0) | MPFB2+Rigify human (CC0), all driven by the SAME semantic script (walk -> reach PHONE -> hold).
Prereq: candidate_drive.py frames exist in output/tests/blender_audit/{oga_stickman,mpfb_rigify}_drive/.  -> output/tests/candidate_integration_walk_reach.mp4"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.skeleton import short as SH, v2_evidence as E   # noqa: E402
import make_semantic_channels as MS                          # noqa: E402

W, H, FPS = 360, 480, MS.FPS
d, P, p, ch = MS.build()
n = len(ch["root_x"])
a = E.make_actor("A", d, view="profile", facing=1, origin=(700.0, E.GROUND), hand_set="basic", start="stand", resolver=lambda tid, t: (700.0 + 520.0, E.GROUND - 620.0))
a.perf = p
a.perf.origin = (700.0, E.GROUND)
a.channels = ch
cx = np.array([700.0 + ch["root_x"][i] + 40.0 for i in range(n)])
cam = dict(cx=cx, cy=np.full(n, E.GROUND - 470.0), zoom=np.full(n, 0.44), gain=np.ones(n))
work, rep = E.blender_frames([a], cam, W, H, FPS, "candidate_ours", samples=6)
out_dir = os.path.join(ROOT, "output/tests/blender_audit")
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
except Exception:
    font = None


def ours(i):
    im = Image.new("RGBA", (W, H), (58, 60, 66, 255))
    f = Image.open(os.path.join(work, "frames", f"e{i:05d}.png")).convert("RGBA")
    im.alpha_composite(f)
    return im.convert("RGB")


def cand(name, i):
    return Image.open(os.path.join(out_dir, f"{name}_drive", f"f{i:04d}.png")).convert("RGB").resize((W, H))


labels = ["OURS: generated 2D rig + Open Peeps (CC0)", "Creomoto Stick Man fixed (CC0)", "MPFB2 + Rigify human (CC0 output)"]


def frames():
    for i in range(n):
        c = Image.new("RGB", (W * 3, H + 30), (20, 20, 22))
        for k, im in enumerate((ours(i), cand("oga_stickman", i), cand("mpfb_rigify", i))):
            c.paste(im, (k * W, 30))
            ImageDraw.Draw(c).text((k * W + 8, 6), labels[k], fill=(255, 255, 255), font=font)
        yield c


E.encode(frames(), W * 3, H + 30, FPS, os.path.join(ROOT, "output/tests/candidate_integration_walk_reach.mp4"))
print("COMPARE_OK", n)
