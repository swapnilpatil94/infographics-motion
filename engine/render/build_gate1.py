"""Gate 1 orchestrator: assembles world + character + phone + lighting +
camera + style from manifests/shot_plan.json and manifests/style_profile.json,
then renders the frame range. Run with:

  blender --background --python engine/render/build_gate1.py -- [--preview]

--preview renders at low res/samples for a fast iteration pass.
"""
import sys, os, json, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy

from engine.common.scene import clear_scene
from engine.common.paths import MANIFESTS_DIR, FRAMES_DIR, RENDERS_DIR, ensure_dirs
from engine.worlds import bedroom_night
from engine.characters import rahul
from engine.props import phone as phone_prop
from engine.lighting import profiles as lighting
from engine.cameras import shots as camera_shots
from engine.style import apply_style

FPS = 24
CHAR_LOCATION = (0.5, -0.9, 0.52)  # seats pelvis (rest z=0.03) onto bed top (z=0.55)


def build(preview=False):
    ensure_dirs()
    clear_scene()

    style_cfg = apply_style.load_style_profile(os.path.join(MANIFESTS_DIR, "style_profile.json"))
    with open(os.path.join(MANIFESTS_DIR, "shot_plan.json")) as f:
        shot_plan = json.load(f)

    master_coll = bpy.data.collections.new("Gate1_Master")
    bpy.context.scene.collection.children.link(master_coll)

    world_objects, continuity = bedroom_night.build()
    world_coll = bpy.data.collections["World_BedroomNight"]
    bpy.context.scene.collection.children.unlink(world_coll)
    master_coll.children.link(world_coll)

    char = rahul.build()
    char_coll = char["collection"]
    bpy.context.scene.collection.children.unlink(char_coll)
    master_coll.children.link(char_coll)
    char["armature"].location = CHAR_LOCATION
    rahul.set_pose_sitting_phone(char["armature"])

    bpy.context.view_layer.update()
    hand_matrix_world = char["armature"].matrix_world @ char["armature"].pose.bones["hand.R"].matrix
    hand_world_pos = hand_matrix_world.translation
    phone_loc = (hand_world_pos.x - 0.01, hand_world_pos.y - 0.06, hand_world_pos.z + 0.06)
    phone = phone_prop.build(char_coll, location=phone_loc)
    phone["body"].rotation_euler = (math.radians(80), 0, math.radians(-15))
    bpy.context.view_layer.update()
    con = phone["body"].constraints.new('CHILD_OF')
    con.target = char["armature"]
    con.subtarget = "hand.R"
    con.inverse_matrix = hand_matrix_world.inverted()

    light_coll = bpy.data.collections.new("Lighting")
    master_coll.children.link(light_coll)
    room_lights = lighting.build_night_bedroom_rig(light_coll, world_objects["window"])
    phone_glow = lighting.build_phone_glow(light_coll, phone["body"])

    ignite_shot = next(s for s in shot_plan["shots"] if s.get("phone_screen_ignite_at_s") is not None)
    ignite_frame = round(ignite_shot["phone_screen_ignite_at_s"] * FPS) + 1
    lighting.keyframe_energy(phone_glow, [
        (1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 6, 3.5),
    ])
    phone_prop.keyframe_screen(phone, [
        (1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 6, 4.0),
    ])

    pose_by_shot = {
        "S01": "base",
        "S02": "notice",
        "S03": "phone",
        "S04": "phone",
        "S05": "realization",
    }
    previous_pose = "base"
    for shot in shot_plan["shots"]:
        start_s = shot["start_s"]
        end_s = shot["end_s"]
        frame = round(start_s * FPS) + 1
        emotion = shot["characters"][0]["emotion"]
        pose_name = pose_by_shot.get(shot["shot_id"], previous_pose)

        # Character acting is now a temporal sequence, not a single pose swap.
        # The short anticipation window makes the change readable while the
        # micro-acting layer supplies breathing/blink/glance/settle.
        transition_start = max(0.0, start_s - 0.20)
        transition_end = min(end_s, start_s + 0.28)
        rahul.keyframe_pose_transition(
            char["armature"], previous_pose, pose_name,
            transition_start, transition_end
        )
        rahul.keyframe_emotion(char["face"], emotion, frame)
        if shot["shot_id"] != "S01":
            rahul.keyframe_motion_grammar(
                char["armature"], char["face"],
                start_s, end_s,
                intensity=0.65 if shot["shot_id"] in ("S02", "S03") else 0.8
            )
        else:
            from engine.animation import motion_grammar
            motion_grammar.add_breathing(
                char["armature"], start_s, end_s,
                amplitude_deg=0.45, cycles=1.25, fps=FPS
            )
        previous_pose = pose_name

    head_pos = (char["armature"].matrix_world @ char["armature"].pose.bones["head"].matrix).translation
    chest_pos = (char["armature"].matrix_world @ char["armature"].pose.bones["chest"].matrix).translation
    head_target = (head_pos.x, head_pos.y, head_pos.z + 0.09)
    chest_target = (chest_pos.x, chest_pos.y, chest_pos.z)

    cam, target, focus = camera_shots.build_camera(master_coll)
    cam_shots = [
        {
            "start_s": 0.0, "end_s": 3.0,
            "cam_location": (0.5, -3.3, 1.3),
            "target_location": (0.5, -1.1, 0.9),
            "focus_location": (0.5, -1.1, 0.9),
            "lens_mm": 24,
        },
        {
            "start_s": 3.0, "end_s": 5.5,
            "cam_location": (0.5, -2.7, 1.2),
            "target_location": chest_target,
            "focus_location": chest_target,
            "lens_mm": 28,
            "cam_location_end": (0.5, -1.9, 1.05),
            "target_location_end": head_target,
            "focus_location_end": head_target,
        },
        {
            "start_s": 5.5, "end_s": 8.5,
            "cam_location": (0.3, -1.95, 0.88),
            "target_location": phone_loc,
            "focus_location": phone_loc,
            "lens_mm": 50,
        },
        {
            "start_s": 8.5, "end_s": 11.5,
            "cam_location": (0.35, -2.35, 1.2),
            "target_location": head_target,
            "focus_location": head_target,
            "lens_mm": 55,
            "cam_location_end": (0.4, -2.0, 1.15),
        },
    ]
    camera_shots.animate_camera(cam, target, focus, cam_shots)

    apply_style.apply_color_management(bpy.context.scene, style_cfg)
    apply_style.apply_render_settings(
        bpy.context.scene,
        resolution=(480, 270) if preview else (1280, 720),
        samples=16 if preview else 96,
    )
    for mat in bpy.data.materials:
        apply_style.flatten_material_specular(mat)
    apply_style.add_line_art(master_coll, style_cfg, name="Gate1_LineArt")

    last_end_s = shot_plan["shots"][-1]["end_s"]
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = round(last_end_s * FPS)

    with open(os.path.join(MANIFESTS_DIR, "continuity.json"), "w") as f:
        json.dump(continuity, f, indent=2)

    return cam


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--preview" in argv
    build(preview=preview)

    scene = bpy.context.scene
    out_dir = FRAMES_DIR if not preview else os.path.join(FRAMES_DIR, "preview")
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, "frame_")
    print(f"RENDER_RANGE {scene.frame_start} {scene.frame_end}")
    bpy.ops.render.render(animation=True)
    print("BUILD_GATE1_DONE")
