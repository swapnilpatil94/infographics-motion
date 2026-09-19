# Skeleton Factory V2 - final report

Deliverable: `output/shorts/skeleton_factory_v2/final.mp4` - "एक गलत कॉल", 46.3 s, 1080x1920 @ 30 fps, 2 characters, 20 shots. QC v2: **43/43 checks pass** (`qc_report.json`). Unit tests: **Ran 121 tests in 7.333s / OK**.

Every number below is read from a measurement file (manifest, QC evidence, `determinism_v2.json`, `parallax_measurement.json`, `lighting_measurement.json`, the registry) by `tools/make_v2_report.py`.

## 1. What changed

- **CharacterDNA v2** (`engine/skeleton/dna2.py`) + **art v2** (`parts_art2.py`): 10 roles x 12 palettes, 7 tops / 5 bottoms / 4 shoes / 6 accessories, all recolourable; 3 views (profile, 3/4, front) of the SAME identity on the SAME 26 bones; 10 hand poses; separable eyes/brows/mouth/hair/nose; a sloped-shoulder / waisted / rounded-hem torso outline (replaced the boxy V1 tube).
- **Motion v2** (`motion_v2.py`): 56 semantic actions incl. WALK_TO, REACH (anticipation-reach-contact-hold), GRAB/RELEASE/HOLD, HAND_OVER/RECEIVE, READ_PHONE, lip-sync SPEAK from Devanagari vowels, target-based LOOK_AT; reach targets outside the arm's envelope are clamped and logged (`reach_clamped`) - found by the new unit tests.
- **Face system + real gaze**: shape-key visemes A/E/I/O/U/shocked, smile/worried lips, 7 eye types, 5 brow types, 11 semantic emotions; eye bones aim at a resolved `target_id` (PHONE / PERSON_x / DOOR / MONEY / SCREEN / CAMERA / POINT).
- **Compositor v2**: contact-shadow layer, rim light, phone-light on the face, depth-of-field / rack focus, camera moves truck / reveal / rack_focus / isolate / dolly_through, foreground occlusion, lamp/hall/moon lighting states.
- **Story + QC**: `short_director_v2.py` (20-beat story, cast pinned: mother = feminine bun, no facial hair), `qc_v2.py` (43 gates), `build_v2.py` (`--skeleton-short-v2`, `--from-plan`, performance block).
- **Asset acquisition + licence registry** (`tools/assets/acquire_v2.py`, `acquire_blender_audit.py`, `engine/licensing/policy.py`) and the **Blender free-rig audit** (`docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md`).
- **Lighting QC fix, not a threshold change**: the lamp-brightness gate measured the whole last shot including the deliberate title-card dim; it now measures the lit-room window (`lamp_on + 0.9 s` -> title card) against the previous shot and still requires `> +0.02` luma (measured delta: **0.052**).

## 2. Assets downloaded (exact licences, URLs, local paths)

| asset_id | licence | decision | status | source URL | download URL | local path | SHA256 |
|---|---|---|---|---|---|---|---|
| kenney_platformer_characters_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_EVALUATED | https://kenney.nl/assets/platformer-characters | https://kenney.nl/media/pages/assets/platformer-characters/b85f388c42-1677693768/kenney_platformer-characters.zip | `assets/raw/kenney/kenney_platformer-characters.zip` | `7abbee0635e83a8f...` |
| kenney_modular_characters_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_EVALUATED | https://kenney.nl/assets/modular-characters | https://kenney.nl/media/pages/assets/modular-characters/d84577feef-1677670340/kenney_modular-characters.zip | `assets/raw/kenney/kenney_modular-characters.zip` | `ff08976d4b93c10c...` |
| open_peeps_flat_v1 | CC0-1.0 | ACCEPT | USED | https://www.openpeeps.com/ | https://www.openpeeps.com/ (Gumroad pay-what-you-want download, saved once via browser) | `assets/character/raw/open_peeps/open_peeps_flat_assets.zip` | `2e0a4e79c868ae71...` |
| oga_creomoto_stickman_fixed_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://opengameart.org/content/creomotos-stick-man-fixed-up | https://opengameart.org/sites/default/files/StickMan_0.blend | `assets/raw/blender_audit/oga_stickman_fixed.blend` | `2965a6b4490ce8d4...` |
| oga_lowpoly_rigged_man_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://opengameart.org/content/low-poly-rigged-man | https://opengameart.org/sites/default/files/blockfigureRigged6.blend | `assets/raw/blender_audit/oga_lowpoly_rigged_man.blend` | `d2ae9ab97de11972...` |
| oga_old_lady_rigged_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://opengameart.org/content/old-lady | https://opengameart.org/sites/default/files/oldlady-v2.blend | `assets/raw/blender_audit/oga_old_lady.blend` | `02e6acd66a07cdc1...` |
| oga_puppet_base_rigged_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://opengameart.org/content/puppet-base-rigged | https://opengameart.org/sites/default/files/baseRelease.7z | `assets/raw/blender_audit/oga_puppet_base.7z` | `d47296afb8804d48...` |
| blenderstudio_gp_cutout_pepe_v1 | CC-BY-4.0 | ACCEPT_WITH_OBLIGATIONS | DOWNLOADED_TESTED | https://studio.blender.org/training/grease-pencil-fundamentals/5cba1d2e53491006f35d95d0/ | https://studio.blender.org/download-source/files/a9/a9e64c4c1c654e0dabc3fbaeaee85fb5/a9e64c4c1c654e0dabc3fbaeaee85fb5.blend | `assets/raw/blender_audit/gp_pepe_cutout.blend` | `c0ff650b7f348e91...` |
| blenderstudio_gp_cutout_cowboy_v1 | CC-BY-4.0 | ACCEPT_WITH_OBLIGATIONS | DOWNLOADED_TESTED | https://studio.blender.org/training/grease-pencil-fundamentals/5d9c6ee20f9018baaca071c3/ | https://studio.blender.org/download-source/files/11/119c054515814654afdd498964a57879/119c054515814654afdd498964a57879.blend | `assets/raw/blender_audit/gp_cowboy_cutout.blend` | `7f94cadbad4e4026...` |
| blenderstudio_gp_cutout_boyhead282_v1 | CC-BY-4.0 | ACCEPT_WITH_OBLIGATIONS | DOWNLOADED_TESTED | https://studio.blender.org/training/grease-pencil-fundamentals/5d9c6fbd2ed9a72b3fae65b0/ | https://studio.blender.org/download-source/files/a6/a6ee4be7a0e5405e813ebdc6e4129568/a6ee4be7a0e5405e813ebdc6e4129568.blend | `assets/raw/blender_audit/gp_boyhead_cutout_282.blend` | `888a127817854ad0...` |
| blenderstudio_gp_brush_pack_v2 | CC-BY-4.0 | ACCEPT_WITH_OBLIGATIONS | DOWNLOADED_TESTED | https://studio.blender.org/training/grease-pencil-fundamentals/5f235cc297f8815e74ffb90b/ | https://studio.blender.org/download-source/files/1f/1fc0d9422d724dd680f3240b07fb8017/1fc0d9422d724dd680f3240b07fb8017.zip | `assets/raw/blender_audit/gp_brush_pack_v2.zip` | `f4509fa3172f3dde...` |
| artell_mike_rig_v1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://www.blendernation.com/2019/02/13/free-download-mike-fully-rigged-character-cc-0/ | http://lucky3d.fr/auto-rig-pro/mike.zip | `assets/raw/blender_audit/mike_rig.zip` | `4e56244e9f2baf8e...` |
| blender_human_base_meshes_v1_4_1 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://www.blender.org/download/demo-files/ | https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip | `assets/raw/blender_audit/human_base_meshes_v1.4.1.zip` | `811f43accbb31a88...` |
| mpfb2_extension_2_0_17 | GPL-3.0-or-later | QUARANTINE | EXTERNAL_TOOL | https://extensions.blender.org/add-ons/mpfb/ | https://extensions.blender.org/download/sha256:4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87/add-on-mpfb-v2.0.17.zip | `assets/raw/blender_audit/mpfb_2.0.17.zip` | `4f0a879d64a39bf6...` |
| mpfb2_generated_humans_cc0 | CC0-1.0 | ACCEPT | DOWNLOADED_TESTED | https://static.makehumancommunity.org/about/license.html | n/a (generated: tools/assets/mpfb_build.py) | `assets/raw/blender_audit/mpfb_out/mpfb_rigify.blend` | `aba05c81090d4927...` |
| blenderstudio_gp_cutout_suzanno_v1 | None | QUARANTINE | DOWNLOADED_QUARANTINED | https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/ | https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/cutout-rig-suzanno-by-francisco-antonio-peinado-currobot-49d7d95171da4b11a26e8e56ac73d559.blend | `assets/raw/blender_audit/gp_suzanno_cutout.blend` | `6e64eaa60c9a6e14...` |
| blenderstudio_gp_cutout_simplehead_v1 | None | QUARANTINE | DOWNLOADED_QUARANTINED | https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/ | https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/cutout-rig-simple-head-by-maisam-hosaini-f220e2ef0c254e54b6da628fa784013b.blend | `assets/raw/blender_audit/gp_simplehead_cutout.blend` | `7435c2b88cda5070...` |
| blenderstudio_gp_cutout_eye282_v1 | None | QUARANTINE | DOWNLOADED_QUARANTINED | https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/ | https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/cutout-rig-eye-by-jefferson-nascimento-e4087d677ddb4328ab5d57984ab6004f.blend | `assets/raw/blender_audit/gp_eye_cutout_282.blend` | `92f5d170678552ea...` |

Not downloaded (need sign-in / e-mail checkout / gated, or licence unknown): `blendswap_stickman_basic_rig_30507` (BLOCKED_LOGIN), `blendswap_2d_stickman_rig_v2_15217` (BLOCKED_LOGIN), `gumroad_gp_spider_rig_dantti` (BLOCKED_CHECKOUT), `gumroad_super_stickman_ahmad` (BLOCKED_CHECKOUT), `gumroad_gp_character_rigs_yadoob` (BLOCKED_CHECKOUT), `quaternius_universal_base_characters` (BLOCKED_GATED), `stickman_v4gp_2d` (NOT_FOUND). Full detail: `assets/registry/asset_registry.json`, `assets/registry/license_report.json`.

## 3. Primary character foundation and why

**Open Peeps (CC0, Pablo Stanley)** supplies the heads, hair (41 styles), faces, facial hair, nose and glasses atoms and the monochrome ink *style language*; bodies, limbs, hands, feet and clothing are generated in the same line style so every part is separable and rigged. Rejected as foundations after measurement: **Kenney Platformer/Modular** (CC0; single-segment limbs, baked face, front-only wardrobe, 17x33 px sprites - `output/tests/kenney_rig_test.png`: rig and IK accept the parts, 6 of 8 criteria fail), **Open Peeps / Humaaans whole-body templates** (single illustrations), **Blender-side free rigs** (audit doc).

## 4. Rig architecture

One armature definition (`engine/skeleton/rig_def.py`) for every character and every view; identity only changes proportions (`proportions_v2`) and art. Rig space is pixels, x forward, y up, origin on the ground between the feet; Blender units = 0.01/px; facing left is a mirrored geometry with sign-flipped rotations (no negative scale). Parts are quads skinned 100 % to one bone; face features are flat-colour meshes on face bones with shape keys. Blender builds the armature, IK constraints, skinned meshes, shape keys and **keyframes every channel** headlessly (`engine/blender/skeleton_scene.py`); the compositor only lays the rendered RGBA actors into the 2.5D room.

## 5. Bone list (26)

| bone | parent |
|---|---|
| ROOT | - |
| PELVIS | ROOT |
| SPINE | PELVIS |
| CHEST | SPINE |
| NECK | CHEST |
| HEAD | NECK |
| HAIR | HEAD |
| SHOULDER_L | CHEST |
| ARM_L | SHOULDER_L |
| FOREARM_L | ARM_L |
| HAND_L | FOREARM_L |
| THIGH_L | PELVIS |
| SHIN_L | THIGH_L |
| FOOT_L | SHIN_L |
| SHOULDER_R | CHEST |
| ARM_R | SHOULDER_R |
| FOREARM_R | ARM_R |
| HAND_R | FOREARM_R |
| THIGH_R | PELVIS |
| SHIN_R | THIGH_R |
| FOOT_R | SHIN_R |
| EYE_L | HEAD |
| BROW_L | HEAD |
| EYE_R | HEAD |
| BROW_R | HEAD |
| MOUTH | HEAD |

## 6. IK architecture

4 two-bone IK chains (`IK_HAND_L/R`: ARM->FOREARM->HAND, `IK_FOOT_L/R`: THIGH->SHIN->FOOT), chain length 2, `use_tail`, X/Y locked, Z limits, targets are empties. Blender finds the natural knee/elbow branch only when the FK pose is **seeded with the analytic two-bone solution** (`rig_def.two_bone`); hanging limbs rotate counter-clockwise-forward (`rzl`), upright bones clockwise-forward (`rz`) and IK limits follow. Probed IK error over the final Short: **0.0 px** (gate < 2 px); Blender stage: {'version': '5.2.2 LTS', 'objects': 111, 'frames_rendered': 1189, 'actions': 71}.

## 7. Face architecture

Eyes: white (`wide` shape key) + ring + pupil on the EYE bones (location = gaze, scale = blink / narrow / droop), 7 eye types; brows: BROW bones with raise / tilt / asymmetry, 5 brow types; mouth: lip line with shape keys smile / frown / worried plus a cavity with viseme keys A E I O U shocked, MOUTH-bone scale = openness, 4 mouth types. 11 emotions (neutral, curious, confused, worried, fear, surprise, realization, relief, sadness, anger, determination) map to channel rows in `motion.EMO`. Distinct expressions measured in the Short: **24**; blinks: 16.

## 8. Eye gaze architecture

`gaze_toward` resolves a semantic target through the scene registry, converts it to a rig-space bearing from the eye and saturates the pupil offset (target behind -> looks back); head follows for large angles. Events are logged and QC-checked: **{'events': 12, 'distinct_targets': ['CAMERA', 'PERSON_A', 'PERSON_D', 'PHONE', '{'], 'wrong_direction': 0}**. Unit tests: `test_eye_target_accuracy_bearing_and_saturation`, `test_unknown_target_raises`.

## 9. Hand system

10 poses (open, closed, point, grab, hold_phone, hold_card, hold_money, gesture, palm_up, fist) are separate meshes on the wrist bone, swapped by keyed visibility (`hand_{L,R}_pose_id`); props (phone, card, money) and a fingers overlay attach to the wrist; HAND_OVER swaps prop ownership at the meeting point. Poses used in the Short: [0, 1, 2, 3, 4]; hand-over: {'meet_error_px': 0.1, 'ownership': {'a_phone_after': 0.0, 'd_phone_after': 1.0, 'release_t': [27.157], 'take_t': 27.404184079601986, 'give_t': 27.34679268292683}}.

## 10. Clothing system

Tops: tee, shirt, polo, hoodie, kurta, sweater, jacket. Bottoms: jeans, trousers, shorts, skirt, salwar. Shoes: sneakers, sandals, formal, slippers. Accessories: glasses, watch, bag, backpack, earrings, cap. Every garment is drawn from `TOP_STYLE / BOTTOM_STYLE` tables (sleeve, hem, collar, cuff, seams, pattern) and recoloured from the DNA palette; tests bake all 7 tops (7 distinct torso textures) and all 4 shoes (4 distinct feet).

## 11. CharacterDNA schema (`kathaya.character_dna/2`)

Keys: `schema`, `seed`, `role`, `age`, `age_group`, `gender_presentation`, `body`, `skin`, `hair`, `facial_hair`, `eyebrows`, `eyes`, `nose`, `mouth`, `wardrobe`, `posture`, `personality`, `glasses`, `silhouette`, `palette`, `id`.

```json
{
 "schema": "kathaya.character_dna/2",
 "id": "cdna_d573329913",
 "role": "young_man",
 "age": 17,
 "gender_presentation": "masculine",
 "body": {
  "height": 1.006,
  "width": 1.143,
  "shoulder": 1.117,
  "head_size": 1.084,
  "neck": 0.801,
  "leg_ratio": 0.94,
  "build": "broad"
 },
 "skin": {
  "id": "skin_07",
  "hex": "#7f4f33"
 },
 "hair": {
  "style": "Short 3",
  "length": "short",
  "color": "#000000"
 },
 "wardrobe": {
  "top": "polo",
  "bottom": "shorts",
  "shoes": "sneakers",
  "accessories": [
   "backpack",
   "cap"
  ],
  "palette": "olive",
  "pattern": "seeds",
  "top_color": "#8a8f5a",
  "bottom_color": "#43483b",
  "shoe_color": "#2f2b24",
  "accent": "#d8c7a0"
 },
 "posture": "confident",
 "personality": "calm",
 "silhouette": "standard"
}
```

Roles: young_man, young_woman, middle_aged_man, middle_aged_woman, elderly_man, elderly_woman, office_worker, student, shopkeeper, banker; 12 palettes; eye types ['round', 'almond', 'narrow', 'wide', 'small', 'droopy', 'lashed']; brow types ['thin', 'normal', 'bold', 'arched', 'straight']; mouth types ['thin', 'full', 'wide', 'small']; postures ['upright', 'slouched', 'confident', 'hunched']; personalities ['calm', 'anxious', 'confident', 'tired', 'cheerful', 'stern']. Validation: `dna2.validate`.

## 12. Motion grammar

The planner never emits raw rotations: `perform(perf, action, t, dur, emotion, intensity, **params)`. Actions: `anger`, `blink`, `breathe`, `buzz`, `call`, `confusion`, `emotion_curious`, `emotion_determination`, `emotion_neutral`, `emotion_sadness`, `emotion_worried`, `eyes_closed`, `face`, `fear`, `flinch`, `freeze`, `gesture`, `grab`, `hand_down`, `hand_over`, `hand_pose`, `hangup`, `head_tilt`, `head_turn`, `hesitate`, `hold`, `hold_phone`, `idle`, `listen`, `look_ahead`, `look_at`, `look_at_phone`, `look_down`, `look_left`, `look_right`, `look_up`, `pickup_phone`, `point`, `reach`, `reach_for_phone`, `read_phone`, `realization`, `receive`, `release`, `relief`, `shrug`, `sit`, `slump`, `speak`, `stand`, `surprise`, `talk`, `type`, `wake`, `walk`, `walk_to`.

## 13. Interaction grammar

Semantic targets resolved by a scene registry (`short.make_resolver`): `PERSON_x`, `PHONE`, `HANDOVER`, `DOOR`, `LAMP` and plan `targets`; verbs `look_at(target)`, `reach(target)`, `walk_to(target)`, `hand_over(point)`, `receive(point)`, `grab/release(prop)`. Ownership of the phone is a channel (`phone_vis`) that flips at the meeting point; QC verifies both hands meet within 30 px and the prop changes owner: **{'meet_error_px': 0.1, 'ownership': {'a_phone_after': 0.0, 'd_phone_after': 1.0, 'release_t': [27.157], 'take_t': 27.404184079601986, 'give_t': 27.34679268292683}}**.

## 14. Camera grammar

Intents `(target, size, move)`; sizes/moves used: **{'moves': ['drift', 'hold', 'isolate', 'pull', 'push', 'rack_focus', 'reveal', 'track', 'truck'], 'sizes': ['close', 'full', 'medium', 'reveal', 'two', 'two_reach', 'wide']}**; focus range [0.85, 1.6]; per-frame arrays for cx / cy / zoom / gain / aperture / focus; handheld micro-motion is seeded.

## 15. 2.5D implementation

12 layers with parallax factors [0.6, 0.62, 0.66, 0.8, 0.86, 0.94, 1.0, 1.12, 1.22, 1.3]; camera view per layer via `Camera.view(par)`; Blender actor frames are pinned screen-space layers with contact shadow, rim light and DoF. Measured in the marker test (`parallax_measurement.json`): 32/32 markers detected, mean error **0.51 px** (max 1.1 px) versus the predicted screen position; shift over the same 4 s truck: red (par 1.3) -286.5 px (pred -285.9), green (par 1.0) -212.0 px (pred -211.7), blue (par 0.86) -175.0 px (pred -175.5), yellow (par 0.6) -117.0 px (pred -117.5); ordered by parallax: **True**.

## 16. Grease Pencil implementation

Restrained semantic GP effects chosen by meaning, banked from Blender and composited: **['arcs', 'arrow', 'rays', 'ring', 'scribble', 'ticks', 'worry']**; GP bank {'renders': 128, 'blender': '5.2.2 LTS'}; procedural money-network shot in S17. Blender 5.2 GPv3 is used for the effect bank; Blender Studio GP rigs were audited (`BLENDER_FREE_HUMAN_ASSET_AUDIT.md`), a pupil-layer gaze test ran on the Boy Head cutout.

## 17. Automated tests

`.venv/bin/python -m unittest discover -s tests` -> **Ran 121 tests in 7.333s / OK** (V2 suite `tests/test_skeleton_v2.py`: 41 tests incl. Blender-backed and measured-evidence ones). Required-test mapping:

| required test | where |
|---|---|
| rig bone count / required bone names | RigTests.test_required_bone_names_and_count, test_same_bone_list_for_every_dna_and_view; QC `skeleton_26_bones_per_character` |
| IK constraint count | BlenderTests.test_blender_ik_hand_and_foot_target_accuracy_and_constraints (4 per character); QC `blender_ik_4_constraints_per_character` |
| IK / hand / foot target accuracy | same Blender test (< 1 px, four chains) + MotionCoverageTests.test_hand_target_accuracy_at_contact; QC `ik_reaches_targets_(<2px)` |
| eye target accuracy | MotionCoverageTests.test_eye_target_accuracy_bearing_and_saturation; QC `gaze_targets_(...)` |
| character variation count / same-rig identity | CharacterFactoryTests.test_fifty_characters_are_different_people, test_same_rig_ten_different_looking_characters, test_three_views_share_one_identity |
| asset licence validity / SHA256 / missing-asset detection | AssetLicenseTests.*; CharacterFactoryTests.test_no_missing_body_part_and_missing_asset_detection; QC `assets_licensed_(...)` |
| deterministic frame output / plan output | BlenderTests.test_deterministic_blender_frames; PlanDeterminismTests.test_v2_plan_is_deterministic_and_semantic; `determinism_v2.json` |
| parallax movement / camera movement / lighting change | CameraDepthLightingTests.*; `parallax_measurement.json`, `lighting_measurement.json`; QC `parallax_measured_...`, `camera_movement_...`, `lighting_variation_...` |
| animation action coverage / no frozen character | MotionCoverageTests.test_all_spec_actions_exist, test_hand_pose_set_is_the_ten_required, test_no_frozen_character_during_required_actions; QC `no_frozen_frames` |
| no missing body part / no z-fighting / no accidental overlap | CharacterFactoryTests.test_no_missing_body_part_..., test_no_z_fighting_...; OverlapTests.* |
| narration alignment | PlanDeterminismTests.test_narration_alignment; QC `narration_sync_(...)`: cut offsets [0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12]... |

QC v2 checks (all evaluated on the rendered file / plan):

- PASS - 1080x1920
- PASS - 30fps
- PASS - duration_45_60s
- PASS - has_audio
- PASS - loudness_-19_to_-13_LUFS
- PASS - no_unintended_black_frames_(fades_and_the_S12_dip_excluded)
- PASS - no_frozen_frames
- PASS - skeleton_26_bones_per_character
- PASS - blender_ik_4_constraints_per_character
- PASS - ik_reaches_targets_(<2px)
- PASS - same_rig_architecture_for_all_characters
- PASS - two_different_characters
- PASS - full_body_character_visible_head_to_feet
- PASS - sitting_and_standing
- PASS - real_skeletal_walk_(steps,distance,foot_lift)
- PASS - reaching_(hand_travel>=half_the_arm_length)
- PASS - holding_phone_(>=90_frames)
- PASS - prop_interaction_(pick_up_event_and_free_phone_hidden_after)
- PASS - eye_movement_(gaze_range)
- PASS - blinking_(>=4_blinks)
- PASS - head_movement_(range>=20deg)
- PASS - facial_variation_(>=12_distinct_expressions)
- PASS - environment_layers_(>=10,_>=6_parallax_factors)
- PASS - parallax_measured_(far_vs_near_layer_shift>60px)
- PASS - camera_movement_(>=4_move_types,_>=4_sizes)
- PASS - lighting_variation_(luma_span>=0.08)
- PASS - grease_pencil_fx_(>=4_effects,_procedural_money_shot)
- PASS - narration_sync_(every_cut_lands_0-0.35s_before_its_beat)
- PASS - captions_inside_safe_zone
- PASS - cinematic_composition_(shot_size_variety_and_subject_in_frame)
- PASS - dna_v2_valid_(schema_and_wardrobe_vocabulary)
- PASS - assets_licensed_(registry:_ACCEPT,_sha256,_licence_proof)
- PASS - non_profile_view_used_(three_quarter_or_front)
- PASS - hand_poses_used_(>=5_distinct)
- PASS - gaze_targets_(>=8_events,_>=4_targets,_bearing_sign_correct)
- PASS - hand_over_(both_hands_meet_within_30px;_phone_changes_owner)
- PASS - walk_stance_feet_planted_(max_slide_<=45px)
- PASS - contact_shadows_rim_light_face_light_enabled
- PASS - lamp_raises_brightness_(lit_room_>_previous_shot)
- PASS - camera_vocabulary_(>=7_moves,_>=6_sizes)
- PASS - rack_focus_(focus_depth_changes_>=0.5)
- PASS - character_isolation_(>=2_shallow-DoF_shots)
- PASS - foreground_occlusion_(fg_layer_overlaps_the_actor_in_>=10_sampled_frames)

## 18. Determinism results

- **run1_vs_run2_studio_skeleton_short_v2**: plan_sha256=True, plan_sha256_raw_bytes=False, manifest_core_sha256=True, blender_frames=True, blender_frames_pixel_sha256=True, blender_frames_file_sha256=False, video_frames=True, video_frames_md5_sha256=True, audio_decoded_md5=True, mp4_file_sha256=True, differing_video_frames=0, first_differing_video_frames=[]
- **run1_vs_run3_from_plan**: plan_sha256=True, plan_sha256_raw_bytes=True, manifest_core_sha256=True, blender_frames=True, blender_frames_pixel_sha256=True, blender_frames_file_sha256=False, video_frames=True, video_frames_md5_sha256=True, audio_decoded_md5=True, mp4_file_sha256=True, differing_video_frames=0, first_differing_video_frames=[]
- run `run1`: plan `19b8c5ea1a92`, manifest-core `196b45f2cfaa`, 1189 Blender frames (pixel hash `43a2c9b1e951`), 1390 video frames (decoded md5-set `13bcd78acc9c`), audio md5 `MD5=9b655dc7562c6b3571ba3117b9bb057c`, QC passed True []
- run `run2_studio_skeleton_short_v2`: plan `19b8c5ea1a92`, manifest-core `196b45f2cfaa`, 1189 Blender frames (pixel hash `43a2c9b1e951`), 1390 video frames (decoded md5-set `13bcd78acc9c`), audio md5 `MD5=9b655dc7562c6b3571ba3117b9bb057c`, QC passed True []
- run `run3_from_plan`: plan `19b8c5ea1a92`, manifest-core `196b45f2cfaa`, 1189 Blender frames (pixel hash `43a2c9b1e951`), 1390 video frames (decoded md5-set `13bcd78acc9c`), audio md5 `MD5=9b655dc7562c6b3571ba3117b9bb057c`, QC passed True []

## 19. Performance results (M4 Pro-class Apple Silicon, 24 GB; clean full run)

| stage | value |
|---|---|
| planning_s | 0.1 |
| asset_generation_s | 0.4 |
| blender_build_and_render_s | 174.8 |
| blender_render_only_s | 161.1 |
| compositing_encode_s | 346.4 |
| total_s | 537.0 |
| peak_ram_python_mb | 4585 |
| peak_ram_largest_child_mb | 1786 |
| output_mb | 62.6 |

## 20. Evidence paths

| file | size |
|---|---|
| `output/tests/character_factory_50_sheet.png` | 8.2 MB |
| `output/tests/10_character_same_rig.mp4` | 4.8 MB |
| `output/tests/rig_motion_v2.mp4` | 1.1 MB |
| `output/tests/face_expression_test.mp4` | 0.5 MB |
| `output/tests/eye_gaze_test.mp4` | 0.3 MB |
| `output/tests/hand_pose_test.mp4` | 0.3 MB |
| `output/tests/multi_character_interaction.mp4` | 30.5 MB |
| `output/tests/parallax_depth_test.mp4` | 14.4 MB |
| `output/tests/lighting_test.mp4` | 24.5 MB |
| `output/tests/crowd_test_v2.mp4` | 3.5 MB |
| `output/tests/asset_registry.json` | 0.0 MB |
| `output/tests/license_report.json` | 0.0 MB |
| `output/tests/character_factory_report.json` | 0.0 MB |
| `output/tests/same_identity_views.mp4` | 1.0 MB |
| `output/tests/kenney_rig_test.png` | 0.2 MB |
| `output/tests/candidate_integration_walk_reach.mp4` | 0.2 MB |
| `output/tests/determinism_v2.json` | 0.0 MB |
| `output/tests/parallax_measurement.json` | 0.0 MB |
| `output/tests/lighting_measurement.json` | 0.0 MB |
| `output/shorts/skeleton_factory_v2/final.mp4` | 62.6 MB |

## 21. Known remaining limitations (read these)

- **Head turns are a feature shift, not a re-drawn head**: the Open Peeps head art is the same 3/4 head in every view; front/3/4 differ by eye/nose/mouth offsets. Real turnarounds would need a 3D head backend (see the audit's MPFB+Rigify recommendation).
- **Front-view walking is not supported** (leg/foot art is profile-first); walking uses profile / 3/4.
- **Limbs are simple tapered capsules with cuffs**; hands are stylised poses; no cloth simulation - folds are painted. The rig reads as a jointed illustration, not fluid hand-drawn animation.
- **Small dot eyes and thin mouths** limit micro-acting; expression amplitude was raised late (mouth/brow) and has been re-rendered in the evidence videos but only spot-checked by eye.
- **Blender renders actors only**; room, lighting and FX are composited in Python, so 3D-correct interaction shadows are approximations.
- **The mother/son two-shot is tight** (torso centres 230 px apart, arms overlap during the hand-over); overlap is checked at torso level only.
- **Determinism scope**: identical plan, Blender frames, video and audio on this machine/Blender build; the MP4 container bytes are compared too, but cross-machine equality is untested.
- **Kenney / Blender free rigs were tested, not adopted** (details in the audit); no external rig replaces ours.
- **Narration** is Chatterbox Hindi with a fixed tempo (1.08) and WhisperX alignment; VibeVoice was evaluated and rejected for intelligibility/pace.
- Not verified: cross-platform runs, Blender versions other than 5.2.2, any scene beyond the single V2 story.
