import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from engine.characters import rahul
from engine.common.paths import PREVIEWS_DIR, ensure_dirs
from engine.common.scene import clear_scene

ensure_dirs()
clear_scene()

char = rahul.build()
rahul.set_pose_sitting_phone(char["armature"])
rahul.set_emotion(char["face"], "curious")

cam_data = bpy.data.cameras.new("TestCam")
cam_data.lens = 50
cam = bpy.data.objects.new("TestCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (1.6, -1.8, 1.35)
bpy.context.scene.camera = cam
target = bpy.data.objects.new("TestCamTarget", None)
bpy.context.scene.collection.objects.link(target)
target.location = (0.0, -0.3, 1.15)
tc = cam.constraints.new(type='TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

key = bpy.data.lights.new("Key", type='SUN')
key.energy = 3.0
key.angle = math.radians(2)
key_obj = bpy.data.objects.new("Key", key)
bpy.context.scene.collection.objects.link(key_obj)
key_obj.location = (1.2, -1.2, 1.8)
key_obj.rotation_euler = (math.radians(55), 0, math.radians(45))

fill = bpy.data.lights.new("Fill", type='POINT')
fill.energy = 25
fill_obj = bpy.data.objects.new("Fill", fill)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.location = (-1.4, -1.0, 1.2)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.use_raytracing = False
scene.render.resolution_x = 640
scene.render.resolution_y = 720
scene.render.filepath = os.path.join(PREVIEWS_DIR, "character_rahul_test.png")
bpy.ops.render.render(write_still=True)
print("RENDERED_TO", scene.render.filepath)
