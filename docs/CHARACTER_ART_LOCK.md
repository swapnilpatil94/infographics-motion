# Character art + acting quality lock - final report

Deliverable: `output/shorts/skeleton_factory_v3/final.mp4` (46.3 s, 1080x1920, 2 characters). Automated gates: **52/52**; unit tests: **Ran 141 tests in 8.668s / OK**.

> These numbers say the film is *technically* correct. They do **not** say it looks good - that judgement is yours; section P lists what I know is still weak.

## A. What was wrong

- **A real rig bug, found by measuring, not by eye**: every limb texture was rotated the wrong way about its joint, so each part sat *two rest angles* away from its bone (upper arm 14 deg, **forearm 36 deg**, hand 52 deg). In the V2 film this is why forearms and hands looked like disconnected capsules and why the phone hovered beside the hand. Fixed in `engine/blender/skeleton_scene.py` (`add_textured_part`, `add_textured_part_at`); regression test `RestOrientationTests` measures every limb mesh against its bone in Blender for both facings (< 1 deg).
- Hands: 4 fat sausages on a box, 10 poses, no anchors. Eyes: bare dots. Mouths: a hair-thin line. Walking: the stance foot slid (the planted foot followed a fixed rate while the body ramped) and the pelvis bobbed the wrong way (lowest at *passing*). Emotions: single expression swaps. The mother: a layer that was simply present at the edge of the frame.
- Line weights: hands 2-3 px against limbs 6 px (measured, `tools/line_weight_report.py`).

## B. What assets were missing

A hand library with palm / thumb / finger silhouettes and semantic anchors, a phone hand drawing that actually closes on the phone, prop grip points, a back view, readable eyes, and any acting beyond expression swaps. Not available as free ready-made art in one place: no source provides modular limbs + hands + faces in the Open Peeps ink language.

## C. Assets downloaded

- `rgs_cc0_modular_animated_vector_characters` - CC0-1.0 - https://opengameart.org/content/free-cc0-modular-animated-vector-characters-2d - `assets/raw/rgs/free_2d_animated_vector_game_character_sprites.zip` - sha256 `b44bac3ee8d4be48...` - DOWNLOADED_EVALUATED
- `openpeeps_device_hand_harvest_v1` - CC0-1.0 - https://www.openpeeps.com/ - `assets/character/harvest/openpeeps_device_hand.fill.npy` - sha256 `a4384bbf0e6f946e...` - USED
- Already registered and used from earlier: Open Peeps (CC0) heads/hair/faces/style; the Blender free-rig audit (`docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md`) covers Pepe/Boy-Head cutouts, MPFB2+Rigify, Creomoto, Mike. Puppet Mode and Tiny 2D Rig Tools were consulted as architecture only (no licence -> no code).

## D. What was rejected

- **RGS CC0 Modular Animated Vector Characters** (72.7 MB): 3 monster heads, glossy cel-shaded eyes, 8 mouths, ONE hand and ONE foot as 2048 px white-tinted game sprites - a game-monster style, not the flat editorial ink of the Open Peeps heads, and one hand sprite cannot make a hand library. Style reference only.
- **Open Peeps body atoms as a hand source, except one**: the atoms are mono line art whose hand outlines are open strokes; my contour-fill harvest (`tools/assets/harvest_openpeeps.py`) produced a clean recolourable hand for **Device** (phone hold) but only blobs for Explaining / Coffee / Macbook / Gaming / Killer. Tracing polygons by hand for each was not done.
- Humaaans (whole torso/legs), Kenney (single-segment limbs, baked face), 3D rigs (audit doc) - unchanged.

## E. What was actually integrated

- `hold_phone` = a **real Open Peeps drawing** (harvested from the Device atom), recoloured to the DNA skin tone and normalised to the shared ink weight; 19 other poses are **procedural** in the same language (so the library is uneven: one hero hand, nineteen competent cartoon hands).
- Style normalisers (`engine/skeleton/normalize.py`): line weight, palette, scale, stroke join, stroke cap, shadow.
- Everything else in the film is our own generated art + Open Peeps heads/hair.

## F. Hand system

20 poses x left/right x profile/3/4 (`hands3.POSES`: open, closed, point, grab, hold_phone, hold_card, hold_money, gesture, palm_up, fist, relaxed, pinch, hold_pen, hold_cup, type, touch_screen, push, pull, wave, palm_down); each has anchors (wrist, palm, grip, tip, thumb tip). Sheet: `output/tests/hand_library_v3_sheet.png`. Ink weight measured: hands 4.0 / 3.6 px, limbs/torso 6.0 px (two-weight hierarchy: silhouettes 6, small parts 4).

## G. Face system

Eyes: visible sclera at rest (was a bare dot), `wide` key, blink/narrow/lid scale, pupils driven by gaze; brows: raise/tilt/asymmetry (5 types); mouth: lips 1.4x thicker, stronger smile/frown/worried keys, viseme cavity 1.35x larger (A E I O U shocked). **Gaze** is a saccade: anticipation -> fast move with overshoot -> settle, target-based (PHONE / PERSON_x / DOOR / MONEY / SCREEN / CAMERA / POINT). Limits: still 2 eye types drawn as ellipses; mouth shapes are line/ellipse keys, not drawn replacement mouths.

## H. Replacement-drawing system

Implemented: hand poses (20, swapped by keyed visibility), views as separate baked art sets per character (front, 3/4, profile, **back**), phone perspective flatten (shape key), `char_vis` to swap view-sets at run time. **Not implemented**: head views beyond the feature shift (front and 3/4 share the Open Peeps 3/4 head), arm/leg bent-straight variants, walking contact/passing/push drawings (the gait is skeletal + foot roll), torso pose variants (neutral/slouch/alert/...).

## I. View system

`R.VIEWS = profile, three_quarter, front, back`; `output/tests/turnaround_v3.png` (front | 3/4 L | side | 3/4 R | back, same identity `cdna_1f795b524f`, same_identity=True). Runtime turns use replacement view-sets (`v3_evidence.human_motion_quality`); the **film itself does not turn characters**.

## J. Prop-grip system

`engine/skeleton/props3.py`: semantic grips per prop. **SOLVED and gated: PHONE only** - `PHONE.right_hand_grip` solves wrist position and wrist angle from the hand drawing's phone anchor; measured contact error [0.0] px; hand-over phone centres coincide within 3.11 px; the phone never disappears between hands (gap frames: 0). Cards, money, cup, laptop and door have DEFINED grip tables but the solver is not wired - they still use the v2 heuristic.

## K. Acting system

`realization` (look -> hold -> pupils shift -> brows rise -> eyes widen -> head stops -> mouth O -> exhale), `fear` (recoil -> shoulders -> head retracts -> eyes -> fast shallow breathing -> tremor), `confusion` (tilt -> eyes -> brow compression -> pause -> shrug), `notice`, `eye_contact`; sequences logged as events: {'realization': 8, 'fear': 5, 'notice': 0, 'confusion': 5}. Weakness: no torso/neck replacement poses, so the body acting is subtle.

## L. Walking system

Planted stance (foot x constant during stance by construction), heel-strike -> flat -> push-off (heel rises) -> swing, stride follows the speed profile (small first/last steps), cadence follows the effective speed, pelvis lowest at contact, weight transfer, arm counter-swing, head stabilised. Measured in the film: flat-foot slide 0.05 px, max foot step 28.76 px/frame. No arm/leg replacement drawings, so knee/elbow shapes are the capsule art.

## M. Two-character blocking

Mother starts off-screen at x=1440.0, walks 390 px, notices him (eyes first), he notices the door then her, eye contact both ways ({'A': 2, 'D': 2}), stops at personal-space distance (min torso centre distance 270.0 px vs 175 px needed). No depth-layer separation between the two (both are on the same plane), and no per-character personal-space model beyond the two stop targets.

## N. Style normalization

Measured: limbs/torso/neck/pelvis 6.0 px, hands 4.0 px (`line_weight_report.json`, big_ok=True, hands_ok=True). Palette: DNA skin tone everywhere. **Not done**: matching the environment's hatching/texture detail on the characters - the environment is still more detailed than the figures.

## O. Final Short results

| gate | result |
|---|---|
| 1080x1920 | PASS |
| 30fps | PASS |
| duration_45_60s | PASS |
| has_audio | PASS |
| loudness_-19_to_-13_LUFS | PASS |
| no_unintended_black_frames_(fades_and_the_S12_dip_excluded) | PASS |
| no_frozen_frames | PASS |
| skeleton_26_bones_per_character | PASS |
| blender_ik_4_constraints_per_character | PASS |
| ik_reaches_targets_(<2px) | PASS |
| same_rig_architecture_for_all_characters | PASS |
| two_different_characters | PASS |
| full_body_character_visible_head_to_feet | PASS |
| sitting_and_standing | PASS |
| real_skeletal_walk_(steps,distance,foot_lift) | PASS |
| reaching_(hand_travel>=half_the_arm_length) | PASS |
| holding_phone_(>=90_frames) | PASS |
| prop_interaction_(pick_up_event_and_free_phone_hidden_after) | PASS |
| eye_movement_(gaze_range) | PASS |
| blinking_(>=4_blinks) | PASS |
| head_movement_(range>=20deg) | PASS |
| facial_variation_(>=12_distinct_expressions) | PASS |
| environment_layers_(>=10,_>=6_parallax_factors) | PASS |
| parallax_measured_(far_vs_near_layer_shift>60px) | PASS |
| camera_movement_(>=4_move_types,_>=4_sizes) | PASS |
| lighting_variation_(luma_span>=0.08) | PASS |
| grease_pencil_fx_(>=4_effects,_procedural_money_shot) | PASS |
| narration_sync_(every_cut_lands_0-0.35s_before_its_beat) | PASS |
| captions_inside_safe_zone | PASS |
| cinematic_composition_(shot_size_variety_and_subject_in_frame) | PASS |
| dna_v2_valid_(schema_and_wardrobe_vocabulary) | PASS |
| assets_licensed_(registry:_ACCEPT,_sha256,_licence_proof) | PASS |
| non_profile_view_used_(three_quarter_or_front) | PASS |
| hand_poses_used_(>=5_distinct) | PASS |
| gaze_targets_(>=8_events,_>=4_targets,_bearing_sign_correct) | PASS |
| walk_stance_feet_planted_(max_slide_<=45px) | PASS |
| contact_shadows_rim_light_face_light_enabled | PASS |
| lamp_raises_brightness_(lit_room_>_previous_shot) | PASS |
| camera_vocabulary_(>=7_moves,_>=6_sizes) | PASS |
| rack_focus_(focus_depth_changes_>=0.5) | PASS |
| character_isolation_(>=2_shallow-DoF_shots) | PASS |
| foreground_occlusion_(fg_layer_overlaps_the_actor_in_>=10_sampled_frames) | PASS |
| hand_over_(phone_centres_coincide_<=8px;_phone_changes_owner) | PASS |
| phone_never_disappears_during_hand-over | PASS |
| hand_library_(>=20_poses_per_hand) | PASS |
| phone_grip_contact_(hand_closes_on_the_phone_<=3px) | PASS |
| planted_feet_(flat-foot_slide_<=8px) | PASS |
| no_teleporting_feet_(<=60px_per_frame_=_human_swing_peak) | PASS |
| mother_enters_(starts_off-screen,_walks_>=300px,_notices_him) | PASS |
| eye_contact_both_ways | PASS |
| acting_sequences_(realization,fear,confusion_with_>=5_steps) | PASS |
| characters_never_intersect_(torso_spacing) | PASS |

**Determinism** (3 runs: `--skeleton-short-v3` x2 + `--from-plan`):

- run1_vs_run2_studio_skeleton_short_v3: plan_sha256=True, plan_sha256_raw_bytes=False, manifest_core_sha256=True, blender_frames=True, blender_frames_pixel_sha256=True, blender_frames_file_sha256=False, video_frames=True, video_frames_md5_sha256=True, audio_decoded_md5=True, mp4_file_sha256=True, differing_video_frames=0, first_differing_video_frames=[]
- run1_vs_run3_from_plan: plan_sha256=True, plan_sha256_raw_bytes=True, manifest_core_sha256=True, blender_frames=True, blender_frames_pixel_sha256=True, blender_frames_file_sha256=False, video_frames=True, video_frames_md5_sha256=True, audio_decoded_md5=True, mp4_file_sha256=True, differing_video_frames=0, first_differing_video_frames=[]
- run `run1`: 1189 Blender frames, 1390 video frames, plan `daabdffc0344`, manifest `0171e6782e62`, mp4 `c618cd39a1a4`, QC True
- run `run2_studio_skeleton_short_v3`: 1189 Blender frames, 1390 video frames, plan `daabdffc0344`, manifest `0171e6782e62`, mp4 `c618cd39a1a4`, QC True
- run `run3_from_plan`: 1189 Blender frames, 1390 video frames, plan `daabdffc0344`, manifest `0171e6782e62`, mp4 `c618cd39a1a4`, QC True

**Performance**: planning_s=0.1, asset_generation_s=0.0, blender_build_and_render_s=183.2, blender_render_only_s=167.1, compositing_encode_s=340.2, total_s=538.5, peak_ram_python_mb=4644, peak_ram_largest_child_mb=1784, output_mb=62.6

**Evidence**

| file | size |
|---|---|
| `output/tests/hand_library_v3_sheet.png` | 0.6 MB |
| `output/tests/hand_phone_contact.mp4` | 15.3 MB |
| `output/tests/human_motion_quality_v3.mp4` | 1.1 MB |
| `output/tests/turnaround_v3.png` | 0.3 MB |
| `output/tests/silhouette_test_v3.png` | 0.1 MB |
| `output/tests/silhouette_test_v3.json` | 0.0 MB |
| `output/tests/character_factory_50_sheet.png` | 8.2 MB |
| `output/tests/line_weight_report.json` | 0.0 MB |
| `output/tests/multi_character_interaction.mp4` | 30.6 MB |
| `output/tests/determinism_v3.json` | 0.0 MB |
| `output/shorts/skeleton_factory_v3/final.mp4` | 62.6 MB |

Silhouette test: 24 cases, every case one connected body = **True** (a connected-component check - readability itself is for your eyes).

## P. Remaining limitations (honest)

- **The film is better, not finished.** Hands, eyes, attached arms and the grip are real improvements; the characters still read as clean vector figures against a more textured room.
- Only ONE of the twenty hands is a real Open Peeps drawing; curled poses (fist, closed, grab) are lumpy; thumbs are simple leaves.
- No head replacement views (front/3/4 heads are the same Open Peeps head), no neck compression, no torso pose variants, no bent/straight limb drawings, no knee/elbow shape change - the gait and arms are skeletal motion of capsule art.
- Prop grips: only the phone is solved; card/money/cup/laptop/door grips are defined, unverified.
- The film does not contain a body turn; turns exist in the evidence video only. Front-view walking is unsupported.
- The environment still carries more detail (hatching, texture) than the characters; no shading normaliser is applied in the compositor.
- Depth blocking: both characters share one depth plane; overlap is prevented by spacing only.
- Silhouette test passes the connectivity check, but front / 3/4 / side / back silhouettes are nearly IDENTICAL (the body art is side-on with lateral offsets, not truly frontal), and the 'reaching' case is a modest reach - so the turnaround is much weaker than the spec asks.
- Standing rest pose: arms rest bent in front of the body and the torso leans (the rig's rest pose + DNA posture); a neutral A-pose was not built.
- The V2 Short and its evidence (`output/shorts/skeleton_factory_v2`, `docs/v2_evidence`) were rendered BEFORE the rest-orientation fix; re-running `--skeleton-short-v2` now gives a different (better-attached) film. The V2 determinism proof is historical.
- Everything is verified on one machine and one story.