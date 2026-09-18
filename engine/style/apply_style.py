"""Global style application: color management, render engine, Line Art.

Halation/grain via the compositor are deliberately OUT of Gate 1 v1 — Blender
5.x rebuilt the compositor as a node-group system with a materially
different API (Glare's controls are now input sockets, not node
properties, and the old Scene.node_tree/use_nodes path is gone) and get
that right needs real iteration. Gate 1's cinematic read leans on Line Art
+ motivated lighting + AgX instead; halation is a follow-up, not a blocker.
"""
import bpy
import json


def load_style_profile(path):
    with open(path) as f:
        return json.load(f)


def apply_render_settings(scene, resolution=(1280, 720), samples=64):
    bpy.ops.preferences.addon_enable(module='cycles')
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.fps = 24
    scene.render.film_transparent = False


def apply_color_management(scene, cfg):
    vs = scene.view_settings
    vs.view_transform = cfg["color_management"]["view_transform"]
    vs.look = cfg["color_management"]["look"]
    vs.exposure = cfg["color_management"]["exposure"]


def add_line_art(source_collection, cfg, name="LineArt"):
    """Creates a Grease Pencil object whose LINEART modifier traces the
    given collection's mesh contours/creases/material boundaries."""
    bpy.context.view_layer.active_layer_collection = _find_layer_collection(
        bpy.context.view_layer.layer_collection, source_collection.name
    ) or bpy.context.view_layer.layer_collection
    bpy.ops.object.grease_pencil_add(type='LINEART_COLLECTION')
    gp = bpy.context.active_object
    gp.name = name
    mod = gp.modifiers[0]
    mod.source_collection = source_collection
    mod.use_material = True
    if gp.data.materials:
        mat = gp.data.materials[0]
        if mat.grease_pencil:
            mat.grease_pencil.color = (*cfg["line_art"]["color"], 1.0)
    try:
        mod.thickness = cfg["line_art"]["line_weight_px"]
    except Exception:
        pass
    try:
        mod.crease_threshold = cfg["line_art"]["crease_angle_deg"] * 3.14159 / 180.0
    except Exception:
        pass
    return gp


def _find_layer_collection(layer_coll, name):
    if layer_coll.collection.name == name:
        return layer_coll
    for child in layer_coll.children:
        found = _find_layer_collection(child, name)
        if found:
            return found
    return None


def flatten_material_specular(mat, roughness_floor=0.6):
    """Restrained/matte look: kill glossy hotspots that read as 'plastic 3D'."""
    if not mat.use_nodes:
        return
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        return
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    if bsdf.inputs["Roughness"].default_value < roughness_floor:
        bsdf.inputs["Roughness"].default_value = roughness_floor
