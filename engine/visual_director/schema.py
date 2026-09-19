"""Validates a shot-list DSL before anything touches Blender. Invalid plans
fail early with a readable error; the compiler never sees them.

Deliberately small and dependency-free (no jsonschema): the DSL is tiny,
and a hand-written check gives precise messages, including cross-field
rules (an action/emotion must exist in the character's rig_spec) that a
generic JSON-schema wouldn't express anyway.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHOT_TYPES = {"wide_3q", "medium_push", "medium_close", "closeup"}
ACTIONS = {"idle", "look_at_phone"}
PHONE_STATES = {"off", "ignite", "on"}


class DSLError(ValueError):
    pass


def _require(cond, msg):
    if not cond:
        raise DSLError(msg)


def validate(dsl):
    for key in ("version", "characters", "shots"):
        _require(key in dsl, f"missing top-level key '{key}'")

    emotions_by_char = {}
    for cid, cfg in dsl["characters"].items():
        spec_path = os.path.join(ROOT, cfg.get("rig_spec", ""))
        _require(os.path.exists(spec_path), f"character '{cid}': rig_spec not found: {cfg.get('rig_spec')}")
        with open(spec_path) as f:
            spec = json.load(f)
        emotions_by_char[cid] = set(spec["parts"]["face"]["variants"])

    _require(dsl["shots"], "shots list is empty")
    prev_end = None
    ignite_seen = 0
    for shot in dsl["shots"]:
        sid = shot.get("shot_id", "?")
        for key in ("start_s", "end_s", "characters", "camera"):
            _require(key in shot, f"shot {sid}: missing '{key}'")
        _require(shot["end_s"] > shot["start_s"], f"shot {sid}: end_s must be > start_s")
        if prev_end is not None:
            _require(abs(shot["start_s"] - prev_end) < 1e-6, f"shot {sid}: starts at {shot['start_s']} but previous shot ended at {prev_end} (gap/overlap)")
        prev_end = shot["end_s"]
        _require(shot["camera"].get("shot_type") in SHOT_TYPES, f"shot {sid}: unknown shot_type '{shot['camera'].get('shot_type')}' (allowed: {sorted(SHOT_TYPES)})")
        for c in shot["characters"]:
            _require(c.get("id") in emotions_by_char, f"shot {sid}: unknown character '{c.get('id')}'")
            _require(c.get("emotion") in emotions_by_char[c["id"]], f"shot {sid}: character '{c['id']}' has no emotion/face variant '{c.get('emotion')}' (has: {sorted(emotions_by_char[c['id']])})")
            _require(c.get("action") in ACTIONS, f"shot {sid}: unknown action '{c.get('action')}' (allowed: {sorted(ACTIONS)})")
        state = shot.get("phone_screen", "off")
        _require(state in PHONE_STATES, f"shot {sid}: unknown phone_screen '{state}'")
        ignite_seen += state == "ignite"
    _require(ignite_seen <= 1, "more than one shot has phone_screen='ignite'")
    return dsl
