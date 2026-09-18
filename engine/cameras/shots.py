"""Camera: builds one physical camera + a tracked target empty, then
animates both across a shot list (the Shot DSL, see manifests/shot_plan.json)
by keyframing location/lens on shot boundaries. The TRACK_TO constraint on
the tracked target means we never hand-author rotation matrices.
"""
import bpy

FPS = 24


def build_camera(coll, name="MainCamera"):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = 35
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 2.8
    cam = bpy.data.objects.new(name, cam_data)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam

    target = bpy.data.objects.new(name + "_Target", None)
    coll.objects.link(target)
    tc = cam.constraints.new(type='TRACK_TO')
    tc.target = target
    tc.track_axis = 'TRACK_NEGATIVE_Z'
    tc.up_axis = 'UP_Y'

    focus = bpy.data.objects.new(name + "_Focus", None)
    coll.objects.link(focus)
    cam_data.dof.focus_object = focus

    return cam, target, focus


def _kf(obj, path, frame, value=None):
    if value is not None:
        setattr(obj, path, value) if "." not in path else None
    obj.keyframe_insert(data_path=path, frame=frame)


def animate_camera(cam, target, focus, shots):
    """shots: list of dicts with start_s, cam_location, target_location,
    focus_location, lens_mm. One keyframe per shot at its start time; the
    last shot also gets an end keyframe so its move plays out."""
    for i, shot in enumerate(shots):
        frame = round(shot["start_s"] * FPS) + 1
        cam.location = shot["cam_location"]
        cam.keyframe_insert(data_path="location", frame=frame)
        target.location = shot["target_location"]
        target.keyframe_insert(data_path="location", frame=frame)
        focus.location = shot["focus_location"]
        focus.keyframe_insert(data_path="location", frame=frame)
        cam.data.lens = shot["lens_mm"]
        cam.data.keyframe_insert(data_path="lens", frame=frame)

        if "end_s" in shot and "cam_location_end" in shot:
            end_frame = round(shot["end_s"] * FPS)
            cam.location = shot["cam_location_end"]
            cam.keyframe_insert(data_path="location", frame=end_frame)
            target.location = shot.get("target_location_end", shot["target_location"])
            target.keyframe_insert(data_path="location", frame=end_frame)
            focus.location = shot.get("focus_location_end", shot["focus_location"])
            focus.keyframe_insert(data_path="location", frame=end_frame)

