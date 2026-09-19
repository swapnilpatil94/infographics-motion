"""The deterministic compiler: reads a shot-list DSL (manifests/gate3_shots
.json-shaped) + a character rig_spec + the asset registry, and builds the
full Blender scene by calling the REUSABLE builders — engine.character.rig
/.actions, engine.fx.grease_pencil_fx, engine.cameras.shots,
engine.style.svg_import, engine.lighting.profiles. No shot-specific
Blender code lives here beyond "read the DSL, call the generic builders
with the DSL's numbers" — this is intentionally NOT a rewritten copy of
build_gate2_svg.py's inline scene construction.

An LLM/planner may produce the shot-list JSON. It does NOT touch Blender —
this module is the only thing that does, and only by interpreting a
validated JSON structure (engine.visual_director.schema), never by
executing arbitrary generated code.
"""
import bpy
import json
import math
import os

from engine.character.rig import CharacterRig
from engine.character import actions
from engine.style import svg_import, apply_style
from engine.cameras import shots as camera_shots
from engine.fx import grease_pencil_fx as gpfx
from mathutils import Vector

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FPS = 24

ENV_DIR = "assets/environment/raw/kathaaya_minimal"
PROP_DIR = "assets/props/raw/kathaaya_minimal"

CAMERA_FRAMING = {
    "wide_3q": {"dist": 1.65, "lens": 28, "target_z_offset": -0.10},
    "medium_push": {"dist": 1.35, "lens": 45, "target_z_offset": -0.02},
    "medium_close": {"dist": 1.05, "lens": 55, "target_z_offset": 0.0},
    "closeup": {"dist": 0.85, "lens": 70, "target_z_offset": 0.03},
}


def _t2f(t):
    return round(t * FPS) + 1


def load_shot_list(path):
    from engine.visual_director.schema import validate
    with open(os.path.join(REPO_ROOT, path)) as f:
        return validate(json.load(f))


def build_environment(master_coll, root_z):
    """Positions every environment piece relative to `root_z` (the
    character's feet/seat level, see CharacterRig) rather than hardcoded
    absolute numbers — the SVG import pipeline used for this character
    (extract_head_only/extract_body_only preserving the full composed
    canvas) puts the figure at a noticeably different absolute scale than
    Gate 2's normalized-canvas approach, so environment numbers copied
    verbatim from Gate 2 put a wall-sized plane almost on top of the
    camera. Measured empirically: feet ~= root_z, head/neck ~= root_z+0.56."""
    feet_z = root_z
    head_z = root_z + 0.56

    # NOTE: a modeled wall plane (rotated 90 deg around X, the same
    # technique Gate 2 used successfully) produced an unexplained
    # occlusion bug in THIS scene specifically — with the exact same
    # material/scale/rotation code, the character rendered almost
    # entirely hidden behind it despite being measurably closer to the
    # camera on every axis I checked (world-space Y ordering, hide_render
    # states, and object positions all looked correct in isolation).
    # I could not root-cause it within this pass's time budget, and I'm
    # not going to ship a render built on a mechanism I don't understand.
    # Using a flat world-background color for the backdrop instead is an
    # honest simplification, not a silent workaround: it is visually
    # flatter than a modeled wall, and re-adding a real wall plane is the
    # first thing to revisit.
    world = bpy.data.worlds.get("Gate3World") or bpy.data.worlds.new("Gate3World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.09, 0.10, 0.16, 1.0)
    bpy.context.scene.world = world
    wall = None

    window = svg_import.import_flat_svg(
        os.path.join(REPO_ROOT, ENV_DIR, "window.svg"), master_coll, "Env_Window",
        fill_color=(0.55, 0.65, 0.85), ink_color=(0.04, 0.04, 0.06),
    )
    window.location = (-0.75, 1.9, head_z + 0.1)
    window.scale = (0.0016, 0.0016, 0.0016)

    nightstand = svg_import.import_flat_svg(
        os.path.join(REPO_ROOT, ENV_DIR, "nightstand.svg"), master_coll, "Env_Nightstand",
        fill_color=(0.62, 0.47, 0.32), ink_color=(0.04, 0.03, 0.03),
    )
    nightstand.location = (0.55, 0.65, feet_z - 0.32)
    nightstand.scale = (0.0013, 0.0013, 0.0013)

    bed_edge = svg_import.import_flat_svg(
        os.path.join(REPO_ROOT, ENV_DIR, "bed_edge.svg"), master_coll, "Env_BedEdge",
        fill_color=(0.16, 0.19, 0.30), ink_color=(0.04, 0.04, 0.06),
    )
    bed_edge.location = (0, -0.55, feet_z - 0.45)
    bed_edge.scale = (0.0021, 0.0021, 0.0021)

    return {"window": window, "nightstand": nightstand, "bed_edge": bed_edge}


def build_phone(master_coll, location):
    phone = svg_import.import_flat_svg(
        os.path.join(REPO_ROOT, PROP_DIR, "phone.svg"), master_coll, "Prop_Phone",
        fill_color=(0.08, 0.08, 0.09), ink_color=(0.04, 0.03, 0.03),
    )
    phone.location = location
    phone.scale = (0.0013, 0.0013, 0.0013)
    screen = next((c for c in phone.children if c.name.lower().startswith("screen")), None)

    screen_mat = bpy.data.materials.new("Mat_PhoneScreenGlow")
    screen_mat.use_nodes = True
    nt = screen_mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1.0)
    emit.inputs["Strength"].default_value = 0.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    if screen is not None and screen.data.materials:
        screen.data.materials[len(screen.data.materials) - 1] = screen_mat

    glow_light = bpy.data.lights.new("Light_PhoneGlow", type='POINT')
    glow_light.energy = 0.0
    glow_light.color = (0.75, 0.85, 1.0)
    glow_light.shadow_soft_size = 0.05
    glow_obj = bpy.data.objects.new("Light_PhoneGlow", glow_light)
    master_coll.objects.link(glow_obj)
    glow_obj.parent = phone
    glow_obj.location = (0, 0, 0.02)

    return {"body": phone, "screen": screen, "emit": emit, "glow_light": glow_light}


def build_lighting(master_coll):
    moon = bpy.data.lights.new("Light_WindowMoon", type='SUN')
    moon.energy = 1.6
    moon.color = (0.55, 0.65, 1.0)
    moon.angle = math.radians(3)
    moon_obj = bpy.data.objects.new("Light_WindowMoon", moon)
    master_coll.objects.link(moon_obj)
    moon_obj.rotation_euler = (math.radians(75), 0, math.radians(30))

    ambient = bpy.data.lights.new("Light_Ambient", type='SUN')
    ambient.energy = 0.35
    ambient.color = (0.4, 0.45, 0.6)
    ambient_obj = bpy.data.objects.new("Light_Ambient", ambient)
    master_coll.objects.link(ambient_obj)
    ambient_obj.rotation_euler = (math.radians(-60), 0, math.radians(-40))
    return {"moon": moon_obj, "ambient": ambient_obj}


def compile_shot_list(shot_list_path, preview=True):
    from engine.common.scene import clear_scene
    clear_scene()

    dsl = load_shot_list(shot_list_path)
    master_coll = bpy.data.collections.new("Gate3_Master")
    bpy.context.scene.collection.children.link(master_coll)

    root_z = 0.55
    env = build_environment(master_coll, root_z)
    lighting = build_lighting(master_coll)

    rig_spec_rel = dsl["characters"]["rahul"]["rig_spec"]
    rig = CharacterRig.build("rahul", rig_spec_rel, master_coll)
    rig.root.location = (0.0, 0.0, root_z)

    phone_loc = (env["nightstand"].location.x - 0.05, env["nightstand"].location.y - 0.28, root_z - 0.20)
    phone = build_phone(master_coll, phone_loc)

    # Grease Pencil atmosphere: a soft shaft from the window, a light
    # scatter of dust in the same beam — deterministic (seeded).
    fx_coll = bpy.data.collections.new("FX")
    master_coll.children.link(fx_coll)
    window_world = env["window"].matrix_world.translation
    gpfx.add_light_ray_cone(
        fx_coll, window_world + Vector((0.0, -0.05, 0.05)), Vector((0.5, -1.0, -0.3)),
        length=1.1, count=3, width_deg=10, alpha=0.05, seed=7, name="WindowRays",
    )
    gpfx.add_dust_motes(
        fx_coll, (-0.1, -0.3, 0.3), (0.4, 0.1, 0.9), count=10, seed=11, alpha=0.25, name="DustMotes",
    )

    ignite_shot = next(s for s in dsl["shots"] if s.get("phone_screen") == "ignite")
    ignite_frame = _t2f(ignite_shot["end_s"] - 0.15)
    for f, v in [(1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 3.2)]:
        phone["glow_light"].energy = v
        phone["glow_light"].keyframe_insert(data_path="energy", frame=f)
    for f, v in [(1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 5.0)]:
        phone["emit"].inputs["Strength"].default_value = v
        phone["emit"].inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

    cam, target, focus = camera_shots.build_camera(master_coll)
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.2
    phone_world = Vector(phone_loc)

    actions.idle_sway(rig, 1, _t2f(dsl["shots"][-1]["end_s"]))
    actions.breathing(rig, 1, _t2f(dsl["shots"][-1]["end_s"]))
    actions.blink(rig, _t2f(1.6))

    cam_shots = []
    for shot in dsl["shots"]:
        f0 = _t2f(shot["start_s"])
        for c in shot["characters"]:
            actions.emotion(rig, c["emotion"], f0)
            if c["action"] == "look_at_phone":
                actions.look_at(rig, phone_world, f0)
            elif c["action"] == "idle":
                actions.reset_head(rig, f0)

        framing = CAMERA_FRAMING[shot["camera"]["shot_type"]]
        head_pos = rig.head_world_point()
        target_pt = (head_pos.x, head_pos.y, head_pos.z + framing["target_z_offset"])
        cam_pos = (head_pos.x + 0.45, head_pos.y - framing["dist"], head_pos.z + 0.05)
        cam_shots.append({
            "start_s": shot["start_s"], "end_s": shot["end_s"],
            "cam_location": cam_pos, "target_location": target_pt, "focus_location": target_pt,
            "lens_mm": framing["lens"],
        })

    camera_shots.animate_camera(cam, target, focus, cam_shots)

    style_cfg = {"color_management": {"view_transform": "AgX", "look": "AgX - Punchy", "exposure": 0.5}}
    apply_style.apply_color_management(bpy.context.scene, style_cfg)
    apply_style.apply_render_settings(
        bpy.context.scene,
        resolution=(480, 600) if preview else (1080, 1350),
        samples=24 if preview else 128,
    )
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = _t2f(dsl["shots"][-1]["end_s"])
    return {"rig": rig, "camera": cam, "dsl": dsl}
