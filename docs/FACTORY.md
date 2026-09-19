# The factory: story -> cinematic film, no operator

```
python3 studio.py --story stories/<name>.md --narration narration/<name>.wav.segments.json     # full pipeline
python3 studio.py --project-plan output/projects/<name>/project/shot_plan.json                  # deterministic re-render, no LLM
python3 studio.py --story ... --narration ... --plan-only                                       # stop after planning
python3 studio.py --project-plan ... --stills 12.5,40                                           # a few frames
python3 studio.py --project-plan ... --window 60,105                                            # one Short-length window
```

## Input contract
* `story.md` - markdown, `# title` optional, paragraphs = blank-line separated. Source of truth (Hindi or English).
* `<name>.wav.segments.json` (+ `<name>.wav` beside it) - `{"segments":[{"beat_id","text","start_seconds","end_seconds","words"?,"speaker"?,"emphasis"?,"pause"?}]}`
  or a plain list of `{text,start,end}`. Word timings are optional.
* optional: `project.json`, `style_override.json`, `topic_override.json`.

## Output contract (`output/projects/<name>/`)
`final/master.mp4`, `final/shorts/` - `project/` (story, story_analysis, characters, locations, props, psychology, visual_treatment, shot_plan, animation_plan,
camera_plan, lighting_plan, gp_plan, asset_requirements, vertical_plan) - `assets/` (manifest, licenses, retimed narration) - `render/` - `qc/` (qc.json, timing_report,
contact_sheet.png, shot_timeline.png, warnings.json) - `logs/` (timing_log.json).

## Pipeline
1. **contract** (`engine/factory/contract.py`): parse story + narration; align every segment to its paragraph.
2. **analysis** (`analysis.py`): READER (gemma4, Hindi) tags each segment (speaker, emotion, action verb, location, characters, phone UI, amounts, psychology, advice, importance);
   SYNTHESIS (qwen3, JSON-schema) gives characters, monotone narrative phases (HOOK..PAYOFF), central question and a story-specific visual treatment.
   **LLM tags are hypotheses**: each is corroborated by textual cues from the domain pack (`domain.json -> cues`) or dropped; cues can override a wrong tag.
   Story-quality warnings (weak hook / escalation / payoff ...) are produced before rendering.
3. **director** (`director.py`): deterministic Visual Director -> validated shot plan. Per shot: treatment (performance | insert_ui | procedural), purpose, camera, lighting mood,
   Grease Pencil effects with timing, transitions, sound cues, story state before/after. Anti-repetition pass; designed pauses.
4. **state / continuity** (`state.py`): money, pressure, phone-in-hand, knowledge; the numbers on screen come only from this state.
5. **asset check** (`assets.py`): library -> procedural -> approved source plan -> MISSING report (shots + solutions). Missing assets stop the render unless `--allow-fallbacks`.
6. **render** (`render.py`): layered rigs (`engine/shorts/rig2.py`) + verbs (`verbs.py`), 2.5D sets, mood lighting, Blender Grease Pencil bank, procedural graphics, phone UI screens.
7. **audio** (`audio_pipeline.py`): narration retimed with designed pauses, synthesized underscore, sound design, sidechain-free ducked mix, loudnorm -16 LUFS.
8. **QC** (`qc.py`): 20 checks + contact sheet + timeline + timing log. A film that fails a check says which and where.

## Domain packs (`domains/<id>/domain.json`)
Vocabularies (emotions, verbs, environments -> sets, props availability, outfits), psychology registry -> visual grammars, cue lists, procedural/UI/GP inventories.
Add a domain by adding a folder + JSON; the engine reads nothing domain-specific from code. See `docs/ADDING_TOPIC_PACKS.md`.

## What is reusable vs. what needs art
Reusable now: rig + verbs, sets (3), procedural graphics (11), UI screens (7), GP effects (6), director rules, QC. Needs new art per new topic:
locations (bank branch, police station, call centre, ATM ...), on-screen characters beyond the 3 cast heads, non-phone props.

---

# v2 — the component factories (plan `version: 2`)

The v1 director chose *treatments*; v2 additionally composes every performance shot from seeded, validated components. All of it is
plain JSON in `shot_plan.json` (the DSL) — `engine/dsl/schema.py::validate_plan` runs before any frame is rendered, and the LLM never emits code.

| Stage | Module | What it does |
|---|---|---|
| Character DNA | `engine/characters/dna.py` | archetype × seed → skin, hair, eyes, brows, body, outfit (pattern/collar/badge), accessories. `plan["characters"][id]["dna"]`; rig built by `LayeredRig(dna=…)` |
| Environments | `engine/environments/{families,factory}.py` | 7 families (office, street, bedroom, bank, call centre, living room, ATM) + hue/palette variation → `EF.resolve(env)` returns a registered set id |
| Props | `engine/props/factory.py` | 23 ink props, recolourable, screen variation, named slots per set |
| Crowd | `engine/crowd/factory.py` | seeded DNA people baked to sprites, depth/parallax/sway, per-set insertion slot, absent for `isolated` beats |
| Motion grammar | `engine/animation/grammar.py` | semantic action (`talk, listen, type, walk, point, reach_for_phone, hesitate, …`) × emotion style × intensity → rig channels |
| Camera grammar | `engine/camera/grammar.py` | story intent (`fear, realization, investigation, scale, urgency, authority, isolation, intimacy, reveal`) → size/move/keyframes/shake/focal gain |
| Grease Pencil FX | `engine/shorts/gp_strokes.py`, `engine/render/gp_bank_blender.py` | 14 hand-drawn effects authored in real Blender GPv3; the director picks them by *meaning* (`director._semantic_fx`) and records the `relationship` |
| Variation | `engine/dsl/variation.py` | every random choice is `f(story_id, shot_id, salt)`; `style.seed` adds a controlled salt |
| Licensing | `engine/licensing/policy.py`, `assets/licenses.json` | unknown → quarantine, NC/ND → reject, GPL code never enters the core |
| Asset library | `engine/assets/library.py`, `assets/library/index.json` | schema-validated, sha256-deduped records; resolution order existing → variation → procedural → approved external → generated |
| Asset acquisition | `tools/assets/{discover,download,verify_license,normalize,register}.py` | live GitHub licence lookup → download → normalise → register (see `assets/sources.json`, `assets/library/source_decisions.json`) |

## API (what a UI calls) — `engine/api.py`

```json
{"story": "stories/x.md", "narration_segments": "narration/x.wav.segments.json",
 "style": {"domain": "money_psychology", "seed": "v2", "name": "my_film"}, "aspect_ratio": "9:16"}
```
```bash
python3 studio.py --api-request request.json
```
`api.generate(req)` returns `{status, project_dir, master, derivatives, plan, qc}` (or `rejected`/`failed` with `errors`). `api.rerender(plan)` is the no-LLM re-render.

## Adding things
* **Character archetype**: add to `ARCHETYPES` in `engine/characters/dna.py`, then map story roles to it in `domain.json → character_archetypes`.
* **Environment family**: add a generator to `engine/environments/families.py::FAMILIES` (+ an entry in `factory.LIGHTS`, a slot list in `engine/props/factory.py::SLOTS`, a crowd `after` layer in `director.CROWD_AFTER`).
* **Prop**: add a function to `engine/props/factory.py` and list it in `PROPS`; add narration cue words in `domain.json → cues.props`.
* **GP effect**: add a generator + `SPRITES` entry in `gp_strokes.py` (the bank rebuilds automatically, cached by content hash), a trigger in `director._semantic_fx`, a drawer in `render._draw_semantic`.
* **Domain pack**: copy `domains/money_psychology/` and change vocab / environments / psychology grammars / cues.

## Known limits (honest)
* The frame renderer is a 2D layer compositor (numpy/OpenCV). Blender authors the Grease Pencil bank and a native bone-parented-GP + IK rig is proven (`tools/verify_native_gp_rig.py`), but the film is **not** rendered by Blender.
* Art is portrait-native. `aspect_ratio: "16:9"` produces a labelled **blur-pad derivative** (`engine/compositing/reframe.py`), not a re-staged widescreen composition.
* Rigs are busts (no walking / full body / sitting); `walk`/`sit`/`stand` degrade to posture + camera.
* OpenMoji icons (CC BY-SA 4.0, share-alike) are in the library but unused in the film.
