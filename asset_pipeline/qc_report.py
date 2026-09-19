"""QC gate for the Gate 2 SVG shot: license, frame, and asset checks.
Not a full production QC suite (audio/story-coverage checks don't apply to
a single silent test shot) — scoped to what's actually verifiable here.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asset_pipeline import registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_license_gate():
    quarantined = registry.all_quarantined()
    return {
        "pass": len(quarantined) == 0,
        "registered_count": len(registry.all_registered()),
        "quarantined_count": len(quarantined),
        "quarantined_ids": [a["id"] for a in quarantined],
    }


def check_frames(frames_dir, expected_count):
    if not os.path.isdir(frames_dir):
        return {"pass": False, "reason": "frames dir missing"}
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    missing = expected_count - len(files)
    sizes = [os.path.getsize(os.path.join(frames_dir, f)) for f in files]
    zero_byte = [f for f, s in zip(files, sizes) if s < 1024]
    return {
        "pass": missing == 0 and not zero_byte,
        "found": len(files),
        "expected": expected_count,
        "missing_count": max(0, missing),
        "suspiciously_small_frames": zero_byte,
    }


def check_normalization_report():
    path = os.path.join(ROOT, "assets/character/normalized/normalization_report.json")
    if not os.path.exists(path):
        return {"pass": False, "reason": "no normalization report found"}
    report = json.load(open(path))
    all_warnings = [w for r in report for w in r["warnings"]]
    return {"pass": True, "files_normalized": len(report), "warnings": all_warnings}


if __name__ == "__main__":
    frames_dir = os.path.join(ROOT, "output/frames/gate2_preview")
    result = {
        "license_gate": check_license_gate(),
        "frame_integrity": check_frames(frames_dir, 264),
        "svg_normalization": check_normalization_report(),
        "known_visual_issues": [
            "Small striped/hatched rendering artifact near the chin on some "
            "expressions (face/Concerned, face/Fear atoms) — traced to Blender's "
            "curve importer not honoring the source SVG's fill-rule=evenodd on a "
            "decorative shading sub-path. Cosmetic only; does not affect facial "
            "feature legibility. Not fixed in this pass.",
            "No environment geometry (window/nightstand/phone) is in frame during "
            "the close-up hold — by composition choice for this shot, not a bug, "
            "but means the phone itself is only inferred via its light, not seen.",
        ],
    }
    out_path = os.path.join(ROOT, "manifests", "gate2_qc_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
