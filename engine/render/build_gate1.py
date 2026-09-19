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
    arm = char["armature"]
    arm.location = CHAR_LOCATION
    rahul.apply_pose(arm, "base")

    # Bind the phone to hand.R while relaxed (phone resting in the lap,
    # not yet being looked at) — CHILD_OF is a LIVE constraint, so it keeps
    # following hand.R correctly through every later pose/keyframe below.
    bpy.context.view_layer.update()
    hand_matrix_world = arm.matrix_world @ arm.pose.bones["hand.R"].matrix
    hand_world_pos = hand_matrix_world.translation
    phone_loc = (hand_world_pos.x - 0.01, hand_world_pos.y - 0.06, hand_world_pos.z + 0.06)
    phone = phone_prop.build(char_coll, location=phone_loc, size=(0.075, 0.009, 0.155))
    phone["body"].rotation_euler = (math.radians(80), 0, math.radians(-15))
    bpy.context.view_layer.update()
    con = phone["body"].constraints.new('CHILD_OF')
    con.target = arm
    con.subtarget = "hand.R"
    con.inverse_matrix = hand_matrix_world.inverted()

    light_coll = bpy.data.collections.new("Lighting")
    master_coll.children.link(light_coll)
    room_lights = lighting.build_night_bedroom_rig(light_coll, world_objects["window"])
    phone_glow = lighting.build_phone_glow(light_coll, phone["body"])

    # --- Acting timeline -------------------------------------------------
    # Named poses (engine.characters.rahul.POSES) carry the story beats:
    # base (relaxed, alone) -> notice (screen catches his eye) -> phone
    # (raises it, commits to looking) -> realization (settles/sinks).
    # Small breathing keyframes ride on top of "base"/"phone"/"realization"
    # holds so the character never looks like a frozen prop.
    def t2f(t):
        return round(t * FPS) + 1

    rahul.keyframe_pose_named(arm, "base", t2f(0.0))
    bpy.context.view_layer.update()
    base_head = (arm.matrix_world @ arm.pose.bones["head"].matrix).translation
    base_chest = (arm.matrix_world @ arm.pose.bones["chest"].matrix).translation

    rahul.keyframe_pose_named(arm, "base", t2f(1.2), breathe_x_delta=1.6)
    rahul.keyframe_pose_named(arm, "base", t2f(2.3), breathe_x_delta=-1.0)

    rahul.keyframe_pose_named(arm, "notice", t2f(3.55))
    rahul.keyframe_pose_named(arm, "notice", t2f(3.85))  # brief hesitation hold

    rahul.keyframe_pose_named(arm, "phone", t2f(5.0))
    bpy.context.view_layer.update()
    phone_pose_head = (arm.matrix_world @ arm.pose.bones["head"].matrix).translation
    phone_raised_loc = tuple((arm.matrix_world @ arm.pose.bones["hand.R"].matrix).translation)

    rahul.keyframe_pose_named(arm, "phone", t2f(6.2), breathe_x_delta=1.2)
    rahul.keyframe_pose_named(arm, "phone", t2f(8.6), breathe_x_delta=-0.8)

    rahul.keyframe_pose_named(arm, "realization", t2f(10.0))
    bpy.context.view_layer.update()
    realization_head = (arm.matrix_world @ arm.pose.bones["head"].matrix).translation

    rahul.keyframe_pose_named(arm, "realization", t2f(12.2), breathe_x_delta=1.0)

    ignite_shot = next(s for s in shot_plan["shots"] if s.get("phone_screen_ignite_at_s") is not None)
    ignite_frame = t2f(ignite_shot["phone_screen_ignite_at_s"])
    lighting.keyframe_energy(phone_glow, [
        (1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 4.0),
    ])
    phone_prop.keyframe_screen(phone, [
        (1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 4.5),
    ])

    for shot in shot_plan["shots"]:
        frame = t2f(shot["start_s"])
        emotion = shot["characters"][0]["emotion"]
        rahul.keyframe_emotion(char["face"], emotion, frame)

    base_target = (base_head.x, base_head.y, base_head.z + 0.06)
    chest_target = (base_chest.x, base_chest.y, base_chest.z)
    phone_target = (phone_pose_head.x, phone_pose_head.y, phone_pose_head.z + 0.08)
    realization_target = (realization_head.x, realization_head.y, realization_head.z + 0.07)

    cam, target, focus = camera_shots.build_camera(master_coll)
    char_x, char_y = CHAR_LOCATION[0], CHAR_LOCATION[1]
    cam_shots = [
        {
            # 3/4 angle, not dead-on-axis: reads the sitting silhouette
            # along its length instead of foreshortening the legs, and is
            # simply a more deliberate establishing composition.
            "start_s": 0.0, "end_s": 3.2,
            "cam_location": (char_x + 1.35, char_y - 2.75, 1.35),
            "target_location": base_target,
            "focus_location": base_target,
            "lens_mm": 28,
        },
        {
            "start_s": 3.2, "end_s": 5.0,
            "cam_location": (char_x + 1.05, char_y - 2.15, 1.2),
            "target_location": chest_target,
            "focus_location": chest_target,
            "lens_mm": 32,
            "cam_location_end": (char_x + 0.75, char_y - 1.55, 1.05),
            "target_location_end": base_target,
            "focus_location_end": base_target,
        },
        {
            # Phone-forward composition: camera low and close to the raised
            # hand so the lit screen reads as a foreground shape, face soft
            # behind it — the phone becomes the subject, not a prop.
            "start_s": 5.0, "end_s": 7.4,
            "cam_location": (phone_raised_loc[0] + 0.42, phone_raised_loc[1] - 0.30, phone_raised_loc[2] - 0.10),
            "target_location": phone_raised_loc,
            "focus_location": phone_raised_loc,
            "lens_mm": 60,
        },
        {
            "start_s": 7.4, "end_s": 10.0,
            "cam_location": (char_x + 0.55, char_y - 1.85, 1.18),
            "target_location": phone_target,
            "focus_location": phone_target,
            "lens_mm": 75,
        },
        {
            # Pull back out to a medium-wide — the release after four
            # shots of pushing in, and the visual "isolation reveal".
            "start_s": 10.0, "end_s": 13.5,
            "cam_location": (char_x + 0.55, char_y - 1.9, 1.15),
            "target_location": realization_target,
            "focus_location": realization_target,
            "lens_mm": 60,
            "cam_location_end": (char_x + 1.5, char_y - 3.3, 1.5),
            "target_location_end": (realization_target[0], realization_target[1] + 0.15, realization_target[2] - 0.05),
            "focus_location_end": (realization_target[0], realization_target[1] + 0.15, realization_target[2] - 0.05),
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
