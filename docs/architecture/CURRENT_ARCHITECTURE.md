# Current architecture (inspected before the Kathaya refactor)

| layer | where | what it is |
|---|---|---|
| entry points | `studio.py` (CLI), `engine/studio/server.py` (web UI + API) | many legacy flags (`--make`, `--factory`, `--skeleton-*`, `--production`); the UI wraps `--production` |
| story understanding | `engine/skeleton/story_semantics.py` (keyword/regex rules), `topic_story.py` (7 fixed scam packs), `acts.py` (32-act vocabulary + grammar) | **brittle**: a Hindi sentence becomes an *act*, a *place* and *emotion* by cue words; unsupported places are refused |
| scene direction | `scene_director.py`, `scene_acts.py`, `environments/locations.py` | acts -> shots + character actions on a fixed set of 12 stage layouts |
| characters | `characters/dna.py`, `skeleton/dna2.py`, `lab_dna.py` (15 archetypes) | parametric DNA -> Open Peeps art + 26-bone rig |
| rendering | `skeleton/short.py` (actor frames via `blender_job.py` + `engine/blender/skeleton_scene.py`, 2.5D compositor `engine/shorts/*`), `motion_v2.py`, `props4.py`, `parts_art2.py` | deterministic; content-addressed frame cache (`output/cache/actor_frames`) |
| audio | `audio_director.py` (synthesised ambience/music/foley, ducking, limiter), TTS via `engine/shorts/voice.py` -> Chatterbox Hindi + whisperx alignment | |
| QC | `qc_v4.py` (30-31 measured gates) + `critic.py` (measured framing, deterministic fixes) | |
| assets | `assets/registry/asset_registry.json` (licence policy), `assets/library/*`, `engine/licensing` | licence-audited third-party art only |
| UI | `engine/studio/web/*` (SPA), modes Create/Script/Production, director controls | user must pick modes, places, cast, camera options |
| cache | frame cache, audio mix cache, TTS cache | |

Problems relative to the target architecture: (1) meaning is extracted by keyword rules inside the renderer path; (2) environments are a closed list of 12 and a missing place is *refused* or force-fitted (`LOC.resolve` silently moves a bank to daytime); (3) camera is chosen by the renderer, not by intent; (4) no asset catalog / request / approval flow; (5) the UI exposes renderer internals.
