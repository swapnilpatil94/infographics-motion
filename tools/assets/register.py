#!/usr/bin/env python3
"""Register a normalized file in the canonical library (schema-validated, sha256-deduped). Usage: register.py <json record file>  (or import register())"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from engine.assets import library
from engine.licensing import policy


def register(rec, license_decision=None):
    dec = license_decision or policy.decide(rec["license"], "asset", True, rec.get("attribution_text"))
    rec = dict(rec, commercial_use=dec.get("commercial_use"), attribution_required=dec.get("attribution_required", False),
               share_alike=dec.get("share_alike", False), modification_allowed=dec.get("modification_allowed", True),
               status={"ACCEPT": "REGISTERED", "ACCEPT_WITH_OBLIGATIONS": "REGISTERED_WITH_OBLIGATIONS", "REJECT": "REJECTED"}.get(dec["decision"], "QUARANTINED"),
               status_reason=dec["reason"])
    lib, how = library.add(rec)
    library.save(lib)
    return rec["id"], how, rec["status"]


if __name__ == "__main__":
    for r in json.load(open(sys.argv[1])):
        print(register(r))
