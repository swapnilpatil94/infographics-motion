"""Blender-side renderer for the Grease Pencil sprite bank.  Run:  blender -b -P gp_bank_blender.py -- spec.json outdir

For every sprite/variant it builds a REAL Grease Pencil object (layer, frame, strokes with per-point radius/opacity,
GP material), adds GP modifiers (Noise for hand wobble; Build for the draw-on of hand-drawn rings), renders a
transparent RGBA PNG with an orthographic camera. The Python compositor then tracks these sprites to the action.
"""
import json
import os
import sys
import time

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.shorts import gp_strokes as G          # noqa: E402  (pure python)

spec_path, outdir = sys.argv[sys.argv.index("--") + 1:][:2]
spec = json.load(open(spec_path))
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "Standard"
cam = bpy.data.cameras.new("cam")
cam.type = "ORTHO"
co = bpy.data.objects.new("cam", cam)
sc.collection.objects.link(co)
sc.camera = co
co.rotation_euler = (0, 0, 0)
_mats = {}


def material(color):
    key = tuple(round(c, 3) for c in color)
    if key not in _mats:
        m = bpy.data.materials.new(f"ink{len(_mats)}")
        bpy.data.materials.create_gpencil_data(m)
        m.grease_pencil.color = (*color, 1.0)
        m.grease_pencil.show_stroke = True            # a fresh GP material has show_stroke=False (renders black/none)
        m.grease_pencil.show_fill = False
        _mats[key] = m
    return _mats[key]


def build_object(name, strokes, size, anchor, ppu, noise_seed, build_frames=None):
    w, h = size
    bpy.ops.object.grease_pencil_add(type="EMPTY")
    ob = bpy.context.object
    ob.name = name
    gp = ob.data
    gp.materials.clear()                              # drop GP's default 'Black' slot so material_index maps to ours
    colors = sorted({tuple(s["color"]) for s in strokes})
    for c in colors:
        gp.materials.append(material(c))
    layer = gp.layers.new("fx")
    layer.use_lights = False                          # flat, emissive-looking ink (the compositor lights the scene)
    drawing = layer.frames.new(1).drawing
    drawing.add_strokes([len(s["pts"]) for s in strokes])
    ox, oy = (w / 2.0, h / 2.0) if anchor == "center" else (0.0, 0.0)
    for st, s in zip(drawing.strokes, strokes):
        st.material_index = colors.index(tuple(s["color"]))
        st.cyclic = bool(s.get("cyclic"))
        for p, (x, y, r, a) in zip(st.points, s["pts"]):
            p.position = (x + ox, -(y + oy), 0.0)           # local px, y down -> blender y up; sprite canvas top-left = (0,0)
            p.radius = max(0.2, r) * 0.5
            p.opacity = max(0.0, min(1.0, a))
    n = ob.modifiers.new("hand", "GREASE_PENCIL_NOISE")
    n.factor = 1.6
    n.factor_thickness = 0.0
    n.noise_scale = 0.3
    n.use_random = True
    n.seed = noise_seed
    if build_frames:
        b = ob.modifiers.new("draw_on", "GREASE_PENCIL_BUILD")
        b.mode, b.transition, b.time_mode = "SEQUENTIAL", "GROW", "FRAMES"
        b.start_delay, b.length = 0.0, float(build_frames)
    return ob


t0 = time.time()
n_strokes = n_render = 0
report = {}
for name, sp in spec["sprites"].items():
    gen = G.SPRITES[name]["gen"]
    w, h = sp["size"]
    ppu = sp["ppu"]
    sc.render.resolution_x, sc.render.resolution_y = int(w * ppu), int(h * ppu)
    cam.ortho_scale = max(w, h)
    co.location = (w / 2.0, -h / 2.0, 20.0)
    for v in range(sp["variants"]):
        for o in list(bpy.data.objects):
            if o.type == "GREASEPENCIL":
                bpy.data.objects.remove(o, do_unlink=True)
        strokes = gen(v)
        n_strokes += len(strokes)
        ob = build_object(f"{name}_{v}", strokes, (w, h), sp["anchor"], ppu, 3 + v * 7, build_frames=(sp["variants"] if sp.get("build") else None))
        frame = 1 + (v if sp.get("build") else 0)           # ring: variant k = k frames into the Build-modifier draw-on
        sc.frame_set(frame)
        sc.render.filepath = os.path.join(outdir, f"{name}_{v:02d}.png")
        bpy.ops.render.render(write_still=True)
        n_render += 1
    report[name] = sp["variants"]
json.dump(dict(renders=n_render, strokes=n_strokes, seconds=round(time.time() - t0, 2), sprites=report, blender=bpy.app.version_string),
          open(os.path.join(outdir, "report.json"), "w"))
print("GP_BANK_DONE", n_render, "renders", n_strokes, "strokes", round(time.time() - t0, 1), "s")
