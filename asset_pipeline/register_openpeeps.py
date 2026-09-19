"""Registers the Open Peeps assets actually used in the Gate 2 SVG shot.
Run once after downloading + composing. Real metadata, not inferred.
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asset_pipeline import registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
PACK_ZIP = os.path.join(ROOT, "assets/character/raw/open_peeps/open_peeps_flat_assets.zip")

COMMON = dict(
    source="Open Peeps",
    source_url="https://openpeeps.com/",
    download_url="https://pablostanley.gumroad.com/l/openpeeps",
    license="CC0",
    commercial_use=True,
    attribution_required=False,
    share_alike=False,
    modification_allowed=True,
    author="Pablo Stanley",
    downloaded_at=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
    asset_type="character",
    style="hand-drawn ink, mix-and-match component library",
)

FILES = [
    ("openpeeps_pose_sitting_base", "a person/sitting.svg", ["pose", "head", "face", "body"]),
    ("openpeeps_face_calm", "face/Calm.svg", ["face"]),
    ("openpeeps_face_awe", "face/Awe.svg", ["face"]),
    ("openpeeps_face_concerned", "face/Concerned.svg", ["face"]),
    ("openpeeps_face_fear", "face/Fear.svg", ["face"]),
    ("openpeeps_face_serious", "face/Serious.svg", ["face"]),
    ("openpeeps_face_concerned_fear", "face/Concerned Fear.svg", ["face"]),
    ("openpeeps_face_hectic", "face/Hectic.svg", ["face"]),
    ("openpeeps_face_eyes_closed", "face/Eyes Closed.svg", ["face"]),
    ("openpeeps_head_flat_top", "head/Flat Top.svg", ["head"]),
    ("openpeeps_body_device", "body/Device.svg", ["body"]),
]

if __name__ == "__main__":
    registry.register(dict(
        COMMON,
        id="openpeeps_flat_assets_pack",
        sha256=registry.sha256_of(PACK_ZIP) if os.path.exists(PACK_ZIP) else None,
        asset_type="character",
        layers=["source pack"],
        riggable=True,
    ))
    for asset_id, rel_path, layers in FILES:
        full_path = os.path.join(ATOMS, rel_path)
        registry.register(dict(
            COMMON,
            id=asset_id,
            source_url="https://openpeeps.com/",
            sha256=registry.sha256_of(full_path) if os.path.exists(full_path) else None,
            layers=layers,
            riggable=True,
        ))
    for a in registry.all_registered():
        print(a["status"], a["id"])
    for a in registry.all_quarantined():
        print(a["status"], a["id"], a["status_reason"])
