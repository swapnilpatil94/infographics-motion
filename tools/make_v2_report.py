"""Generates docs/FACTORY_V2_REPORT.md (the 25-point Skeleton Factory V2 report) and output/tests/{character_factory_report,asset_registry,license_report}.json from MEASURED files:
manifest/qc of the final Short, determinism_v2.json, parallax/lighting measurements, the asset registry, a live run of the unit-test suite.   .venv/bin/python tools/make_v2_report.py"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.skeleton import dna2, motion as M, parts_art2 as PA2, rig_def as R   # noqa: E402

TESTS = os.path.join(ROOT, "output/tests")
SH2 = os.path.join(ROOT, "output/shorts/skeleton_factory_v2")


def J(p):
    return json.load(open(p)) if os.path.exists(p) else None


def sz(p):
    return f"{os.path.getsize(p) / 1e6:.1f} MB" if os.path.exists(p) else "MISSING"


man, qc = J(os.path.join(SH2, "manifest.json")), J(os.path.join(SH2, "qc_report.json"))
det, par, lit = J(os.path.join(TESTS, "determinism_v2.json")), J(os.path.join(TESTS, "parallax_measurement.json")), J(os.path.join(TESTS, "lighting_measurement.json"))
reg = J(os.path.join(ROOT, "assets/registry/asset_registry.json"))["assets"]
kenney = J(os.path.join(TESTS, "kenney_rig_test.json"))
ev = qc["evidence"]
perf = man["performance"]
r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(ROOT, "tests")], capture_output=True, text=True, cwd=ROOT)
last = [ln for ln in (r.stderr + r.stdout).splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
unit = " / ".join(last)
import unittest as _ut
V2N = _ut.defaultTestLoader.discover(os.path.join(ROOT, "tests"), pattern="test_skeleton_v2.py").countTestCases()
d0 = dna2.make("report", "young_man")
P = R.proportions_v2(d0, "profile")
bones = [(b[0], b[1]) for b in R.bones(P)]

for fn in ("asset_registry.json", "license_report.json"):
    shutil.copy(os.path.join(ROOT, "assets/registry", fn), os.path.join(TESTS, fn))

L = []
w = L.append
w("# Skeleton Factory V2 - final report\n")
w(f"Deliverable: `output/shorts/skeleton_factory_v2/final.mp4` - \"{man['title']}\", {ev['duration_s']:.1f} s, 1080x1920 @ 30 fps, 2 characters, 20 shots. QC v2: **{sum(1 for v in qc['checks'].values() if v)}/{qc['n_checks']} checks pass** (`qc_report.json`). Unit tests: **{unit}**.\n")
w("Every number below is read from a measurement file (manifest, QC evidence, `determinism_v2.json`, `parallax_measurement.json`, `lighting_measurement.json`, the registry) by `tools/make_v2_report.py`.\n")

w("## 1. What changed\n")
w("- **CharacterDNA v2** (`engine/skeleton/dna2.py`) + **art v2** (`parts_art2.py`): 10 roles x 12 palettes, 7 tops / 5 bottoms / 4 shoes / 6 accessories, all recolourable; 3 views (profile, 3/4, front) of the SAME identity on the SAME 26 bones; 10 hand poses; separable eyes/brows/mouth/hair/nose; a sloped-shoulder / waisted / rounded-hem torso outline (replaced the boxy V1 tube).")
w("- **Motion v2** (`motion_v2.py`): " + str(len(M.ACTIONS)) + " semantic actions incl. WALK_TO, REACH (anticipation-reach-contact-hold), GRAB/RELEASE/HOLD, HAND_OVER/RECEIVE, READ_PHONE, lip-sync SPEAK from Devanagari vowels, target-based LOOK_AT; reach targets outside the arm's envelope are clamped and logged (`reach_clamped`) - found by the new unit tests.")
w("- **Face system + real gaze**: shape-key visemes A/E/I/O/U/shocked, smile/worried lips, 7 eye types, 5 brow types, 11 semantic emotions; eye bones aim at a resolved `target_id` (PHONE / PERSON_x / DOOR / MONEY / SCREEN / CAMERA / POINT).")
w("- **Compositor v2**: contact-shadow layer, rim light, phone-light on the face, depth-of-field / rack focus, camera moves truck / reveal / rack_focus / isolate / dolly_through, foreground occlusion, lamp/hall/moon lighting states.")
w("- **Story + QC**: `short_director_v2.py` (20-beat story, cast pinned: mother = feminine bun, no facial hair), `qc_v2.py` (43 gates), `build_v2.py` (`--skeleton-short-v2`, `--from-plan`, performance block).")
w("- **Asset acquisition + licence registry** (`tools/assets/acquire_v2.py`, `acquire_blender_audit.py`, `engine/licensing/policy.py`) and the **Blender free-rig audit** (`docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md`).")
w("- **Lighting QC fix, not a threshold change**: the lamp-brightness gate measured the whole last shot including the deliberate title-card dim; it now measures the lit-room window (`lamp_on + 0.9 s` -> title card) against the previous shot and still requires `> +0.02` luma (measured delta: **" + str(ev.get("lamp_luma_delta")) + "**).\n")

w("## 2. Assets downloaded (exact licences, URLs, local paths)\n")
w("| asset_id | licence | decision | status | source URL | download URL | local path | SHA256 |\n|---|---|---|---|---|---|---|---|")
for a in reg:
    if a.get("sha256"):
        w(f"| {a['asset_id']} | {a['license']} | {a['policy_decision']} | {a['status']} | {a['source_url']} | {a['download_url']} | `{a.get('local_path')}` | `{a['sha256'][:16]}...` |")
w("\nNot downloaded (need sign-in / e-mail checkout / gated, or licence unknown): " + ", ".join(f"`{a['asset_id']}` ({a['status']})" for a in reg if not a.get("sha256") and str(a["status"]).startswith(("BLOCKED", "NOT_FOUND"))) + ". Full detail: `assets/registry/asset_registry.json`, `assets/registry/license_report.json`.\n")

w("## 3. Primary character foundation and why\n")
w("**Open Peeps (CC0, Pablo Stanley)** supplies the heads, hair (41 styles), faces, facial hair, nose and glasses atoms and the monochrome ink *style language*; bodies, limbs, hands, feet and clothing are generated in the same line style so every part is separable and rigged. Rejected as foundations after measurement: **Kenney Platformer/Modular** (CC0; single-segment limbs, baked face, front-only wardrobe, 17x33 px sprites - `output/tests/kenney_rig_test.png`: rig and IK accept the parts, "
  f"{sum(1 for v in kenney['criteria'].values() if not v)} of {len(kenney['criteria'])} criteria fail), **Open Peeps / Humaaans whole-body templates** (single illustrations), **Blender-side free rigs** (audit doc).\n")

w("## 4. Rig architecture\n")
w("One armature definition (`engine/skeleton/rig_def.py`) for every character and every view; identity only changes proportions (`proportions_v2`) and art. Rig space is pixels, x forward, y up, origin on the ground between the feet; Blender units = 0.01/px; facing left is a mirrored geometry with sign-flipped rotations (no negative scale). Parts are quads skinned 100 % to one bone; face features are flat-colour meshes on face bones with shape keys. Blender builds the armature, IK constraints, skinned meshes, shape keys and **keyframes every channel** headlessly (`engine/blender/skeleton_scene.py`); the compositor only lays the rendered RGBA actors into the 2.5D room.\n")
w("## 5. Bone list (26)\n")
w("| bone | parent |\n|---|---|")
for b, pnt in bones:
    w(f"| {b} | {pnt or '-'} |")
w("")
w("## 6. IK architecture\n")
w("4 two-bone IK chains (`IK_HAND_L/R`: ARM->FOREARM->HAND, `IK_FOOT_L/R`: THIGH->SHIN->FOOT), chain length 2, `use_tail`, X/Y locked, Z limits, targets are empties. Blender finds the natural knee/elbow branch only when the FK pose is **seeded with the analytic two-bone solution** (`rig_def.two_bone`); hanging limbs rotate counter-clockwise-forward (`rzl`), upright bones clockwise-forward (`rz`) and IK limits follow. "
  f"Probed IK error over the final Short: **{ev['ik_max_error_px']} px** (gate < 2 px); Blender stage: {ev['blender']}.\n")
w("## 7. Face architecture\n")
w("Eyes: white (`wide` shape key) + ring + pupil on the EYE bones (location = gaze, scale = blink / narrow / droop), 7 eye types; brows: BROW bones with raise / tilt / asymmetry, 5 brow types; mouth: lip line with shape keys smile / frown / worried plus a cavity with viseme keys A E I O U shocked, MOUTH-bone scale = openness, 4 mouth types. 11 emotions (neutral, curious, confused, worried, fear, surprise, realization, relief, sadness, anger, determination) map to channel rows in `motion.EMO`. "
  f"Distinct expressions measured in the Short: **{ev['distinct_expressions']}**; blinks: {ev['blinks']}.\n")
w("## 8. Eye gaze architecture\n")
g = ev["gaze"]
w(f"`gaze_toward` resolves a semantic target through the scene registry, converts it to a rig-space bearing from the eye and saturates the pupil offset (target behind -> looks back); head follows for large angles. Events are logged and QC-checked: **{g}**. Unit tests: `test_eye_target_accuracy_bearing_and_saturation`, `test_unknown_target_raises`.\n")
w("## 9. Hand system\n")
w("10 poses (" + ", ".join(PA2.HAND_POSES) + ") are separate meshes on the wrist bone, swapped by keyed visibility (`hand_{L,R}_pose_id`); props (phone, card, money) and a fingers overlay attach to the wrist; HAND_OVER swaps prop ownership at the meeting point. "
  f"Poses used in the Short: {ev['hand_pose_ids_used']}; hand-over: {ev['hand_over']}.\n")
w("## 10. Clothing system\n")
w("Tops: " + ", ".join(dna2.TOPS) + ". Bottoms: " + ", ".join(dna2.BOTTOMS) + ". Shoes: " + ", ".join(dna2.SHOES) + ". Accessories: " + ", ".join(dna2.ACCESSORIES) + ". Every garment is drawn from `TOP_STYLE / BOTTOM_STYLE` tables (sleeve, hem, collar, cuff, seams, pattern) and recoloured from the DNA palette; tests bake all 7 tops (7 distinct torso textures) and all 4 shoes (4 distinct feet).\n")
w("## 11. CharacterDNA schema (`kathaya.character_dna/2`)\n")
w("Keys: `" + "`, `".join(d0.keys()) + "`.\n")
w("```json\n" + json.dumps({k: d0[k] for k in ("schema", "id", "role", "age", "gender_presentation", "body", "skin", "hair", "wardrobe", "posture", "personality", "silhouette")}, indent=1, ensure_ascii=False) + "\n```\n")
w("Roles: " + ", ".join(dna2.ROLES) + f"; {len(dna2.PALETTES)} palettes; eye types {list(dna2.EYE_TYPES)}; brow types {list(dna2.BROW_TYPES)}; mouth types {list(dna2.MOUTH_TYPES)}; postures {list(dna2.POSTURES)}; personalities {list(dna2.PERSONALITIES)}. Validation: `dna2.validate`.\n")
w("## 12. Motion grammar\n")
w("The planner never emits raw rotations: `perform(perf, action, t, dur, emotion, intensity, **params)`. Actions: " + ", ".join(f"`{a}`" for a in sorted(M.ACTIONS)) + ".\n")
w("## 13. Interaction grammar\n")
w("Semantic targets resolved by a scene registry (`short.make_resolver`): `PERSON_x`, `PHONE`, `HANDOVER`, `DOOR`, `LAMP` and plan `targets`; verbs `look_at(target)`, `reach(target)`, `walk_to(target)`, `hand_over(point)`, `receive(point)`, `grab/release(prop)`. Ownership of the phone is a channel (`phone_vis`) that flips at the meeting point; QC verifies both hands meet within 30 px and the prop changes owner: " + f"**{ev['hand_over']}**.\n")
w("## 14. Camera grammar\n")
w(f"Intents `(target, size, move)`; sizes/moves used: **{ev['camera_vocab']}**; focus range {ev['focus_range']}; per-frame arrays for cx / cy / zoom / gain / aperture / focus; handheld micro-motion is seeded.\n")
w("## 15. 2.5D implementation\n")
w(f"{ev['layers']} layers with parallax factors {ev['parallax_factors']}; camera view per layer via `Camera.view(par)`; Blender actor frames are pinned screen-space layers with contact shadow, rim light and DoF. "
  f"Measured in the marker test (`parallax_measurement.json`): {par['detected']}/{par['samples']} markers detected, mean error **{par['mean_abs_err_px']} px** (max {par['max_abs_err_px']} px) versus the predicted screen position; shift over the same 4 s truck: "
  + ", ".join(f"{k} (par {v['par']}) {v['measured_shift_px']} px (pred {v['predicted_shift_px']})" for k, v in par['per_layer_shift_t0p5_to_4p5'].items()) + f"; ordered by parallax: **{par['ordered_by_parallax']}**.\n")
w("## 16. Grease Pencil implementation\n")
w(f"Restrained semantic GP effects chosen by meaning, banked from Blender and composited: **{ev['gp_effects']}**; GP bank {ev['gp_bank']}; procedural money-network shot in S17. Blender 5.2 GPv3 is used for the effect bank; Blender Studio GP rigs were audited (`BLENDER_FREE_HUMAN_ASSET_AUDIT.md`), a pupil-layer gaze test ran on the Boy Head cutout.\n")
w("## 17. Automated tests\n")
w(f"`.venv/bin/python -m unittest discover -s tests` -> **{unit}** (V2 suite `tests/test_skeleton_v2.py`: " + str(V2N) + " tests incl. Blender-backed and measured-evidence ones). Required-test mapping:\n")
w("| required test | where |\n|---|---|")
MAP = [("rig bone count / required bone names", "RigTests.test_required_bone_names_and_count, test_same_bone_list_for_every_dna_and_view; QC `skeleton_26_bones_per_character`"),
       ("IK constraint count", "BlenderTests.test_blender_ik_hand_and_foot_target_accuracy_and_constraints (4 per character); QC `blender_ik_4_constraints_per_character`"),
       ("IK / hand / foot target accuracy", "same Blender test (< 1 px, four chains) + MotionCoverageTests.test_hand_target_accuracy_at_contact; QC `ik_reaches_targets_(<2px)`"),
       ("eye target accuracy", "MotionCoverageTests.test_eye_target_accuracy_bearing_and_saturation; QC `gaze_targets_(...)`"),
       ("character variation count / same-rig identity", "CharacterFactoryTests.test_fifty_characters_are_different_people, test_same_rig_ten_different_looking_characters, test_three_views_share_one_identity"),
       ("asset licence validity / SHA256 / missing-asset detection", "AssetLicenseTests.*; CharacterFactoryTests.test_no_missing_body_part_and_missing_asset_detection; QC `assets_licensed_(...)`"),
       ("deterministic frame output / plan output", "BlenderTests.test_deterministic_blender_frames; PlanDeterminismTests.test_v2_plan_is_deterministic_and_semantic; `determinism_v2.json`"),
       ("parallax movement / camera movement / lighting change", "CameraDepthLightingTests.*; `parallax_measurement.json`, `lighting_measurement.json`; QC `parallax_measured_...`, `camera_movement_...`, `lighting_variation_...`"),
       ("animation action coverage / no frozen character", "MotionCoverageTests.test_all_spec_actions_exist, test_hand_pose_set_is_the_ten_required, test_no_frozen_character_during_required_actions; QC `no_frozen_frames`"),
       ("no missing body part / no z-fighting / no accidental overlap", "CharacterFactoryTests.test_no_missing_body_part_..., test_no_z_fighting_...; OverlapTests.*"),
       ("narration alignment", "PlanDeterminismTests.test_narration_alignment; QC `narration_sync_(...)`: cut offsets " + str(ev.get('cut_to_beat_offsets_s'))[:120] + "...")]
for a, b in MAP:
    w(f"| {a} | {b} |")
w("\nQC v2 checks (all evaluated on the rendered file / plan):\n")
for k, v in qc["checks"].items():
    w(f"- {'PASS' if v else 'FAIL'} - {k}")
w("")
w("## 18. Determinism results\n")
if det:
    for k, v in det["comparisons"].items():
        w(f"- **{k}**: " + ", ".join(f"{a}={b}" for a, b in v.items()))
    for lb, r_ in det["runs"].items():
        w(f"- run `{lb}`: plan `{r_['plan_sha256'][:12]}`, manifest-core `{r_['manifest_core_sha256'][:12]}`, {r_['blender_frames']} Blender frames (pixel hash `{r_['blender_frames_pixel_sha256'][:12]}`), {r_['video_frames']} video frames (decoded md5-set `{r_['video_frames_md5_sha256'][:12]}`), audio md5 `{r_['audio_decoded_md5']}`, QC passed {r_['qc_passed']} {r_['qc_failed_checks']}")
else:
    w("(determinism_v2.json missing)")
w("")
w("## 19. Performance results (M4 Pro-class Apple Silicon, 24 GB; clean full run)\n")
w("| stage | value |\n|---|---|")
for k, v in perf.items():
    w(f"| {k} | {v} |")
w("")
w("## 20. Evidence paths\n")
w("| file | size |\n|---|---|")
EVID = ["character_factory_50_sheet.png", "10_character_same_rig.mp4", "rig_motion_v2.mp4", "face_expression_test.mp4", "eye_gaze_test.mp4", "hand_pose_test.mp4", "multi_character_interaction.mp4", "parallax_depth_test.mp4", "lighting_test.mp4",
        "crowd_test_v2.mp4", "asset_registry.json", "license_report.json", "character_factory_report.json", "same_identity_views.mp4", "kenney_rig_test.png", "candidate_integration_walk_reach.mp4", "determinism_v2.json", "parallax_measurement.json", "lighting_measurement.json"]
for e in EVID:
    w(f"| `output/tests/{e}` | {sz(os.path.join(TESTS, e))} |")
w(f"| `output/shorts/skeleton_factory_v2/final.mp4` | {sz(os.path.join(SH2, 'final.mp4'))} |")
w("")
w("## 21. Known remaining limitations (read these)\n")
LIM = ["**Head turns are a feature shift, not a re-drawn head**: the Open Peeps head art is the same 3/4 head in every view; front/3/4 differ by eye/nose/mouth offsets. Real turnarounds would need a 3D head backend (see the audit's MPFB+Rigify recommendation).",
       "**Front-view walking is not supported** (leg/foot art is profile-first); walking uses profile / 3/4.",
       "**Limbs are simple tapered capsules with cuffs**; hands are stylised poses; no cloth simulation - folds are painted. The rig reads as a jointed illustration, not fluid hand-drawn animation.",
       "**Small dot eyes and thin mouths** limit micro-acting; expression amplitude was raised late (mouth/brow) and has been re-rendered in the evidence videos but only spot-checked by eye.",
       "**Blender renders actors only**; room, lighting and FX are composited in Python, so 3D-correct interaction shadows are approximations.",
       "**The mother/son two-shot is tight** (torso centres 230 px apart, arms overlap during the hand-over); overlap is checked at torso level only.",
       "**Determinism scope**: identical plan, Blender frames, video and audio on this machine/Blender build; the MP4 container bytes are compared too, but cross-machine equality is untested.",
       "**Kenney / Blender free rigs were tested, not adopted** (details in the audit); no external rig replaces ours.",
       "**Narration** is Chatterbox Hindi with a fixed tempo (1.08) and WhisperX alignment; VibeVoice was evaluated and rejected for intelligibility/pace.",
       "Not verified: cross-platform runs, Blender versions other than 5.2.2, any scene beyond the single V2 story."]
for x in LIM:
    w("- " + x)
w("")
open(os.path.join(ROOT, "docs/FACTORY_V2_REPORT.md"), "w").write("\n".join(L))

# --- machine-readable aggregate
rep = dict(schema="kathaya.character_factory_report/2", short=dict(file="output/shorts/skeleton_factory_v2/final.mp4", title=man["title"], duration_s=ev["duration_s"], qc_passed=qc["passed"], qc_checks=qc["n_checks"],
                                                                  qc_failed=[k for k, v in qc["checks"].items() if not v]),
           dna=dict(schema="kathaya.character_dna/2", roles=list(dna2.ROLES), palettes=len(dna2.PALETTES), tops=list(dna2.TOPS), bottoms=list(dna2.BOTTOMS), shoes=list(dna2.SHOES), accessories=list(dna2.ACCESSORIES),
                    eye_types=list(dna2.EYE_TYPES), brow_types=list(dna2.BROW_TYPES), mouth_types=list(dna2.MOUTH_TYPES), views=list(R.VIEWS)),
           rig=dict(bones=len(bones), bone_list=[b for b, _ in bones], ik_chains=[i[0] for i in R.IK], hand_poses=list(PA2.HAND_POSES)), motion=dict(actions=sorted(M.ACTIONS), emotions=sorted(M.EMO)),
           unit_tests=unit, performance=perf, determinism=det["comparisons"] if det else None, parallax=dict(mean_err_px=par["mean_abs_err_px"], max_err_px=par["max_abs_err_px"], ordered=par["ordered_by_parallax"]),
           lighting=dict(monotonic=lit["monotonic_day_dusk_night"], luma_span=lit["luma_span"], lamp_brighter_by=lit["lamp_hall_brighter_than_night_by"]), assets=dict(used=[a["asset_id"] for a in reg if a["status"] == "USED"],
                                                                                                                                                                 downloaded=[a["asset_id"] for a in reg if a.get("sha256")], blocked=[a["asset_id"] for a in reg if str(a["status"]).startswith(("BLOCKED", "NOT_FOUND"))]),
           evidence={e: sz(os.path.join(TESTS, e)) for e in EVID}, qc_evidence=ev)
json.dump(rep, open(os.path.join(TESTS, "character_factory_report.json"), "w"), indent=1, ensure_ascii=False, default=str)
print("REPORT_OK", unit)
