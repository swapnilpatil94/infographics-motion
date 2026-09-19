"""Canonical asset library: schema-validated records, queryable, de-duplicated by sha256, with the resolution order of spec sec. 49.

    existing canonical asset -> existing variation -> procedural generation -> approved external asset -> new generated asset
"""
import hashlib
import json
import os

from engine.shorts.raster import ROOT

INDEX = os.path.join(ROOT, "assets/library/index.json")
SCHEMA = os.path.join(ROOT, "assets/schema/asset.schema.json")
LICENSES_VIEW = os.path.join(ROOT, "assets/licenses.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def validate(rec, schema=None):
    """Small JSON-schema subset validator (required, enum, type, pattern) - no third-party dependency."""
    import re
    schema = schema or json.load(open(SCHEMA))
    errs = []
    for k in schema["required"]:
        if k not in rec:
            errs.append(f"missing '{k}'")
    for k, spec in schema["properties"].items():
        if k not in rec:
            continue
        v = rec[k]
        if "enum" in spec and v not in spec["enum"]:
            errs.append(f"{k}={v!r} not in enum")
        if "pattern" in spec and not re.match(spec["pattern"], str(v)):
            errs.append(f"{k}={v!r} does not match {spec['pattern']}")
        t = spec.get("type")
        if t:
            ts = t if isinstance(t, list) else [t]
            ok = any({"string": isinstance(v, str), "boolean": isinstance(v, bool), "array": isinstance(v, list), "null": v is None}.get(x, True) for x in ts)
            if not ok:
                errs.append(f"{k} has wrong type")
    return errs


def load():
    return json.load(open(INDEX)) if os.path.exists(INDEX) else dict(version=1, assets=[])


def save(lib):
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    lib["assets"].sort(key=lambda a: a["id"])
    json.dump(lib, open(INDEX, "w"), indent=1, ensure_ascii=False)
    json.dump([license_view(a) for a in lib["assets"] if a["status"] != "REJECTED"], open(LICENSES_VIEW, "w"), indent=1, ensure_ascii=False)


def license_view(a):
    """assets/licenses.json row in the spec's sec. 35 shape."""
    return dict(asset_id=a["id"], source=a["source"], source_url=a.get("source_url", ""), author=a.get("author", ""), license=a["license"],
                commercial_use=a.get("commercial_use"), attribution_required=a.get("attribution_required", False), share_alike=a.get("share_alike", False),
                modification_allowed=a.get("modification_allowed", True), proof_url=a.get("proof_url", a.get("source_url", "")), sha256=a["sha256"],
                status=a["status"])


def add(rec, lib=None, replace=True):
    """Insert a record; refuses invalid records and de-duplicates by sha256 (same content under another id is reported, not duplicated)."""
    lib = lib or load()
    errs = validate(rec)
    if errs:
        raise ValueError(f"invalid asset record {rec.get('id')}: {errs}")
    for a in lib["assets"]:
        if a["sha256"] == rec["sha256"] and a["id"] != rec["id"] and rec.get("path"):
            return lib, f"duplicate of {a['id']}"
    lib["assets"] = [a for a in lib["assets"] if a["id"] != rec["id"]] + [rec]
    return lib, "added"


def find(type=None, tags=(), lib=None, usable_only=True):
    lib = lib or load()
    out = []
    for a in lib["assets"]:
        if type and a["type"] != type:
            continue
        if usable_only and a["status"] not in ("REGISTERED", "REGISTERED_WITH_OBLIGATIONS"):
            continue
        if all(t in a["tags"] for t in tags):
            out.append(a)
    return out


def resolve(need_type, tags=(), lib=None):
    """Resolution order (spec 49). Returns (asset|None, how). Procedural/external stages report how they would be satisfied."""
    lib = lib or load()
    hits = find(need_type, tags, lib)
    if hits:
        return hits[0], "existing canonical asset"
    hits = find(need_type, tags[:1], lib) if tags else []
    if hits:
        return hits[0], "existing variation (partial tag match)"
    proc = [a for a in find("procedural", (need_type,), lib)]
    if proc:
        return proc[0], "procedural generation"
    return None, "approved external asset or newly generated asset required"
