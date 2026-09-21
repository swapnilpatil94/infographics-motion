"""The CREATIVE DIRECTOR PROMPT. The same text goes to a local LLM (structured output) or is copied into ChatGPT by the user; the reply is the same JSON either way and is validated the same way."""
import json

from kathaya import schemas

RULES = """You are the creative director of Kathaya, a deterministic 2D/2.5D story renderer. You design the FILM for a narration: what is shown, when, from which camera, with which characters, props and actions.
The renderer only executes your plan; it does not interpret the story. The narration is the source of truth and its timeline is fixed: you decide WHAT to show for each narration segment, never the times.

HARD RULES
1. Show what is being narrated, when it is narrated. Every narration segment N.. gets 1 to 3 visuals (use more than one only when the sentence has a clear second moment: an action then a reaction). Never invent visuals that do not serve the narration.
2. The story requirement always wins. Choose an environment `asset_id` from the catalog ONLY if it truly is the place of the story. If the story needs a place / landmark / prop / character that the catalog does not have, set `asset_id` to null and describe the real subject precisely in `subject` (a specific real place is `type: "real_landmark"` with its full name, e.g. "Bombay Stock Exchange Mumbai"). Do NOT substitute the nearest existing asset. Also give 2-3 `reference_queries` for a missing environment.
3. Time of day is part of the requirement: set `environment.time_of_day` (day, dusk or night) from the story. If the catalog asset does not support it, still write what the story needs (the system will ask for a new asset).
4. Characters: `cast` lists every person that appears: exactly one protagonist, at most one partner and at most two extras. Pick `archetype` from `archetypes`; `asset_id` is `char_<archetype with underscores>` or null. If nobody in the catalog fits, set asset_id null and describe the person in `description`.
5. Every visual has one `action.capability` chosen from `actions` (these are what the renderer can physically perform). If NONE of them can show what the story needs, use capability "OTHER" and describe the required action in `action.requested`. Never replace a needed action by a different one.
6. The renderer keeps state between actions (`needs` / `sets`). Respect it: the first visual's action is ESTABLISH or ARRIVE, the last is RESOLVE, actions marked `once` are used at most once, and an action may only follow the actions that set what it needs (e.g. a phone must be picked up before it can be read or handed over).
7. Camera: choose `camera.shot` from `shots` and `camera.movement` from `movements` for the dramatic purpose (tension = slow push, reaction = close, reveal = reveal/truck, establishing = wide). `camera.subject` must form a valid pair with the shot (see `valid_framings`), or null to let the system frame the shot. If you need a camera move that is not in `movements` (for example tilt or orbit), use "OTHER" and describe it in `camera.requested`.
8. A phone message or sign that is shown full-screen uses action INSERT_SCREEN and `screen: {"sender": "...", "text": "<the exact words from the narration>"}` (sender is a generic fictional id, never a real company). Money moving uses action VISUALIZE_FLOW with `action.params: {"amount": <integer rupees>, "from_label": "<Hindi>", "to": ["...", "..."]}`.
9. `emotion` is one of `emotions`. `visual_intent` is one of the listed intents. `effects` are ids from `effects` or empty. `transition` is one of `transitions` (cut unless a time jump or a new place needs fade/dip).
10. Output ONLY the JSON object required by the output schema. No commentary."""


def output_schema(manifest_c, catalog_c):
    acts = [a["id"] for a in manifest_c["actions"]] + ["OTHER"]
    return {"type": "object", "required": ["title", "cast", "visuals"], "properties": {
        "title": {"type": "string"},
        "cast": {"type": "array", "items": {"type": "object", "required": ["id", "role", "archetype", "gender"], "properties": {"id": {"type": "string"}, "role": {"enum": ["protagonist", "partner", "extra"]}, "archetype": {"type": "string"},
                                                                                                                                  "gender": {"enum": ["male", "female", "either"]}, "name": {"type": "string"}, "description": {"type": "string"}, "asset_id": {"type": ["string", "null"]}}}},
        "visuals": {"type": "array", "items": {"type": "object", "required": ["narration_id", "visual_intent", "environment", "characters", "action", "emotion", "camera"], "properties": {
            "narration_id": {"type": "string"}, "share": {"type": "number"}, "at_word": {"type": ["integer", "null"]}, "visual_intent": {"enum": schemas.INTENTS},
            "environment": {"type": "object", "required": ["type", "subject", "time_of_day"], "properties": {"type": {"enum": ["generic", "real_landmark"]}, "subject": {"type": "string"}, "asset_id": {"type": ["string", "null"]},
                                                                                                             "time_of_day": {"enum": ["day", "dusk", "night"]}, "reference_queries": {"type": "array", "items": {"type": "string"}}}},
            "characters": {"type": "array", "items": {"type": "string"}}, "props": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}},
            "action": {"type": "object", "required": ["capability"], "properties": {"capability": {"enum": acts}, "actor": {"type": ["string", "null"]}, "requested": {"type": "string"}, "params": {"type": "object"}}},
            "emotion": {"enum": manifest_c["emotions"]},
            "camera": {"type": "object", "required": ["shot", "movement"], "properties": {"shot": {"enum": manifest_c["shots"] + ["OTHER"]}, "movement": {"enum": sorted(manifest_c["movements"]) + ["OTHER"]}, "subject": {"type": ["string", "null"]},
                                                                                        "requested": {"type": "string"}}},
            "effects": {"type": "array", "items": {"type": "string"}}, "transition": {"type": "string"}, "screen": {"type": ["object", "null"], "properties": {"sender": {"type": "string"}, "text": {"type": "string"}}},
            "rationale": {"type": "string"}}}}}}


DIRECTION_NOTE = ("USER'S SCENE DIRECTION (written by the person who owns the film). Follow it wherever it names a place, a time of day, a character, an action, an emotion or a camera, and keep its order. "
                  "Where it is silent, decide yourself. Places / times must still come from the catalog (a place it does not have is reported, never approximated). Never invent facts the narration does not say.")


def direction_block(direction):
    return f"\n\n{DIRECTION_NOTE}\n<<<\n{direction.strip()}\n>>>" if (direction or "").strip() else ""


def build(timeline, manifest_c, catalog_c, fmt="short", repair=None, direction=""):
    nar = [dict(id=s["id"], start=s["start"], end=s["end"], text=s["text"]) for s in timeline["narration"]]
    body = dict(format=fmt, narration_timeline=nar, actions=manifest_c["actions"], emotions=manifest_c["emotions"], shots=manifest_c["shots"], movements=manifest_c["movements"], camera_subjects=manifest_c["camera_subjects"],
                valid_framings=manifest_c["valid_framings"], unsupported_camera_moves=manifest_c["unsupported_camera"], effects=manifest_c["effects"], transitions=manifest_c["transitions"], intents=schemas.INTENTS,
                catalog=dict(environments=catalog_c["environments"], archetypes=manifest_c["archetypes"], characters=catalog_c["characters"], props=catalog_c["props"]))
    fmt_note = ("SHORTS (9:16): a hook in the first seconds, quick reactions, a clear climax and a closing beat." if fmt == "short" else "LONG-FORM: the same rules; more room for establishing shots, montage and slower pacing.")
    text = RULES + direction_block(direction) + f"\n\nFORMAT: {fmt_note}\n\nINPUT (JSON)\n" + json.dumps(body, ensure_ascii=False) + "\n\nOUTPUT: one JSON object: {\"title\": str, \"cast\": [...], \"visuals\": [...]} as specified. `visuals` are in narration order; several visuals of one narration segment share its `narration_id` (split its time with `share`, e.g. 0.6 / 0.4)."
    if repair:
        text += "\n\nYOUR PREVIOUS ANSWER WAS REJECTED FOR THESE REASONS (fix exactly these, keep everything else):\n" + "\n".join("- " + r for r in repair[:14])
    return text
