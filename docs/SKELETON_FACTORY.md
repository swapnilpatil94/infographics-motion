# Full-body 2D skeleton character factory

Proof artefact: `output/shorts/skeleton_factory_proof/final.mp4` — "एक कॉल ने सब बदल दिया" (38 s, 1080x1920, 30 fps, 13 shots). The Short is the acceptance test.

```
DNA (archetype × seed)                       engine/characters/dna.py           who this person is (skin, hair atom, outfit, build, face style)
   │
   ▼  engine/skeleton/parts_art.py           ONE vector part per body part (18 textures + face meshes), each drawn in its own JOINT frame
REUSABLE PARTS  (upperarm/forearm/hand/thigh/shin/foot ×L,R · torso · pelvis · neck · skull · hair · nose · phone · fingers)
   │
   ▼  engine/skeleton/rig_def.py             the ONE skeleton (26 bones) + 4 IK chains — proportions come from the DNA, topology never changes
SKELETON
   │  engine/skeleton/motion.py              semantic actions × emotion style × intensity → channels (hand/foot IK targets, pelvis, spine, head, gaze, brows, mouth…)
MOTION GRAMMAR
   │
   ▼  engine/blender/skeleton_scene.py       Blender builds armature + IK + skinned meshes + shape keys, KEYFRAMES every channel, renders RGBA
BLENDER (stock 5.2.2, headless, no add-on)
   │
   ▼  engine/skeleton/short.py               ActorLayer at '@char' in a 2.5D bedroom (13 parallax layers), lights, Grease Pencil FX, captions, mix
FILM
```

## Rig (what Blender actually builds)
ROOT › PELVIS › SPINE › CHEST › NECK › HEAD › (HAIR, EYE_L/R, BROW_L/R, MOUTH) · CHEST › SHOULDER › ARM › FOREARM › HAND (L,R) · PELVIS › THIGH › SHIN › FOOT (L,R) = 26 bones.
* Every body part is its own mesh, skinned 100 % to one bone (Armature modifier + vertex group) — a rigid cut-out, so it rotates about the joint.
* Face is not an image swap: eyes (pupil + white/ring meshes with a `wide` shape key; EYE bone location = gaze, scale = blink/droop), brows (BROW bones rotate/raise = tilt/raise/asymmetry),
  mouth (line mesh with `smile`/`frown` shape keys + cavity mesh scaled by the MOUTH bone = open). Hair is a separate layer with its own bone (secondary motion).
* **IK**: 2-bone chains on both arms and legs (`IK` constraint, chain 2, `use_tail`, X/Y locked, Z limits so knees/elbows only bend the natural way). Targets are Blender empties animated in world space.
  Blender's solver only converges to the natural branch if it starts near it, so each frame's FK pose is SEEDED with the analytic 2-bone solution (`rig_def.two_bone`); the final pose is Blender's IK.
  Measured: **max IK error 0.0 px** over every probed frame of the Short (report in `manifest.json`/`qc_report.json`).
* Facing left = mirror of the same rig (bones and quads mirrored), never a second rig.

## Motion primitives (semantic; `engine/skeleton/motion.py`)
idle · blink · look_left/right/down/up/ahead · look_at_phone · head_turn · head_tilt · shrug · walk · sit · stand · reach(_for_phone) · grab · hold_phone (chest/face/ear) · read_phone ·
point · gesture · talk · listen · fear · surprise · confusion · realization · face · wake · slump · buzz · hangup · hand_down (36 names).
Command shape: `{"action":"reach_for_phone","emotion":"hesitant","intensity":0.7,"target":"nightstand_phone"}`.
* **walk** is a procedural gait: cadence and stride from the character's own leg length; stance feet are planted in the world (no sliding), swing feet arc, pelvis bobs, spine counter-rotates, arms counter-swing, foot pitch heel-strike → toe-off.
* **sit / stand** move the pelvis over planted feet (hips travel back/forward, torso leans, knees flex by IK) — not a pose swap.
* **reach** = eyes first, torso commits, arm leads, overshoot-settle; a *hesitant* style adds a doubt pause and tremor; *confident* goes direct.

## Character variation
`make_dna(archetype, seed)` → skin (8 tones), Open Peeps hair atoms (gender-strict), facial hair, glasses, eye/brow style, mouth width, outfit (colour/pattern/collar/sleeve length), bottoms, shoes, hair colour, build (slim…heavy), age (proportions), height scale.
15 archetypes × seeds. Contact sheet: 24 generated characters — `output/tests/character_factory_contact_sheet.png`. All share one bone list (asserted by QC and tests).

## Commands
```bash
python3 studio.py --skeleton-short [--tts chatterbox|vibevoice] [--tempo 1.16]            # narration -> pacing -> plan.json -> Blender rig -> film + QC
python3 studio.py --from-plan output/shorts/skeleton_factory_proof/plan.json               # deterministic re-render (no LLM, no TTS, no analysis)
.venv/bin/python -c "from engine.skeleton import factory_tests as F; F.run_all()"          # contact sheet + rig_motion_test.mp4 + crowd_test.mp4
.venv/bin/python -m unittest tests.test_skeleton                                           # 26 tests incl. a headless-Blender IK test
```

## Adding things
* **Character**: add an archetype in `engine/characters/dna.py` (hair/outfit/build lists) — the same rig, actions and Short plan work unchanged.
* **Action**: write `a_<name>(perf, t, dur, st, **kw)` in `motion.py` using `perf.to(channel, t0, t1, value)` / `hand_to` / `gaze`, register in `ACTIONS`. It automatically works for every character.
* **Prop that a hand holds**: `phone` is a part parented to `HAND_R` with keyed visibility; add a part texture in `parts_art.py` and a `PART_BONE` entry.
* **Environment**: a family generator (see `engine/environments/bedroom_wide.py`: floor line, seat height, doorway, foreground occluders).
* **New story**: write a director like `short_director.py` (narration beats → shots → semantic actions); everything downstream is reused.

## Known limitations (honest)
* **Side-on rig.** Characters are drawn in a flat 3/4-profile style (head from Open Peeps, body in profile). No front/back views, no turn-around; two characters can face each other but a character cannot turn mid-shot.
* **Body art is own work**, simple (capsule limbs, mitten hands). Hands cannot make finger poses except the phone-grip overlay. Long garments (kurta) are a longer torso block, not cloth.
* **Blender renders only the characters** (flat emission RGBA with anti-aliasing). Environments, lighting, depth-of-field, Grease Pencil FX, captions and post are the 2D compositor (Blender authors the GP effect bank). The characters therefore get the compositor's light-map, not Blender lighting.
* Sit/stand assume one seat height per scene; walking is straight-line on a flat floor; no stairs, no interaction with furniture beyond the phone.
* The Short is 38 s, one location, two acting characters; crowd/variation tests are separate videos, not part of the Short.
