import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from engine.render.build_gate1 import build, FPS
from engine.common.paths import PREVIEWS_DIR, ensure_dirs

ensure_dirs()
build(preview=True)
scene = bpy.context.scene

for label, frame in [
    ("s01_wide", round(1.8 * FPS)),
    ("s02_notice", round(4.4 * FPS)),
    ("s03_phone", round(6.2 * FPS)),
    ("s04_unease", round(8.8 * FPS)),
    ("s05_pullback", round(12.8 * FPS)),
]:
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(PREVIEWS_DIR, f"gate1_still_{label}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", label, scene.render.filepath)
