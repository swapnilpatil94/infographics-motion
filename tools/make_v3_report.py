"""Generates docs/CHARACTER_ART_LOCK.md (final report A-P) from MEASURED files. .venv/bin/python tools/make_v3_report.py"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.skeleton import hands3 as H3, motion as M, props3   # noqa: E402

T = os.path.join(ROOT, "output/tests")
S3 = os.path.join(ROOT, "output/shorts/skeleton_factory_v3")


def J(p):
    return json.load(open(p)) if os.path.exists(p) else None


def sz(p):
    return f"{os.path.getsize(p) / 1e6:.1f} MB" if os.path.exists(p) else "MISSING"


qc, man = J(os.path.join(S3, "qc_report.json")), J(os.path.join(S3, "manifest.json"))
det, lw = J(os.path.join(T, "determinism_v3.json")), J(os.path.join(T, "line_weight_report.json"))
sil, tur = J(os.path.join(T, "silhouette_test_v3.json")), J(os.path.join(T, "turnaround_v3.json"))
reg = J(os.path.join(ROOT, "assets/registry/asset_registry.json"))["assets"]
ev = qc["evidence"]
r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(ROOT, "tests")], capture_output=True, text=True, cwd=ROOT)
unit = " / ".join(ln for ln in (r.stderr + r.stdout).splitlines() if ln.startswith(("Ran ", "OK", "FAILED")))
L = []
w = L.append
w("# Character art + acting quality lock - final report\n")
w(f"Deliverable: `output/shorts/skeleton_factory_v3/final.mp4` ({ev['duration_s']:.1f} s, 1080x1920, 2 characters). Automated gates: **{sum(1 for v in qc['checks'].values() if v)}/{qc['n_checks']}**; unit tests: **{unit}**.\n")
w("> These numbers say the film is *technically* correct. They do **not** say it looks good - that judgement is yours; section P lists what I know is still weak.\n")

w("## A. What was wrong\n")
w("- **A real rig bug, found by measuring, not by eye**: every limb texture was rotated the wrong way about its joint, so each part sat *two rest angles* away from its bone (upper arm 14 deg, **forearm 36 deg**, hand 52 deg). In the V2 film this is why forearms and hands looked like disconnected capsules and why the phone hovered beside the hand. Fixed in `engine/blender/skeleton_scene.py` (`add_textured_part`, `add_textured_part_at`); regression test `RestOrientationTests` measures every limb mesh against its bone in Blender for both facings (< 1 deg).")
w("- Hands: 4 fat sausages on a box, 10 poses, no anchors. Eyes: bare dots. Mouths: a hair-thin line. Walking: the stance foot slid (the planted foot followed a fixed rate while the body ramped) and the pelvis bobbed the wrong way (lowest at *passing*). Emotions: single expression swaps. The mother: a layer that was simply present at the edge of the frame.")
w("- Line weights: hands 2-3 px against limbs 6 px (measured, `tools/line_weight_report.py`).\n")

w("## B. What assets were missing\n")
w("A hand library with palm / thumb / finger silhouettes and semantic anchors, a phone hand drawing that actually closes on the phone, prop grip points, a back view, readable eyes, and any acting beyond expression swaps. Not available as free ready-made art in one place: no source provides modular limbs + hands + faces in the Open Peeps ink language.\n")

w("## C. Assets downloaded\n")
for a in reg:
    if a["asset_id"] in ("rgs_cc0_modular_animated_vector_characters", "openpeeps_device_hand_harvest_v1"):
        w(f"- `{a['asset_id']}` - {a['license']} - {a['source_url']} - `{a.get('local_path')}` - sha256 `{(a.get('sha256') or '')[:16]}...` - {a['status']}")
w("- Already registered and used from earlier: Open Peeps (CC0) heads/hair/faces/style; the Blender free-rig audit (`docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md`) covers Pepe/Boy-Head cutouts, MPFB2+Rigify, Creomoto, Mike. Puppet Mode and Tiny 2D Rig Tools were consulted as architecture only (no licence -> no code).\n")

w("## D. What was rejected\n")
w("- **RGS CC0 Modular Animated Vector Characters** (72.7 MB): 3 monster heads, glossy cel-shaded eyes, 8 mouths, ONE hand and ONE foot as 2048 px white-tinted game sprites - a game-monster style, not the flat editorial ink of the Open Peeps heads, and one hand sprite cannot make a hand library. Style reference only.")
w("- **Open Peeps body atoms as a hand source, except one**: the atoms are mono line art whose hand outlines are open strokes; my contour-fill harvest (`tools/assets/harvest_openpeeps.py`) produced a clean recolourable hand for **Device** (phone hold) but only blobs for Explaining / Coffee / Macbook / Gaming / Killer. Tracing polygons by hand for each was not done.")
w("- Humaaans (whole torso/legs), Kenney (single-segment limbs, baked face), 3D rigs (audit doc) - unchanged.\n")

w("## E. What was actually integrated\n")
w(f"- `hold_phone` = a **real Open Peeps drawing** (harvested from the Device atom), recoloured to the DNA skin tone and normalised to the shared ink weight; 19 other poses are **procedural** in the same language (so the library is uneven: one hero hand, nineteen competent cartoon hands).")
w("- Style normalisers (`engine/skeleton/normalize.py`): line weight, palette, scale, stroke join, stroke cap, shadow.")
w("- Everything else in the film is our own generated art + Open Peeps heads/hair.\n")

w("## F. Hand system\n")
w(f"20 poses x left/right x profile/3/4 (`hands3.POSES`: {', '.join(H3.POSES)}); each has anchors (wrist, palm, grip, tip, thumb tip). Sheet: `output/tests/hand_library_v3_sheet.png`. Ink weight measured: hands {lw['parts']['hand_R_open']['median']} / {lw['parts']['hand_R_hold_phone']['median']} px, limbs/torso {lw['parts']['forearm_R']['median']} px (two-weight hierarchy: silhouettes 6, small parts 4).\n")

w("## G. Face system\n")
w("Eyes: visible sclera at rest (was a bare dot), `wide` key, blink/narrow/lid scale, pupils driven by gaze; brows: raise/tilt/asymmetry (5 types); mouth: lips 1.4x thicker, stronger smile/frown/worried keys, viseme cavity 1.35x larger (A E I O U shocked). **Gaze** is a saccade: anticipation -> fast move with overshoot -> settle, target-based (PHONE / PERSON_x / DOOR / MONEY / SCREEN / CAMERA / POINT). Limits: still 2 eye types drawn as ellipses; mouth shapes are line/ellipse keys, not drawn replacement mouths.\n")

w("## H. Replacement-drawing system\n")
w("Implemented: hand poses (20, swapped by keyed visibility), views as separate baked art sets per character (front, 3/4, profile, **back**), phone perspective flatten (shape key), `char_vis` to swap view-sets at run time. **Not implemented**: head views beyond the feature shift (front and 3/4 share the Open Peeps 3/4 head), arm/leg bent-straight variants, walking contact/passing/push drawings (the gait is skeletal + foot roll), torso pose variants (neutral/slouch/alert/...).\n")

w("## I. View system\n")
w(f"`R.VIEWS = profile, three_quarter, front, back`; `output/tests/turnaround_v3.png` (front | 3/4 L | side | 3/4 R | back, same identity `{tur['dna_id'] if tur else '?'}`, same_identity={tur['same_identity'] if tur else '?'}). Runtime turns use replacement view-sets (`v3_evidence.human_motion_quality`); the **film itself does not turn characters**.\n")

w("## J. Prop-grip system\n")
w("`engine/skeleton/props3.py`: semantic grips per prop. **SOLVED and gated: PHONE only** - `PHONE.right_hand_grip` solves wrist position and wrist angle from the hand drawing's phone anchor; measured contact error " + str(ev.get("phone_contact_error_px")) + " px; hand-over phone centres coincide within " + str(ev.get("hand_over_phone_centre_error_px")) + " px; the phone never disappears between hands (gap frames: " + str(ev.get("hand_over_phone_gap_frames")) + "). Cards, money, cup, laptop and door have DEFINED grip tables but the solver is not wired - they still use the v2 heuristic.\n")

w("## K. Acting system\n")
w("`realization` (look -> hold -> pupils shift -> brows rise -> eyes widen -> head stops -> mouth O -> exhale), `fear` (recoil -> shoulders -> head retracts -> eyes -> fast shallow breathing -> tremor), `confusion` (tilt -> eyes -> brow compression -> pause -> shrug), `notice`, `eye_contact`; sequences logged as events: " + str(ev.get("acting_sequences")) + ". Weakness: no torso/neck replacement poses, so the body acting is subtle.\n")

w("## L. Walking system\n")
w(f"Planted stance (foot x constant during stance by construction), heel-strike -> flat -> push-off (heel rises) -> swing, stride follows the speed profile (small first/last steps), cadence follows the effective speed, pelvis lowest at contact, weight transfer, arm counter-swing, head stabilised. Measured in the film: flat-foot slide {ev.get('flat_foot_slide_px_max')} px, max foot step {ev.get('foot_step_px_per_frame_max')} px/frame. No arm/leg replacement drawings, so knee/elbow shapes are the capsule art.\n")

w("## M. Two-character blocking\n")
w(f"Mother starts off-screen at x={ev['entrance']['start_x']}, walks {ev['entrance']['walk_px']} px, notices him (eyes first), he notices the door then her, eye contact both ways ({ev['entrance']['eye_contact']}), stops at personal-space distance (min torso centre distance {ev.get('min_torso_centre_distance_px')} px vs {round(0.5*1.2*(152+140))} px needed). No depth-layer separation between the two (both are on the same plane), and no per-character personal-space model beyond the two stop targets.\n")

w("## N. Style normalization\n")
w(f"Measured: limbs/torso/neck/pelvis {lw['parts']['forearm_R']['median']} px, hands {lw['parts']['hand_R_open']['median']} px (`line_weight_report.json`, big_ok={lw['big_ok']}, hands_ok={lw['hands_ok']}). Palette: DNA skin tone everywhere. **Not done**: matching the environment's hatching/texture detail on the characters - the environment is still more detailed than the figures.\n")

w("## O. Final Short results\n")
w("| gate | result |\n|---|---|")
for k, v in qc["checks"].items():
    w(f"| {k} | {'PASS' if v else 'FAIL'} |")
w("")
if det:
    w("**Determinism** (3 runs: `--skeleton-short-v3` x2 + `--from-plan`):\n")
    for k, v in det["comparisons"].items():
        w(f"- {k}: " + ", ".join(f"{a}={b}" for a, b in v.items()))
    for lb, r_ in det["runs"].items():
        w(f"- run `{lb}`: {r_['blender_frames']} Blender frames, {r_['video_frames']} video frames, plan `{r_['plan_sha256'][:12]}`, manifest `{r_['manifest_core_sha256'][:12]}`, mp4 `{r_['mp4_file_sha256'][:12]}`, QC {r_['qc_passed']}")
if man and man.get("performance"):
    w("\n**Performance**: " + ", ".join(f"{k}={v}" for k, v in man["performance"].items()))
w("\n**Evidence**\n")
w("| file | size |\n|---|---|")
for e in ("hand_library_v3_sheet.png", "hand_phone_contact.mp4", "human_motion_quality_v3.mp4", "turnaround_v3.png", "silhouette_test_v3.png", "silhouette_test_v3.json", "character_factory_50_sheet.png", "line_weight_report.json", "multi_character_interaction.mp4",
          "determinism_v3.json"):
    w(f"| `output/tests/{e}` | {sz(os.path.join(T, e))} |")
w(f"| `output/shorts/skeleton_factory_v3/final.mp4` | {sz(os.path.join(S3, 'final.mp4'))} |")
if sil:
    w(f"\nSilhouette test: {len(sil['cases'])} cases, every case one connected body = **{sil['all_single_connected_body']}** (a connected-component check - readability itself is for your eyes).")

w("\n## P. Remaining limitations (honest)\n")
for x in ["**The film is better, not finished.** Hands, eyes, attached arms and the grip are real improvements; the characters still read as clean vector figures against a more textured room.",
          "Only ONE of the twenty hands is a real Open Peeps drawing; curled poses (fist, closed, grab) are lumpy; thumbs are simple leaves.",
          "No head replacement views (front/3/4 heads are the same Open Peeps head), no neck compression, no torso pose variants, no bent/straight limb drawings, no knee/elbow shape change - the gait and arms are skeletal motion of capsule art.",
          "Prop grips: only the phone is solved; card/money/cup/laptop/door grips are defined, unverified.",
          "The film does not contain a body turn; turns exist in the evidence video only. Front-view walking is unsupported.",
          "The environment still carries more detail (hatching, texture) than the characters; no shading normaliser is applied in the compositor.",
          "Depth blocking: both characters share one depth plane; overlap is prevented by spacing only.",
          "Silhouette test passes the connectivity check, but front / 3/4 / side / back silhouettes are nearly IDENTICAL (the body art is side-on with lateral offsets, not truly frontal), and the 'reaching' case is a modest reach - so the turnaround is much weaker than the spec asks.",
          "Standing rest pose: arms rest bent in front of the body and the torso leans (the rig's rest pose + DNA posture); a neutral A-pose was not built.",
          "The V2 Short and its evidence (`output/shorts/skeleton_factory_v2`, `docs/v2_evidence`) were rendered BEFORE the rest-orientation fix; re-running `--skeleton-short-v2` now gives a different (better-attached) film. The V2 determinism proof is historical.",
          "Everything is verified on one machine and one story."]:
    w("- " + x)
open(os.path.join(ROOT, "docs/CHARACTER_ART_LOCK.md"), "w").write("\n".join(L))
print("REPORT3_OK")
