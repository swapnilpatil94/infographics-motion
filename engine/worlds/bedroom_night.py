"""World: bedroom_night.

Builds a persistent, continuity-tracked bedroom set: floor, walls, window,
door, bed, nightstand. Geometry is intentionally simple/blocky (Gate 1 is
about light + camera + character read, not prop fidelity) but every object
is real geometry with correct scale so lighting and camera behave like a
real room, not a backdrop.

World units: meters. Room origin (0,0,0) is the floor center.
"""
import bpy
import math

WORLD_ID = "bedroom_night"
ROOM_W = 3.6   # x
ROOM_D = 4.2   # y
ROOM_H = 2.6   # z


def _new_mesh_obj(name, coll):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def _cube(name, coll, size, location, rotation=(0, 0, 0)):
    obj = _new_mesh_obj(name, coll)
    bm_verts = []
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(obj.data)
    bm.free()
    obj.scale = size
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def _material(name, base_color, roughness=0.8, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if emission is not None:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def build(collection_name="World_BedroomNight"):
    """Builds the set into its own collection. Returns a continuity dict."""
    if collection_name in bpy.data.collections:
        coll = bpy.data.collections[collection_name]
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)

    objects = {}

    floor = _cube("Floor", coll, (ROOM_W, ROOM_D, 0.05), (0, 0, -0.025))
    floor.data.materials.append(_material("Mat_Floor", (0.09, 0.07, 0.06), roughness=0.55))
    objects["floor"] = floor

    wall_back = _cube("Wall_Back", coll, (ROOM_W, 0.08, ROOM_H), (0, ROOM_D / 2, ROOM_H / 2))
    wall_left = _cube("Wall_Left", coll, (0.08, ROOM_D, ROOM_H), (-ROOM_W / 2, 0, ROOM_H / 2))
    wall_right = _cube("Wall_Right", coll, (0.08, ROOM_D, ROOM_H), (ROOM_W / 2, 0, ROOM_H / 2))
    for w in (wall_back, wall_left, wall_right):
        w.data.materials.append(_material("Mat_Wall", (0.14, 0.12, 0.15), roughness=0.9))
        objects[w.name.lower()] = w

    window = _cube("Window_Frame", coll, (1.1, 0.06, 1.3), (-ROOM_W / 2 + 0.04, 1.2, 1.55))
    window.data.materials.append(_material("Mat_WindowFrame", (0.05, 0.05, 0.05), roughness=0.6))
    objects["window"] = window

    bed = _cube("Bed", coll, (1.4, 2.0, 0.55), (0.9, -1.0, 0.275))
    bed.data.materials.append(_material("Mat_Bed", (0.18, 0.16, 0.22), roughness=0.95))
    objects["bed"] = bed

    nightstand = _cube("Nightstand", coll, (0.45, 0.4, 0.55), (0.05, -0.05, 0.275))
    nightstand.data.materials.append(_material("Mat_Nightstand", (0.12, 0.09, 0.07), roughness=0.7))
    objects["nightstand"] = nightstand

    door = _cube("Door", coll, (0.9, 0.06, 2.05), (1.2, ROOM_D / 2 - 0.02, 1.025))
    door.data.materials.append(_material("Mat_Door", (0.1, 0.08, 0.07), roughness=0.75))
    objects["door"] = door

    # --- Dressing: cheap, procedural, gives the room identity without a
    # real asset pipeline (Gate 3). Kept low-poly/blocky on purpose.
    glass = _cube("Window_Glass", coll, (0.02, 0.94, 1.08), (-ROOM_W / 2 + 0.05, 1.2, 1.58))
    glass_mat = _material("Mat_WindowGlass", (0.5, 0.65, 0.95), roughness=0.15,
                           emission=(0.55, 0.68, 1.0), emission_strength=0.35)
    glass.data.materials.append(glass_mat)
    objects["window_glass"] = glass

    curtain_l = _cube("Curtain_L", coll, (0.05, 0.10, 1.35), (-ROOM_W / 2 + 0.06, 0.62, 1.55))
    curtain_r = _cube("Curtain_R", coll, (0.05, 0.10, 1.35), (-ROOM_W / 2 + 0.06, 1.78, 1.55))
    for c in (curtain_l, curtain_r):
        c.data.materials.append(_material("Mat_Curtain", (0.16, 0.13, 0.16), roughness=0.95))
        objects[c.name.lower()] = c

    pillow = _cube("Pillow", coll, (0.55, 0.35, 0.16), (0.9, 0.15, 0.61))
    pillow.data.materials.append(_material("Mat_Pillow", (0.30, 0.27, 0.30), roughness=0.9))
    objects["pillow"] = pillow

    blanket = _cube("Blanket", coll, (1.3, 1.1, 0.10), (0.9, -1.35, 0.60))
    blanket.data.materials.append(_material("Mat_Blanket", (0.15, 0.14, 0.24), roughness=0.9))
    objects["blanket"] = blanket

    frame = _cube("Wall_Frame", coll, (0.5, 0.04, 0.65), (0.9, ROOM_D / 2 - 0.03, 1.6))
    frame.data.materials.append(_material("Mat_Frame", (0.06, 0.05, 0.05), roughness=0.6))
    objects["wall_frame"] = frame

    lamp_base = _cube("Lamp_Base", coll, (0.10, 0.10, 0.05), (-0.12, -0.05, 0.575))
    lamp_shade = _cube("Lamp_Shade", coll, (0.14, 0.14, 0.16), (-0.12, -0.05, 0.70))
    for lo in (lamp_base, lamp_shade):
        lo.data.materials.append(_material("Mat_Lamp", (0.08, 0.07, 0.06), roughness=0.5))
        objects[lo.name.lower()] = lo

    continuity = {
        "world_id": WORLD_ID,
        "collection": collection_name,
        "room_dimensions_m": {"width": ROOM_W, "depth": ROOM_D, "height": ROOM_H},
        "origin": "floor_center",
        "objects": {
            k: {
                "location": list(v.location),
                "rotation_euler": list(v.rotation_euler),
                "dimensions": list(v.dimensions),
            }
            for k, v in objects.items()
        },
        "screen_direction_notes": (
            "Window is on -X wall; character sits/lies on bed facing +X/-Y "
            "toward nightstand+phone. Camera stays on the -Y/-X side of the "
            "180-degree line drawn between character and phone for Gate 1."
        ),
        "camera_safe_zone": {
            "x": [-1.6, 1.6],
            "y": [-2.4, 1.8],
            "z": [0.3, 2.3],
        },
    }
    return objects, continuity
