"""Debug: composite a baked character's parts in the REST pose with plain 2D transforms (no Blender) to check the art."""
import json, math, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from engine.characters import dna as D
from engine.skeleton import parts_art as PA, rig_def as R
from engine.shorts.raster import ROOT

REST_ANGLE = dict(upperarm=R.REST["arm"], forearm=R.REST["arm"] + R.REST["elbow"], hand=R.REST["arm"] + R.REST["elbow"] + R.REST["wrist"],
                  thigh=R.REST["thigh"], shin=R.REST["thigh"] + R.REST["knee"])

def compose(dna, path, scale=0.9, H=1200, W=700):
    man = PA.bake(dna); P = man["P"]; J = R.rest_joints(P)
    joint = dict(upperarm=J["shoulder"], forearm=J["elbow"], hand=J["wrist"], thigh=J["hip"], shin=J["knee"], foot=J["ankle"], pelvis=J["hip"], torso=J["hip"],
                 neck=(0, P["shoulder_y"]), skull=(0, P["neck_top_y"]), hair=(0, P["neck_top_y"]), nose=(0, P["neck_top_y"]), fingers=J["wrist"], phone=J["wrist"])
    canvas = np.zeros((H, W, 4), np.float32); canvas[..., :3] = 0.93; canvas[..., 3] = 1
    order = ["upperarm_L", "forearm_L", "hand_L", "thigh_L", "shin_L", "foot_L", "neck", "pelvis", "thigh_R", "shin_R", "foot_R", "torso", "skull", "nose", "hair", "upperarm_R", "forearm_R", "hand_R"]
    for name in order:
        p = man["parts"][name]; base = name.split("_")[0]
        img = np.asarray(Image.open(os.path.join(ROOT, p["png"])).convert("RGBA")).astype(np.float32) / 255
        jx, jy = joint[base]
        ang = REST_ANGLE.get(base, 0.0)
        # rig (x fwd, y up) -> screen: x0 + x*scale, ground - y*scale
        sx, sy = 260 + jx * scale, H - 40 - jy * scale
        k = scale / p["res"]
        a = math.radians(ang)                                          # forward = clockwise on screen
        c, s = math.cos(a) * k, math.sin(a) * k
        px, py = p["pivot"]
        Mx = np.array([[c, -s, sx - (c * px - s * py)], [s, c, sy - (s * px + c * py)]], np.float32)
        warped = cv2.warpAffine(img, Mx, (W, H), flags=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        a_ = warped[..., 3:4]
        canvas[..., :3] = warped[..., :3] * a_ + canvas[..., :3] * (1 - a_)
    Image.fromarray((canvas[..., :3] * 255).astype(np.uint8)).save(path)

if __name__ == "__main__":
    dn = D.make(sys.argv[1] if len(sys.argv) > 1 else "young_man", "t:1")
    compose(dn, sys.argv[2] if len(sys.argv) > 2 else "/tmp/rest.png")
