"""ONE full-body 2D skeleton (spec: ROOT>PELVIS>SPINE>CHEST>NECK>HEAD(EYES,BROWS,MOUTH), SHOULDER>ARM>FOREARM>HAND, THIGH>SHIN>FOOT).

Everything is defined in RIG SPACE: pixels, x = forward (the way the character faces), y = up, origin = ground point between the feet.
The same definition is consumed by
  * engine/skeleton/parts_art.py   - draws each body part in its own joint frame,
  * engine/skeleton/motion.py      - the semantic motion grammar (needs limb lengths, hip/shoulder positions),
  * engine/blender/skeleton_scene.py - builds the Blender armature + IK + textured parts from this exact table.
A character is `proportions(dna)` - the skeleton topology never changes; only lengths/widths do (that is what "character variation" means here).
Facing left is a mirror of x (handled by the consumers, never by a second rig).
"""
import math

S = 0.01                                   # Blender units per rig px
HEAD_CANVAS_H = 413.0                      # Open Peeps head shell: hair top -> neck base, in canvas px
NECK_PIVOT_CANVAS = (612.0, 655.0)         # neck base in the head-shell canvas
# face feature positions in the head-shell canvas (from asset_pipeline/rig_art.py: FACE_ORIGIN + feature)
FACE = dict(eye_l=(623.0, 478.0), eye_r=(741.0, 476.0), brow_l=(617.0, 438.0), brow_r=(741.0, 433.0), mouth=(696.0, 594.0), nose=(690.0, 520.0))

BUILD = {"slim": dict(torso_w=112, limb=48), "average": dict(torso_w=128, limb=54), "broad": dict(torso_w=146, limb=62), "heavy": dict(torso_w=166, limb=68)}
AGE_K = {"young": 0.97, "adult": 1.0, "elder": 0.94}

# rest-pose bends (deg, forward positive). Non-zero so a 2-bone IK chain has an unambiguous bend direction.
REST = dict(arm=7.0, elbow=11.0, wrist=8.0, thigh=3.0, knee=-7.0)


VIEWS = ("profile", "three_quarter", "front", "back")
VIEW_LAT = dict(profile=(0.0, 0.0, 0.0), three_quarter=(0.24, 0.10, 0.10), front=(0.50, 0.26, 0.35), back=(0.50, 0.26, 0.0))   # (shoulder, hip) lateral offset as a fraction of torso width; face shift


def _derive(P, view="profile"):
    P["hip_y"] = P["foot_h"] + P["shin"] + P["thigh"]
    P["shoulder_y"] = P["hip_y"] + P["torso"]
    P["shoulder_joint_y"] = P["shoulder_y"] - 34 * P["k"]        # arm pivot sits a little below the top of the torso
    P["neck_top_y"] = P["shoulder_y"] + P["neck"]
    P["hs"] = P["head"] / HEAD_CANVAS_H                          # head-shell canvas px -> rig px
    P["height"] = P["neck_top_y"] + P["head"]
    P["stride_max"] = 0.62 * (P["thigh"] + P["shin"])
    ls, lh, fd = VIEW_LAT[view]
    P["view"], P["lat_s"], P["lat_h"], P["face_dx"] = view, ls * P["torso_w"] * P.get("shoulder_k", 1.0), lh * P["torso_w"], fd
    return P


def proportions(dna, height_scale=1.0, view="profile"):
    k = AGE_K[dna["age_group"]] * (0.95 if dna["gender"] == "female" else 1.0) * height_scale
    b = BUILD[dna["body_type"]]
    P = dict(head=200 * k, neck=34 * k, torso=286 * k, upper_arm=176 * k, forearm=160 * k, hand=64 * k, thigh=246 * k, shin=236 * k, foot_h=42 * k, foot_len=128 * k,
             torso_w=b["torso_w"] * (0.94 if dna["gender"] == "female" else 1.0), limb=b["limb"] * (0.92 if dna["gender"] == "female" else 1.0), k=k)
    return _derive(P, view)


def proportions_v2(d2, view="profile"):
    """CharacterDNA v2 body parameters -> proportions (same skeleton, different lengths / widths / head size)."""
    b = d2["body"]
    age = d2["age"]
    k = (0.90 + 0.10 * min(1.0, max(0.0, (age - 12) / 8.0))) * (0.985 if d2["gender_presentation"] == "feminine" else 1.0) * b["height"]
    hs_ = b["head_size"] * (1.06 if age < 20 else 1.0)
    fem = d2["gender_presentation"] == "feminine"
    P = dict(head=200 * k * hs_, neck=34 * k * b["neck"], torso=286 * k, upper_arm=176 * k, forearm=160 * k, hand=64 * k * (0.94 if fem else 1.0), thigh=246 * k * b["leg_ratio"],
             shin=236 * k * b["leg_ratio"], foot_h=42 * k, foot_len=128 * k * (0.94 if fem else 1.0), torso_w=128 * b["width"] * (0.94 if fem else 1.0) * (1.03 if age > 55 else 1.0),
             limb=54 * (0.5 + 0.5 * b["width"]) * (0.93 if fem else 1.0), k=k, shoulder_k=b["shoulder"])
    return _derive(P, view)


def side_offsets(P):
    """Lateral (screen-x) rest offsets of the far (L) and near (R) limbs in this view: 0 in profile, symmetric about the spine in front view."""
    ls, lh = P.get("lat_s", 0.0), P.get("lat_h", 0.0)
    return dict(sL=+ls, sR=-ls, hL=+lh, hR=-lh)


def _dir(a_deg):
    """Unit vector pointing DOWN from a joint, rotated a_deg toward +x (forward)."""
    a = math.radians(a_deg)
    return (math.sin(a), -math.cos(a))


def rest_joints(P):
    """Rest-pose joint positions (rig space)."""
    hip = (0.0, P["hip_y"])
    knee = (hip[0] + P["thigh"] * _dir(REST["thigh"])[0], hip[1] + P["thigh"] * _dir(REST["thigh"])[1])
    a2 = REST["thigh"] + REST["knee"]
    ankle = (knee[0] + P["shin"] * _dir(a2)[0], knee[1] + P["shin"] * _dir(a2)[1])
    toe = (ankle[0] + P["foot_len"] - 34 * P["k"], P["foot_h"] * 0.55)
    sh = (0.0, P["shoulder_joint_y"])
    elbow = (sh[0] + P["upper_arm"] * _dir(REST["arm"])[0], sh[1] + P["upper_arm"] * _dir(REST["arm"])[1])
    a3 = REST["arm"] + REST["elbow"]
    wrist = (elbow[0] + P["forearm"] * _dir(a3)[0], elbow[1] + P["forearm"] * _dir(a3)[1])
    a4 = a3 + REST["wrist"]
    tip = (wrist[0] + P["hand"] * _dir(a4)[0], wrist[1] + P["hand"] * _dir(a4)[1])
    return dict(hip=hip, knee=knee, ankle=ankle, toe=toe, shoulder=sh, elbow=elbow, wrist=wrist, tip=tip)


def side_joints(P, side):
    """rest_joints shifted by the view's lateral offset for one side (arm chain by lat_s, leg chain by lat_h)."""
    J = rest_joints(P)
    so = side_offsets(P)
    a, l = so["s" + side], so["h" + side]
    out = {}
    for k_, v in J.items():
        off = a if k_ in ("shoulder", "elbow", "wrist", "tip") else l
        out[k_] = (v[0] + off, v[1])
    return out


def head_point(P, canvas_xy):
    """A point in the head-shell canvas -> rig-space rest position (the head sits on the neck top)."""
    hs = P["hs"]
    dx = canvas_xy[0] - NECK_PIVOT_CANVAS[0]
    if P.get("face_dx"):                                           # turn trick: in front / 3-4 views the features sit closer to the head's centre line
        dx = dx - P["face_dx"] * (dx - (-5.0))
    return (P_neck_x(P) + dx * hs, P["neck_top_y"] - (canvas_xy[1] - NECK_PIVOT_CANVAS[1]) * hs)


def P_neck_x(P):
    return 0.0


def bones(P):
    """[(name, parent, head, tail)] in rig space. Order = parents first. Two limbs per side: L = far side, R = near side (facing +x).
    In 3/4 and front views the limbs of the two sides are laterally offset (side_joints); the bone LIST is identical in every view."""
    out = []
    add = lambda n, par, h, t: out.append((n, par, tuple(h), tuple(t)))
    add("ROOT", None, (0, 0), (0, 24 * P["k"]))
    add("PELVIS", "ROOT", (0, P["hip_y"]), (0, P["hip_y"] + 42 * P["k"]))
    add("SPINE", "PELVIS", (0, P["hip_y"]), (0, P["hip_y"] + P["torso"] * 0.5))
    add("CHEST", "SPINE", (0, P["hip_y"] + P["torso"] * 0.5), (0, P["shoulder_y"]))
    add("NECK", "CHEST", (0, P["shoulder_y"]), (0, P["neck_top_y"]))
    add("HEAD", "NECK", (0, P["neck_top_y"]), (0, P["neck_top_y"] + P["head"] * 0.9))
    add("HAIR", "HEAD", (0, P["neck_top_y"] + P["head"] * 0.55), (0, P["neck_top_y"] + P["head"] * 0.95))
    for side in ("L", "R"):
        J = side_joints(P, side)
        add(f"SHOULDER_{side}", "CHEST", J["shoulder"], (J["shoulder"][0] + 14 * P["k"], J["shoulder"][1]))
        add(f"ARM_{side}", f"SHOULDER_{side}", J["shoulder"], J["elbow"])
        add(f"FOREARM_{side}", f"ARM_{side}", J["elbow"], J["wrist"])
        add(f"HAND_{side}", f"FOREARM_{side}", J["wrist"], J["tip"])
        add(f"THIGH_{side}", "PELVIS", J["hip"], J["knee"])
        add(f"SHIN_{side}", f"THIGH_{side}", J["knee"], J["ankle"])
        add(f"FOOT_{side}", f"SHIN_{side}", J["ankle"], J["toe"])
    for side, key in (("L", "eye_l"), ("R", "eye_r")):
        p = head_point(P, FACE[key])
        add(f"EYE_{side}", "HEAD", p, (p[0] + 8 * P["k"], p[1]))
        b = head_point(P, FACE["brow_l" if side == "L" else "brow_r"])
        add(f"BROW_{side}", "HEAD", b, (b[0] + 16 * P["k"], b[1]))
    m = head_point(P, FACE["mouth"])
    add("MOUTH", "HEAD", m, (m[0] + 16 * P["k"], m[1]))
    return out


# IK chains: (name, upper bone, lower bone, end bone, elbow/knee limit range about REST in deg, forward positive)
IK = [("IK_HAND_L", "ARM_L", "FOREARM_L", "HAND_L", (-11.0, 150.0)), ("IK_HAND_R", "ARM_R", "FOREARM_R", "HAND_R", (-11.0, 150.0)),
      ("IK_FOOT_L", "THIGH_L", "SHIN_L", "FOOT_L", (-150.0, 7.0)), ("IK_FOOT_R", "THIGH_R", "SHIN_R", "FOOT_R", (-150.0, 7.0))]

# draw order back -> front. (part, bone, layer_group). Face feature meshes sit between skull and hair.
PART_ORDER = ["upperarm_L", "forearm_L", "hand_L", "thigh_L", "shin_L", "foot_L", "neck", "pelvis", "backpack", "thigh_R", "shin_R", "foot_R", "skirt", "torso",
              "skull", "nose", "@face", "hair", "upperarm_R", "forearm_R", "bag", "phone", "hand_R", "fingers"]
PART_BONE = dict(upperarm_L="ARM_L", forearm_L="FOREARM_L", hand_L="HAND_L", thigh_L="THIGH_L", shin_L="SHIN_L", foot_L="FOOT_L", neck="NECK", pelvis="PELVIS",
                 thigh_R="THIGH_R", shin_R="SHIN_R", foot_R="FOOT_R", torso="CHEST", skull="HEAD", nose="HEAD", hair="HAIR", upperarm_R="ARM_R",
                 forearm_R="FOREARM_R", hand_R="HAND_R", backpack="CHEST", skirt="PELVIS", bag="CHEST")


# ---------------------------------------------------------------------------- 2-bone IK (analytic; the Blender IK solver must agree with this)
def two_bone(base, target, l1, l2, bend=+1):
    """Analytic 2-bone IK in the rig plane (y up, x forward). Returns (joint, tip, a1, a2): a1/a2 = upper/lower bone absolute angle (deg, measured from
    straight-down toward +x). bend=+1: the joint lies on the LEFT of the base->target direction (a knee: forward when the leg points down);
    bend=-1: on the RIGHT (an elbow). The target is clamped to the reachable annulus."""
    dx, dy = target[0] - base[0], target[1] - base[1]
    d = min(max(math.hypot(dx, dy), abs(l1 - l2) + 1e-3), (l1 + l2) * 0.9995)
    ang = math.atan2(dy, dx)
    cosa = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.acos(max(-1.0, min(1.0, cosa)))
    cands = []
    for s_ in (1, -1):
        t = ang + s_ * a
        j = (base[0] + l1 * math.cos(t), base[1] + l1 * math.sin(t))
        cross = math.cos(ang) * (j[1] - base[1]) - math.sin(ang) * (j[0] - base[0])      # >0: joint on the left of the base->target direction
        cands.append((cross, j))
    cands.sort(key=lambda c: c[0])
    j = cands[-1][1] if bend > 0 else cands[0][1]
    tip = (base[0] + d * math.cos(ang), base[1] + d * math.sin(ang))
    a1 = math.degrees(math.atan2(j[0] - base[0], -(j[1] - base[1])))
    a2 = math.degrees(math.atan2(tip[0] - j[0], -(tip[1] - j[1])))
    return j, tip, a1, a2
