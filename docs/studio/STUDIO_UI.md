# Kathaaya Studio — web UI + production API

The renderer is unchanged (deterministic plan → 26-bone rig in Blender → 2.5D composite → QC). The Studio is a thin layer on top:
the browser holds no business logic; every check, edit and progress number comes from the server, which calls the same functions the CLI uses
(`engine/skeleton/backend.py`, `production.py`, `story_semantics.py`, `qc_v4.py`).

## Start

```bash
python3 studio.py --ui                 # http://127.0.0.1:8765   (--port N to change)
```

## Make a movie (one screen)

1. **Create** (topic), **Script** (paste text / load `story.md` / `story.json`) or **Production** (your story + narration segments JSON + audio; or one of the three accepted examples).
2. Language · Format (9:16 / 16:9) · Duration (Auto / about 45–60 s) · Voice · Visual style → **Generate Movie**.
3. **Story review**: title, hook, protagonist, supporting characters, conflict, psychology, act structure, ending, estimated duration. **Edit Story** / **Regenerate** / **Approve & Generate**.
   **Script review**: every narration line with time and duration; click a line to edit, tick lines to **Regenerate selected** (local LLM, validated or refused).
4. **Production dashboard**: real stage progress over SSE (see below). **Cancel** stops Blender and ffmpeg immediately.
5. **Movie**: video, duration, resolution, shots, characters, environments, audio events, render time split (total / Blender / audio / compositing / QC), cache reuse, QC (passed / failed / auto-fixes), file paths, download.
6. **Movie inspector**: shot timeline → per-shot preview, characters, environment, actions, emotion, camera, audio events, QC state; safe edits (camera, emotion / act, character look) with the exact cache impact before rendering.

Levels: **Simple** (topic → generate) · **Director** (character, environment, style, typography, camera / pacing, voice, audio overrides — all default to Auto) · **Expert** (acts / places / times in the story editor, shot plan and `plan.json`).

## What the controls really do

| control | effect (nothing else is touched) |
|---|---|
| Format 16:9 | the 9:16 master, pillar-boxed on a blurred backdrop (1920×1080) as `final_16x9.mp4`; scenes are still staged for 9:16 |
| Duration | narration tempo window (target ± 2.5 s); the final summary shows requested vs actual |
| Character / partner / extras | archetype / gender of the cast in the story graph; **variation** re-seeds every character and set (0 = Auto) |
| Environment | *Preferred*: place used where the story names none; *Forced*: every scene is staged there (a bank is never night) |
| Pacing / camera | camera **moves** only (calm → gentler, intense → push-ins, locked-off); sizes, targets, cuts and acting are untouched |
| Captions off | no burned-in captions |
| Music / sfx / ambience | multipliers of the Audio Director's levels; speech ducking and the limiter stay on; an automatic QC gain fix wins over the slider |

All defaults leave the plan **byte-identical** to the CLI's (`tests/test_studio.py::test_production_mode_graph_is_the_cli_graph_and_plan_is_byte_identical`).

## Inputs and ChatGPT prompts (nav: *Inputs & prompts*)

Shows what to bring per mode (and that no art, sound or images are needed), the limits, the allowed values, and three copy-paste prompts:
**1** write the story + script (fill topic / protagonist / partner / places, copy) · **2** convert a script you already have · **3** timed transcript -> narration-segments JSON for Production mode.
The prompts are generated from the parser's real vocabulary (places, roles, person types) and contain the format, the machine-checked rules, the story order the parser recognises, and a worked example; a test fails if they drift from the parser.
*Check the reply* runs a pasted reply through the same checks as the film (code fences stripped, `UNSUPPORTED:` refusals shown, slips such as `location: bank [day]` or `amount: 50,000` repaired and reported, unknown values refused with the allowed list).

## Unsupported input

Refused with `422 {"error": {"code", "message", "reasons": [...], "hint"}}` — never a film: not Hindi, digits / Latin in the narration, fewer than 8 or more than 40 segments,
places without a stage (hospital, temple …), no money / scam cue, more than 3 supporting roles, topics outside the seven scam domains, invalid narration JSON, unknown acts / emotions / places.

## API

```
GET  /api/options
GET  /api/guide                     what to bring + the three copy-paste ChatGPT prompts (built from the live vocabulary)
POST /api/guide/check               {kind:"script"|"segments", text}   check a pasted chat reply exactly as the film would
POST /api/story                     {mode, topic|script_text|story_md|story_json|example|segments_json,audio_upload, language, format, duration, voice, style,
                                     character, environment, typography, director, variation}   → draft {id, review, script, graph, warnings}
                                    {draft_id, edits:{title, beats:{id:{act,emotion,loc,time}}, cast:{protagonist,partner,extras}}}   or   {draft_id, regenerate:true}
POST /api/script                    {draft_id, segments:[{id,text}]} | {draft_id, regenerate:[ids]} | {script_text} (new SCRIPT draft)
GET  /api/draft/{id}
POST /api/upload?kind=audio|text&name=x.wav      raw body
POST /api/generate                  {draft_id, approve:true}       → {production_id, status}      (one production runs at a time; the rest queue)
POST /api/cancel                    {production_id}
POST /api/preview                   {production_id, shot_id, source:"final"|"working"}
POST /api/render                    {production_id}                → renders the edited plan as a NEW production (only changed frames re-render)
GET  /api/productions
GET  /api/production/{id}           meta + summary
GET  /api/production/{id}/status    stages, overall %, active-stage detail (folded from the event log)
GET  /api/production/{id}/events    Server-Sent Events (?after=<seq> or Last-Event-ID to resume)
GET  /api/production/{id}/qc  /plan
POST /api/production/{id}/edit      {ops:[{op:"camera",shot,size,move,dx,dy} | {op:"beat",beat,emotion,act} | {op:"character",char,skin,palette,top} | {op:"director",…} | {op:"reset"}]}
GET  /api/production/{id}/video[?variant=16x9]  /download  /poster  /shot/{S01}.jpg  /file/{name}
```

The same routes also exist without the `/api` prefix.

## Production events

One JSON object per line in `output/studio/productions/<id>/events.jsonl` (the single source of truth; status is always folded from it, so it survives a server restart), streamed over SSE as
`{"event": {...}, "state": {...}}` (the state is the server-side fold; the browser only renders it).

```json
{"seq": 231, "ts": 1789905911.4, "event": "progress", "stage": "blender_render", "status": "running", "pass": 0, "overall": 0.412,
 "shot": 12, "total_shots": 19, "frame": 742, "total_frames": 1182, "rendered": 310, "to_render": 595, "cache_reused": 587,
 "fps": 2.8, "elapsed_seconds": 271, "eta_seconds": 167, "current_operation": "rendering rig frames (Blender)"}
```

* events: `started · progress · completed · failed · cancelled · skipped · queued · new_pass · qc_fix · log`; job-level events use `"stage": "job"`.
* stages: story_analysis · story_graph · script · narration · scene_direction · asset_preparation · blender_render · audio · compositing · qc · export.
* **Blender progress is the number of frame PNGs that appeared on disk** since the render started (not console text); fps and ETA come from their timestamps. Frames served by the frame cache are counted as `cache_reused`.
* **overall** = Σ weight × measured state of every stage (completed = 1, running = its own measured fraction, pending = 0); the weights are the typical cost of a stage (compositing 45 %, Blender 20 %, QC 10 % …) and are the only estimate in the number. Skipped stages (e.g. narration in Production mode) count as done and are labelled as skipped.
* The Chatterbox TTS reports no progress; the dashboard shows only its elapsed time.
* A QC failure that has an automatic fix starts a **new pass** (`new_pass`): only the render stages restart and only changed frames re-render.

## Cache behaviour (unchanged)

Camera → only that shot's frames · character → only shots where they are on the set · audio → the mix only (0 video frames). The inspector shows the exact numbers before you render:
`frames_to_render / frames_total`, `shots_affected`, `audio_remixed`. Compositing + encoding always re-runs over the whole film (≈ 0.23 s / frame).

## Files

`engine/studio/{core,jobs,worker,movie,server}.py`, `engine/studio/web/{index.html,style.css,app.js}`, `engine/skeleton/{events,director_opts}.py`,
tests `tests/test_studio.py`, real end-to-end driver `tools/studio/e2e.py` → `docs/studio/E2E_RESULTS.json`.

## Evidence and known limits

* Real end-to-end results (accepted stories through the UI path, script mode, create mode with real TTS, director options, real cancel, real failed render, edit + re-render with cache reuse): `docs/studio/RESULTS.md`, raw `docs/studio/E2E_RESULTS.json`. Screenshots: `docs/studio/screens/`.
* The UI path is the CLI path: accepted story A rendered through the UI is pixel-identical to the CLI film (2004/2004 sampled frames) and reused 1182/1182 cached frames.
* **Create mode** (topic → story) uses the seven deterministic scam-domain packs (no LLM). All seven were verified to analyse and plan; the "instant loan app" topic was rendered twice (two variations) for real and both films pass 30 of 31 QC gates: the engine's `ik_reachable` gate (the protagonist's hand is clamped for 109-115 frames, budget 95) has no automatic fix. The UI shows the failed gate; nothing is hidden or relaxed. Other packs were not rendered in this pass.
* A re-render of edited shots runs no critic pass: a bad camera edit is flagged before rendering (measured framing) and, if rendered anyway, QC fails the same gate (observed: 29/30, head clipped).
* 16:9 is a pillar-boxed export of the 9:16 master; only Hindi; one narrator voice; one visual style; captions have one style.
* Blender progress inside the *scene direction* stage (critic preview stills) and the TTS report only elapsed time.
