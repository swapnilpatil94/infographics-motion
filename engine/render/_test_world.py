import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from engine.worlds import bedroom_night
from engine.common.paths import PREVIEWS_DIR, ensure_dirs
from engine.common.scene import clear_scene

ensure_dirs()
clear_scene()

objects, continuity = bedroom_night.build()
print(json.dumps(continuity, indent=2))

# simple test camera + light so we can SEE the room, not final lighting
cam_data = bpy.data.cameras.new("TestCam")
cam_data.lens = 24
cam = bpy.data.objects.new("TestCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (0.2, -3.6, 1.9)
bpy.context.scene.camera = cam

target = bpy.data.objects.new("TestCamTarget", None)
bpy.context.scene.collection.objects.link(target)
target.location = (0.0, -0.2, 1.1)
tc = cam.constraints.new(type='TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

light_data = bpy.data.lights.new("TestLight", type='SUN')
light_data.energy = 2.0
light = bpy.data.objects.new("TestLight", light_data)
bpy.context.scene.collection.objects.link(light)
light.rotation_euler = (math.radians(50), 0, math.radians(30))

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.filepath = os.path.join(PREVIEWS_DIR, "world_bedroom_night_test.png")
bpy.ops.render.render(write_still=True)
print("RENDERED_TO", scene.render.filepath)
