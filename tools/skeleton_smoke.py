"""Smoke test of the whole rig path: DNA -> parts -> motion grammar -> Blender (IK) -> frames. Usage: .venv/bin/python tools/skeleton_smoke.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.characters import dna as D
from engine.skeleton import parts_art as PA, blender_job as BJ, motion as M
from PIL import Image

d = D.make("young_man", "proof:young_man", gender="male")
man = PA.bake(d)
P = man["P"]
perf = M.Performance(P, seed=3, world=dict(seat_h=270))
M.pose_sit(perf)
t = 0.5
t = M.perform(perf, "look_at_phone", t, 0.6, "hesitant", 0.7, point=(330, 320))
t = M.perform(perf, "reach_for_phone", t + 0.2, 1.2, "hesitant", 0.7, target=(330, 330))
t = M.perform(perf, "grab", t, 0.1)
t = M.perform(perf, "hold_phone", t + 0.1, 0.9, "hesitant", 0.6, pos="chest")
t = M.perform(perf, "read_phone", t + 0.1, 1.6)
t = M.perform(perf, "stand", t + 0.2, 1.4, "fearful", 0.6)
t = M.perform(perf, "walk", t + 0.2, 2.6)
M.perform(perf, "surprise", t + 0.1, 0.9, "shocked", 0.8)
M.auto_blinks(perf, 0, t + 1, 3)
fps, T1 = 30, t + 1.2
ch = M.sample(perf, fps, 0.0, T1)
n = len(ch["root_x"])
job = dict(width=540, height=960, fps=fps, start=0, end=n - 1, out="/tmp/sk_smoke", prefix="f", samples=4, save_blend="/tmp/sk_smoke/smoke.blend",
           characters=[dict(id="A", manifest=os.path.join(PA.ROOT, man["dir"], "parts.json"), facing=1, origin=[300, 1600], channels=ch)],
           camera=dict(cx=640, cy=1150, zoom=0.5))
rep = BJ.run(job, "/tmp/sk_smoke")
errs = [max(e[k] for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")) for e in rep["ik_error_px"]]
print("frames", n, "max IK err px", max(errs), "mean", sum(errs) / len(errs))
