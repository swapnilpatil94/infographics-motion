# Production factory — story + narration JSON → finished cinematic Short

Architecture is unchanged: **deterministic plan → 26-bone rig (4 IK chains) in Blender → 2.5D composite → QC**. Open Peeps stays the 2D art foundation; MPFB2 / Rigify stay supporting references (no new asset packs were downloaded; every asset used is still `ACCEPT` in `assets/registry`).

## Generate a new movie

**From a browser (no JSON, no commands):** `python3 studio.py --ui` → http://127.0.0.1:8765 — see `docs/studio/STUDIO_UI.md`. The UI drives exactly the pipeline below.

```bash
# 1. write the story notes (optional, 6 lines) and the narration segments JSON (Chatterbox, or any voice with start/end per segment)
#    stories/<name>/story.md          # title + `protagonist: कमला जी, female, older woman` / `other: अजनबी, stranger` / `sender:` / `amount:` notes
#    stories/<name>/segments.json     # {"segments":[{"id","text","start","end","words"?}], "audio":"path/to/paced.wav", "tts":"chatterbox"}
# 2. one command
python3 studio.py --production stories/<name>/story.md --narration-json stories/<name>/segments.json --out-dir output/production/<name>
# deterministic re-render of the saved plan (no parser, no LLM, frame-cached)
python3 studio.py --from-plan output/production/<name>/plan.json
```

Voice from script lines only (Chatterbox Hindi, content-hash cached): `engine.skeleton.narration_io.synthesize(beats, out_dir)` → writes `segments.json` + `paced.wav`.

## What the pipeline does (all deterministic; `engine/skeleton/`)

| stage | module | notes |
|---|---|---|
| story → graph | `story_semantics.py` | closed vocabulary (32 acts, 12 locations, 5 props, 15 roles, 8 emotions), Hindi cue rules, nukta-normalised, locative-aware (a place word only counts as a *place* with a locative), quoted message text never changes time of day. Unsupported stories raise `StoryNotSupported` with the reason. |
| graph → plan v4 | `scene_director.py`, `scene_acts.py` | scenes (location + time), per-scene layout & target registry, cast blocking with teleport at cuts, per-act camera options (deterministic rotation, never the same framing twice in a row, long beats covered by two shots), lighting presets per time of day, audio mood, SFX hooks, insert / procedural shots |
| environments | `environments/locations.py`, `stages.py` | bedroom, study, living room, office, classroom, cafe, bank counter, shop, police, ATM, call centre, street; day / dusk / night are only allowed where possible (a bank is never open at night); sky, lights and set are drawn for the same time |
| acting | `motion_v2.py`, `motion_polish.py` | idle/breath/weight shift, blink, gaze (target-driven: phone, person, object, screen, money, camera, location), fear / confusion / suspicion / realisation sequences, hesitation, talk / listen, reach → contact → grab → hold → use → release, hand-over / receive, walk, run, sit, stand, teleport at cuts; follow-through (hair spring, neck lag, breathing) |
| props | `props4.py`, `parts_art2.py` | phone, card, money, document, cup, laptop, bag, ATM keypad; real artwork, grip-anchored, `prop_cycle` |
| critic | `critic.py` | measured framing (heads, feet, phone, caption band, set edges, face size) at 3 moments per shot, pixel checks on preview stills, deterministic fixes keyed by shot; falls back to another shot size when no camera position fits |
| audio | `audio_director.py` | per-scene ambience, per-mood music, foley from the actions, ducking, `-16 LUFS` + limiter, content-hash cached |
| QC | `qc_v4.py` | 30–31 measured gates per film (plan validity, licence policy, environment/time-of-day, lighting-vs-time, clipped heads / cropped bodies, face vs caption band and caption pixels, ghost actors, cast distinctness, hand-object contact, IK reach, prop flicker, hand-over pairs, snapping, gaze, rhythm, framing variety, duplicates, dead frames, end screen, slideshow, audio clipping / intelligibility / duration / dead air, narration alignment, decode + frame count, missing frames) + `autofix` → re-plan → re-render (frame cache) → re-QC |
| cache | `short._frame_keys` | per-frame content address (actor DNA + channels of every *visible* actor + camera + quality) |
| backend | `backend.py` | UI-ready interfaces (below) |

## Backend interfaces (for a future web UI; CLI stays fully functional)

`story_analyze` / `story_edit` · `narration_validate` / `narration_synthesize` · `characters` / `character_catalog` / `character_override` · `assets` · `environments` · `voices` · `styles` · `generate` · `preview_shot` · `edit_shot` · `render_final` · `qc_report` (module `engine/skeleton/backend.py`; all take/return plain JSON-able data).

## Limits that matter

* Views: characters are drawn **3/4** (the Open Peeps style). A shot never needs a back or true-profile turn: turning is staged as a cut (partners face the protagonist by stage geometry) and as head/eye gaze. There is no rigged back view.
* Vocabulary is closed: up to 1 protagonist + 1 principal + 2 extra roles, 8–40 narration segments, the 12 locations above. Anything else fails with a reason, it is never silently approximated.
* Sign / screen text is drawn from the narration text (Devanagari font); it is not OCR-verified.

## Evidence (see `ACCEPTANCE.md`, `ACCEPTANCE.json`, `evidence/`)

* `python3 studio.py --production-acceptance` → ACCEPTED: 3 stories 30/30, 31/31, 31/31 QC gates; `--from-plan` re-render of story A is **byte-identical** (video + audio); camera change of one shot re-keys 90 of 1182 frames (all inside that shot); changing the partner's skin re-keys only the 594 frames where he is on the set; an audio-config change re-keys 0 video frames and re-hashes the mix; original hand-authored film (`--skeleton-short-v3`) still 52/52; 189 unit tests pass; 16-scenario runtime matrix: 16 distinct protagonists, 14 partners, 12 locations, day/dusk/night, 142 distinct (act, place, time, emotion) situations, 42 prop contacts all reachable and ≤ 6 px, 0 unreachable IK targets, 0 snaps, 0 ghost actors, 0 unfixable framing failures.
* Cost: a cold film takes ≈ 8–10 min on this Mac (Blender frames ≈ 1.5–3 min, composite ≈ 0.23 s/frame); the frame cache (`output/cache/actor_frames`, ≈ 0.7 MB/frame, safe to delete) makes re-renders after a small edit cost only the changed frames + the composite.

## Honest limitations
* Day-lit characters with very light skin and grey/blond hair (story B protagonist, story C protagonist) read with low face/background contrast; the critic only fixes faces that are too *dark*.
* `no_snapping` is enforced by a rate limiter on rotation channels (22°/frame; the gate fails above 32°): a very fast wrist flick is spread over a few frames rather than popping.
* `RUN_AWAY` uses the Creomoto run cycle with the phone arm raised; it is exercised in the matrix but not in the three acceptance films.
* The audio is fully synthesized (no recorded room tone / foley): it is clean and deterministic, but simple.
* The VLM critic (qwen) stays optional and advisory (`use_vlm`); acceptance ran the measured critic only.
