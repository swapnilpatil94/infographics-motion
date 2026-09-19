"""Blender-side capability tests for rigged human/stickman candidates (run:  blender -b --disable-autoexec <file> -P blender_audit_tests.py -- <out_dir> <id> [armature_name]).
Every number is measured on the evaluated depsgraph in Blender 5.2.2:
  walk    IK foot targets driven through a stride/lift cycle -> foot tracking error, lift, stride;   sit  feet planted 90/90 (thigh horizontal, shin vertical) -> tip error + knee angle
  reach   hand IK target at 0.5/0.9/1.2 x arm length forward + overhead -> tip error;                hold  cube bone-parented to the hand follows the IK target
  face    shape keys (count, each displaces vertices?), eye-bone rotation displaces vertices?;       proportions  scale leg+spine bones 1.2 -> evaluated mesh height change
  pipeline  how many of our 26 bone roles map to bones by name.
Writes <id>_tests.json and <id>_tests.png (rest, walk contact, walk pass, sit, reach)."""
import json
import math
import os
import re
import sys
import traceback

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, AID = argv[0], argv[1]
ARM = argv[2] if len(argv) > 2 else None
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
R = dict(id=AID, blender=bpy.app.version_string)
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if ARM:
    arms = [o for o in arms if o.name == ARM]
if not arms:
    R["error"] = "no armature"
    json.dump(R, open(os.path.join(OUT, AID + "_tests.json"), "w"), indent=1)
    print("TESTS_OK", AID)
    sys.exit(0)
ob = max(arms, key=lambda o: len(o.data.bones))
R["armature"] = ob.name
LEG = re.compile(r"leg|shin|calf|foot|thigh|knee|ankle|toe", re.I)
ARMR = re.compile(r"arm|hand|elbow|wrist|shoulder", re.I)


def update():
    bpy.context.view_layer.update()


def strip_action():
    """Base pose = the file's idle-ish action (else first action) at its first frame; then the action is removed so the test drives the rig, not the file's animation."""
    if not (ob.animation_data and ob.animation_data.action) and not bpy.data.actions:
        return None
    acts = [a for a in bpy.data.actions if "idle" in a.name.lower()] or list(bpy.data.actions)
    if not ob.animation_data:
        ob.animation_data_create()
    ob.animation_data.action = acts[0] if acts else ob.animation_data.action
    sc.frame_set(int(ob.animation_data.action.frame_range[0]) if ob.animation_data.action else sc.frame_current)
    stash = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy(), pb.scale.copy()) for pb in ob.pose.bones}
    name = ob.animation_data.action.name if ob.animation_data.action else None
    ob.animation_data.action = None
    for pb in ob.pose.bones:
        pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = stash[pb.name]
    bpy.context.view_layer.update()
    return name


def ev():
    return ob.evaluated_get(bpy.context.evaluated_depsgraph_get())


def tail(pb):
    e = ev()
    return e.matrix_world @ e.pose.bones[pb.name].tail


def head(pb):
    e = ev()
    return e.matrix_world @ e.pose.bones[pb.name].head


def goal_pos(c):
    t = c.target
    if t.type == "ARMATURE" and c.subtarget:
        return t.matrix_world @ t.pose.bones[c.subtarget].head
    return t.matrix_world.translation.copy()


def set_goal(c, pos):
    t = c.target
    if t.type == "ARMATURE" and c.subtarget:
        tb = t.pose.bones[c.subtarget]
        M = tb.matrix.copy()
        M.translation = t.matrix_world.inverted() @ Vector(pos)
        tb.matrix = M
    else:
        M = t.matrix_world.copy()
        M.translation = Vector(pos)
        t.matrix_world = M
    update()


def snapshot():
    snap = []
    for pb in ob.pose.bones:
        snap.append((pb, pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy(), pb.scale.copy()))
    return snap


def restore(snap):
    for pb, l, q, e, s in snap:
        pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = l, q, e, s
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o is not ob:
            for pb in o.pose.bones:
                pb.location = (0, 0, 0)
    update()


R['base_pose_from_action'] = strip_action()
# ----------------------------------------------------------------------------------------- IK chains
chains = []
for pb in ob.pose.bones:
    for c in pb.constraints:
        if c.type == "IK" and c.target and (c.target.type != "ARMATURE" or c.subtarget) and c.chain_count != 1:
            n = c.chain_count or (len(list(pb.parent_recursive)) + 1)
            bones = [pb] + list(pb.parent_recursive)[: n - 1]
            key = " ".join([pb.name, c.subtarget or c.target.name] + [b.name for b in bones])
            kind = "leg" if LEG.search(key) and not ARMR.search(pb.name + (c.subtarget or "")) else ("arm" if ARMR.search(key) else "other")
            if LEG.search(pb.name + (c.subtarget or "")):
                kind = "leg"
            side = "L" if re.search(r"(?:^|[._\- ])(l|left)(?:$|[._\- ])|_l$|\.l$", pb.name, re.I) else ("R" if re.search(r"(?:^|[._\- ])(r|right)(?:$|[._\- ])|_r$|\.r$", pb.name, re.I) else "?")
            chains.append(dict(pb=pb, con=c, bones=bones, kind=kind, side=side, length=sum(b.length for b in bones) * ob.matrix_world.to_scale()[0]))
R["ik_chains"] = [dict(tip=c["pb"].name, kind=c["kind"], side=c["side"], bones=[b.name for b in c["bones"]], length_m=round(c["length"], 3)) for c in chains]
legs = [c for c in chains if c["kind"] == "leg"]
handc = [c for c in chains if c["kind"] == "arm"]
update()
rest_snap = snapshot()
goal0 = {id(c): goal_pos(c["con"]) for c in chains}
up = Vector((0, 0, 1))

# forward / lateral from leg IK goal positions (else from bbox)
lateral = Vector((1, 0, 0))
if len(legs) >= 2:
    d = goal0[id(legs[0])] - goal0[id(legs[1])]
    d.z = 0
    if d.length > 1e-4:
        lateral = d.normalized()
forward = up.cross(lateral).normalized()
R["axes"] = dict(lateral=[round(x, 3) for x in lateral], forward=[round(x, 3) for x in forward])


def rerr(c):
    return (tail(c["pb"]) - goal_pos(c["con"])).length * 100


frames = {}      # name -> list of (chain, goal position)
results = {}

# ----------------------------------------------------------------------------------------- walk
try:
    if len(legs) >= 2:
        A, B = legs[0], legs[1]
        stride = 0.22 * A["length"] / 0.9
        lift = 0.12 * A["length"] / 0.9
        errs, tips_f, tips_z = [], {0: [], 1: []}, {0: [], 1: []}
        for i in range(24):
            ph = i / 24.0 * 2 * math.pi
            for k, c in enumerate((A, B)):
                p = ph + k * math.pi
                pos = goal0[id(c)] + forward * (stride * math.sin(p)) + up * (lift * max(0.0, math.cos(p)))
                set_goal(c["con"], pos)
            errs.append(max(rerr(A), rerr(B)))
            for k, c in enumerate((A, B)):
                t = tail(c["pb"])
                tips_f[k].append(t.dot(forward))
                tips_z[k].append(t.z)
            if i == 6:
                frames["walk_contact"] = [(c["con"], goal_pos(c["con"])) for c in (A, B)]
            if i == 12:
                frames["walk_pass"] = [(c["con"], goal_pos(c["con"])) for c in (A, B)]
        results["walk"] = dict(chains=[c["pb"].name for c in (A, B)], foot_track_err_max_cm=round(max(errs), 2), stride_m=round(max(tips_f[0]) - min(tips_f[0]), 3), foot_lift_m=round(max(tips_z[0]) - min(tips_z[0]), 3),
                               alternating_feet=abs(sum(1 for a, b in zip(tips_f[0], tips_f[1]) if (a - b) > 0) - 12) < 8, pass_ik_walk=(max(errs) < 1.0 and (max(tips_f[0]) - min(tips_f[0])) > 0.1))
        for c in (A, B):
            set_goal(c["con"], goal0[id(c)])
    else:
        results["walk"] = dict(pass_ik_walk=False, reason="no 2-bone leg IK chains with a target (walking would need hand-keyed FK)")
except Exception:
    results["walk"] = dict(error=traceback.format_exc()[-300:])

# ----------------------------------------------------------------------------------------- sit
try:
    if len(legs) >= 2:
        sit = []
        for c in legs[:2]:
            root = c["bones"][-1]
            hipw = head(root)
            l1 = c["bones"][-1].length * ob.matrix_world.to_scale()[0]
            l2 = (c["length"] - l1)
            pos = hipw + forward * l1 - up * l2
            set_goal(c["con"], pos)
            sit.append(dict(err_cm=round(rerr(c), 2), knee_deg=None))
            if len(c["bones"]) >= 2:
                th = head(c["bones"][-1]).copy()
                kn = tail(c["bones"][-1])
                ft = tail(c["pb"])
                a, b = (th - kn), (ft - kn)
                sit[-1]["knee_deg"] = round(math.degrees(a.angle(b)), 1)
        frames["sit"] = [(c["con"], goal_pos(c["con"])) for c in legs[:2]]
        results["sit"] = dict(legs=sit, pass_seated_pose=all(s["err_cm"] < 1.0 and s["knee_deg"] and 70 < s["knee_deg"] < 115 for s in sit), note="feet 90/90 relative to hip (thigh horizontal, shin vertical); pelvis lowering / hip rotation not modelled")
        for c in legs:
            set_goal(c["con"], goal0[id(c)])
    else:
        results["sit"] = dict(pass_seated_pose=False, reason="no leg IK")
except Exception:
    results["sit"] = dict(error=traceback.format_exc()[-300:])

# ----------------------------------------------------------------------------------------- reach + hold
try:
    if handc:
        rr = []
        for c in handc[:2]:
            root = c["bones"][-1]
            sh = head(root)
            L = c["length"]
            for label, off in (("0.5L_forward", forward * 0.5 * L), ("0.9L_forward", forward * 0.9 * L), ("0.9L_up", up * 0.9 * L), ("1.2L_forward(out of reach)", forward * 1.2 * L)):
                set_goal(c["con"], sh + off)
                rr.append(dict(hand=c["pb"].name, target=label, err_cm=round(rerr(c), 2)))
                if label == "0.9L_forward" and c is handc[0]:
                    frames["reach"] = [(c["con"], goal_pos(c["con"]))]
            set_goal(c["con"], goal0[id(c)])
        inreach = [r for r in rr if "out of reach" not in r["target"]]
        results["reach"] = dict(trials=rr, pass_reach=all(r["err_cm"] < 1.0 for r in inreach))
        # hold: cube on the hand bone follows the IK target
        c = handc[0]
        cube = bpy.data.objects.new("_audit_cube", bpy.data.meshes.new("_audit_cube"))
        cube.data.from_pydata([(-0.03, -0.03, -0.03), (0.03, -0.03, -0.03), (0.03, 0.03, -0.03), (-0.03, 0.03, -0.03), (-0.03, -0.03, 0.03), (0.03, -0.03, 0.03), (0.03, 0.03, 0.03), (-0.03, 0.03, 0.03)], [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 3, 7, 4)])
        sc.collection.objects.link(cube)
        cube.parent, cube.parent_type, cube.parent_bone = ob, "BONE", c["pb"].name
        update()
        d0 = (cube.matrix_world.translation - tail(c["pb"])).length
        set_goal(c["con"], head(c["bones"][-1]) + forward * 0.6 * c["length"] + up * 0.2)
        d1 = (cube.matrix_world.translation - tail(c["pb"])).length
        moved = (cube.matrix_world.translation - (goal0[id(c)])).length
        results["hold"] = dict(cube_offset_before_cm=round(d0 * 100, 2), cube_offset_after_cm=round(d1 * 100, 2), pass_prop_attach=abs(d1 - d0) < 0.01 and moved > 0.05, hand_bone=c["pb"].name)
        set_goal(c["con"], goal0[id(c)])
        bpy.data.objects.remove(cube)
    else:
        results["reach"] = dict(pass_reach=False, reason="no arm IK")
        results["hold"] = dict(pass_prop_attach=any(re.search("hand|wrist", b.name, re.I) for b in ob.pose.bones), reason="no arm IK; hand bone present: %s" % any(re.search("hand|wrist", b.name, re.I) for b in ob.pose.bones))
except Exception:
    results["reach"] = dict(error=traceback.format_exc()[-300:])

# ----------------------------------------------------------------------------------------- face / eyes
def mesh_positions():
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    skinned = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object is ob for m in o.modifiers)]
    for o in (skinned or [o for o in bpy.data.objects if o.type == "MESH"]):
        if not o.hide_render and o.name != "_audit_cube":
            e = o.evaluated_get(dg)
            m = e.to_mesh()
            mat = e.matrix_world
            out.append([mat @ v.co for v in m.vertices])
            e.to_mesh_clear()
    return out


def disp(a, b):
    tot = 0.0
    mx = 0.0
    for x, y in zip(a, b):
        for p, q in zip(x, y):
            d = (p - q).length
            tot += d
            mx = max(mx, d)
    return tot, mx


try:
    update()
    base = mesh_positions()
    face = dict(shape_keys=0, working_shape_keys=0, expression_named=0, eye_bones=[], eye_rotation_moves_mesh=False)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data.shape_keys:
            kbs = [k for k in o.data.shape_keys.key_blocks if k.name != "Basis"]
            face["shape_keys"] += len(kbs)
            face["expression_named"] += sum(1 for k in kbs if re.search(r"smile|frown|blink|brow|mouth|jaw|eye|sad|angry|happy|surpris|open|cheek|lip|pucker|viseme|aa|oh", k.name, re.I))
            for k in kbs[:60]:
                old = k.value
                k.value = 1.0
                update()
                t, m = disp(base, mesh_positions())
                if m > 1e-4:
                    face["working_shape_keys"] += 1
                k.value = old
    update()
    eyes = [pb for pb in ob.pose.bones if re.search(r"(^|[._\-])eye(?!lid|brow|lash)|pupil|iris", pb.name, re.I) and not re.search(r"proxy|ref|target|track|ctrl|c_", pb.name, re.I)] or [pb for pb in ob.pose.bones if re.search(r"eye", pb.name, re.I)]
    face["eye_bones"] = [pb.name for pb in eyes][:6]
    for pb in eyes[:2]:
        pb.rotation_mode = "XYZ"
        best = 0.0
        for axis in range(3):
            old = pb.rotation_euler.copy()
            e = old.copy()
            e[axis] += math.radians(30)
            pb.rotation_euler = e
            update()
            t, m = disp(base, mesh_positions())
            best = max(best, m)
            pb.rotation_euler = old
        update()
        if best > 1e-4:
            face["eye_rotation_moves_mesh"] = True
            face["eye_max_disp_cm"] = round(best * 100, 2)
    brows = [pb for pb in ob.pose.bones if re.search(r"brow", pb.name, re.I) and not re.search(r"proxy|ref|c_", pb.name, re.I)]
    face["brow_bones"] = len(brows)
    results["face"] = face
except Exception:
    results["face"] = dict(error=traceback.format_exc()[-300:])

# ----------------------------------------------------------------------------------------- proportions
try:
    restore(rest_snap)
    update()
    dg = bpy.context.evaluated_depsgraph_get()

    def height():
        z = [p.z for m in mesh_positions() for p in m]
        return (max(z) - min(z)) if z else 0

    h0 = height()
    for pb in ob.pose.bones:
        if re.search(r"thigh|shin|calf|leg|spine|chest|neck|hip", pb.name, re.I) and not re.search(r"ik|ctrl|proxy|c_|pole|target", pb.name, re.I):
            pb.scale = (1.0, 1.2, 1.0)
    update()
    h1 = height()
    results["proportions"] = dict(height_before_m=round(h0, 3), height_after_m=round(h1, 3), change_pct=round(100 * (h1 / h0 - 1), 1) if h0 else None, pass_bone_scale_changes_body=(h0 > 0 and abs(h1 / h0 - 1) > 0.05))
    restore(rest_snap)
except Exception:
    results["proportions"] = dict(error=traceback.format_exc()[-300:])

# ----------------------------------------------------------------------------------------- pipeline mapping
ROLES = {"PELVIS": r"pelvis|hips?$|c_root|root_master", "SPINE": r"spine|abdomen|torso", "CHEST": r"chest|spine[._]?[34]|c_spine_02|upper", "NECK": r"neck", "HEAD": r"^head|head\b|c_head", "HAND_L": r"hand.*(l|left)\b|hand[._]l|hand_l", "HAND_R": r"hand.*(r|right)\b|hand[._]r|hand_r",
         "FOREARM_L": r"forearm[._]?l|lowerarm[._]?l|lower_arm[._]?l", "FOREARM_R": r"forearm[._]?r|lowerarm[._]?r|lower_arm[._]?r", "ARM_L": r"(^|[._])(arm|upperarm|upper_arm)[._]?l", "ARM_R": r"(^|[._])(arm|upperarm|upper_arm)[._]?r",
         "THIGH_L": r"thigh[._]?l|upperleg[._]?l", "THIGH_R": r"thigh[._]?r|upperleg[._]?r", "SHIN_L": r"shin[._]?l|calf[._]?l|lowerleg[._]?l", "SHIN_R": r"shin[._]?r|calf[._]?r|lowerleg[._]?r", "FOOT_L": r"foot[._]?l", "FOOT_R": r"foot[._]?r",
         "SHOULDER_L": r"shoulder[._]?l|clavicle[._]?l", "SHOULDER_R": r"shoulder[._]?r|clavicle[._]?r", "EYE_L": r"eye[._]?l", "EYE_R": r"eye[._]?r", "BROW": r"brow", "MOUTH": r"mouth|lip|jaw"}
names = [b.name for b in ob.data.bones]
hit = {k: next((n for n in names if re.search(v, n, re.I) and not re.search(r"proxy|_ref|target|pole|ik", n, re.I)), None) for k, v in ROLES.items()}
R["pipeline_mapping"] = dict(mapped=sum(1 for v in hit.values() if v), of=len(ROLES), roles=hit)
R["tests"] = results

# ----------------------------------------------------------------------------------------- pose sheet render
try:
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 300, 420
    sc.display.shading.light = "STUDIO"
    update()
    dg = bpy.context.evaluated_depsgraph_get()
    zs = [p for m in mesh_positions() for p in m]
    lo = Vector((min(p[i] for p in zs) for i in range(3)))
    hi = Vector((max(p[i] for p in zs) for i in range(3)))
    ctr, size = (lo + hi) / 2, hi - lo
    cd = bpy.data.cameras.new("_c")
    cd.type = "ORTHO"
    cd.ortho_scale = max(size.z * 1.6, 0.3)
    cd.clip_end = 1e4
    cam = bpy.data.objects.new("_c", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    side = lateral
    cam.location = ctr + side * (max(size.length, 1) * 2) + Vector((0, 0, 0))
    look = -side
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    paths = []
    order = ["rest", "walk_contact", "walk_pass", "sit", "reach"]
    for nm in order:
        restore(rest_snap)
        for c in chains:
            set_goal(c["con"], goal0[id(c)])
        for con, pos in frames.get(nm, []):
            set_goal(con, pos)
        update()
        p = os.path.join(OUT, f"_{AID}_{nm}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    R["pose_sheet"] = paths
except Exception:
    R["pose_sheet_error"] = traceback.format_exc()[-400:]

json.dump(R, open(os.path.join(OUT, AID + "_tests.json"), "w"), indent=1, default=str)
print("TESTS_OK", AID)
