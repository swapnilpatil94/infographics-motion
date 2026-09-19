import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from engine.render.build_gate2_svg import build, FPS
from engine.common.paths import PREVIEWS_DIR, ensure_dirs

ensure_dirs()
build(preview=True)
scene = bpy.context.scene

for label, t in [("relaxed", 0.5), ("curious", 3.0), ("uneasy", 5.8), ("realization", 8.6)]:
    scene.frame_set(round(t * FPS))
    scene.render.filepath = os.path.join(PREVIEWS_DIR, f"gate2_still_{label}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", label)
