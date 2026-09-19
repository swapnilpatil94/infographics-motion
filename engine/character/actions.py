"""Reusable action primitives for any engine.character.rig.CharacterRig.
Not written for Rahul specifically — every function takes a `rig` and
generic parameters, so the SAME functions drive any character built from
a rig_spec of the same shape. The visual_director compiler is what maps a
shot's requested action name to a call here.

Honest granularity (see rig.py): body_pose is rigid, head is an
independently-rotatable rigid pivot, face is a rigid per-expression swap.
"reach"/"raise_phone" therefore do NOT bend an elbow — no such joint
exists in the source art — they move the PROP and turn the HEAD to look
at it, which is what's actually achievable and, blocked well, reads fine.

All keyframing here forces CONSTANT interpolation for hide_render/
hide_viewport swaps (hard cut, not a cross-fade — see the Gate 2 bug
notes) and leaves Blender's default Bezier easing for continuous
transforms (rotation/location/scale), which is what gives these actions
their anticipation/settle feel instead of robotic linear motion.
"""
import bpy
import math


def _keyed(obj, data_path, frame, constant=False):
    prev = bpy.context.preferences.edit.keyframe_new_interpolation_type
    if constant:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
    obj.keyframe_insert(data_path=data_path, frame=frame)
    if constant:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = prev


def emotion(rig, name, frame):
    """Swaps the whole head (hair+face) to a named expression variant —
    covers curious/uneasy/realization/surprise/relaxed/notice/etc, i.e.
    whatever variants that character's rig_spec actually defines."""
    rig.set_face(name, frame=frame)


def blink(rig, frame, hold_frames=3, resume_variant=None):
    """Quick swap to the 'blink' head variant and back. Needs a 'blink'
    variant in the rig's face parts (see rig_generator's face_variants)."""
    resume_variant = resume_variant or rig.current_face
    rig.set_face(resume_variant, frame=frame - 1)
    rig.set_face("blink", frame=frame)
    rig.set_face(resume_variant, frame=frame + hold_frames)


def idle_sway(rig, frame_start, frame_end, amplitude_deg=0.8, period_s=3.4, fps=24):
    """Very subtle whole-body weight-shift so a held pose never looks
    frozen. Small, slow, on the root (not the head) so it reads as
    posture, not nodding."""
    period_f = period_s * fps
    t = frame_start
    sign = 1
    while t <= frame_end:
        rig.root.rotation_euler = (0, 0, math.radians(amplitude_deg * sign))
        _keyed(rig.root, "rotation_euler", round(t))
        t += period_f / 2
        sign *= -1


def breathing(rig, frame_start, frame_end, amplitude=0.012, period_s=3.8, fps=24):
    """Subtle uniform scale pulse on the body silhouette approximating a
    chest rise/fall — there's no separate chest geometry to inflate, so
    this is a whole-body breathe, kept small enough to read as life, not
    as the character literally growing."""
    period_f = period_s * fps
    base = rig.body.scale[0]
    t = frame_start
    phase = 0
    while t <= frame_end:
        s = base * (1.0 + amplitude * math.sin(phase))
        rig.body.scale = (s, s, s)
        _keyed(rig.body, "scale", round(t))
        t += period_f / 8
        phase += math.pi / 4


def head_turn(rig, angle_deg, frame, hold=False):
    """Rotates the head pivot around Z (world up) — a genuine independent
    head turn, not a whole-figure lean, because rig.head is a real
    separate object (see rig.py)."""
    x, y, z = rig.head.rotation_euler
    rig.head.rotation_euler = (x, y, math.radians(angle_deg))
    _keyed(rig.head, "rotation_euler", frame)


def head_tilt(rig, angle_deg, frame):
    """Rotates the head pivot around X (nod/tilt down-up)."""
    x, y, z = rig.head.rotation_euler
    rig.head.rotation_euler = (math.radians(angle_deg), y, z)
    _keyed(rig.head, "rotation_euler", frame)


def look_at(rig, target_world_point, frame, turn_scale=1.0, tilt_scale=1.0):
    """Points the head roughly toward a world-space point by deriving a
    turn/tilt angle from the vector head->target. Approximate (no
    independent eye/pupil geometry exists in the source art to aim
    precisely — see rig_generator's granularity notes) but reads
    correctly for 'notices/looks at the phone' beats."""
    head_pos = rig.head_world_point()
    dx = target_world_point.x - head_pos.x
    dz = target_world_point.z - head_pos.z
    dy = target_world_point.y - head_pos.y
    turn = math.degrees(math.atan2(-dx, max(abs(dy), 0.05))) * turn_scale
    tilt = math.degrees(math.atan2(dz, max(abs(dy), 0.05))) * -tilt_scale
    turn = max(-28, min(28, turn))
    tilt = max(-22, min(22, tilt))
    head_turn(rig, turn, frame)
    head_tilt(rig, tilt, frame)
    return turn, tilt


def reset_head(rig, frame):
    rig.head.rotation_euler = (0, 0, 0)
    _keyed(rig.head, "rotation_euler", frame)
