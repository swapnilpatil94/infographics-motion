"""Blender side of the full-body 2D skeleton pipeline.   blender -b -P engine/blender/skeleton_scene.py -- job.json

Receives a DETERMINISTIC job (characters = baked part textures + per-frame semantic-control channels; camera; props) and
  1. builds, per character, a REAL Blender armature from engine/skeleton/rig_def.py (ROOT>PELVIS>SPINE>CHEST>NECK>HEAD>HAIR/EYES/BROWS/MOUTH,
     SHOULDER>ARM>FOREARM>HAND, THIGH>SHIN>FOOT) with IK constraints (limited 2-bone chains) on both arms and both legs,
  2. builds every body part as its own mesh (textured quad for the vector art, flat-colour meshes + shape keys for eyes/brows/mouth) skinned to its bone
     with an Armature modifier (vertex group weight 1 = a rigid cut-out part),
  3. inserts real keyframes (bone rotations/locations/scales, IK target empties, shape-key values, visibility) - the armature is ANIMATED in Blender,
  4. renders an orthographic transparent RGBA sequence that the 2D compositor lays into the 2.5D scene.
No add-on is used: stock Blender only (see docs/RIG_RESEARCH_V2.md). Nobody touches the Blender UI.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import rig_def as R   # noqa: E402  (pure python)

S = R.S
job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
W, H = job["width"], job["height"]
FPS = job["fps"]
F0, F1 = job["start"], job["end"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
try:
    sc.eevee.taa_render_samples = int(job.get("samples", 12))
except Exception:
    pass
sc.frame_start, sc.frame_end = F0, F1

_mats = {}


def flat_material(rgb):
    key = tuple(round(c, 4) for c in rgb)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new("flat%d" % len(_mats))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    _mats[key] = m
    return m


def tex_material(png):
    if png in _mats:
        return _mats[png]
    m = bpy.data.materials.new(os.path.basename(png))
    m.use_nodes = True
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    img = bpy.data.images.load(png)
    img.alpha_mode = "STRAIGHT"
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    tx.interpolation = "Linear"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    nt.links.new(tx.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    _mats[png] = m
    return m


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    return tuple((v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c)


# ------------------------------------------------------------------------------------------------------------------ camera
cam_d = bpy.data.cameras.new("cam")
cam_d.type = "ORTHO"
cam_d.sensor_fit = "HORIZONTAL"
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam.rotation_euler = (math.radians(90), 0, 0)
cam.location = (0, -50, 0)
cam_d.clip_start, cam_d.clip_end = 0.1, 200

# ------------------------------------------------------------------------------------------------------------------ characters
CH = []


class Char:
    pass


def to3(p, facing, y=0.0):
    return (facing * p[0] * S, y, p[1] * S)


def build_char(spec, idx):
    man = json.load(open(spec["manifest"]))
    P = man["P"]
    facing = spec.get("facing", 1)
    ox, oy = spec["origin"]
    depth = idx * 1.0
    c = Char()
    c.spec, c.P, c.man, c.facing, c.origin = spec, P, man, facing, (ox, oy)
    c.J = R.rest_joints(P)
    c.JS = {"L": R.side_joints(P, "L"), "R": R.side_joints(P, "R")}
    c.obj_y = -depth
    # ---- armature (in the character's stage frame; object placed at the stage origin)
    arm_d = bpy.data.armatures.new("rig_" + spec["id"])
    arm = bpy.data.objects.new("rig_" + spec["id"], arm_d)
    sc.collection.objects.link(arm)
    arm.location = (ox * S, c.obj_y, -oy * S)
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    blist = R.bones(P)
    for name, parent, head, tail in blist:
        eb = arm_d.edit_bones.new(name)
        eb.head, eb.tail = to3(head, facing), to3(tail, facing)
        if parent:
            eb.parent = arm_d.edit_bones[parent]
        eb.align_roll((0, 1, 0))
    bpy.ops.object.mode_set(mode="POSE")
    c.arm = arm
    zaxis = arm_d.bones["THIGH_R"].matrix_local.to_3x3() @ Vector((0, 0, 1))
    c.zsign = 1.0 if zaxis.y > 0 else -1.0                       # bone-local Z is +-world Y: fix the sign once
    c.rest3 = {b.name: b.matrix_local.to_3x3() for b in arm_d.bones}
    # ---- IK
    c.ik = {}
    for name, up, low, end, (lo, hi) in R.IK:
        e = bpy.data.objects.new(name + "_" + spec["id"], None)
        e.empty_display_type = "PLAIN_AXES"
        sc.collection.objects.link(e)
        e.location = (ox * S, c.obj_y, -oy * S)
        pb = arm.pose.bones[low]
        con = pb.constraints.new("IK")
        con.target = e
        con.chain_count = 2
        con.use_tail = True
        for bn in (up, low):
            b = arm.pose.bones[bn]
            b.lock_ik_x = b.lock_ik_y = True
            b.lock_ik_z = False
        pb.use_ik_limit_z = True
        # rig_def limits are in LIMB convention (forward = counter-clockwise for a hanging limb); Blender's local-Z rotation is clockwise-positive
        a, b_ = sorted((-c.zsign * facing * math.radians(lo), -c.zsign * facing * math.radians(hi)))
        pb.ik_min_z, pb.ik_max_z = a, b_
        c.ik[name] = e
    # ---- part meshes
    c.parts = {}
    c.handposes = {"L": [], "R": []}
    order = [p for p in R.PART_ORDER]
    poses = man.get("hand_poses") or []
    for i, pname in enumerate(order):
        if pname in ("@face", "phone", "fingers"):
            continue
        if pname in ("hand_L", "hand_R") and pname not in man["parts"]:                      # v2: a SET of reusable hand poses per wrist
            side = pname[-1]
            for pose in poses:
                ob = add_textured_part(c, f"hand_{side}_{pose}", i, bone_override="HAND_" + side)
                c.handposes[side].append((pose, ob))
            continue
        if pname not in man["parts"]:
            continue
        add_textured_part(c, pname, i)
    add_face(c, order.index("@face"))
    add_phone(c, order.index("phone"))
    if man.get("view") == "back":                                                          # seen from behind: no face features, no nose
        for ob in c.face.values():
            ob.scale = (0.0001, 0.0001, 0.0001)
        if "nose" in c.parts:
            c.parts["nose"].scale = (0.0001, 0.0001, 0.0001)
    c.all_objs = list(c.parts.values()) + list(c.face.values()) + [ob for _, ob in c.handposes["L"]] + [ob for _, ob in c.handposes["R"]]
    return c


def _obj_from_mesh(name, verts, faces, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if uvs:
        uv = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                uv.data[li].uv = uvs[vi]
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def skin_to(c, ob, bone):
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    md = ob.modifiers.new("arm", "ARMATURE")
    md.object = c.arm


def rest_angle_deg(pname):
    Rr = R.REST
    return {"upperarm": Rr["arm"], "forearm": Rr["arm"] + Rr["elbow"], "hand": Rr["arm"] + Rr["elbow"] + Rr["wrist"], "thigh": Rr["thigh"], "shin": Rr["thigh"] + Rr["knee"]}.get(pname.split("_")[0], 0.0)


def _side_of(pname):
    t = pname.split("_")
    return t[1] if len(t) > 1 and t[1] in ("L", "R") else None


def joint_of(c, pname):
    P = c.P
    side = _side_of(pname)
    J = R.side_joints(P, side) if side else R.rest_joints(P)
    base = pname.split("_")[0]
    return {"upperarm": J["shoulder"], "forearm": J["elbow"], "hand": J["wrist"], "thigh": J["hip"], "shin": J["knee"], "foot": J["ankle"], "pelvis": J["hip"], "torso": J["hip"],
            "skirt": J["hip"], "backpack": J["hip"], "bag": J["hip"],
            "neck": (0.0, P["shoulder_y"]), "skull": (0.0, P["neck_top_y"]), "hair": (0.0, P["neck_top_y"]), "nose": (0.0, P["neck_top_y"])}[base]


def add_textured_part(c, pname, order_i, extra=None, bone_override=None):
    p = c.man["parts"][pname]
    px, py = p["pivot"]
    w, h = p["size"]
    res = p["res"]
    jx, jy = joint_of(c, pname) if extra is None else extra
    a = math.radians(rest_angle_deg(pname))
    corners = [(-px / res, py / res), ((w - px) / res, py / res), ((w - px) / res, -(h - py) / res), (-px / res, -(h - py) / res)]     # pivot-relative, y up: TL TR BR BL
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
    verts = []
    for (x, y) in corners:
        rx = x * math.cos(a) - y * math.sin(a)                 # rest orientation: a hanging limb tilted FORWARD by a (counter-clockwise, y up) - matches the bone's rest direction
        ry = x * math.sin(a) + y * math.cos(a)                 # (v2 rotated the art the other way: parts sat 2a off their bones, e.g. the forearm 36 deg)
        verts.append(to3((jx + rx, jy + ry), c.facing, 0.0))
    # stage-local -> object at stage origin => vertices are stage-local
    ob = _obj_from_mesh(pname + "_" + c.spec["id"], verts, [(0, 1, 2, 3)], uvs)
    ob.location = (c.arm.location.x, c.obj_y - 0.004 * order_i, c.arm.location.z)
    ob.data.materials.append(tex_material(os.path.join(ROOT, p["png"])))
    bone = bone_override or R.PART_BONE[pname]
    skin_to(c, ob, bone)
    c.parts[pname] = ob
    return ob


def ellipse(cx, cy, rx, ry, n=28):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def flat_mesh(c, name, poly_rig, color_hex, bone, order_i, shape_keys=None):
    """poly_rig: [(x,y)] in rig space (y up, x forward) at REST. Triangle fan around the centroid. Flat-colour, skinned to `bone`."""
    cx = sum(p[0] for p in poly_rig) / len(poly_rig)
    cy = sum(p[1] for p in poly_rig) / len(poly_rig)
    verts = [to3((cx, cy), c.facing)] + [to3(p, c.facing) for p in poly_rig]
    faces = [(0, 1 + i, 1 + (i + 1) % len(poly_rig)) for i in range(len(poly_rig))]
    ob = _obj_from_mesh(name + "_" + c.spec["id"], verts, faces)
    ob.location = (c.arm.location.x, c.obj_y - 0.004 * order_i, c.arm.location.z)
    ob.data.materials.append(flat_material(srgb_to_linear(hex_rgb(color_hex))))
    skin_to(c, ob, bone)
    if shape_keys:
        ob.shape_key_add(name="Basis")
        for kname, poly2 in shape_keys.items():
            k = ob.shape_key_add(name=kname)
            c2 = (sum(p[0] for p in poly2) / len(poly2), sum(p[1] for p in poly2) / len(poly2))
            pts = [to3(c2, c.facing)] + [to3(p, c.facing) for p in poly2]
            for i, v in enumerate(pts):
                k.data[i].co = v
    return ob


def _rot(pts, cx, cy, deg):
    a = math.radians(deg)
    return [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]


VISEMES = dict(A=(0.62, 24.0), E=(0.95, 13.0), I=(0.85, 9.0), O=(0.42, 22.0), U=(0.28, 15.0), shocked=(0.60, 32.0))


def add_face(c, order_i):
    """Face = flat-colour meshes on face bones. eyes: white (`wide` shape key) + ring + pupil (EYE bone: location = gaze, scale = blink/narrow/droop); brows: BROW bones;
    mouth: lip line (shape keys smile / frown / worried) + cavity (shape keys A E I O U shocked, MOUTH bone scale = openness). Style comes from the DNA (`face_style`)."""
    P, hs, k = c.P, c.P["hs"], c.P["k"]
    st = c.man.get("face_style", {})
    eye_rx, eye_ry = 10.8 * hs * st.get("ex", 1.0), 19.0 * hs * st.get("ey", 1.0)                # canvas px -> rig px (hs)
    tilt = st.get("tilt", 0.0)
    brow_t = st.get("brow", 13) * hs
    arch = st.get("arch", 0.0)
    ink = "#000000"
    c.face = {}
    for side, ek, bk in (("L", "eye_l", "brow_l"), ("R", "eye_r", "brow_r")):
        e = R.head_point(P, R.FACE[ek])
        sg = -1 if side == "L" else 1
        t = tilt * sg
        big = st.get("editorial", True)                                            # v3: a visible sclera at rest (a bigger, readable eye) instead of a bare dot
        wide = _rot(ellipse(e[0], e[1], eye_rx * (2.75 if big else 2.4), eye_ry * (1.92 if big else 1.55)), e[0], e[1], t)
        small = _rot(ellipse(e[0], e[1], eye_rx * (2.15 if big else 0.4), eye_ry * (1.42 if big else 0.32)), e[0], e[1], t)
        c.face["eyewhite_" + side] = flat_mesh(c, "eyewhite_" + side, small, "#fbfaf6", "EYE_" + side, order_i, shape_keys={"wide": wide})
        c.face["eyering_" + side] = flat_mesh(c, "eyering_" + side, _rot(ellipse(e[0], e[1], eye_rx * (2.42 if big else 0.45), eye_ry * (1.62 if big else 0.36)), e[0], e[1], t), ink, "EYE_" + side, order_i,
                                              shape_keys={"wide": _rot(ellipse(e[0], e[1], eye_rx * (3.05 if big else 2.75), eye_ry * (2.14 if big else 1.78)), e[0], e[1], t)})
        c.face["eyering_" + side].location.y += 0.0014
        c.face["pupil_" + side] = flat_mesh(c, "pupil_" + side, _rot(ellipse(e[0], e[1], eye_rx * (0.98 if big else 1.0), eye_ry * (0.96 if big else 1.0)), e[0], e[1], t), ink, "EYE_" + side, order_i)
        c.face["pupil_" + side].location.y -= 0.0012
        if st.get("lash"):                                                         # lash flick at the outer top corner
            lx = e[0] + eye_rx * 0.7
            ly = e[1] + eye_ry * 0.9
            c.face["lash_" + side] = flat_mesh(c, "lash_" + side, [(lx - 2 * hs, ly), (lx + 13 * hs, ly + 7 * hs), (lx + 2 * hs, ly - 3 * hs)], ink, "EYE_" + side, order_i)
            c.face["lash_" + side].location.y -= 0.0013
        b = R.head_point(P, R.FACE[bk])
        half = 32 * hs
        ar = arch * 8 * hs
        strip = [(b[0] - half, b[1] - brow_t / 2), (b[0], b[1] - brow_t / 2 + ar), (b[0] + half, b[1] - brow_t / 2), (b[0] + half + brow_t * 0.3, b[1]), (b[0] + half, b[1] + brow_t / 2),
                 (b[0], b[1] + brow_t / 2 + ar), (b[0] - half, b[1] + brow_t / 2), (b[0] - half - brow_t * 0.3, b[1])]
        c.face["brow_" + side] = flat_mesh(c, "brow_" + side, strip, ink, "BROW_" + side, order_i)
    m = R.head_point(P, R.FACE["mouth"])
    mw = 31 * hs * st.get("mouth", 1.0)
    th = st.get("lip", 4.5) * 1.4 * hs

    def lip(smile, worried=0.0, n=9):
        top, bot = [], []
        for i in range(n):
            u = i / (n - 1)
            x = m[0] + (u - 0.5) * 2 * mw
            y = m[1] + smile * (-24.0 * hs) * (1 - (2 * u - 1) ** 2) + smile * (16.0 * hs) * ((2 * u - 1) ** 2)
            y += worried * (14.0 * hs * (1 - (2 * u - 1) ** 2) - 18.0 * hs * ((2 * u - 1) ** 2)) * -1
            top.append((x, y + th))
            bot.append((x, y - th))
        return top + bot[::-1]
    c.face["mouth_line"] = flat_mesh(c, "mouth_line", lip(0.0), ink, "MOUTH", order_i, shape_keys={"smile": lip(1.0), "frown": lip(-1.0), "worried": lip(-0.5, 1.0)})
    cav = lambda rxf, ryv: ellipse(m[0], m[1], mw * rxf, ryv * hs * 1.35)
    c.face["mouth_cavity"] = flat_mesh(c, "mouth_cavity", cav(0.8, 24.0), "#2a0f14", "MOUTH", order_i, shape_keys={n: cav(*v) for n, v in VISEMES.items()})
    c.face["mouth_cavity"].location.y += 0.0009
    c.face["mouth_line"].location.y -= 0.0009


def add_phone(c, order_i):
    """The held phone (part 'phone') rides the near-hand bone; 'fingers' wrap its edge. Visibility is keyframed via scale."""
    P = c.P
    J = R.side_joints(P, "R")
    if "phone" not in c.man["parts"]:
        return
    p = c.man["parts"]["phone"]
    hand_bone = "HAND_R"
    a = math.radians(R.REST["arm"] + R.REST["elbow"] + R.REST["wrist"])
    off = (P["hand"] * 0.62, 6.0)                                 # phone centre relative to the wrist along/perp the hand axis (v2 fallback)
    ax, ay = math.sin(a), -math.cos(a)                            # hand axis (pointing down-forward)
    px_, py_ = J["wrist"][0] + ax * off[0] + ay * off[1] * -1, J["wrist"][1] + ay * off[0] + ax * off[1]
    rot_extra = 0.0
    pp = (c.man.get("hand_anchors", {}).get("hold_phone", {}) or {}).get("prop_phone")
    if pp:                                                        # v3: the phone sits where the real hand drawing holds it
        lx, ly, th = pp
        fx, fy = math.cos(a), math.sin(a)                         # perpendicular (forward-ish)
        px_, py_ = J["wrist"][0] + fx * lx + ax * ly, J["wrist"][1] + fy * lx + ay * ly
        rot_extra = th
    ob = add_textured_part_at(c, "phone", order_i, (px_, py_), (math.degrees(a) - rot_extra) if pp else 0.0, hand_bone)
    c.parts["phone"] = ob
    if pp:                                                        # perspective flatten: a phone lying on the table is a thin slab seen from the side; it turns face-on as it is lifted
        vs = [Vector(v.co) for v in ob.data.vertices]
        ctr = sum(vs, Vector((0, 0, 0))) / 4.0
        wd = (vs[1] - vs[0]).normalized()
        ob.shape_key_add(name="Basis")
        fk = ob.shape_key_add(name="flat")
        for v, w in zip(fk.data, vs):
            v.co = w - wd * ((w - ctr).dot(wd) * 0.86)
        c.phone_flat = fk
    for extra in ("card", "money"):                                          # other held props share the grip point
        if extra in c.man["parts"]:
            c.parts[extra] = add_textured_part_at(c, extra, order_i, (px_ + 8 * ax, py_ + 8 * ay), rest_angle_deg("hand_R") + 90.0, hand_bone)
    if "fingers" in c.man["parts"]:
        f = add_textured_part_at(c, "fingers", order_i + 1, (J["wrist"][0] + ax * P["hand"] * 0.78, J["wrist"][1] + ay * P["hand"] * 0.78), rest_angle_deg("hand_R"), hand_bone)
        c.parts["fingers"] = f


def add_textured_part_at(c, pname, order_i, joint_xy, angle_deg, bone):
    p = c.man["parts"][pname]
    px, py = p["pivot"]
    w, h = p["size"]
    res = p["res"]
    a = math.radians(angle_deg)
    corners = [(-px / res, py / res), ((w - px) / res, py / res), ((w - px) / res, -(h - py) / res), (-px / res, -(h - py) / res)]
    verts = []
    for (x, y) in corners:
        rx = x * math.cos(a) - y * math.sin(a)                 # angle_deg is COUNTER-CLOCKWISE (y up), the same convention as add_textured_part
        ry = x * math.sin(a) + y * math.cos(a)
        verts.append(to3((joint_xy[0] + rx, joint_xy[1] + ry), c.facing))
    ob = _obj_from_mesh(pname + "_" + c.spec["id"], verts, [(0, 1, 2, 3)], [(0, 1), (1, 1), (1, 0), (0, 0)])
    ob.location = (c.arm.location.x, c.obj_y - 0.004 * order_i, c.arm.location.z)
    ob.data.materials.append(tex_material(os.path.join(ROOT, p["png"])))
    skin_to(c, ob, bone)
    return ob


# ------------------------------------------------------------------------------------------------------------------ animation
def local_vec(c, bone, dx, dy):
    """A rig-space displacement (forward, up) -> the pose-bone `location` vector of `bone` (bone rest frame)."""
    v = Vector((c.facing * dx * S, 0.0, dy * S))
    return c.rest3[bone].inverted() @ v


def rz(c, deg):
    """UPRIGHT bones (spine, neck, head, hair ...): + = lean/turn FORWARD (clockwise for a character facing right)."""
    return c.zsign * c.facing * math.radians(deg)


def rzl(c, deg):
    """HANGING limbs (hand, foot): + = swing FORWARD (counter-clockwise for a limb pointing down)."""
    return -c.zsign * c.facing * math.radians(deg)


def setc(ch, name, f, default=0.0):
    arr = ch.get(name)
    if arr is None:
        return default
    return arr[f] if f < len(arr) else arr[-1]


def key_pose(c, f, fi):
    ch = c.spec["channels"]
    A = c.arm
    pb = A.pose.bones
    g = lambda n, d=0.0: setc(ch, n, fi, d)
    for b in pb:
        b.rotation_mode = "XYZ"
    if "char_vis" in ch:                                                                    # a view-set that becomes visible again must get its normal scale back
        skip = set(c.face.values()) | ({c.parts["nose"]} if "nose" in c.parts else set()) if c.man.get("view") == "back" else set()
        for ob in c.all_objs:
            if ob not in skip:
                ob.scale = (1.0, 1.0, 1.0)
    pb["ROOT"].location = local_vec(c, "ROOT", g("root_x"), g("root_y"))
    pb["PELVIS"].location = local_vec(c, "PELVIS", g("pelvis_dx"), g("pelvis_dy"))
    for bn, chn in (("SPINE", "spine_rot"), ("CHEST", "chest_rot"), ("NECK", "neck_rot"), ("HEAD", "head_rot"), ("HAIR", "hair_rot")):
        pb[bn].rotation_euler = (0.0, 0.0, rz(c, g(chn)))
    for bn, chn in (("HAND_L", "hand_L_rot"), ("HAND_R", "hand_R_rot")):
        pb[bn].rotation_euler = (0.0, 0.0, rzl(c, g(chn)))
    for side in ("L", "R"):
        pb["SHOULDER_" + side].location = local_vec(c, "SHOULDER_" + side, g("shrug") * 0.0, g("shrug") * 14.0)
        pb["SHOULDER_" + side].rotation_euler = (0.0, 0.0, 0.0)
    # IK targets (absolute in the stage frame; character origin at the ground point)
    for name in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R"):
        key = name[3:].lower()                                                    # hand_l / foot_r
        e = c.ik[name]
        nm = key.replace("_l", "_L").replace("_r", "_R")
        rj = c.JS[key[-1].upper()]["wrist"] if key.startswith("hand") else c.JS[key[-1].upper()]["ankle"]
        tx, ty = g(nm + "_x", rj[0]), g(nm + "_y", rj[1])
        e.location = (c.arm.location.x + c.facing * tx * S, c.obj_y, c.arm.location.z + ty * S)
    # foot orientation: keep the sole flat (or pitched) in the WORLD regardless of the leg chain (compensated in Python from the analytic solution)
    for side in ("L", "R"):
        pb["FOOT_" + side].rotation_euler = (0.0, 0.0, rzl(c, g("foot_%s_local" % side)))
    # SEED the IK chains with the analytic 2-bone solution (branch selection): Blender's IK solver starts from this FK pose and refines it to the exact
    # target under the joint limits, so knees/elbows always bend the natural way; the final pose is Blender's IK, not the seed.
    P = c.P
    hip0 = (g("root_x") + g("pelvis_dx"), P["hip_y"] + g("root_y") + g("pelvis_dy"))
    lean = math.radians(g("spine_rot") + g("chest_rot"))
    hh = P["shoulder_joint_y"] - P["hip_y"]
    sh0 = (hip0[0] + hh * math.sin(lean), hip0[1] + hh * math.cos(lean))
    so = R.side_offsets(P)
    hipL, hipR = (hip0[0] + so["hL"], hip0[1]), (hip0[0] + so["hR"], hip0[1])
    shL, shR = (sh0[0] + so["sL"], sh0[1]), (sh0[0] + so["sR"], sh0[1])
    Rr = R.REST
    chains = (("THIGH_L", "SHIN_L", hipL, "foot_L", P["thigh"], P["shin"], +1, Rr["thigh"], Rr["thigh"] + Rr["knee"], 0.0, c.JS["L"]["ankle"]),
              ("THIGH_R", "SHIN_R", hipR, "foot_R", P["thigh"], P["shin"], +1, Rr["thigh"], Rr["thigh"] + Rr["knee"], 0.0, c.JS["R"]["ankle"]),
              ("ARM_L", "FOREARM_L", shL, "hand_L", P["upper_arm"], P["forearm"], -1, Rr["arm"], Rr["arm"] + Rr["elbow"], -(g("spine_rot") + g("chest_rot")), c.JS["L"]["wrist"]),
              ("ARM_R", "FOREARM_R", shR, "hand_R", P["upper_arm"], P["forearm"], -1, Rr["arm"], Rr["arm"] + Rr["elbow"], -(g("spine_rot") + g("chest_rot")), c.JS["R"]["wrist"]))
    for up, low, base, key, l1, l2, bend, r1, r2, parent_ccw, rj in chains:
        tgt = (g(key + "_x", rj[0]), g(key + "_y", rj[1]))
        _, _, a1, a2 = R.two_bone(base, tgt, l1, l2, bend)
        d1 = a1 - r1 - parent_ccw                                           # upper bone: CCW-positive delta from rest, minus the parent's rotation
        d2 = (a2 - a1) - (r2 - r1)                                         # lower bone: relative to the upper bone
        pb[up].rotation_euler = (0.0, 0.0, -c.zsign * c.facing * math.radians(d1))
        pb[low].rotation_euler = (0.0, 0.0, -c.zsign * c.facing * math.radians(d2))
    # face
    ez = g("blink")
    wide = g("wide")
    lid = g("lid")
    ey_scale = max(0.06, (1.0 - ez) * (1.0 - 0.45 * lid) * (1.0 - 0.42 * g("narrow")))
    for side in ("L", "R"):
        eb = pb["EYE_" + side]
        eb.location = local_vec(c, "EYE_" + side, g("gaze_x") * 8.5 * c.P["hs"], g("gaze_y") * 6.0 * c.P["hs"])
        eb.scale = (ey_scale, 1.0, 1.0)                                         # local X is the bone's vertical
        sb = pb["BROW_" + side]
        sgn = -1.0 if side == "L" else 1.0
        asym = g("brow_asym") * (1.0 if side == "L" else -1.0)
        sb.location = local_vec(c, "BROW_" + side, 0.0, (g("brow_raise") * 26.0 + asym * 9.0) * c.P["hs"])
        sb.rotation_euler = (0.0, 0.0, rz(c, 32.0 * g("brow_tilt") * sgn))
        for kn in ("eyewhite_", "eyering_"):
            kb = c.face[kn + side].data.shape_keys.key_blocks["wide"]
            kb.value = max(0.0, min(1.0, wide))
    mo = g("mouth_open")
    pb["MOUTH"].scale = (max(0.04, mo), 1.0, 1.0)
    mb = c.face["mouth_line"].data.shape_keys.key_blocks
    sm = g("mouth_smile")
    wr = g("mouth_worried")
    mb["smile"].value, mb["frown"].value, mb["worried"].value = max(0.0, sm), max(0.0, -sm) * (1.0 - wr), max(0.0, min(1.0, wr))
    cb = c.face["mouth_cavity"].data.shape_keys.key_blocks
    for vn in VISEMES:
        cb[vn].value = max(0.0, min(1.0, g("vis_" + vn)))
    # reusable hand poses: exactly one pose mesh per wrist is drawn (scale keyed)
    for side in ("L", "R"):
        idx = int(round(g("hand_%s_pose" % side, 0.0)))
        for j, (pose, ob) in enumerate(c.handposes[side]):
            v = 1.0 if j == idx else 0.0001
            ob.scale = (v, v, v)
    # visibility of held phone / gripping fingers (scale to 0 = not drawn)
    for pn, cn in (("phone", "phone_vis"), ("card", "card_vis"), ("money", "money_vis"), ("fingers", "fingers_vis")):
        if pn not in c.parts:
            continue
        v = 1.0 if g(cn) > 0.5 else 0.0
        c.parts[pn].scale = (v, v, v) if v else (0.0001, 0.0001, 0.0001)
    if getattr(c, "phone_flat", None) is not None:
        c.phone_flat.value = max(0.0, min(1.0, g("phone_flat")))
    hidden = "char_vis" in ch and g("char_vis", 1.0) < 0.5                                   # replacement-drawing turns: only one view-set of a character is drawn at a time
    if hidden:
        for ob in c.all_objs:
            ob.scale = (0.0001, 0.0001, 0.0001)
    # keyframes
    for b in pb:
        for path in ("location", "rotation_euler", "scale"):
            b.keyframe_insert(path, frame=f)
    for e in c.ik.values():
        e.keyframe_insert("location", frame=f)
    for ob in c.face.values():
        if ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks[1:]:
                kb.keyframe_insert("value", frame=f)
    for pn in ("phone", "card", "money", "fingers"):
        if pn in c.parts:
            c.parts[pn].keyframe_insert("scale", frame=f)
    if getattr(c, "phone_flat", None) is not None:
        c.phone_flat.keyframe_insert("value", frame=f)
    if "char_vis" in ch:
        for ob in c.all_objs:
            ob.keyframe_insert("scale", frame=f)
    for side in ("L", "R"):
        for pose, ob in c.handposes[side]:
            ob.keyframe_insert("scale", frame=f)


t0 = time.time()
for i, spec in enumerate(job["characters"]):
    CH.append(build_char(spec, i))
print("BUILD_DONE", round(time.time() - t0, 1), "s", len(bpy.data.objects), "objects")

frames = list(range(F0, F1 + 1))
for fi, f in enumerate(frames):
    for c in CH:
        key_pose(c, f, fi)
print("KEYS_DONE", round(time.time() - t0, 1), "s")

# camera keyframes
camc = job["camera"]
for fi, f in enumerate(frames):
    g = lambda n: camc[n][fi] if isinstance(camc[n], list) else camc[n]
    cam.location = (g("cx") * S, -50.0, -g("cy") * S)
    cam_d.ortho_scale = (W / g("zoom")) * S
    cam.keyframe_insert("location", frame=f)
    cam_d.keyframe_insert("ortho_scale", frame=f)

os.makedirs(job["out"], exist_ok=True)
report = dict(ik_error_px=[], frames=len(frames), zsign={c.spec["id"]: c.zsign for c in CH}, objects=len(bpy.data.objects), blender=bpy.app.version_string,
              bones={c.spec["id"]: len(c.arm.data.bones) for c in CH}, ik_constraints={c.spec["id"]: sum(1 for b in c.arm.pose.bones for k in b.constraints if k.type == "IK") for c in CH},
              actions=len(bpy.data.actions))
probe = set(job.get("probe_frames", frames[::max(1, len(frames) // 12)]))
tr = time.time()
only = set(job["render_frames"]) if job.get("render_frames") is not None else None
for fi, f in enumerate(frames):
    if only is not None and f not in only and f not in probe:
        continue
    sc.frame_set(f)
    if f in probe:                                   # measure how well Blender's IK solver reached the targets (px)
        for c in CH:
            errs = {}
            for name, up, low, end, _ in R.IK:
                tip = c.arm.matrix_world @ c.arm.pose.bones[low].tail
                tgt = c.ik[name].matrix_world.translation
                errs[name] = round((tip - tgt).length / S, 2)
            report["ik_error_px"].append(dict(frame=f, char=c.spec["id"], **errs))
    if job.get("render", True) and (only is None or f in only):
        sc.render.filepath = os.path.join(job["out"], "%s%05d.png" % (job.get("prefix", "f"), f))
        bpy.ops.render.render(write_still=True)
report["render_seconds"] = round(time.time() - tr, 1)
report["rendered_frames"] = len(only) if only is not None else len(frames)
json.dump(report, open(os.path.join(job["out"], "report.json"), "w"), indent=1)
if job.get("save_blend"):
    bpy.ops.wm.save_as_mainfile(filepath=job["save_blend"])
print("SKELETON_DONE", json.dumps({k: report[k] for k in ("frames", "render_seconds", "objects")}))
