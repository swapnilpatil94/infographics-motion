import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from engine.common.scene import clear_scene
from engine.common.paths import PREVIEWS_DIR, ensure_dirs
from engine.style import svg_import

ensure_dirs()
clear_scene()

coll = bpy.data.collections.new("Test")
bpy.context.scene.collection.children.link(coll)

char = svg_import.import_flat_svg(
    "assets/character/normalized/rahul_svg/rahul_uneasy.svg", coll, "Rahul",
    fill_color=(0.93, 0.86, 0.74), ink_color=(0.04, 0.03, 0.03),
)

cam_data = bpy.data.cameras.new("C")
cam_data.lens = 50
cam = bpy.data.objects.new("C", cam_data)
coll.objects.link(cam)
cam.location = (0, -1.6, 0.25)
bpy.context.scene.camera = cam
t = bpy.data.objects.new("T", None)
coll.objects.link(t)
t.location = (0, 0, 0.25)
tc = cam.constraints.new(type='TRACK_TO')
tc.target = t
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

sun = bpy.data.lights.new("S", type='SUN')
sun.energy = 3
sun_o = bpy.data.objects.new("S", sun)
coll.objects.link(sun_o)
sun_o.rotation_euler = (math.radians(60), 0, math.radians(20))

bg = bpy.data.lights.new("Fill", type='SUN')
bg.energy = 1
bg_o = bpy.data.objects.new("Fill", bg)
coll.objects.link(bg_o)
bg_o.rotation_euler = (math.radians(120), 0, math.radians(-40))

bpy.ops.preferences.addon_enable(module='cycles')
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 32
scene.render.resolution_x = 500
scene.render.resolution_y = 600
scene.world = bpy.data.worlds.new("W")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.08, 0.10, 0.18, 1.0)
scene.render.filepath = os.path.join(PREVIEWS_DIR, "svg_character_test.png")
bpy.ops.render.render(write_still=True)
print("DONE")
