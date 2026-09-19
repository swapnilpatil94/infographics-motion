"""Minimal, honest license gate. An asset is REGISTERED (usable) only if
every required license field is known and explicit; anything else is
QUARANTINED. No inference, no "probably fine."
"""
REQUIRED_FIELDS = [
    "source", "source_url", "license", "commercial_use",
    "attribution_required", "share_alike", "modification_allowed", "author",
]


def check(entry):
    missing = [f for f in REQUIRED_FIELDS if entry.get(f) is None]
    if missing:
        return "QUARANTINED", f"missing required license fields: {missing}"
    if entry["commercial_use"] is False:
        return "QUARANTINED", "commercial use not permitted"
    return "REGISTERED", "ok"
