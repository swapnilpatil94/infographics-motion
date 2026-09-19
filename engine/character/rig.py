"""Generic, reusable Character Rig: loads a rig_spec.json (written by
asset_pipeline.rig_generator) and builds live Blender objects from it.
Not specific to any one character — any character with a rig_spec of the
same shape ({parts: {body_pose: {variants}, face: {variants}}}) can be
built through this same class.

Granularity is honest about what 2D cutout SVG art actually supports (see
rig_generator's module docstring): body_pose is ONE rigid silhouette
(no per-limb bones), the head is a SEPARATE rigid piece that rotates
independently of the body (real turn/tilt, not a whole-figure lean — see
compose_character.extract_head_only/extract_body_only for how the split
is done without breaking alignment), and each face expression is a rigid
whole-face swap (eyes/eyebrows/mouth are not independently addressable).
"""
import bpy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from engine.style import svg_import

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIGURE_SCALE = 1.05


class CharacterRig:
    def __init__(self, character_id):
        self.character_id = character_id
        self.root = None       # Empty — world anchor, set .location/.rotation here
        self.body = None       # rigid body/legs object, child of root
        self.head = None       # Empty pivot — child of root; rotate this for turn/tilt
        self.face_objs = {}    # variant_name -> object, each child of head
        self.current_face = None
        self.spec = None

    @classmethod
    def build(cls, character_id, rig_spec_path, coll, fill_color=(0.93, 0.87, 0.76), ink_color=(0.05, 0.04, 0.04)):
        with open(os.path.join(ROOT, rig_spec_path)) as f:
            spec = json.load(f)
        rig = cls(character_id)
        rig.spec = spec

        rig.root = bpy.data.objects.new(f"{character_id}_root", None)
        coll.objects.link(rig.root)

        body_rel = spec["parts"]["body_pose"]["variants"]["default"]
        rig.body = svg_import.import_flat_svg(
            os.path.join(ROOT, body_rel), coll, f"{character_id}_body",
            fill_color=fill_color, ink_color=ink_color,
        )
        rig.body.scale = (FIGURE_SCALE, FIGURE_SCALE, FIGURE_SCALE)
        rig.body.parent = rig.root

        # Head pivot: extract_head_only/extract_body_only share the
        # composed document's coordinate frame, so the head content needs
        # NO alignment offset to match the body (verified by render). But
        # the pivot Empty itself starts at (0,0,0) while the actual head
        # geometry is drawn ~0.56-0.69 units up inside that content (raw
        # SVG-import coordinates, measured directly — see NECK_LOCAL_Z
        # below) — rotating an Empty at the origin would swing the head on
        # a long "boom" instead of turning at the neck. Fix: move the
        # pivot itself to the measured neck point, and shift each face
        # object's .location by the same amount in the opposite direction
        # so the RENDERED position is unchanged (pivot_offset + child_
        # offset cancels) while the ROTATION origin is now correct.
        neck_local = (0.068, 0.0, 0.5626)
        rig.head = bpy.data.objects.new(f"{character_id}_head_pivot", None)
        rig.head.parent = rig.root
        rig.head.location = neck_local
        coll.objects.link(rig.head)

        first = True
        for variant_name, rel_path in spec["parts"]["face"]["variants"].items():
            obj = svg_import.import_flat_svg(
                os.path.join(ROOT, rel_path), coll, f"{character_id}_head_{variant_name}",
                fill_color=fill_color, ink_color=ink_color,
            )
            obj.scale = (FIGURE_SCALE, FIGURE_SCALE, FIGURE_SCALE)
            obj.location = (-neck_local[0], -neck_local[1], -neck_local[2])
            obj.parent = rig.head
            _hide_recursive(obj, not first)
            rig.face_objs[variant_name] = obj
            if first:
                rig.current_face = variant_name
                first = False

        return rig

    def set_face(self, variant_name, frame=None):
        if variant_name not in self.face_objs:
            raise KeyError(f"{self.character_id} has no face variant '{variant_name}' (has: {list(self.face_objs)})")
        for name, obj in self.face_objs.items():
            _hide_recursive(obj, name != variant_name, frame)
        self.current_face = variant_name

    def world_point(self, local_xyz):
        from mathutils import Vector
        bpy.context.view_layer.update()
        return self.root.matrix_world @ Vector(local_xyz)

    def head_world_point(self):
        bpy.context.view_layer.update()
        return self.head.matrix_world.translation


def _hide_recursive(obj, hidden, frame=None):
    for target in [obj] + list(obj.children_recursive):
        target.hide_render = hidden
        target.hide_viewport = hidden
        if frame is not None:
            target.keyframe_insert(data_path="hide_render", frame=frame)
            target.keyframe_insert(data_path="hide_viewport", frame=frame)
