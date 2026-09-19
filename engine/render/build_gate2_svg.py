"""Gate 2 orchestrator: rebuilds the phone-reaction shot using real Open
Peeps SVG character assets + hand-authored environment/prop vector art,
composited as 2.5D flat layers, using the SAME camera/lighting/style/render
pipeline as Gate 1 (engine.cameras, engine.style, engine.lighting).

Run: blender --background --python engine/render/build_gate2_svg.py -- [--preview]
"""
import sys, os, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy

from engine.common.scene import clear_scene
from engine.common.paths import FRAMES_DIR, PREVIEWS_DIR, ensure_dirs
from engine.style import svg_import, apply_style
from engine.cameras import shots as camera_shots

FPS = 24
CHAR_SVG_DIR = "assets/character/normalized/rahul_svg_clean"
ENV_DIR = "assets/environment/raw/kathaaya_minimal"
PROP_DIR = "assets/props/raw/kathaaya_minimal"

# Z-depth layers (world Y is "depth" here since the scene is built on the
# XZ plane facing -Y, matching the rest of the engine's convention).
Z0_BG_Y = 1.2
Z1_ENV_Y = 0.55
Z2_FURNITURE_Y = 0.15
Z3_CHARACTER_Y = 0.0
Z4_FOREGROUND_Y = -0.35

EXPRESSIONS = ["relaxed", "curious", "uneasy", "realization"]


def build(preview=False):
    ensure_dirs()
    clear_scene()

    master_coll = bpy.data.collections.new("Gate2_Master")
    bpy.context.scene.collection.children.link(master_coll)

    # --- Background wall: a simple flat colored plane (cool night tone).
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, Z0_BG_Y, 0.9))
    wall = bpy.context.active_object
    wall.name = "Env_Wall"
    wall.scale = (2.2, 1, 1.9)
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall_mat = bpy.data.materials.new("Mat_Wall")
    wall_mat.use_nodes = True
    wall_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.10, 0.12, 0.19, 1.0)
    wall_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    wall.data.materials.append(wall_mat)
    for c in list(wall.users_collection):
        c.objects.unlink(wall)
    master_coll.objects.link(wall)

    # --- Window (environment layer): warm-lit glass, cool frame.
    window = svg_import.import_flat_svg(
        os.path.join(ENV_DIR, "window.svg"), master_coll, "Env_Window",
        fill_color=(0.55, 0.65, 0.85), ink_color=(0.04, 0.04, 0.06),
    )
    window.location = (-0.62, Z1_ENV_Y, 1.15)
    window.scale = (0.0016, 0.0016, 0.0016)

    # --- Nightstand + phone (furniture layer).
    nightstand = svg_import.import_flat_svg(
        os.path.join(ENV_DIR, "nightstand.svg"), master_coll, "Env_Nightstand",
        fill_color=(0.62, 0.47, 0.32), ink_color=(0.04, 0.03, 0.03),
    )
    nightstand.location = (0.34, Z2_FURNITURE_Y, 0.16)
    nightstand.scale = (0.0013, 0.0013, 0.0013)

    phone = svg_import.import_flat_svg(
        os.path.join(PROP_DIR, "phone.svg"), master_coll, "Prop_Phone",
        fill_color=(0.08, 0.08, 0.09), ink_color=(0.04, 0.03, 0.03),
    )
    phone.location = (0.30, Z2_FURNITURE_Y - 0.02, 0.30)
    phone.scale = (0.0013, 0.0013, 0.0013)
    phone_screen = _find_screen_obj(phone)

    # --- Bed edge (foreground layer, bottom of frame).
    bed_edge = svg_import.import_flat_svg(
        os.path.join(ENV_DIR, "bed_edge.svg"), master_coll, "Env_BedEdge",
        fill_color=(0.16, 0.19, 0.30), ink_color=(0.04, 0.04, 0.06),
    )
    bed_edge.location = (0, Z4_FOREGROUND_Y, -0.15)
    bed_edge.scale = (0.0021, 0.0021, 0.0021)

    # --- Character: import all 4 expressions stacked at the same
    # transform; toggle hide_render/hide_viewport to switch between them.
    char_layers = {}
    for expr in EXPRESSIONS:
        char = svg_import.import_flat_svg(
            os.path.join(CHAR_SVG_DIR, f"rahul_{expr}.svg"), master_coll, f"Rahul_{expr}",
            fill_color=(0.93, 0.87, 0.76), ink_color=(0.05, 0.04, 0.04),
        )
        # rahul_*.svg's own local bbox center is (0.2616, 0.3160) and its
        # bottom edge is at local y=-0.0099 (measured directly, not
        # assumed) — offset so the figure sits centered on X and with feet
        # near world Z=0.05.
        char.location = (0.10 - 0.2616 * 1.05, Z3_CHARACTER_Y, 0.05 + 0.0099 * 1.05)
        char.scale = (1.05, 1.05, 1.05)
        char_layers[expr] = char

    # hide_render/hide_viewport are keyframed as a hard step (expression
    # swap, not a cross-fade) — force CONSTANT interpolation or Bezier
    # easing between "hidden"(1.0) and "visible"(0.0) makes the OTHER
    # expression pop in/out around the midpoint between keyframes instead
    # of exactly at the beat frame.
    prev_interp = bpy.context.preferences.edit.keyframe_new_interpolation_type
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'

    def _set_hidden(obj, hidden, frame):
        # hide_render on a parent Empty does NOT cascade to its children in
        # Blender's renderer — the actual curve geometry has to be keyed too.
        for target in [obj] + list(obj.children_recursive):
            target.hide_render = hidden
            target.hide_viewport = hidden
            target.keyframe_insert(data_path="hide_render", frame=frame)
            target.keyframe_insert(data_path="hide_viewport", frame=frame)

    for expr, obj in char_layers.items():
        _set_hidden(obj, expr != "relaxed", 1)

    beat_frames = {"relaxed": 1, "curious": round(2.6 * FPS), "uneasy": round(5.4 * FPS), "realization": round(8.2 * FPS)}
    end_frame = round(11.0 * FPS)
    for expr, frame in beat_frames.items():
        for other_expr, obj in char_layers.items():
            _set_hidden(obj, other_expr != expr, frame)

    bpy.context.preferences.edit.keyframe_new_interpolation_type = prev_interp

    # --- Phone glow: screen emission + a soft point light.
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
    if phone_screen is not None and phone_screen.data.materials:
        phone_screen.data.materials[len(phone_screen.data.materials) - 1] = screen_mat

    glow_light = bpy.data.lights.new("Light_PhoneGlow", type='POINT')
    glow_light.energy = 0.0
    glow_light.color = (0.75, 0.85, 1.0)
    glow_light.shadow_soft_size = 0.05
    glow_obj = bpy.data.objects.new("Light_PhoneGlow", glow_light)
    master_coll.objects.link(glow_obj)
    glow_obj.location = (phone.location.x, phone.location.y - 0.05, phone.location.z + 0.02)

    ignite_frame = beat_frames["curious"] + 4
    for f, v in [(1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 3.2)]:
        glow_light.energy = v
        glow_light.keyframe_insert(data_path="energy", frame=f)
    for f, v in [(1, 0.0), (ignite_frame - 1, 0.0), (ignite_frame + 5, 5.0)]:
        emit.inputs["Strength"].default_value = v
        emit.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

    # --- Lighting: cool window-moon key, faint ambient, phone glow (above).
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

    # --- Camera: slow push-in toward the face as the reaction lands.
    cam, target, focus = camera_shots.build_camera(master_coll)
    cam.data.sensor_fit = 'VERTICAL'
    # Character parent origin sits with feet at world Z~0.06; head top is
    # ~0.73, face/eye height ~0.60-0.65 (measured off the local bbox, see
    # the offset comment above) — camera targets aim there, not at torso.
    cam_shots = [
        {
            "start_s": 0.0, "end_s": 4.0,
            "cam_location": (0.05, -1.65, 0.52),
            "target_location": (0.08, 0, 0.48),
            "focus_location": (0.08, 0, 0.48),
            "lens_mm": 50,
        },
        {
            "start_s": 4.0, "end_s": 11.0,
            "cam_location": (0.02, -1.35, 0.56),
            "target_location": (0.09, 0, 0.60),
            "focus_location": (0.09, 0, 0.60),
            "lens_mm": 65,
            "cam_location_end": (-0.02, -1.05, 0.58),
            "target_location_end": (0.10, 0, 0.62),
            "focus_location_end": (0.10, 0, 0.62),
        },
    ]
    camera_shots.animate_camera(cam, target, focus, cam_shots)
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.2

    style_cfg = apply_style.load_style_profile(
        os.path.join(os.path.dirname(FRAMES_DIR), "..", "manifests", "style_profile.json")
    ) if False else {"color_management": {"view_transform": "AgX", "look": "AgX - Punchy", "exposure": 0.5}}
    apply_style.apply_color_management(bpy.context.scene, style_cfg)
    apply_style.apply_render_settings(
        bpy.context.scene,
        resolution=(480, 600) if preview else (1080, 1350),
        samples=24 if preview else 128,
    )

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = end_frame
    return cam


def _find_screen_obj(phone_parent):
    for child in phone_parent.children:
        if child.name.lower().startswith("screen"):
            return child
    return None


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--preview" in argv
    build(preview=preview)

    scene = bpy.context.scene
    out_dir = os.path.join(FRAMES_DIR, "gate2_preview" if preview else "gate2_final")
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, "frame_")
    print(f"RENDER_RANGE {scene.frame_start} {scene.frame_end}")
    bpy.ops.render.render(animation=True)
    print("BUILD_GATE2_DONE")
