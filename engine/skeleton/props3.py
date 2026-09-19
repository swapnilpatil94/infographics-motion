"""Interactive props expose SEMANTIC GRIP POINTS. A motion target is written `PROP.grip_name` (e.g. `PHONE.right_hand_grip`); the planner never sees a coordinate.

status:
  SOLVED  - the wrist position and wrist angle are solved from the hand drawing's grip anchor so the hand closes ON the prop (measured <= 3 px, tests + QC gate). Only the PHONE is solved in this milestone.
  DEFINED - the grip point exists in the table (position on the prop in prop-local px, hand pose to use) but the motion solver still uses the v2 heuristic offset; NOT verified for contact.
"""
GRIPS = {
    "PHONE": {"right_hand_grip": dict(pose="hold_phone", hand="R", local=(0.0, 0.0), status="SOLVED"), "left_hand_grip": dict(pose="hold_phone", hand="L", local=(0.0, 0.0), status="DEFINED (mirrored anchor)")},
    "CARD": {"right_hand_grip": dict(pose="hold_card", hand="R", local=(0.0, 0.0), status="DEFINED"), "left_hand_grip": dict(pose="hold_card", hand="L", local=(0.0, 0.0), status="DEFINED")},
    "MONEY": {"right_hand_grip": dict(pose="hold_money", hand="R", local=(0.0, 0.0), status="DEFINED"), "left_hand_grip": dict(pose="hold_money", hand="L", local=(0.0, 0.0), status="DEFINED")},
    "CUP": {"handle_grip": dict(pose="hold_cup", hand="R", local=(30.0, 0.0), status="DEFINED")},
    "LAPTOP": {"left_support": dict(pose="type", hand="L", local=(-60.0, 8.0), status="DEFINED"), "right_support": dict(pose="type", hand="R", local=(60.0, 8.0), status="DEFINED")},
    "DOOR": {"handle_grip": dict(pose="grab", hand="R", local=(0.0, 0.0), status="DEFINED")},
}


def parse(target):
    """'PHONE.right_hand_grip' -> ('PHONE', 'right_hand_grip', spec) ; unknown prop or grip -> KeyError (no silent fallback)"""
    prop, _, grip = str(target).partition(".")
    if prop not in GRIPS:
        raise KeyError(f"prop {prop!r} exposes no grip points")
    if grip and grip not in GRIPS[prop]:
        raise KeyError(f"prop {prop!r} has no grip {grip!r} (have {sorted(GRIPS[prop])})")
    return prop, grip or next(iter(GRIPS[prop])), GRIPS[prop][grip or next(iter(GRIPS[prop]))]


def solved(prop):
    return any(g["status"] == "SOLVED" for g in GRIPS.get(prop, {}).values())
