"""GP candidate integration test: drive the Blender-Studio Boy Head cutout rig's pupil layers ('Left','Right' of the Eyes GP object) from a gaze target, render 5 gazes in Blender 5.2.2 (EEVEE).
blender -b --disable-autoexec gp_boyhead_cutout_282.blend -P gp_gaze_test.py -- <out_dir>"""
import json
import os
import sys

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
eyes = bpy.data.objects["Eyes"]
lay = {l.name: l for l in eyes.data.layers}
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 480, 480
dg = bpy.context.evaluated_depsgraph_get()
ev = eyes.evaluated_get(dg)
pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
lo = Vector((min(p[i] for p in pts) for i in range(3)))
hi = Vector((max(p[i] for p in pts) for i in range(3)))
ctr, size = (lo + hi) / 2, hi - lo
cd = bpy.data.cameras.new("c")
cd.type = "ORTHO"
cd.ortho_scale = max(size.x, size.z) * 2.2
cam = bpy.data.objects.new("c", cd)
sc.collection.objects.link(cam)
import math
cam.location = ctr + Vector((0, -20, 0))
cam.rotation_euler = (math.radians(90), 0, 0)
sc.camera = cam
GAZE = dict(center=(0, 0), left=(-1, 0), right=(1, 0), up=(0, 1), down=(0, -1))
amp = size.x * 0.035
res = dict(layers=list(lay), amp_units=round(amp, 4), renders={})
for nm, (gx, gy) in GAZE.items():
    for k in ("Left", "Right"):
        if k in lay:
            lay[k].translation = (gx * amp, 0, gy * amp)
    bpy.context.view_layer.update()
    p = os.path.join(OUT, f"gp_boyhead_gaze_{nm}.png")
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    res["renders"][nm] = p
json.dump(res, open(os.path.join(OUT, "gp_boyhead_gaze.json"), "w"), indent=1)
print("GAZE_OK")
