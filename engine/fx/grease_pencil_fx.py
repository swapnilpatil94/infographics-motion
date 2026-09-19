"""Grease Pencil atmospheric FX: light rays, dust motes, ink accents.

Approach: build the shape as an ordinary Blender curve (bezier/circle),
then `bpy.ops.object.convert(target='GREASEPENCIL')`. Authoring raw GP3
stroke/point data directly is possible but far more brittle in Blender
5.x's new curves-based Grease Pencil API; converting from a curve gets
the same hand-drawn-strokable result (GP modifiers like Noise/Thickness
still apply post-conversion) with a fraction of the risk. SVG stays the
primary source for designed reusable artwork (character/props/env) —
Grease Pencil is reserved for THIS role: atmosphere that benefits from an
organic, imperfect, animated line rather than a static vector fill.

Determinism: every function takes an explicit `seed`, so re-running the
generator produces the same scatter/wobble every time (per the project's
reproducibility requirement) — never Python's unseeded `random`.
"""
import bpy
import random
import math


def _gp_material(name, color, alpha=1.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    return mat


def _curve_to_gp(curve_obj, coll, name, stroke_color, stroke_alpha=1.0, bevel=0.004, noise_strength=0.0, seed=0):
    curve_obj.data.bevel_depth = bevel
    curve_obj.data.resolution_u = 8
    for c in list(curve_obj.users_collection):
        c.objects.unlink(curve_obj)
    coll.objects.link(curve_obj)
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)
    bpy.ops.object.convert(target='GREASEPENCIL')
    gp_obj = bpy.context.view_layer.objects.active
    gp_obj.name = name
    if gp_obj.data.materials:
        mat = gp_obj.data.materials[0]
        if mat.grease_pencil:
            mat.grease_pencil.color = (*stroke_color, stroke_alpha)
    if noise_strength > 0:
        mod = gp_obj.modifiers.new("HandDrawnWobble", 'GREASE_PENCIL_NOISE')
        mod.factor = noise_strength
        mod.seed = seed
    return gp_obj


def add_light_ray_cone(coll, origin, direction, length=1.4, width_deg=14, count=3,
                        color=(1.0, 0.92, 0.75), alpha=0.10, seed=0, name="LightRays"):
    """A few thin converging strokes from `origin` along `direction` —
    reads as a soft shaft of window/moon light without a volumetric
    render pass. `direction` and `origin` are world-space mathutils
    Vectors."""
    rng = random.Random(seed)
    objs = []
    direction = direction.normalized()
    # build an arbitrary perpendicular basis for spreading the rays
    up = mathutils_vector((0, 0, 1)) if abs(direction.z) < 0.9 else mathutils_vector((1, 0, 0))
    right = direction.cross(up).normalized()
    for i in range(count):
        t = (i / max(1, count - 1)) - 0.5
        spread = math.radians(width_deg) * t
        ray_dir = (direction + right * math.tan(spread)).normalized()
        end = origin + ray_dir * length * rng.uniform(0.85, 1.15)
        curve = bpy.data.curves.new(f"{name}_ray{i}", 'CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(1)
        spline.bezier_points[0].co = origin
        spline.bezier_points[1].co = end
        for p in spline.bezier_points:
            p.handle_left_type = p.handle_right_type = 'AUTO'
        obj = bpy.data.objects.new(f"{name}_ray{i}", curve)
        bpy.context.scene.collection.objects.link(obj)
        gp = _curve_to_gp(obj, coll, f"{name}_ray{i}", color, alpha, bevel=0.006 * (1 - abs(t)), noise_strength=0.15, seed=seed + i)
        objs.append(gp)
    return objs


def add_dust_motes(coll, bounds_min, bounds_max, count=14, seed=0, color=(0.85, 0.88, 0.95), alpha=0.35, name="DustMotes"):
    """Small point-like strokes scattered in a box — cheap, restrained
    atmosphere. Deterministic from `seed`."""
    rng = random.Random(seed)
    objs = []
    for i in range(count):
        pos = mathutils_vector((
            rng.uniform(bounds_min[0], bounds_max[0]),
            rng.uniform(bounds_min[1], bounds_max[1]),
            rng.uniform(bounds_min[2], bounds_max[2]),
        ))
        curve = bpy.data.curves.new(f"{name}_{i}", 'CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(1)
        r = rng.uniform(0.004, 0.01)
        spline.bezier_points[0].co = pos
        spline.bezier_points[1].co = pos + mathutils_vector((r, 0, 0))
        for p in spline.bezier_points:
            p.handle_left_type = p.handle_right_type = 'AUTO'
        obj = bpy.data.objects.new(f"{name}_{i}", curve)
        bpy.context.scene.collection.objects.link(obj)
        gp = _curve_to_gp(obj, coll, f"{name}_{i}", color, alpha, bevel=rng.uniform(0.002, 0.0045))
        objs.append(gp)
    return objs


def mathutils_vector(t):
    from mathutils import Vector
    return Vector(t)
