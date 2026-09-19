"""Character: rahul.

A recurring CHARACTER MODEL (not an image asset): armature + a continuous
Skin-modifier-generated body + a separate clothing overlay + a minimal face
rig. Built procedurally so it is deterministic, reproducible and
license-free.

v2 note: v1 built the body from joined primitives (cylinders/boxes/spheres)
and read as a blocky prototype — hard seams at every joint. This version
builds the body from a single continuous vertex/edge "skeleton" mesh
(matching the armature's joint positions) run through Blender's Skin +
Subdivision Surface modifiers, which is a well-established technique for
generating a smooth, tapered, seamless humanoid silhouette from a stick
figure. Vertex groups assigned on the seed skeleton propagate through
Skin/Subsurf via interpolation, so the result is still rigged to the same
armature below — same bones, same pose/emotion API, just a better-looking
mesh generator underneath.

Rig convention:
- world units = meters. REST POSE IS SEATED (legs already extended -Y,
  torso already upright, arm relaxed toward the lap) — z=0 is hip/seat
  height, facing -Y. See "why rest = seated" below.
- bone local rotation: X axis = flex/extend.

Why rest = seated: v2's first attempt kept the v1 standing rest pose (legs
hanging down) and reached the sitting pose via a ~90 degree pelvis/spine
counter-rotation at pose time. That is a huge relative rotation between
adjacent bones, and under Skin-modifier geometry it tore visibly at the
pelvis/spine boundary no matter how the vertex weights were computed —
any hard-ish weight boundary shows when the two sides it separates are
rotating ~180 degrees apart. Making the seated posture the REST pose
means the only bones that need to move for the "reach for phone" beat are
the arm bones, a much smaller rotation that a simple nearest-bone rigid
weighting (see _bind_nearest_bone_weights) can actually carry.
"""
import bpy
import bmesh
import math
from mathutils import Vector

CHAR_ID = "rahul"

# (bone_name, parent, head, tail, deform)
BONES = [
    ("root", None, (0, 0, -0.05), (0, 0, 0.05), False),
    ("pelvis", "root", (0, 0, 0.05), (0, 0, 0.15), True),
    ("spine", "pelvis", (0, 0, 0.15), (0, 0, 0.35), True),
    ("chest", "spine", (0, 0, 0.35), (0, 0, 0.52), True),
    ("neck", "chest", (0, 0, 0.52), (0, 0, 0.60), True),
    ("head", "neck", (0, 0, 0.60), (0, 0, 0.78), True),

    ("shoulder.R", "chest", (0.06, 0, 0.50), (0.17, 0, 0.48), True),
    ("upperarm.R", "shoulder.R", (0.17, 0, 0.48), (0.15, -0.10, 0.27), True),
    ("forearm.R", "upperarm.R", (0.15, -0.10, 0.27), (0.09, -0.20, 0.15), True),
    ("hand.R", "forearm.R", (0.09, -0.20, 0.15), (0.06, -0.26, 0.09), True),

    ("shoulder.L", "chest", (-0.06, 0, 0.50), (-0.17, 0, 0.48), True),
    ("upperarm.L", "shoulder.L", (-0.17, 0, 0.48), (-0.15, -0.10, 0.27), True),
    ("forearm.L", "upperarm.L", (-0.15, -0.10, 0.27), (-0.09, -0.20, 0.15), True),
    ("hand.L", "forearm.L", (-0.09, -0.20, 0.15), (-0.06, -0.26, 0.09), True),

    ("thigh.R", "pelvis", (0.10, 0, 0.05), (0.10, -0.42, 0.03), True),
    ("shin.R", "thigh.R", (0.10, -0.42, 0.03), (0.10, -0.80, 0.02), True),
    ("foot.R", "shin.R", (0.10, -0.80, 0.02), (0.10, -0.92, 0.02), True),

    ("thigh.L", "pelvis", (-0.10, 0, 0.05), (-0.10, -0.42, 0.03), True),
    ("shin.L", "thigh.L", (-0.10, -0.42, 0.03), (-0.10, -0.80, 0.02), True),
    ("foot.L", "shin.L", (-0.10, -0.80, 0.02), (-0.10, -0.92, 0.02), True),
]

CLOTH_COLOR = (0.09, 0.10, 0.19)
SKIN_COLOR = (0.62, 0.42, 0.30)
HAIR_COLOR = (0.03, 0.025, 0.025)
EYE_COLOR = (0.05, 0.04, 0.035)

# Seed skeleton for the BODY (skin) layer: (name, position, radius, bone_group)
# `bone_group` is unused now (weighting is proximity-based, see
# _bind_nearest_bone_weights) but kept for readability/debugging.
BODY_VERTS = [
    ("pelvis", (0, 0, 0.03), 0.100, "pelvis"),
    ("spine", (0, 0, 0.17), 0.086, "spine"),
    ("chest", (0, 0, 0.375), 0.118, "chest"),
    ("neck", (0, 0, 0.535), 0.046, "neck"),
    ("head_base", (0, 0, 0.60), 0.088, "head"),
    ("head_mid", (0, 0.01, 0.715), 0.108, "head"),
    ("head_top", (0, -0.005, 0.81), 0.078, "head"),

    ("shoulder.R", (0.145, 0, 0.475), 0.050, "upperarm.R"),
    ("elbow.R", (0.155, -0.10, 0.275), 0.040, "forearm.R"),
    ("wrist.R", (0.10, -0.19, 0.15), 0.030, "hand.R"),
    ("hand.R", (0.07, -0.25, 0.09), 0.033, "hand.R"),

    ("shoulder.L", (-0.145, 0, 0.475), 0.050, "upperarm.L"),
    ("elbow.L", (-0.155, -0.10, 0.275), 0.040, "forearm.L"),
    ("wrist.L", (-0.10, -0.19, 0.15), 0.030, "hand.L"),
    ("hand.L", (-0.07, -0.25, 0.09), 0.033, "hand.L"),

    ("hip.R", (0.095, 0, 0.02), 0.072, "thigh.R"),
    ("knee.R", (0.10, -0.42, 0.005), 0.058, "shin.R"),
    ("ankle.R", (0.10, -0.80, -0.005), 0.040, "foot.R"),
    ("toe.R", (0.10, -0.92, -0.02), (0.036, 0.055), "foot.R"),

    ("hip.L", (-0.095, 0, 0.02), 0.072, "thigh.L"),
    ("knee.L", (-0.10, -0.42, 0.005), 0.058, "shin.L"),
    ("ankle.L", (-0.10, -0.80, -0.005), 0.040, "foot.L"),
    ("toe.L", (-0.10, -0.92, -0.02), (0.036, 0.055), "foot.L"),
]
BODY_EDGES = [
    ("pelvis", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head_base"),
    ("head_base", "head_mid"), ("head_mid", "head_top"),
    ("chest", "shoulder.R"), ("shoulder.R", "elbow.R"), ("elbow.R", "wrist.R"), ("wrist.R", "hand.R"),
    ("chest", "shoulder.L"), ("shoulder.L", "elbow.L"), ("elbow.L", "wrist.L"), ("wrist.L", "hand.L"),
    ("pelvis", "hip.R"), ("hip.R", "knee.R"), ("knee.R", "ankle.R"), ("ankle.R", "toe.R"),
    ("pelvis", "hip.L"), ("hip.L", "knee.L"), ("knee.L", "ankle.L"), ("ankle.L", "toe.L"),
]
BODY_ROOTS = {"pelvis", "chest"}

# Clothing overlay: short-sleeve top over torso/shoulders/upper-arms + shorts
# over hips/thighs. Radii are deliberately larger than the matching BODY_VERTS
# entries so the layer reads as fabric sitting over the body, not a second
# body clipping through the first.
CLOTH_VERTS = [
    ("waist", (0, 0, 0.0), 0.108, "pelvis"),
    ("spine", (0, 0, 0.17), 0.096, "spine"),
    ("chest", (0, 0, 0.375), 0.132, "chest"),
    ("upper_chest", (0, 0, 0.46), 0.112, "chest"),
    ("collar", (0, 0, 0.525), 0.088, "chest"),

    ("shoulder.R", (0.145, 0, 0.475), 0.062, "upperarm.R"),
    ("sleeve.R", (0.16, -0.09, 0.35), 0.056, "upperarm.R"),

    ("shoulder.L", (-0.145, 0, 0.475), 0.062, "upperarm.L"),
    ("sleeve.L", (-0.16, -0.09, 0.35), 0.056, "upperarm.L"),

    ("hip.R", (0.095, 0, 0.02), 0.082, "thigh.R"),
    ("short_hem.R", (0.10, -0.28, 0.02), 0.066, "thigh.R"),

    ("hip.L", (-0.095, 0, 0.02), 0.082, "thigh.L"),
    ("short_hem.L", (-0.10, -0.28, 0.02), 0.066, "thigh.L"),
]
CLOTH_EDGES = [
    ("waist", "spine"), ("spine", "chest"), ("chest", "upper_chest"), ("upper_chest", "collar"),
    ("chest", "shoulder.R"), ("shoulder.R", "sleeve.R"),
    ("chest", "shoulder.L"), ("shoulder.L", "sleeve.L"),
    ("waist", "hip.R"), ("hip.R", "short_hem.R"),
    ("waist", "hip.L"), ("hip.L", "short_hem.L"),
]
CLOTH_ROOTS = {"waist", "chest"}

DEFORM_BONES = [(n, h, t) for n, p, h, t, d in BONES if d]


def _closest_dist_to_segment(p, a, b):
    p, a, b = Vector(p), Vector(a), Vector(b)
    ab = b - a
    len_sq = ab.length_squared
    t = 0.0 if len_sq < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / len_sq))
    return (p - (a + ab * t)).length


def _bind_nearest_bone_weights(obj, bone_segments=DEFORM_BONES):
    """Assigns each vertex 100% to its single nearest bone segment (rest
    pose). Rigid, not smooth-blended — acceptable here because Gate 1's
    acting is subtle (breathing, head turn, shoulder tension), not big
    joint bends where a hard weight boundary would visibly facet."""
    mesh = obj.data
    groups = {}
    for v in mesh.vertices:
        best_name, best_dist = None, None
        for name, head, tail in bone_segments:
            d = _closest_dist_to_segment(v.co, head, tail)
            if best_dist is None or d < best_dist:
                best_dist, best_name = d, name
        if best_name not in groups:
            groups[best_name] = obj.vertex_groups.new(name=best_name)
        groups[best_name].add([v.index], 1.0, 'REPLACE')


def _bake_modifiers(obj):
    """Evaluates Skin+Subsurf into real static geometry and strips the
    modifiers, so weighting happens on the final vertex count/positions."""
    dg = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(eval_obj)
    old_mesh = obj.data
    obj.modifiers.clear()
    obj.data = baked
    bpy.data.meshes.remove(old_mesh)


def _material(name, color, roughness=0.75):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _build_armature(name):
    arm_data = bpy.data.armatures.new(name + "_data")
    arm_obj = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    ebones = {}
    for bname, parent, head, tail, deform in BONES:
        eb = arm_data.edit_bones.new(bname)
        eb.head = head
        eb.tail = tail
        eb.use_deform = deform
        ebones[bname] = eb
    for bname, parent, *_ in BONES:
        if parent:
            ebones[bname].parent = ebones[parent]
            ebones[bname].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def _build_skin_layer(coll, name, verts_spec, edges_spec, roots, material, subsurf_levels=2, bone_segments=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm = bmesh.new()
    index_of = {}
    for i, (vname, pos, radius, group) in enumerate(verts_spec):
        bm.verts.new(pos)
        index_of[vname] = i
    bm.verts.ensure_lookup_table()
    for a, b in edges_spec:
        bm.edges.new((bm.verts[index_of[a]], bm.verts[index_of[b]]))
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)

    skin_mod = obj.modifiers.new("Skin", 'SKIN')
    skin_layer = mesh.skin_vertices[0]
    for vname, pos, radius, group in verts_spec:
        r = radius if isinstance(radius, tuple) else (radius, radius)
        skin_layer.data[index_of[vname]].radius = r
        if vname in roots:
            skin_layer.data[index_of[vname]].use_root = True

    sub_mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    sub_mod.levels = subsurf_levels
    sub_mod.render_levels = subsurf_levels

    # Bake Skin+Subsurf to real geometry, then weight the BAKED vertices by
    # nearest-bone-segment. (Relying on the Skin modifier to propagate the
    # seed mesh's vertex groups through to the generated surface produced
    # visibly broken deformation at branch points — see git history / v1
    # notes. Proximity-based rebinding after baking is more code but
    # actually correct.)
    _bake_modifiers(obj)
    _bind_nearest_bone_weights(obj, bone_segments or DEFORM_BONES)

    obj.data.materials.append(material)
    return obj


def _add_face_feature(coll, name, size, location, mat, parent_arm, bone):
    """Places obj at an absolute (armature-space) `location` and binds it to
    `bone` via a CHILD_OF constraint with the inverse baked at the bone's
    CURRENT matrix (call this before posing). This is deliberately not
    parent_type='BONE': that attaches relative to the bone's rest-space
    frame (tail-relative, roll-axis dependent) rather than world space, and
    silently drifts once the bone is posed by anything more than a few
    degrees."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.scale = size
    obj.name = name
    obj.data.materials.append(mat)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    bpy.context.view_layer.update()
    bone_matrix_world = parent_arm.matrix_world @ parent_arm.pose.bones[bone].matrix
    con = obj.constraints.new('CHILD_OF')
    con.target = parent_arm
    con.subtarget = bone
    con.inverse_matrix = bone_matrix_world.inverted()
    return obj


def build(collection_name="Char_Rahul"):
    if collection_name in bpy.data.collections:
        coll = bpy.data.collections[collection_name]
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)

    arm_obj = _build_armature("RIG_rahul")
    for c in list(arm_obj.users_collection):
        c.objects.unlink(arm_obj)
    coll.objects.link(arm_obj)

    skin_mat = _material("Mat_Rahul_Skin", SKIN_COLOR, roughness=0.55)
    cloth_mat = _material("Mat_Rahul_Cloth", CLOTH_COLOR, roughness=0.85)

    body = _build_skin_layer(coll, "CHAR_rahul_body", BODY_VERTS, BODY_EDGES, BODY_ROOTS, skin_mat)
    body.parent = arm_obj
    body_arm_mod = body.modifiers.new("Armature", 'ARMATURE')
    body_arm_mod.object = arm_obj

    cloth = _build_skin_layer(coll, "CHAR_rahul_cloth", CLOTH_VERTS, CLOTH_EDGES, CLOTH_ROOTS, cloth_mat, subsurf_levels=2)
    cloth.parent = arm_obj
    cloth_arm_mod = cloth.modifiers.new("Armature", 'ARMATURE')
    cloth_arm_mod.object = arm_obj

    hair_mat = _material("Mat_Rahul_Hair", HAIR_COLOR, roughness=0.35)
    hair = _build_skin_layer(
        coll, "CHAR_rahul_hair",
        [("crown", (0, 0.02, 0.72), 0.075, "head"), ("cap", (0, -0.03, 0.835), 0.09, "head")],
        [("crown", "cap")], {"crown"}, hair_mat, subsurf_levels=2,
    )
    hair.parent = arm_obj
    hair_arm_mod = hair.modifiers.new("Armature", 'ARMATURE')
    hair_arm_mod.object = arm_obj

    eye_mat = _material("Mat_Rahul_Eye", EYE_COLOR, roughness=0.2)
    brow_mat = _material("Mat_Rahul_Brow", HAIR_COLOR, roughness=0.5)
    mouth_mat = _material("Mat_Rahul_Mouth", (0.25, 0.08, 0.08), roughness=0.6)

    face = {}
    face["eye.R"] = _add_face_feature(coll, "Face_Eye.R", (0.015, 0.014, 0.015), (0.032, -0.10, 0.715), eye_mat, arm_obj, "head")
    face["eye.L"] = _add_face_feature(coll, "Face_Eye.L", (0.015, 0.014, 0.015), (-0.032, -0.10, 0.715), eye_mat, arm_obj, "head")
    face["brow"] = _add_face_feature(coll, "Face_Brow", (0.095, 0.012, 0.013), (0.0, -0.095, 0.755), brow_mat, arm_obj, "head")
    face["mouth"] = _add_face_feature(coll, "Face_Mouth", (0.04, 0.012, 0.011), (0.0, -0.10, 0.645), mouth_mat, arm_obj, "head")

    return {"armature": arm_obj, "body": body, "cloth": cloth, "hair": hair, "face": face, "collection": coll}


# Named pose states, expressed as deltas from the seated rest pose. Legs
# and the L arm barely move across ANY of these — only chest/neck/head/R-arm
# carry the acting, which is deliberate: big relative rotations are what
# tore the Skin-modifier mesh (see module docstring), and it also just
# matches how a person actually reacts to their phone while sitting still.
POSES = {
    # Alone, relaxed, phone resting in hand, not looking at it.
    "base": {
        "chest": (-2, 0, 0), "neck": (5, 0, 5), "head": (5, 0, 7),
        "thigh.R": (0, 0, 2), "thigh.L": (0, 0, -4),
    },
    # The screen just lit up at the edge of vision — a small, incomplete
    # turn toward it, arm hasn't moved yet. This is the "notices it" beat.
    "notice": {
        "chest": (-3, 0, 0), "neck": (7, 0, -6), "head": (8, 0, -10),
        "thigh.R": (0, 0, 2), "thigh.L": (0, 0, -4),
    },
    # Committed: phone raised to face, head down and in toward it.
    "phone": {
        "chest": (-6, 0, 0), "neck": (16, 0, 2), "head": (14, 0, 3),
        "upperarm.R": (-88, 8, -14), "forearm.R": (98, 0, 0), "hand.R": (-8, 0, 0),
        "upperarm.L": (-6, 0, 2), "forearm.L": (6, 0, 0),
        "thigh.R": (0, 0, 2), "thigh.L": (0, 0, -4),
    },
    # Realization settles into the shoulders/neck — a slight further sink
    # and tuck, not a big new gesture.
    "realization": {
        "chest": (-9, 0, 0), "neck": (19, 0, 4), "head": (17, 0, 5),
        "upperarm.R": (-84, 8, -14), "forearm.R": (100, 0, 0), "hand.R": (-8, 0, 0),
        "upperarm.L": (-9, 0, 2), "forearm.L": (8, 0, 0),
        "thigh.R": (0, 0, 2), "thigh.L": (0, 0, -4),
    },
}


def apply_pose(arm_obj, pose_name):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm_obj.pose.bones
    for bname, (x, y, z) in POSES[pose_name].items():
        b = pb[bname]
        b.rotation_mode = 'XYZ'
        b.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))
    bpy.ops.object.mode_set(mode='OBJECT')


def set_pose_base(arm_obj):
    apply_pose(arm_obj, "base")


def set_pose_sitting_phone(arm_obj):
    apply_pose(arm_obj, "phone")


def keyframe_pose(arm_obj, frame):
    """Keys every deforming pose bone's rotation at the CURRENT pose state."""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    for bname, parent, head, tail, deform in BONES:
        if not deform:
            continue
        arm_obj.pose.bones[bname].keyframe_insert(data_path="rotation_euler", frame=frame)
    bpy.ops.object.mode_set(mode='OBJECT')


def keyframe_pose_named(arm_obj, pose_name, frame, breathe_x_delta=0.0):
    """Applies a named pose (optionally nudging chest-X for a breathing
    beat) and keys it at `frame` in one call."""
    apply_pose(arm_obj, pose_name)
    if breathe_x_delta:
        pb = arm_obj.pose.bones["chest"]
        x, y, z = pb.rotation_euler
        pb.rotation_euler = (x + math.radians(breathe_x_delta), y, z)
    keyframe_pose(arm_obj, frame)


EMOTIONS = {
    "relaxed": {"brow_rot_x": -3, "brow_z": 0.0, "mouth_scale_y": 0.30},
    "curious": {"brow_rot_x": -6, "brow_z": 0.006, "mouth_scale_y": 0.45},
    "uneasy": {"brow_rot_x": 10, "brow_z": -0.004, "mouth_scale_y": 0.32},
    "realization": {"brow_rot_x": -14, "brow_z": 0.01, "mouth_scale_y": 0.22},
}


BASE_BROW_Z = 0.755
BASE_MOUTH_SCALE_Y = 0.011


def set_emotion(face, name):
    cfg = EMOTIONS[name]
    brow = face["brow"]
    brow.rotation_euler = (math.radians(cfg["brow_rot_x"]), 0, 0)
    brow.location.z = BASE_BROW_Z + cfg["brow_z"]
    mouth = face["mouth"]
    mouth.scale.y = BASE_MOUTH_SCALE_Y * cfg["mouth_scale_y"]


def keyframe_emotion(face, name, frame):
    set_emotion(face, name)
    brow, mouth = face["brow"], face["mouth"]
    brow.keyframe_insert(data_path="rotation_euler", frame=frame)
    brow.keyframe_insert(data_path="location", frame=frame)
    mouth.keyframe_insert(data_path="scale", frame=frame)
