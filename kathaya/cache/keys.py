"""CACHE / DETERMINISM KEYS. A film is a pure function of (visual scene plan, narration timeline + audio, assets, renderer version). These hashes are recorded with every render; the pixel-level caches of the renderer
(content-addressed actor frames, the audio mix cache) then invalidate exactly the frames / audio a change touches."""
import hashlib
import json


def _h(o):
    return hashlib.sha1(json.dumps(o, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


def visual_hashes(plan):
    """hash of each visual's full content (a change to one visual changes only its hash)"""
    return {v["id"]: _h(v) for v in plan["visuals"]}


def asset_hashes(plan, catalog):
    idx = {a["id"]: a for a in catalog["assets"]}
    ids = {c.get("asset_id") for c in plan["cast"]} | {v["environment"].get("asset_id") for v in plan["visuals"]} | {p.get("asset_id") for v in plan["visuals"] for p in v.get("props", [])}
    return {i: _h(idx[i]) for i in sorted(x for x in ids if x and x in idx)}


def run_keys(plan, timeline, catalog, renderer_version):
    return dict(plan_hash=_h(plan), timeline_hash=_h([(s["id"], s["start"], s["end"], s["text"]) for s in timeline["narration"]]), audio=timeline.get("audio"), renderer_version=renderer_version, catalog_hash=catalog.get("catalog_hash"),
                visual_hashes=visual_hashes(plan), asset_hashes=asset_hashes(plan, catalog))


def changed_visuals(old_plan, new_plan):
    a, b = visual_hashes(old_plan), visual_hashes(new_plan)
    return sorted(k for k in b if a.get(k) != b[k]) + sorted(k for k in a if k not in b)
