"""Reusable motivated lighting profiles.

Every light here is motivated by something in-world (moonlight through the
window, the phone's own screen, ambient bounce) — no default-Blender flat
fill. Values tuned for the bedroom_night set's scale (meters).
"""
import bpy
import math


def _light_obj(name, kind, location, rotation=(0, 0, 0), energy=1.0, color=(1, 1, 1), coll=None):
    data = bpy.data.lights.new(name, type=kind)
    data.energy = energy
    data.color = color
    obj = bpy.data.objects.new(name, data)
    (coll or bpy.context.scene.collection).objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def build_night_bedroom_rig(coll, window_obj):
    """window_moon (cold, directional) + faint room ambient bounce (cold,
    very low) + a warm practical hint near the nightstand (near-off until
    the phone lights it). Returns a dict of light objects."""
    lights = {}

    moon = _light_obj(
        "Light_WindowMoon", 'SUN',
        location=(window_obj.location.x, window_obj.location.y - 0.3, window_obj.location.z),
        rotation=(math.radians(62), 0, math.radians(-35)),
        energy=2.8, color=(0.55, 0.65, 1.0), coll=coll,
    )
    moon.data.angle = math.radians(3)
    lights["window_moon"] = moon

    ambient = _light_obj(
        "Light_RoomAmbient", 'POINT',
        location=(0.0, -0.6, 2.2),
        energy=55.0, color=(0.35, 0.42, 0.6), coll=coll,
    )
    ambient.data.shadow_soft_size = 1.2
    lights["room_ambient"] = ambient

    return lights


def build_phone_glow(coll, phone_obj, energy_on=9.0, energy_off=0.0):
    """A small warm-white point light bound to the phone's screen position.
    Animate `.data.energy` between energy_off and energy_on for the
    notification beat."""
    glow = _light_obj(
        "Light_PhoneGlow", 'POINT',
        location=phone_obj.location,
        energy=energy_off, color=(0.75, 0.85, 1.0), coll=coll,
    )
    glow.data.shadow_soft_size = 0.04
    glow.parent = phone_obj
    glow.location = (0, 0, 0.01)
    return glow


def keyframe_energy(light_obj, frames_values):
    """frames_values: list of (frame, energy) pairs."""
    for frame, value in frames_values:
        light_obj.data.energy = value
        light_obj.data.keyframe_insert(data_path="energy", frame=frame)
