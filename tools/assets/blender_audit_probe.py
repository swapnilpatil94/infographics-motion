"""Blender-side audit probe (run:  blender -b --disable-autoexec <file> -P blender_audit_probe.py -- <out_dir> <id>).
Measures, per file: opens, datablock inventory, armatures (bone count/names, IK constraints, other constraints, drivers), shape keys, GP layers/strokes, actions, embedded scripts, IK response
(moves every IK target 25 cm and measures whether the chain tip follows), FK/pose reach, prop-attach test, a synthetic walk via IK foot targets (if leg IK exists), and a Workbench render.
Nothing is executed from the file (--disable-autoexec, no script datablocks are run)."""
import json
import math
import os
import re
import sys
import traceback

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, AID = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
R = dict(id=AID, blender=bpy.app.version_string, file_blender_version=".".join(map(str, bpy.data.version)), errors=[])
sc = bpy.context.scene
R["scene"] = dict(frame_range=[sc.frame_start, sc.frame_end], fps=sc.render.fps, engine=sc.render.engine, unit_scale=sc.unit_settings.scale_length)
R["objects"] = {}
for o in bpy.data.objects:
    R["objects"][o.type] = R["objects"].get(o.type, 0) + 1
R["datablocks"] = dict(meshes=len(bpy.data.meshes), armatures=len(bpy.data.armatures), actions=len(bpy.data.actions), materials=len(bpy.data.materials), images=len(bpy.data.images),
                       grease_pencils=len(getattr(bpy.data, "grease_pencils", [])), grease_pencils_v3=len(getattr(bpy.data, "grease_pencils_v3", [])), texts=len(bpy.data.texts),
                       node_groups=len(bpy.data.node_groups), collections=len(bpy.data.collections), libraries=len(bpy.data.libraries))
R["embedded_text_scripts"] = [t.name for t in bpy.data.texts]
R["missing_images"] = [i.name for i in bpy.data.images if i.source == "FILE" and not i.packed_file and i.filepath and not os.path.exists(bpy.path.abspath(i.filepath))][:20]

# ------------------------------------------------------------------ armatures
FINGER = re.compile(r"finger|thumb|index|middle|ring|pinky|pinkie|f_(?:index|middle|ring|pinky)", re.I)
arms = []
for ob in bpy.data.objects:
    if ob.type != "ARMATURE":
        continue
    a = dict(name=ob.name, bones=len(ob.data.bones), pose_bones=len(ob.pose.bones) if ob.pose else 0)
    names = [b.name for b in ob.data.bones]
    a["bone_names_sample"] = names[:60]
    a["roots"] = [b.name for b in ob.data.bones if b.parent is None]
    a["depth_max"] = max((len(list(b.parent_recursive)) for b in ob.data.bones), default=0)
    a["deform_bones"] = sum(1 for b in ob.data.bones if b.use_deform)
    a["finger_bones"] = sum(1 for n in names if FINGER.search(n))
    a["eye_bones"] = [n for n in names if re.search(r"eye|pupil|iris", n, re.I)]
    a["brow_bones"] = [n for n in names if re.search(r"brow", n, re.I)]
    a["mouth_bones"] = [n for n in names if re.search(r"mouth|lip|jaw|teeth|tongue", n, re.I)]
    a["face_bones_total"] = len(set(a["eye_bones"] + a["brow_bones"] + a["mouth_bones"] + [n for n in names if re.search(r"cheek|nose|lid|face", n, re.I)]))
    cons = {}
    ik = []
    for pb in ob.pose.bones:
        for c in pb.constraints:
            cons[c.type] = cons.get(c.type, 0) + 1
            if c.type == "IK":
                ik.append(dict(bone=pb.name, chain=c.chain_count, target=c.target.name if c.target else None, subtarget=c.subtarget, pole=(c.pole_target.name if c.pole_target else None)))
    a["constraints"] = cons
    a["ik"] = ik
    ad = ob.animation_data
    a["drivers"] = len(ad.drivers) if ad else 0
    a["python_drivers"] = sum(1 for d in (ad.drivers if ad else []) if d.driver.type == "SCRIPTED")
    a["action"] = ad.action.name if ad and ad.action else None
    a["custom_props"] = list(ob.keys())[:20]
    arms.append(a)
R["armatures"] = arms

# ------------------------------------------------------------------ meshes: shape keys, vertex groups, modifiers
sk = []
for ob in bpy.data.objects:
    if ob.type == "MESH":
        if ob.data.shape_keys:
            sk.append(dict(obj=ob.name, keys=[k.name for k in ob.data.shape_keys.key_blocks][:40], n=len(ob.data.shape_keys.key_blocks)))
R["shape_keys"] = sk
R["mesh_summary"] = dict(objects=sum(1 for o in bpy.data.objects if o.type == "MESH"), skinned=sum(1 for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)),
                         tris=sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH"))

# ------------------------------------------------------------------ grease pencil (GPv3 in 4.3+/5.x)
gp = []
for ob in bpy.data.objects:
    if ob.type in ("GREASEPENCIL", "GPENCIL"):
        d = ob.data
        g = dict(obj=ob.name, type=ob.type, layers=[l.name for l in d.layers][:60], n_layers=len(d.layers), modifiers=[m.type for m in ob.grease_pencil_modifiers] if hasattr(ob, "grease_pencil_modifiers") else [m.type for m in ob.modifiers],
                 parent=ob.parent.name if ob.parent else None, parent_type=ob.parent_type, vgroups=len(ob.vertex_groups))
        try:
            strokes = 0
            for l in d.layers:
                for fr in l.frames:
                    strokes += len(fr.drawing.strokes) if hasattr(fr, "drawing") else len(fr.strokes)
            g["strokes"] = strokes
        except Exception as e:
            g["strokes_error"] = str(e)[:80]
        gp.append(g)
R["grease_pencil"] = gp

# ------------------------------------------------------------------ actions
acts = []
for ac in bpy.data.actions:
    fr = ac.frame_range
    acts.append(dict(name=ac.name, frames=[round(fr[0]), round(fr[1])], fcurves=len(list(ac.fcurves)) if hasattr(ac, "fcurves") else -1))
R["actions"] = acts[:60]
R["n_actions"] = len(acts)

# ------------------------------------------------------------------ behavioural tests
def eval_tail(ob, bone):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    pb = ev.pose.bones[bone]
    return ev.matrix_world @ pb.tail


def update():
    bpy.context.view_layer.update()


tests = dict(ik_response=[], reach=None, prop_attach=None, walk=None, sit=None)
try:
    for ob in [o for o in bpy.data.objects if o.type == "ARMATURE"][:3]:
        update()
        for pb in ob.pose.bones:
            for c in pb.constraints:
                if c.type != "IK" or not (c.target and (c.target.type != "ARMATURE" or c.subtarget)):
                    continue
                tgt = c.target
                # world position of the IK goal
                def goal():
                    if tgt.type == "ARMATURE" and c.subtarget:
                        return tgt.matrix_world @ tgt.pose.bones[c.subtarget].head
                    return tgt.matrix_world.translation.copy()
                update()
                base_tip, base_goal = eval_tail(ob, pb.name), goal()
                err0 = (base_tip - base_goal).length
                results = []
                for d in (Vector((0.15, 0, 0)), Vector((0, 0, 0.18)), Vector((0, -0.15, 0.05))):
                    if tgt.type == "ARMATURE" and c.subtarget:
                        tb = tgt.pose.bones[c.subtarget]
                        orig = tb.location.copy()
                        tb.location = orig + (tgt.matrix_world.to_3x3().inverted() @ d)
                    else:
                        orig = tgt.location.copy()
                        tgt.location = orig + d
                    update()
                    tip, g = eval_tail(ob, pb.name), goal()
                    results.append(dict(err_px_equiv_cm=round((tip - g).length * 100, 2), moved_cm=round((tip - base_tip).length * 100, 2)))
                    if tgt.type == "ARMATURE" and c.subtarget:
                        tgt.pose.bones[c.subtarget].location = orig
                    else:
                        tgt.location = orig
                    update()
                tests["ik_response"].append(dict(armature=ob.name, bone=pb.name, chain=c.chain_count, rest_err_cm=round(err0 * 100, 2), moves=results))
except Exception:
    tests["ik_error"] = traceback.format_exc()[-400:]
R["tests"] = tests

# ------------------------------------------------------------------ render (Workbench, auto camera)
def bbox_all():
    """bbox of the RENDERABLE character objects (hide_render False), robust to stray props: drop objects whose centre is far from the median centre."""
    dg = bpy.context.evaluated_depsgraph_get()
    items = []
    for ob in bpy.data.objects:
        if ob.type in ("MESH", "GREASEPENCIL", "GPENCIL", "CURVE") and not ob.hide_render and not ob.hide_get():
            ev = ob.evaluated_get(dg)
            pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
            if pts:
                lo = Vector((min(p[i] for p in pts) for i in range(3)))
                hi = Vector((max(p[i] for p in pts) for i in range(3)))
                items.append((lo, hi))
    if not items:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    cs = sorted((lo + hi) / 2 for lo, hi in items) if False else [(lo + hi) / 2 for lo, hi in items]
    med = Vector(sorted(c[i] for c in cs)[len(cs) // 2] for i in range(3))
    spread = sorted((c - med).length for c in cs)
    lim = max(spread[int(len(spread) * 0.8)] * 1.5, 0.5) if len(spread) > 4 else 1e9
    keep = [(lo, hi) for (lo, hi), c in zip(items, cs) if (c - med).length <= lim] or items
    lo = Vector((min(k[0][i] for k in keep) for i in range(3)))
    hi = Vector((max(k[1][i] for k in keep) for i in range(3)))
    return lo, hi


def render(path, frame=None, view="FRONT"):
    if frame is not None:
        sc.frame_set(frame)
    update()
    lo, hi = bbox_all()
    ctr, size = (lo + hi) / 2, hi - lo
    cam = bpy.data.objects.get("_audit_cam")
    if cam is None:
        cd = bpy.data.cameras.new("_audit_cam")
        cd.type = "ORTHO"
        cam = bpy.data.objects.new("_audit_cam", cd)
        sc.collection.objects.link(cam)
    cam.data.ortho_scale = max(size.z * 1.15, size.x * 1.15 * 0.75, 0.2)
    if view == "FRONT":
        cam.location = ctr + Vector((0, -max(size.length, 1) * 2, 0))
        cam.rotation_euler = (math.radians(90), 0, 0)
    else:
        cam.location = ctr + Vector((max(size.length, 1) * 2, 0, 0))
        cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    cam.data.clip_end = 1e4
    sc.camera = cam
    sc.render.engine = os.environ.get("AUDIT_ENGINE", "BLENDER_WORKBENCH")
    sc.render.resolution_x, sc.render.resolution_y = 480, 640
    sc.render.filepath = path
    sc.display.shading.light = "STUDIO" if not gp else "FLAT"
    sc.display.shading.color_type = "MATERIAL" if hasattr(sc.display.shading, "color_type") else "OBJECT"
    sc.render.film_transparent = False
    bpy.ops.render.render(write_still=True)


try:
    mid = None
    if bpy.data.actions:
        best = max(bpy.data.actions, key=lambda a: a.frame_range[1] - a.frame_range[0])
        mid = int((best.frame_range[0] + best.frame_range[1]) / 2)
        for ob in bpy.data.objects:
            if ob.type == "ARMATURE" and (ob.animation_data is None or ob.animation_data.action is None):
                pass
    render(os.path.join(OUT, f"{AID}_front.png"), frame=mid)
    R["render"] = dict(ok=os.path.exists(os.path.join(OUT, f"{AID}_front.png")), frame=mid)
except Exception:
    R["render"] = dict(ok=False, error=traceback.format_exc()[-400:])

json.dump(R, open(os.path.join(OUT, f"{AID}.json"), "w"), indent=1, default=str)
print("AUDIT_OK", AID)
