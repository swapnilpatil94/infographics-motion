"""BLENDER stage facade: the Grease Pencil sprite bank is authored in real Blender GPv3 (engine/render/gp_bank_blender.py) and cached by content hash.
The native-rig proof (bone-parented GP layers + IK in stock Blender 5.2) is tools/verify_native_gp_rig.py."""
from engine.shorts.gp_bank import ensure_bank, Bank                # noqa: F401
