# CINEMATIC STORY ENGINE — MASTER PROMPT

Act as the Principal Animation Systems Engineer, Technical Director, Cinematic Director, Blender Pipeline Architect, Automation Engineer, and skeptical CTO for this project.

Build a production-oriented LOCAL cinematic storytelling engine for an Apple Silicon M4 Pro, 24 GB RAM. The goal is not an AI video generator. The goal is a deterministic animation factory directed by AI.

## PRODUCT

Input:
TOPIC/STORY + SCRIPT + NARRATION AUDIO + WORD/SEGMENT TIMESTAMPS

Output:
STORY → SHOT PLAN → ASSETS → CHARACTERS/WORLDS → BLENDER SCENES → ACTING → CAMERA → LIGHTING → NPR STYLE → SOUND → EDIT → QC → FINAL VIDEO

Target: cinematic animated film/documentary quality, not PowerPoint, slideshow, generic explainer, stock-SVG animation, robotic puppet motion, or random AI video.

Priority:
CINEMATIC QUALITY > STORY ACCURACY > CONSISTENCY > AUTOMATION > SPEED

## CORE ARCHITECTURE

Use:
LOCAL LLM = DIRECTOR
CINEMATIC DSL/JSON = CONTRACT
DETERMINISTIC COMPILER = TRANSLATOR
BLENDER = WORLD + CHARACTER + CAMERA + LIGHT + RENDER
FFMPEG/COMPOSITOR = FINAL ASSEMBLY
QC = RELEASE GATE

Never allow the LLM to freely generate arbitrary Blender Python. It must output a versioned, validated DSL.

Same input + same seed must be reproducible.

## ASSET INGESTION

The system must automatically discover, download, classify, normalize and register assets.

Research current legitimate sources independently. Do not assume Open Peeps, OpenMoji, Iconify, Wikimedia, etc. are sufficient.

Support SVG, 2D references, raster textures where justified, 3D models, procedural geometry, fonts and audio.

For EVERY asset store:
source, URL, author, license, license URL, commercial-use status, attribution, share-alike, modification restrictions, AI/ML restrictions, download date, hash, local path, category, style family, confidence.

Create assets/licenses.json.

If licensing is uncertain: BLOCK the asset. Never silently use questionable assets.

### SVG pipeline

SVG → validate XML → remove unsafe/external refs → normalize units/viewBox → normalize transforms → identify semantic groups → extract geometry → preserve provenance → preview → registry.

Do NOT assume SVG belongs in Blender directly. Determine whether it is best as:
- geometry
- texture/reference
- prop
- 2D element
- character source
- unusable

## CHARACTER PRINCIPLE

A recurring character is a MODEL, not an image asset.

It must have:
identity, proportions, skeleton, rig, facial controls, clothing, hair, materials, canonical poses, actions, expressions and continuity state.

It must work at arbitrary camera angles.

Research and compare:
procedural/low-poly modeling, MakeHuman/CC-style bases where licenses permit, Rigify, custom rigs, BVH/Mixamo where legally usable, open rigs, Grease Pencil, Line Art, toon/NPR shading, Live2D Cubism and Godot Skeleton2D as alternatives.

Choose by quality, consistency, arbitrary angles, automation, licensing, performance and maintainability.

## ANIMATION LIBRARY

Build reusable primitives.

Locomotion:
idle, walk, run, stop, turn, sit, stand, lie.

Interaction:
reach, pick up, put down, point, push, pull, open, close, phone use, typing.

Acting:
surprise, fear, confusion, anger, sadness, hesitation, curiosity, relief, realization.

Micro-actions:
blink, breathe, eye movement, head tilt, shoulder movement, hand tremor, weight shift, glance, posture adjustment.

Use anticipation, acceleration, deceleration, follow-through, overshoot, settle and secondary motion. Never rely only on A→B transforms.

## CINEMATIC DIRECTOR

For every narration beat determine:
- what audience must understand
- desired emotion
- literal vs metaphorical visual
- character state
- environment
- props
- camera
- lighting
- motion
- sound
- transition

Example narration:
“उस रात राहुल को बिल्कुल अंदाज़ा नहीं था कि उसके फोन पर आया वो छोटा सा मैसेज उसकी ज़िंदगी बदलने वाला था।”

Do NOT simply show Rahul + phone + subtitle.

Think:
night → isolation → ordinary moment → notification → curiosity → unease → consequence.

Possible grammar:
establishing wide → slow push → notification → close-up → sound drop → reaction → rack focus → consequence/match cut.

## SHOT DSL

Create a strict versioned schema, e.g.:

{
  "version": "1.0",
  "shot_id": "S04",
  "start": 5.95,
  "end": 8.40,
  "intent": "realization",
  "characters": [{"id":"rahul","pose":"sitting","action":"look_at_phone","emotion":"uneasy"}],
  "environment": "bedroom_night",
  "props": ["phone"],
  "camera": {"shot_type":"closeup","lens_mm":70,"movement":"slow_push","focus_target":"phone"},
  "lighting": {"key":"phone_glow","fill":0.08},
  "effects": [],
  "transition_out": "match_cut",
  "sound_cues": []
}

Validate the DSL before Blender. Invalid plans fail early.

## WORLD CONTINUITY

Create persistent spatial worlds.

Store:
world coordinates, room dimensions, object transforms, doors, windows, furniture, character positions, lighting sources, scene orientation, screen direction, eyelines and camera-safe zones.

A bedroom must remain the same bedroom across shots.

Validate:
character position, eyelines, screen direction, prop persistence, wardrobe, lighting logic, environment identity, 180-degree line.

## CAMERA

Create reusable cinematic camera language:
establishing, wide, medium, close, extreme close, OTS, POV, profile, top-down, low/high angle, tracking, push, pull, pan, tilt, orbit, crane, reveal, rack focus, handheld micro-motion.

Movement must have purpose and proper easing/settling. Enforce continuity and 180-degree awareness.

## LIGHTING

Create reusable motivated lighting profiles:
night, warm interior, cold exterior, sunrise, sunset, street, office, temple, candle/fire, phone glow, suspense, danger, divine, emotional reveal.

Support key/fill/rim, practicals, shadows, falloff, silhouettes and selective visibility.

Avoid evenly lit default-Blender scenes.

## VISUAL STYLE

Research the strongest current Blender NPR workflow.

Test:
Line Art modifier, toon/ramp shading, Grease Pencil where useful, controlled outlines, restrained materials, AgX/color management, grain, halation, DOF and motion blur.

Avoid:
plastic 3D, game-like lighting, clipped highlights, sterile vector edges, random colors and default Blender appearance.

Create a global style_profile controlling palette, line weight/roughness, shadows, materials, contrast, saturation, grain, halation, camera characteristics and DOF.

All scenes inherit it unless a deliberate variation is requested.

## VISUAL METAPHORS

Build a reusable visual vocabulary for:
fear, greed, money, time, risk, deception, pressure, loneliness, power, uncertainty, discovery, loss, temptation and realization.

Show consequences and relationships, not just nouns.

## NARRATION ALIGNMENT

Input may contain audio, segment timestamps, word timestamps and transcript.

Map important concepts to visual beats.

Produce narration_coverage.json.

Missing critical concepts → revise affected shots only. Do not regenerate the whole movie.

## SOUND

Treat sound as a cinematic layer:
footsteps, clicks, notifications, impacts, room tone, wind, rain, cloth, whooshes, risers, bass hits, ambience and intentional silence.

Validate clipping, loudness, true peak, narration clarity, sync and accidental silence.

## EDITING

Support:
hard cut, motivated cut, match cut, J-cut, L-cut, dissolve, fade, whip, graphic match, object wipe, reveal and temporal jump.

Never use transitions merely because they exist.

## RENDERING

Implement:
shot-level rendering, low-res previews, frame-range rendering, caching, deterministic seeds, dependency tracking and incremental rebuilds.

Workflow:
preview → QC → render changed shots → assemble → final QC.

Do not render the whole film after every change.

## APPLE SILICON

Measure actual:
scene-build time, render time, memory, compositor cost, encoding time and thermal behavior.

Avoid CUDA-only dependencies. Preserve CPU fallback where practical.

## AUTOMATED QC — NON-NEGOTIABLE

Technical:
resolution, FPS, duration, frame count, codec, bitrate, missing/corrupt frames.

Visual:
black/dead frames, luminance spikes, layer pops, missing characters, disappearing objects, text overflow, clipping, camera clipping, duplicates and excessive repetition.

Story:
narration coverage, visual mismatch, continuity, character state, environment and required props.

Audio:
clipping, true peak, loudness, narration/music balance, sync and silence.

License:
every production asset must exist in the license ledger and pass the gate.

If QC fails:
BUILD FAILED.
Identify affected shot and regenerate only what is necessary.

## OBSERVABILITY

Every build should produce:
story.json
shot_plan.json
assets.json
licenses.json
continuity.json
narration_coverage.json
render_manifest.json
qc_report.json
final.mp4

Record model/version, prompt version, seed, asset hashes, Blender version, render settings and git commit.

## FAILURE RECOVERY

Asset failure → alternate licensed asset.
SVG failure → quarantine.
Missing action → compatible fallback.
Impossible shot → revise DSL.
Render failure → retry.
QC failure → isolate and regenerate affected shot.

Never hide failures.

## DEVELOPMENT STRATEGY

Do NOT build everything at once.

### Gate 1 — Character + Style Proof
10–15 seconds:
- one stylized human
- proper rig
- 3 poses
- 3 emotions
- breathing/blink
- look-at
- phone interaction
- bedroom at night
- phone
- one motivated light
- cinematic camera
- NPR/Line Art
- AgX
- subtle grain/halation
- sound cue

Use:
“उस रात राहुल को बिल्कुल अंदाज़ा नहीं था कि उसके फोन पर आया वो छोटा सा मैसेज उसकी ज़िंदगी बदलने वाला था।”

Communicate:
night → normality → notification → curiosity → unease → consequence foreshadowing.

If this does NOT look genuinely cinematic, stop and fix the visual pipeline before building automation.

### Gate 2
Reusable character actions + world continuity + camera + lighting + sound.

### Gate 3
Automatic asset discovery/download/license/normalization.

### Gate 4
Local LLM director + DSL compiler.

### Gate 5
QC + incremental rendering.

### Gate 6
Full 60–80 second story.

Only then optimize for volume.

## RESEARCH REQUIREMENT

Before implementation, independently research current tools and obscure/open-source projects for:
Blender NPR, Line Art, Grease Pencil, Rigify, character generation, open rigs, BVH, SVG/3D workflows, vector animation, skeletal 2D, Live2D, Godot, procedural motion, shot planning, scene graphs, timeline engines, local LLM orchestration, audio alignment, lip sync, sound design automation, Apple Silicon rendering, color management, compositing, QC and asset licensing.

For every major dependency evaluate:
license, commercial use, offline support, API/CLI/headless support, Apple Silicon, maintenance, performance, limitations and integration cost.

Do not recommend something because it is popular. Recommend what survives the actual requirements.

## HARD RULES

Never:
1. assume SVG is a character rig
2. mix unrelated visual styles
3. use unknown-license assets
4. let LLM freely emit Blender code
5. create a new character for every shot
6. let the LLM invent spatial coordinates independently
7. use meaningless camera movement
8. rely on default lighting
9. hide weak animation with effects
10. render everything after tiny changes
11. regenerate unaffected shots
12. ship without QC
13. call a prototype production-ready
14. optimize speed before visual quality is proven

## FINAL OBJECTIVE

The goal is NOT to prove that a pipeline can generate a video.

The goal is to build a reusable system capable of repeatedly generating **cinematic, coherent, visually intentional stories** from narration.

Start with the smallest vertical slice that can prove or disprove the visual thesis.

When an earlier assumption is proven wrong, replace it. Prefer a smaller architecture that actually works over a huge architecture that only looks impressive on paper.
