"""Append-only asset registry. Each entry matches the schema from the
project brief. Source of truth is assets/licenses/registry.json.
"""
import json
import os
import hashlib
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, "assets", "licenses", "registry.json")


def _load():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"assets": []}


def _save(data):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(data, f, indent=2)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def register(entry):
    from asset_pipeline.license_checker import check
    status, reason = check(entry)
    entry = dict(entry)
    entry["status"] = status
    entry["status_reason"] = reason
    entry["registered_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
    data = _load()
    data["assets"] = [a for a in data["assets"] if a["id"] != entry["id"]]
    data["assets"].append(entry)
    _save(data)
    return entry


def get(asset_id):
    for a in _load()["assets"]:
        if a["id"] == asset_id:
            return a
    return None


def all_registered():
    return [a for a in _load()["assets"] if a["status"] == "REGISTERED"]


def all_quarantined():
    return [a for a in _load()["assets"] if a["status"] == "QUARANTINED"]
