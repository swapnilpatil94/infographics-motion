"""CANONICAL SCHEMAS of the Kathaya pipeline (JSON Schema draft 2020-12). Structure is checked here; meaning (capabilities, assets, time coverage) is checked by `director.visual_planner` / `assets.resolver`.

    NarrationTimeline   the temporal spine: narration segments with start/end (from audio, timing JSON, TTS or an estimate)
    VisualScenePlan     what to show for every stretch of the narration (the creative director's output; the renderer's only input about the story)
    CapabilityManifest  what the renderer can physically do (generated from the renderer itself)
    AssetCatalog        every environment / character / prop / effect the renderer can use, with tags, source, licence, status
    AssetRequest        a MISSING / UNSUPPORTED requirement that needs a new asset (references -> human approval -> build)

    python3 -m kathaya.schemas --write      writes kathaya/schemas/*.schema.json
"""
import json
import os

import jsonschema

VERSION = 1
INTENTS = ["ESTABLISH_LOCATION", "INTRODUCE_CHARACTER", "SHOW_ACTION", "SHOW_OBJECT", "REVEAL_INFORMATION", "BUILD_TENSION", "FORESHADOW", "CONTRAST", "EMOTIONAL_REACTION", "EXPLAIN_PROCESS", "MONTAGE",
           "TIME_PASSAGE", "MEMORY", "REALIZATION", "CLIMAX", "CONSEQUENCE", "TRANSITION"]
STATUSES = ["AVAILABLE", "UNSUPPORTED", "MISSING", "SUBSTITUTED"]
ID_N, ID_V = r"^N\d{2,}$", r"^V\d{2,}$"
_num = {"type": "number", "minimum": 0}

NARRATION_TIMELINE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "NarrationTimeline", "type": "object", "required": ["schema", "source", "duration", "narration"],
    "properties": {
        "schema": {"const": f"kathaya.narration_timeline/{VERSION}"}, "language": {"type": "string"}, "format": {"enum": ["short", "long"]},
        "source": {"enum": ["timing_json", "audio_and_text", "tts", "estimated"], "description": "where the times come from"}, "audio": {"type": ["string", "null"]}, "duration": _num,
        "warnings": {"type": "array", "items": {"type": "string"}},
        "narration": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "start", "end", "text"], "additionalProperties": True, "properties": {
            "id": {"type": "string", "pattern": ID_N}, "start": _num, "end": _num, "text": {"type": "string", "minLength": 1}, "spoken": {"type": "string"},
            "words": {"type": "array", "items": {"type": "object", "required": ["word", "start", "end"], "properties": {"word": {"type": "string"}, "start": _num, "end": _num}}}}}}}}

_cast = {"type": "object", "required": ["id", "role"], "properties": {"id": {"type": "string"}, "role": {"enum": ["protagonist", "partner", "extra"]}, "archetype": {"type": ["string", "null"]},
                                                                          "gender": {"type": ["string", "null"]}, "name": {"type": "string"}, "description": {"type": "string"}, "asset_id": {"type": ["string", "null"]},
                                                                          "status": {"enum": STATUSES}}}
_env = {"type": "object", "required": ["type", "subject", "status"], "properties": {
    "type": {"enum": ["generic", "real_landmark"]}, "subject": {"type": "string", "minLength": 1}, "asset_id": {"type": ["string", "null"]}, "time_of_day": {"enum": ["day", "dusk", "night"]},
    "tags": {"type": "array", "items": {"type": "string"}}, "status": {"enum": STATUSES}, "reference_queries": {"type": "array", "items": {"type": "string"}}}}
VISUAL_SCENE_PLAN = {
    "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "VisualScenePlan", "type": "object", "required": ["schema", "format", "cast", "visuals"],
    "properties": {
        "schema": {"const": f"kathaya.visual_scene_plan/{VERSION}"}, "format": {"enum": ["short", "long"]}, "title": {"type": "string"}, "corrections": {"type": "array"}, "cast": {"type": "array", "items": _cast},
        "visuals": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "narration_id", "start", "end", "visual_intent", "environment", "camera"], "properties": {
            "id": {"type": "string", "pattern": ID_V}, "narration_id": {"type": "string", "pattern": ID_N}, "start": _num, "end": _num, "visual_intent": {"enum": INTENTS}, "environment": _env,
            "characters": {"type": "array", "items": {"type": "string"}}, "props": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "asset_id": {"type": ["string", "null"]},
                                                                                                                                                       "status": {"enum": STATUSES}}}},
            "action": {"type": ["object", "null"], "properties": {"capability": {"type": "string"}, "actor": {"type": ["string", "null"]}, "params": {"type": "object"}}},
            "emotion": {"type": "string"}, "camera": {"type": "object", "required": ["shot", "movement"], "properties": {"shot": {"type": "string"}, "movement": {"type": "string"}, "subject": {"type": ["string", "null"]}}},
            "effects": {"type": "array", "items": {"type": "string"}}, "transition": {"type": "string"}, "screen": {"type": ["object", "null"], "properties": {"sender": {"type": "string"}, "text": {"type": "string"}}},
            "narration_text": {"type": "string"}, "rationale": {"type": "string"}}}}}}

CAPABILITY_MANIFEST = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "CapabilityManifest", "type": "object", "required": ["schema", "renderer_version", "characters", "camera", "effects", "props", "environments", "transitions", "limits"],
                       "properties": {"schema": {"const": f"kathaya.capability_manifest/{VERSION}"}}}
ASSET = {"type": "object", "required": ["id", "type", "tags", "source", "license", "status"], "properties": {
    "id": {"type": "string"}, "type": {"enum": ["environment", "character", "prop", "effect"]}, "tags": {"type": "array", "items": {"type": "string"}}, "subjects": {"type": "array", "items": {"type": "string"}},
    "source": {"type": "string"}, "license": {"type": "string"}, "local_path": {"type": ["string", "null"]}, "status": {"enum": ["production_ready", "draft", "debug_placeholder"]},
    "supports": {"type": "object"}, "anchors": {"type": "object"}, "capabilities": {"type": "array", "items": {"type": "string"}}, "binding": {"type": "object"}}}
ASSET_CATALOG = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "AssetCatalog", "type": "object", "required": ["schema", "assets"], "properties": {"schema": {"const": f"kathaya.asset_catalog/{VERSION}"}, "assets": {"type": "array", "items": ASSET}}}
ASSET_REQUEST = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "AssetRequest", "type": "object", "required": ["schema", "id", "type", "subject", "status", "reason", "reference_queries", "human_approval_required"],
                 "properties": {"schema": {"const": f"kathaya.asset_request/{VERSION}"}, "id": {"type": "string"}, "type": {"enum": ["environment", "character", "prop", "effect"]}, "asset_kind": {"enum": ["generic", "real_landmark"]},
                                "subject": {"type": "string"}, "status": {"enum": ["MISSING", "UNSUPPORTED"]}, "reason": {"type": "string"}, "required_by": {"type": "array", "items": {"type": "string"}},
                                "required_conditions": {"type": "object"}, "reference_queries": {"type": "array", "minItems": 1, "items": {"type": "string"}}, "reference_count": {"type": "integer", "minimum": 1},
                                "human_approval_required": {"const": True}, "state": {"enum": ["open", "references_found", "approved", "building", "ready", "rejected"]}}}

SCHEMAS = {"NarrationTimeline": NARRATION_TIMELINE, "VisualScenePlan": VISUAL_SCENE_PLAN, "CapabilityManifest": CAPABILITY_MANIFEST, "AssetCatalog": ASSET_CATALOG, "AssetRequest": ASSET_REQUEST}


def validate(name, obj):
    """-> list of structured errors [{path, message}] (empty = valid)"""
    v = jsonschema.Draft202012Validator(SCHEMAS[name])
    return [dict(path="/" + "/".join(str(p) for p in e.absolute_path), message=e.message[:240]) for e in sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path))]


def write():
    d = os.path.dirname(os.path.abspath(__file__))
    for k, s in SCHEMAS.items():
        json.dump(s, open(os.path.join(d, f"{k}.schema.json"), "w"), indent=1)
    return sorted(SCHEMAS)


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        print("wrote", write())
