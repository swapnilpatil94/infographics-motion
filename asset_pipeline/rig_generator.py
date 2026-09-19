"""Generates a reusable, JSON-serializable Character Rig Spec: which base
pose SVG to start from, and which composed SVG file realizes each named
face/hair/pose variant. No bpy dependency here — this is the PLANNING
step; engine/character/rig.py (bpy-dependent) is what actually imports the
files this module writes and builds live Blender objects from them.

Honest scope note: Open Peeps' body/leg/arm silhouette is ONE inseparable
path per pose atom (verified against the raw SVGs — see layer_extractor
notes). A rig built from this source can swap the WHOLE body_pose or the
WHOLE face as rigid/discrete units, and can rigidly rotate the head as a
whole. It cannot independently pose an elbow, a wrist, an eyebrow, or a
pupil — that would require source art decomposed at that granularity,
which no evaluated source provides. The rig spec format below has room
for deeper part trees (arm.upper/forearm/hand etc.) for a future source
that DOES decompose that far; it is simply empty for Open Peeps-derived
characters.
"""
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asset_pipeline import compose_character

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_rig_spec(character_id, base_svg_path, hair_atom_path, face_variants, out_dir):
    """face_variants: {variant_name: atom_svg_path}. Writes:
      - one HEAD-ONLY composed SVG per face variant (hair+face, no body —
        see compose_character.extract_head_only), independently rotatable
      - the body pose atom is referenced directly (already standalone)
    and a rig_spec.json describing the result. Splitting head from body is
    what makes engine.character.actions.head_turn/tilt/look_* rotate only
    the head instead of the whole seated figure — see rig.py."""
    os.makedirs(out_dir, exist_ok=True)
    variant_files = {}
    for variant_name, face_path in face_variants.items():
        out_path = os.path.join(out_dir, f"{character_id}_head_{variant_name}.svg")
        compose_character.extract_head_only(base_svg_path, face_atom_path=face_path, head_atom_path=hair_atom_path, out_path=out_path)
        variant_files[variant_name] = os.path.relpath(out_path, ROOT)

    body_path = os.path.join(out_dir, f"{character_id}_body.svg")
    compose_character.extract_body_only(base_svg_path, out_path=body_path)

    rig_spec = {
        "character_id": character_id,
        "base_svg": os.path.relpath(base_svg_path, ROOT),
        "hair_atom": os.path.relpath(hair_atom_path, ROOT),
        "granularity": {
            "body_pose": "rigid — one inseparable silhouette per pose atom, no per-limb bones",
            "head": "rigid — rotatable independently of the body (turn/tilt), not deformable",
            "face": "rigid per expression — eyes/eyebrows/mouth are not independently addressable",
        },
        "parts": {
            "body_pose": {"variants": {"default": os.path.relpath(body_path, ROOT)}},
            "face": {"variants": variant_files},
        },
    }
    spec_path = os.path.join(out_dir, f"{character_id}_rig_spec.json")
    with open(spec_path, "w") as f:
        json.dump(rig_spec, f, indent=2)
    return rig_spec, spec_path


if __name__ == "__main__":
    ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
    spec, path = generate_rig_spec(
        character_id="rahul",
        base_svg_path=os.path.join(ATOMS, "a person/sitting.svg"),
        hair_atom_path=os.path.join(ATOMS, "head", "Flat Top.svg"),
        face_variants={
            "relaxed": os.path.join(ATOMS, "face", "Calm.svg"),
            "notice": os.path.join(ATOMS, "face", "Serious.svg"),
            "curious": os.path.join(ATOMS, "face", "Awe.svg"),
            "uneasy": os.path.join(ATOMS, "face", "Concerned Fear.svg"),
            "realization": os.path.join(ATOMS, "face", "Hectic.svg"),
            "blink": os.path.join(ATOMS, "face", "Eyes Closed.svg"),
        },
        out_dir=os.path.join(ROOT, "assets/character/normalized/rahul_rig"),
    )
    print("wrote", path)
