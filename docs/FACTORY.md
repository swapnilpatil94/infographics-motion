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
