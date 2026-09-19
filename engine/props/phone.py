"""Prop: phone. A bezel box + an emissive screen plane whose Emission
Strength is meant to be keyframed in lockstep with the matching
Light_PhoneGlow point light (see engine.lighting.profiles.build_phone_glow)."""
import bpy


def _material_emissive(name, color, strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat, emit


def _material_matte(name, color, roughness=0.5):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build(coll, location=(0, 0, 0), size=(0.07, 0.008, 0.145)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    body = bpy.context.active_object
    body.name = "Prop_Phone"
    body.scale = size
    body.data.materials.append(_material_matte("Mat_PhoneBody", (0.02, 0.02, 0.025), roughness=0.3))
    for c in list(body.users_collection):
        c.objects.unlink(body)
    coll.objects.link(body)

    screen_w = size[0] * 0.86
    screen_h = size[2] * 0.9
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(location[0], location[1] - size[1] * 0.55, location[2]))
    screen = bpy.context.active_object
    screen.name = "Prop_PhoneScreen"
    screen.rotation_euler = (1.5708, 0, 0)
    screen.scale = (screen_w, screen_h, 1.0)
    screen_mat, emit_node = _material_emissive("Mat_PhoneScreen", (0.75, 0.85, 1.0), strength=0.0)
    screen.data.materials.append(screen_mat)
    for c in list(screen.users_collection):
        c.objects.unlink(screen)
    coll.objects.link(screen)
    screen.parent = body

    return {"body": body, "screen": screen, "emit_node": emit_node}


def keyframe_screen(phone, frames_values):
    node = phone["emit_node"]
    for frame, value in frames_values:
        node.inputs["Strength"].default_value = value
        node.inputs["Strength"].keyframe_insert(data_path="default_value", frame=frame)
