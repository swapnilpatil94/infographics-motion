"""Records provenance for a file that was fetched and verifies it's still
where the registry says it is. Deliberately NOT an automated web-fetcher:
every accepted source in discover.py either requires interactive checkout
(Open Peeps' Gumroad flow) or was hand-authored in this repo — there is no
bulk/automated download step to wrap for this asset pack, and pretending
otherwise would misrepresent how the assets were actually obtained.
"""
import hashlib
import os


def verify_local_file(path, expected_sha256=None):
    """Confirms a file exists at `path` and (optionally) matches a known
    hash — used to catch a raw asset silently going missing or changing
    between runs, since re-running the generator must be deterministic."""
    if not os.path.exists(path):
        return False, f"missing: {path}"
    if expected_sha256:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != expected_sha256:
            return False, f"hash mismatch for {path}: expected {expected_sha256[:12]}, got {actual[:12]}"
    return True, "ok"


def verify_registry(registry_entries, root):
    """Runs verify_local_file for every registered asset that has a local
    raw/normalized path recorded. Returns a list of problems (empty = clean)."""
    problems = []
    for entry in registry_entries:
        local_path = entry.get("local_path")
        if not local_path:
            continue
        ok, msg = verify_local_file(os.path.join(root, local_path), entry.get("sha256"))
        if not ok:
            problems.append({"id": entry["id"], "problem": msg})
    return problems
