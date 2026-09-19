"""Cinematic motion grammar.

Semantic acting helpers produce deterministic Blender keyframes. They use
anticipation, action, reaction and settle phases so shots do not feel like
pose-to-pose slideshows.
"""
import math
import bpy

def _frame(t_s, fps=24):
    return max(1, round(float(t_s) * fps) + 1)

def set_bezier(obj, data_path=None):
    if not obj.animation_data or not obj.animation_data.action:
        return
    for fc in obj.animation_data.action.fcurves:
        if data_path is None or fc.data_path == data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

def add_breathing(arm_obj, start_s, end_s, amplitude_deg=0.7, cycles=2.0, fps=24):
    bone = arm_obj.pose.bones.get("chest")
    if bone is None:
        return
    duration = max(0.1, end_s-start_s)
    count = max(2, int(cycles * 8))
    base = bone.rotation_euler.x
    for i in range(count + 1):
        t = i / count
        bone.rotation_euler.x = base + math.radians(amplitude_deg) * math.sin(t * cycles * math.tau)
        bone.keyframe_insert(data_path="rotation_euler", index=0, frame=_frame(start_s + duration*t, fps))
    set_bezier(arm_obj, 'pose.bones["chest"].rotation_euler')

def add_blink(face, start_s, end_s, fps=24):
    for key in ("eye.R", "eye.L"):
        eye = face.get(key)
        if eye is None:
            continue
        base_y = eye.scale.y
        for t, value in (
            (start_s, base_y),
            (start_s + (end_s-start_s)*0.45, max(0.12, base_y*0.18)),
            (end_s, base_y),
        ):
            eye.scale.y = value
            eye.keyframe_insert(data_path="scale", frame=_frame(t, fps))
        set_bezier(eye, "scale")

def add_head_glance(arm_obj, start_s, end_s, yaw_deg=4.0, fps=24):
    bone = arm_obj.pose.bones.get("head")
    if bone is None:
        return
    base = bone.rotation_euler.z
    for t, deg in (
        (start_s, 0.0),
        (start_s + (end_s-start_s)*0.35, yaw_deg),
        (end_s, yaw_deg*0.55),
    ):
        bone.rotation_euler.z = base + math.radians(deg)
        bone.keyframe_insert(data_path="rotation_euler", index=2, frame=_frame(t, fps))
    set_bezier(arm_obj, 'pose.bones["head"].rotation_euler')

def add_reaction_sequence(arm_obj, face, start_s, end_s, intensity=1.0, fps=24):
    duration = max(0.8, end_s-start_s)
    add_breathing(arm_obj, start_s, end_s, amplitude_deg=0.55*intensity,
                  cycles=max(1.0, duration/2.2), fps=fps)
    add_blink(face, start_s + duration*0.18, start_s + duration*0.23, fps=fps)
    add_head_glance(arm_obj, start_s + duration*0.22, start_s + duration*0.52,
                    yaw_deg=3.5*intensity, fps=fps)
    chest = arm_obj.pose.bones.get("chest")
    if chest:
        base = chest.rotation_euler.x
        for t, deg in ((start_s+duration*0.55, 0.6*intensity), (end_s, 0.0)):
            chest.rotation_euler.x = base + math.radians(deg)
            chest.keyframe_insert(data_path="rotation_euler", index=0, frame=_frame(t, fps))
        set_bezier(arm_obj, 'pose.bones["chest"].rotation_euler')
