"""Extracts semantic layers from an SVG and maps raw group ids to the
canonical part names the rest of the pipeline (rig_generator, character
rig) expects — head, hair, face, body_pose, facial_hair, accessories, etc.

If an SVG's ids already carry semantic meaning (Open Peeps does: ids like
"face/Concerned", "head/mono/Flat-Top", "pose/sitting/crossed_legs"), we
preserve and canonicalize them via keyword rules below. If a future source
has no semantic ids at all, `CANONICAL_RULES` is the single place to add a
deterministic mapping for it — never inferred by an LLM per-asset.
"""
import re

CANONICAL_RULES = [
    (r"^face/", "face"),
    (r"^head/mono/", "hair"),
    (r"^facial-hair/", "facial_hair"),
    (r"^accessories/", "accessories"),
    (r"^pose/", "body_pose"),
    (r"^body/", "body_pose"),
    (r"^a-mono/", "body_pose"),
]


def canonical_name(raw_id):
    for pattern, canon in CANONICAL_RULES:
        if re.match(pattern, raw_id):
            return canon
    return None


def list_top_level_groups(svg_text):
    """Returns [(raw_id, canonical_name_or_None), ...] for every top-level
    <g id="..."> in document order (nested groups are left to the caller —
    this is a listing pass, not a full tree walk)."""
    ids = re.findall(r'<g id="([^"]+)"', svg_text)
    return [(raw_id, canonical_name(raw_id)) for raw_id in ids]


def extract_layer_map(svg_path):
    with open(svg_path, encoding="utf-8") as f:
        text = f.read()
    groups = list_top_level_groups(text)
    layer_map = {}
    for raw_id, canon in groups:
        if canon:
            layer_map.setdefault(canon, []).append(raw_id)
    return layer_map


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(p, "->", extract_layer_map(p))
