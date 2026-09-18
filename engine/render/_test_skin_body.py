import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy, bmesh
from engine.common.scene import clear_scene
from engine.common.paths import PREVIEWS_DIR, ensure_dirs

ensure_dirs()
clear_scene()

mesh = bpy.data.meshes.new("skin_test")
bm = bmesh.new()

# spine chain: pelvis(0) - spine(1) - chest(2) - neck(3) - head(4)
pelvis = bm.verts.new((0, 0, 0.95))
spine = bm.verts.new((0, 0, 1.05))
chest = bm.verts.new((0, 0, 1.25))
neck = bm.verts.new((0, 0, 1.42))
head = bm.verts.new((0, 0, 1.50))
head_top = bm.verts.new((0, 0, 1.68))
for a, b in [(pelvis, spine), (spine, chest), (chest, neck), (neck, head), (head, head_top)]:
    bm.edges.new((a, b))

# one arm (R): chest -> shoulder -> elbow -> wrist -> hand
sh = bm.verts.new((0.18, 0, 1.38))
elbow = bm.verts.new((0.18, 0, 1.10))
wrist = bm.verts.new((0.18, 0, 0.85))
hand = bm.verts.new((0.18, 0, 0.73))
for a, b in [(chest, sh), (sh, elbow), (elbow, wrist), (wrist, hand)]:
    bm.edges.new((a, b))

# one leg (R): pelvis -> hip -> knee -> ankle -> toe
hip = bm.verts.new((0.10, 0, 0.95))
knee = bm.verts.new((0.10, 0, 0.50))
ankle = bm.verts.new((0.10, 0, 0.08))
toe = bm.verts.new((0.10, 0.14, 0.02))
for a, b in [(pelvis, hip), (hip, knee), (knee, ankle), (ankle, toe)]:
    bm.edges.new((a, b))

bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("SkinTest", mesh)
bpy.context.scene.collection.objects.link(obj)

mod = obj.modifiers.new("Skin", 'SKIN')
radii = {
    0: 0.13,   # pelvis
    1: 0.10,   # spine (waist)
    2: 0.15,   # chest
    3: 0.05,   # neck
    4: 0.10,   # head base
    5: 0.10,   # head top
    6: 0.055,  # shoulder
    7: 0.045,  # elbow
    8: 0.035,  # wrist
    9: 0.03,   # hand
    10: 0.075, # hip
    11: 0.06,  # knee
    12: 0.045, # ankle
    13: 0.045, # toe
}
skin_layer = mesh.skin_vertices[0]
for i, d in enumerate(skin_layer.data):
    r = radii.get(i, 0.05)
    d.radius = (r, r)
skin_layer.data[0].use_root = True  # pelvis is a branch hub
skin_layer.data[2].use_root = True  # chest is a branch hub

subsurf = obj.modifiers.new("Subsurf", 'SUBSURF')
subsurf.levels = 2

mat = bpy.data.materials.new("SkinMat")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.42, 0.30, 1.0)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
obj.data.materials.append(mat)

cam_data = bpy.data.cameras.new("C")
cam = bpy.data.objects.new("C", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (1.2, -1.6, 1.0)
bpy.context.scene.camera = cam
t = bpy.data.objects.new("T", None)
bpy.context.scene.collection.objects.link(t)
t.location = (0.1, 0, 0.8)
tc = cam.constraints.new(type='TRACK_TO')
tc.target = t
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

key = bpy.data.lights.new("K", type='SUN')
key.energy = 3
key_o = bpy.data.objects.new("K", key)
bpy.context.scene.collection.objects.link(key_o)
key_o.rotation_euler = (math.radians(60), 0, math.radians(30))

bpy.ops.preferences.addon_enable(module='cycles')
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 32
scene.render.resolution_x = 500
scene.render.resolution_y = 500
scene.render.filepath = os.path.join(PREVIEWS_DIR, "skin_body_test.png")
bpy.ops.render.render(write_still=True)
print("DONE")
