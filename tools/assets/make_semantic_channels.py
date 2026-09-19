"""Sample OUR semantic motion grammar (idle -> walk -> reach PHONE -> hold) into per-frame IK-target channels so external candidate rigs can be driven by exactly the same motion.
python: .venv/bin/python tools/assets/make_semantic_channels.py -> output/tests/blender_audit/semantic_channels.json"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import dna2, motion as M, rig_def as R   # noqa: E402

FPS, DUR = 24, 5.0


def build():
    d = dna2.make("candidate_drive", "young_woman", {"wardrobe.top": "tee", "wardrobe.bottom": "trousers"})
    P = R.proportions_v2(d, "profile")
    p = M.Performance(P, seed=3, world=dict(seat_h=270), facing=1, origin=(300.0, 1500.0), resolver=lambda tid, t: (300.0 + 520.0, 1500.0 - 620.0))
    M.pose_stand(p, -1.0, 0.0)
    M.perform(p, "breathe", 0.0, DUR, "neutral", 0.5)
    M.perform(p, "walk", 0.4, 2.2, "neutral", 0.6, speed=170)
    M.perform(p, "reach", 2.9, 1.1, "curious", 0.7, target="PHONE", grip="grab")
    M.perform(p, "hold", 4.0, 0.9, "neutral", 0.5)
    return d, P, p, M.sample(p, FPS, 0.0, DUR)


if __name__ == '__main__':
    d, P, p, ch = build()
    keep = ["root_x", "root_y", "pelvis_dx", "pelvis_dy", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y", "hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "head_rot", "spine_rot", "gaze_x", "gaze_y"]
    out = dict(fps=FPS, frames=len(ch["root_x"]), P={k: P[k] for k in ("hip_y", "thigh", "shin", "upper_arm", "forearm", "foot_h", "torso", "k")}, channels={k: [round(float(v), 3) for v in ch[k]] for k in keep},
               events=[(round(t, 3), n) for t, n, *_ in p.events][:20], script="idle+breathe 0-5s | walk 0.4-2.6s | reach PHONE 2.9-4.0s | hold 4.0-4.9s")
    os.makedirs(os.path.join(ROOT, "output/tests/blender_audit"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "output/tests/blender_audit/semantic_channels.json"), "w"))
    print("frames", out["frames"], "root_x range", min(ch["root_x"]), max(ch["root_x"]), "hand_R", ch["hand_R_x"][0], ch["hand_R_x"][-1])
