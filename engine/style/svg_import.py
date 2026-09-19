"""Imports a normalized character/prop SVG into Blender as a flat 2.5D
paper-cutout layer: curves -> filled flat mesh, grouped into one object,
with the "Background" fill recolored (Open Peeps ships these as white
silhouette + black ink linework, meant to be tinted, not used as literal
white) and the "Ink" kept black.
"""
import bpy


def _material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
    return mat


def import_flat_svg(filepath, coll, name, fill_color=(0.95, 0.90, 0.80), ink_color=(0.05, 0.04, 0.04), z_depth=0.0, scale=1.0):
    """Returns a single empty object parenting every imported curve, flattened
    and recolored, ready to be positioned/scaled as one 2.5D cutout layer."""
    existing = set(bpy.data.objects.keys())
    bpy.ops.import_curve.svg(filepath=filepath)
    imported = [o for o in bpy.data.objects if o.name not in existing]

    fill_mat = _material(f"{name}_fill", fill_color)
    ink_mat = _material(f"{name}_ink", ink_color)

    parent = bpy.data.objects.new(name, None)
    coll.objects.link(parent)

    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o.data.dimensions = '2D'
        o.data.fill_mode = 'BOTH'
        o.data.extrude = 0.0
        o.data.bevel_depth = 0.0
        # SVG Y-down -> Blender: flip so the figure stands upright, and
        # push onto the XZ plane (facing -Y, matching the rest of the rig).
        o.rotation_euler = (1.5708, 0, 0)
        o.parent = parent
        is_ink = "Ink" in o.name or "ink" in o.name.lower()
        mat = ink_mat if is_ink else fill_mat
        if o.data.materials:
            o.data.materials[0] = mat
        else:
            o.data.materials.append(mat)
        # keep ink a hair in front of fill on the same cutout so it never
        # z-fights, without needing real depth-sorted transparency.
        o.location.y += -0.0004 if is_ink else 0.0

    parent.scale = (scale, scale, scale)
    parent.location.z += z_depth
    return parent
