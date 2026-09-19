"""Blender entrypoint for the Gate 3 visual director compiler. Run via:

  blender --background --python engine/render/build_from_shots.py -- \
      manifests/gate3_shots.json [--preview]

studio.py is the actual CLI a person runs; it shells out to this.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy

from engine.visual_director.compiler import compile_shot_list
from engine.common.paths import FRAMES_DIR, ensure_dirs

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--preview" in argv
    positional = [a for a in argv if not a.startswith("--")]
    shot_list_path = positional[0] if positional else "manifests/gate3_shots.json"

    ensure_dirs()
    result = compile_shot_list(shot_list_path, preview=preview)

    scene = bpy.context.scene
    out_dir = os.path.join(FRAMES_DIR, "gate3_preview" if preview else "gate3_final")
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, "frame_")
    print(f"RENDER_RANGE {scene.frame_start} {scene.frame_end}")
    bpy.ops.render.render(animation=True)
    print("BUILD_FROM_SHOTS_DONE")
