"""Automated acceptance tests for Character Factory V2 (spec sec. 31). Deterministic; no thresholds relaxed."""
import hashlib
import json
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.shorts.layers import Camera, C0                                     # noqa: E402
from engine.skeleton import dna2, motion as M, parts_art2 as PA2, rig_def as R, short as SH, short_director_v2 as SD2   # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
SPEC_BONES = ["ROOT", "PELVIS", "SPINE", "CHEST", "NECK", "HEAD", "ARM_L", "FOREARM_L", "HAND_L", "ARM_R", "FOREARM_R", "HAND_R", "THIGH_L", "SHIN_L", "FOOT_L", "THIGH_R", "SHIN_R", "FOOT_R",
              "EYE_L", "EYE_R", "BROW_L", "BROW_R", "MOUTH", "HAIR", "SHOULDER_L", "SHOULDER_R"]
SPEC_ACTIONS = ["idle", "breathe", "blink", "look_at", "head_turn", "head_tilt", "walk", "walk_to", "sit", "stand", "reach", "grab", "release", "hold", "point", "gesture", "read_phone", "type", "call",
                "listen", "talk", "hesitate", "freeze", "flinch", "fear", "confusion", "realization", "relief", "anger"]
REG = json.load(open(os.path.join(ROOT, "assets/registry/asset_registry.json")))
FIX = os.path.join(ROOT, "tests/fixtures")


def d2(i, role="office_worker", **ov):
    return dna2.make(f"t{i}", role, ov or None)


def perf(seed=1, role="young_man", view="profile"):
    d = d2(seed, role)
    P = R.proportions_v2(d, view)
    p = M.Performance(P, seed=seed, world=dict(seat_h=270), facing=1, origin=(300.0, 1500.0), resolver=lambda tid, t: (520.0, 1010.0))
    M.pose_stand(p, -1.0, 0.0)
    return p


class RigTests(unittest.TestCase):
    def test_required_bone_names_and_count(self):
        for view in R.VIEWS:
            names = [b[0] for b in R.bones(R.proportions_v2(d2(1), view))]
            self.assertEqual(len(names), 26)
            for n in SPEC_BONES:
                self.assertIn(n, names)

    def test_same_bone_list_for_every_dna_and_view(self):
        lists = {tuple(b[0] for b in R.bones(R.proportions_v2(d2(i, r), v))) for i, r in enumerate(dna2.ROLES) for v in R.VIEWS}
        self.assertEqual(len(lists), 1)

    def test_ik_chain_definition(self):
        self.assertEqual(len(R.IK), 4)
        self.assertEqual({c[0] for c in R.IK}, {"IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R"})

    def test_views_offset_limbs_laterally(self):
        P0, P1, P2 = (R.proportions_v2(d2(3), v) for v in R.VIEWS[:3])
        self.assertEqual(P0["lat_s"], 0.0)
        self.assertGreater(P1["lat_s"], 5)
        self.assertGreater(P2["lat_s"], P1["lat_s"])


@unittest.skipUnless(os.path.exists(BLENDER), "Blender not installed")
class BlenderTests(unittest.TestCase):
    def _job(self, tmp, p, man, facing=1, frames=None, name="t"):
        from engine.skeleton import blender_job
        ch = M.sample(p, 30, 0.0, 2.6)
        n = len(ch["root_x"])
        a = SH.Actor("A", dict(dna=man["_d2"], facing=facing, origin=[300, 1500], view=man["view"], hand_set="full"), dict(story_id="t"))
        a.channels = ch
        job = dict(width=180, height=320, fps=30, start=0, end=n - 1, out=os.path.join(tmp, name), prefix="t", samples=2, render_frames=frames or [20, 60], probe_frames=list(range(0, n, 4)),
                   characters=[dict(id="A", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=facing, origin=[300, 1500], channels=a.job_channels())],
                   camera=dict(cx=540, cy=1000, zoom=0.17))
        return blender_job.run(job, tmp)

    def _setup(self, view="three_quarter"):
        d = d2(7, "young_woman")
        man = dict(PA2.bake2(d, view, "full"))
        man["_d2"] = d
        p = M.Performance(man["P"], seed=2, world=dict(seat_h=270), facing=1, origin=(300.0, 1500.0), resolver=lambda tid, t: (560.0, 1180.0))
        M.pose_stand(p, -1.0, 0.0)
        M.perform(p, "reach", 0.3, 1.0, "hesitant", 0.7, target="PHONE", grip="grab")
        M.perform(p, "walk", 1.6, 1.0, "neutral", 0.6, speed=200)
        return p, man

    def test_unreachable_target_is_clamped_to_the_arm_envelope(self):
        p, man = self._setup("profile")
        self.assertTrue(any(e[1] == "reach_clamped" for e in p.events))

    def test_blender_ik_hand_and_foot_target_accuracy_and_constraints(self):
        p, man = self._setup()
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._job(tmp, p, man)
        self.assertEqual(rep["bones"]["A"], 26)
        self.assertEqual(rep["ik_constraints"]["A"], 4)
        err = {k: max(e[k] for e in rep["ik_error_px"]) for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")}
        for k, v in err.items():
            self.assertLess(v, 1.0, k)

    def test_deterministic_blender_frames(self):
        p, man = self._setup("profile")
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            self._job(t1, p, man)
            self._job(t2, p, man)
            for f in ("t00020.png", "t00060.png"):
                a, b = (np.asarray(Image.open(os.path.join(t, "t", f)).convert("RGBA")) for t in (t1, t2))
                self.assertTrue((a == b).all(), f)


class MotionCoverageTests(unittest.TestCase):
    def test_all_spec_actions_exist(self):
        for a in SPEC_ACTIONS:
            self.assertIn(a, M.ACTIONS, a)

    def test_eleven_semantic_emotions(self):
        for e in ("neutral", "curious", "confused", "worried", "fear", "surprise", "realization", "relief", "sadness", "anger", "determination"):
            self.assertIn(e, M.EMO, e)

    def test_hand_pose_library_has_the_twenty_required_poses(self):
        need = {"open", "relaxed", "fist", "point", "pinch", "grab", "hold_phone", "hold_card", "hold_money", "hold_pen", "hold_cup", "type", "touch_screen", "push", "pull", "wave", "palm_up", "palm_down", "gesture", "closed"}
        self.assertEqual(set(PA2.HAND_POSES), need)
        self.assertEqual(len(PA2.HAND_POSES), 20)

    def test_no_frozen_character_during_required_actions(self):
        for act, kw in (("idle", {}), ("walk", dict(speed=200)), ("reach", dict(target="PHONE")), ("gesture", {}), ("read_phone", {}), ("talk", {}), ("breathe", {})):
            p = perf()
            M.perform(p, "breathe", 0.0, 3.0, "neutral", 0.5)                           # the film keeps breathing under every action
            M.perform(p, act, 0.3, 2.0, "neutral", 0.6, **kw)
            ch = M.sample(p, 30, 0.0, 2.6)
            n = len(ch["root_x"])
            names = [k for k, v in ch.items() if hasattr(v, "__len__") and len(v) == n and not k.startswith("vis_")]
            still = [all(abs(ch[k][i + 1] - ch[k][i]) < 1e-5 for k in names) for i in range(n - 1)]
            run = best = 0
            for i in range(int(0.3 * 30), int(2.3 * 30) - 1):                        # inside the action window
                run = run + 1 if still[i] else 0
                best = max(best, run)
            self.assertLess(best, 8, f"{act}: frozen for {best} consecutive frames (>0.25 s)")

    def test_phone_grip_contact_is_exact(self):
        """the wrist solved for the PHONE grip puts the phone (as the real hand drawing holds it) on the target: no floating hand, no near miss"""
        from engine.skeleton import hands3 as H3
        p = perf()
        end = M.perform(p, "reach", 0.3, 1.2, "confident", 0.6, target="PHONE", grip="grab")
        ev = [e for e in p.events if e[1] == "phone_contact"]
        self.assertTrue(ev)
        C = ev[0][2]["centre"]
        wrist = (p.v("hand_R_x", end), p.v("hand_R_y", end))
        rot = p.v("hand_R_rot", end)
        sh = p.shoulder(end)
        _, _, a1, a2 = R.two_bone(sh, wrist, p.P["upper_arm"], p.P["forearm"], -1)
        H = math.radians(a2 + R.REST["wrist"] + rot)
        lx, ly, th = H3.phone_anchor(p.P)
        centre = (wrist[0] + lx * math.cos(H) + ly * math.sin(H), wrist[1] + lx * math.sin(H) - ly * math.cos(H))
        self.assertLess(math.dist(centre, C), 2.5)
        self.assertAlmostEqual((a2 + R.REST["wrist"] + rot) - th, -90.0, delta=1.0)                # the phone lies flat at contact

    def test_eye_target_accuracy_bearing_and_saturation(self):
        p = perf()
        ex, ey = M.motion_v2._eye_world(p, 0.0)
        cases = []
        for tgt in ((ex + 400, ey), (ex + 200, ey + 120), (ex + 200, ey - 150), (ex - 300, ey)):
            p2 = perf()
            p2.resolver = lambda tid, t, tgt=tgt: (p2.to_world(tgt)[0], p2.to_world(tgt)[1])
            gx, gy = M.motion_v2.gaze_toward(p2, 0.0, 0.5, "X", head=False)
            cases.append((tgt, gx, gy))
            self.assertEqual(gx > 0, tgt[0] > ex)                                    # eyes point the way the target lies
            if abs(tgt[1] - ey) > 60:
                self.assertEqual(gy > 0, tgt[1] > ey)
        self.assertGreater(cases[0][1], cases[1][1] - 0.5)
        self.assertEqual(cases[3][1], -1.0)                                          # a target behind: look back

    def test_unknown_target_raises(self):
        p = perf()
        p.resolver = SH.make_resolver(dict(targets={}), {})
        with self.assertRaises(KeyError):
            p.target_rig("NOWHERE", 0.0)

    def test_walk_to_arrives_at_target(self):
        p = perf()
        p.resolver = lambda tid, t: p.to_world((700.0, 0.0))
        M.perform(p, "walk_to", 0.2, 3.0, "neutral", 0.6, target="X", stop_before=0.0, speed=200)
        ch = M.sample(p, 30, 0.0, 6.0)
        self.assertAlmostEqual(ch["root_x"][-1], 700.0, delta=1.0)

    def test_lip_sync_uses_devanagari_vowels(self):
        self.assertEqual(M.motion_v2._visemes("बेटा"), ["E", "A"])
        p = perf()
        M.perform(p, "speak", 0.0, 1.0, "neutral", 0.5, words=[dict(word="बेटा", start=0.1, end=0.6)])
        ch = M.sample(p, 30, 0.0, 1.0)
        self.assertGreater(max(ch["vis_E"]), 0.9)
        self.assertGreater(max(ch["vis_A"]), 0.9)

    def test_handover_swaps_prop_ownership(self):
        a, b = perf(1), perf(2, "middle_aged_woman")
        M.perform(a, "grab", 0.1, 0.1, prop="phone")
        M.perform(a, "hand_over", 0.5, 1.0, "neutral", 0.5, point="X", prop="phone")
        M.perform(b, "receive", 0.5, 1.0, "neutral", 0.5, point="X", prop="phone")
        M.perform(a, "release", 1.7, 0.4, prop="phone")
        ca, cb = M.sample(a, 30, 0.0, 3.0), M.sample(b, 30, 0.0, 3.0)
        self.assertGreater(ca["phone_vis"][20], 0.5)
        self.assertLess(ca["phone_vis"][-1], 0.5)
        self.assertLess(cb["phone_vis"][10], 0.5)
        self.assertGreater(cb["phone_vis"][-1], 0.5)


class CharacterFactoryTests(unittest.TestCase):
    def test_dna_schema_validates_and_is_deterministic(self):
        a, b = dna2.make("s", "banker"), dna2.make("s", "banker")
        self.assertEqual(a, b)
        self.assertEqual(dna2.validate(a), [])
        bad = json.loads(json.dumps(a))
        bad["wardrobe"]["top"] = "spacesuit"
        self.assertTrue(dna2.validate(bad))

    def test_fifty_characters_are_different_people(self):
        ds = [dna2.make(f"v:{i}", dna2.ROLES and list(dna2.ROLES)[i % len(dna2.ROLES)]) for i in range(50)]
        self.assertEqual(len({d["id"] for d in ds}), 50)
        self.assertGreaterEqual(len({d["hair"]["style"] for d in ds}), 15)
        self.assertGreaterEqual(len({(d["wardrobe"]["top"], d["wardrobe"]["bottom"], d["wardrobe"]["shoes"]) for d in ds}), 30)
        self.assertGreaterEqual(len({d["silhouette"] for d in ds}), 5)
        self.assertGreaterEqual(len({d["wardrobe"]["palette"] for d in ds}), 8)
        self.assertGreaterEqual(len({d["skin"]["id"] for d in ds}), 4)
        heights = [R.proportions_v2(d)["height"] for d in ds]
        self.assertGreater(max(heights) - min(heights), 150)

    def test_wardrobe_vocabulary_is_complete(self):
        self.assertEqual(set(dna2.TOPS), {"tee", "shirt", "polo", "hoodie", "kurta", "sweater", "jacket"})
        self.assertEqual(set(dna2.BOTTOMS), {"jeans", "trousers", "shorts", "skirt", "salwar"})
        self.assertEqual(set(dna2.SHOES), {"sneakers", "sandals", "formal", "slippers"})
        self.assertEqual(set(dna2.ACCESSORIES), {"glasses", "watch", "bag", "backpack", "earrings", "cap"})

    def test_every_wardrobe_item_bakes_and_differs(self):
        seen = {}
        for top in dna2.TOPS:
            man = PA2.bake2(dna2.make("w", "young_man", {"wardrobe.top": top, "wardrobe.pattern": "plain"}), "profile", "basic")
            seen[top] = hashlib.sha1(open(os.path.join(ROOT, man["parts"]["torso"]["png"]), "rb").read()).hexdigest()
            self.assertEqual(PA2.verify(man), [])
        self.assertEqual(len(set(seen.values())), 7)
        for bottom in dna2.BOTTOMS:
            man = PA2.bake2(dna2.make("w", "young_woman", {"wardrobe.bottom": bottom}), "profile", "basic")
            self.assertEqual(PA2.verify(man), [], bottom)
        shoes = {hashlib.sha1(open(os.path.join(ROOT, PA2.bake2(dna2.make("w", "young_man", {"wardrobe.shoes": s}), "profile", "basic")["parts"]["foot_R"]["png"]), "rb").read()).hexdigest() for s in dna2.SHOES}
        self.assertEqual(len(shoes), 4)

    def test_same_rig_ten_different_looking_characters(self):
        ds = [dna2.make(f"ten:{i}", list(dna2.ROLES)[i]) for i in range(10)]
        mans = [PA2.bake2(d, "three_quarter", "basic") for d in ds]
        torsos = {hashlib.sha1(open(os.path.join(ROOT, m["parts"]["torso"]["png"]), "rb").read()).hexdigest() for m in mans}
        self.assertEqual(len(torsos), 10)
        bones = {tuple(b[0] for b in R.bones(m["P"])) for m in mans}
        self.assertEqual(len(bones), 1)

    def test_three_views_share_one_identity(self):
        d = dna2.make("v3", "young_woman")
        m = [PA2.bake2(d, v, "basic") for v in R.VIEWS]
        self.assertEqual({x["dna_id"] for x in m}, {d["id"]})
        self.assertEqual({x["view"] for x in m}, set(R.VIEWS))
        self.assertEqual(len({x["id"] for x in m}), len(R.VIEWS))
        skull = {hashlib.sha1(open(os.path.join(ROOT, x["parts"]["skull"]["png"]), "rb").read()).hexdigest() for x in m if x["view"] != "back"}
        self.assertEqual(len(skull), 1)                                              # the same head, not a new person

    def test_no_missing_body_part_and_missing_asset_detection(self):
        man = json.loads(json.dumps(PA2.bake2(dna2.make("mp", "banker"), "front", "full")))
        self.assertEqual(PA2.verify(man), [])
        man["parts"]["hair"]["png"] = "assets/nope.png"
        del man["parts"]["torso"]
        bad = dict(PA2.verify(man))
        self.assertIn("hair", bad)
        self.assertIn("torso", bad)

    def test_no_z_fighting_or_overlapping_part_depths(self):
        order = [p for p in R.PART_ORDER if p != "@face"]
        self.assertEqual(len(order), len(set(order)))
        depths = [0.004 * i for i in range(len(R.PART_ORDER))]
        self.assertEqual(len(depths), len(set(depths)))
        face_offsets = [0.0014, -0.0012, 0.0009, -0.0009, -0.0013]                    # ring / pupil / cavity / line / lash (all distinct and inside one 0.004 slot)
        self.assertEqual(len(face_offsets), len(set(face_offsets)))
        self.assertTrue(all(abs(o) < 0.002 for o in face_offsets))


EVD = os.path.join(ROOT, "docs/v2_evidence")


def _ev(name):
    with open(os.path.join(EVD, name)) as f:
        return json.load(f)


class MeasuredEvidenceTests(unittest.TestCase):
    """Assertions on the committed measurements of the rendered evidence (docs/v2_evidence/*.json, produced by tools/measure_v2_scenes.py and tools/determinism_v2.py)."""

    def test_parallax_is_measured_and_matches_prediction(self):
        m = _ev("parallax_measurement.json")
        self.assertEqual(m["detected"], m["samples"])
        self.assertLess(m["mean_abs_err_px"], 2.0)
        self.assertLess(m["max_abs_err_px"], 5.0)
        self.assertTrue(m["ordered_by_parallax"])
        self.assertGreater(m["foreground_minus_background_shift_px"], 100)

    def test_lighting_actually_changes(self):
        m = _ev("lighting_measurement.json")
        self.assertTrue(m["monotonic_day_dusk_night"])
        self.assertGreater(m["luma_span"], 0.2)
        self.assertGreater(m["lamp_hall_brighter_than_night_by"], 0.1)
        self.assertTrue(m["phone_shot_bluer_than_night"] and m["lamp_hall_warmer_than_night"])
        self.assertGreater(m["face_crop"]["luma_delta"], 0.1)

    def test_three_runs_are_deterministic(self):
        d = _ev("determinism_v2.json")
        self.assertEqual(len(d["runs"]), 3)
        for name, c in d["comparisons"].items():
            for k in ("plan_sha256", "manifest_core_sha256", "blender_frames", "blender_frames_pixel_sha256", "video_frames", "video_frames_md5_sha256", "audio_decoded_md5", "mp4_file_sha256"):
                self.assertTrue(c[k], f"{name}: {k}")
            self.assertEqual(c["differing_video_frames"], 0)
        for r in d["runs"].values():
            self.assertTrue(r["qc_passed"])
            self.assertEqual(r["video_frames"], 1390)

    def test_final_short_passed_every_qc_gate(self):
        q = _ev("qc_report.json")
        self.assertTrue(q["passed"])
        self.assertEqual(q["n_checks"], 43)
        self.assertTrue(all(q["checks"].values()), [k for k, v in q["checks"].items() if not v])
        self.assertGreaterEqual(q["evidence"]["duration_s"], 45.0)
        self.assertLessEqual(q["evidence"]["duration_s"], 60.0)


class OverlapTests(unittest.TestCase):
    def test_no_accidental_asset_overlap_in_dna(self):
        """two carried bags, or a cap over a hair style that cannot sit under one, are accidental overlaps of assets on the same body"""
        for i in range(400):
            d = dna2.make(f"ov{i}", list(dna2.ROLES)[i % len(dna2.ROLES)])
            acc = set(d["wardrobe"]["accessories"])
            self.assertFalse({"bag", "backpack"} <= acc, d["id"])
            if "cap" in acc:
                self.assertIn(d["hair"]["style"], dna2.CAP_OK, d["id"])

    def test_characters_never_occupy_the_same_space_in_the_short(self):
        import numpy as np
        nar = json.load(open(os.path.join(FIX, "skeleton_v2_narration.json")))
        plan = SD2.build_plan(nar, seed=11)
        actors = SH.build_actors(plan)
        ch = {k: M.sample(a.perf, plan["fps"], 0.0, plan["duration"]) for k, a in actors.items()}
        xa = actors["A"].origin[0] + np.array(ch["A"]["root_x"])
        xd = actors["D"].origin[0] - np.array(ch["D"]["root_x"])                     # D faces left: forward is -x
        half = 0.5 * 1.2 * (actors["A"].P["torso_w"] + actors["D"].P["torso_w"])      # three-quarter torso widths side by side
        self.assertGreaterEqual(float(np.abs(xa - xd).min()), half, "torsos intersect")


class AssetLicenseTests(unittest.TestCase):
    def test_used_assets_are_licensed_hashed_and_proved(self):
        used = [a for a in REG["assets"] if a["status"] == "USED"]
        self.assertTrue(used)
        for a in used:
            self.assertIn(a["policy_decision"], ("ACCEPT", "ACCEPT_WITH_OBLIGATIONS"))
            self.assertTrue(a["sha256"] and a["license_proof"] and a["source_url"] and a["author"] and a["license"])
            self.assertTrue(os.path.exists(os.path.join(ROOT, a["license_proof"])))

    def test_downloaded_files_match_registry_sha256(self):
        n = 0
        for a in REG["assets"]:
            if a.get("local_path") and a.get("sha256") and os.path.exists(os.path.join(ROOT, a["local_path"])):        # big raw binaries are git-ignored: verify whatever is present
                h = hashlib.sha256(open(os.path.join(ROOT, a["local_path"]), "rb").read()).hexdigest()
                self.assertEqual(h, a["sha256"], a["asset_id"])
                n += 1
        self.assertGreaterEqual(n, 3)

    def test_blender_audit_assets_are_all_registered_with_a_decision(self):
        ids = {a["asset_id"] for a in REG["assets"]}
        for need in ("oga_creomoto_stickman_fixed_v1", "blenderstudio_gp_cutout_pepe_v1", "artell_mike_rig_v1", "mpfb2_extension_2_0_17", "mpfb2_generated_humans_cc0", "blendswap_stickman_basic_rig_30507", "stickman_v4gp_2d"):
            self.assertIn(need, ids)
        for a in REG["assets"]:
            if str(a["status"]).startswith(("BLOCKED", "NOT_FOUND", "DOWNLOADED_QUARANTINED")):
                self.assertNotEqual(a["status"], "USED")
                self.assertIn(a["policy_decision"], ("QUARANTINE", "ACCEPT", "ACCEPT_WITH_OBLIGATIONS"))
                self.assertTrue(a["status"] != "DOWNLOADED_QUARANTINED" or a["policy_decision"] == "QUARANTINE", a["asset_id"])
            if a["policy_decision"] == "ACCEPT_WITH_OBLIGATIONS":
                self.assertTrue(a.get("attribution_text"), a["asset_id"])

    def test_unknown_or_gpl_or_nc_never_usable(self):
        for a in REG["assets"]:
            if a["policy_decision"] in ("QUARANTINE", "REJECT"):
                self.assertNotEqual(a["status"], "USED", a["asset_id"])
        from engine.licensing import policy
        self.assertEqual(policy.decide("CC-BY-NC-4.0")["decision"], "REJECT")
        self.assertEqual(policy.decide(None)["decision"], "QUARANTINE")

    def test_registry_records_have_every_required_field(self):
        need = ["asset_id", "source", "source_url", "download_url", "author", "license", "commercial_use", "modification_allowed", "attribution_required", "share_alike", "sha256", "downloaded_at",
                "license_proof", "usage"]
        for a in REG["assets"]:
            for k in need:
                self.assertIn(k, a, (a["asset_id"], k))


class CameraDepthLightingTests(unittest.TestCase):
    def test_parallax_far_vs_near_layers_move_differently(self):
        c0, c1 = Camera(500, 1000, 1.2), Camera(760, 1000, 1.2)
        def scr(cam, par, wx=540.0):
            cx, cy, z = cam.view(par)
            return (wx - cx) * z + C0[0]
        shift = {p: abs(scr(c1, p) - scr(c0, p)) for p in (0.6, 0.86, 1.0, 1.3)}
        self.assertLess(shift[0.6], shift[0.86])
        self.assertLess(shift[0.86], shift[1.0])
        self.assertLess(shift[1.0], shift[1.3])
        self.assertGreater(shift[1.3] - shift[0.6], 100)

    def test_camera_plan_moves_and_focus_racks(self):
        nar = json.load(open(os.path.join(FIX, "skeleton_v2_narration.json")))
        plan = SD2.build_plan(nar, seed=11)
        actors = SH.build_actors(plan)
        cam = SH.build_camera(plan, actors)
        import numpy as np
        self.assertGreater(float(np.ptp(cam["cx"])), 300)
        self.assertGreater(float(np.ptp(cam["zoom"])), 1.0)
        self.assertGreaterEqual(float(np.ptp(cam["focus"])), 0.5)
        self.assertGreater(float(np.ptp(cam["aperture"])), 8)

    def test_lighting_states_change_the_light_map(self):
        import numpy as np
        from engine.shorts.lighting import LightRig
        day, night = LightRig(ambient=(0.72, 0.70, 0.66)), LightRig(ambient=(0.20, 0.22, 0.34))
        cam = Camera()
        a = float(day.lightmap(cam, 0.0, 1.6, {}).mean())
        b = float(night.lightmap(cam, 0.0, 1.6, {}).mean())
        self.assertGreater(a, b * 2.0)


class PlanDeterminismTests(unittest.TestCase):
    def test_v2_plan_is_deterministic_and_semantic(self):
        nar = json.load(open(os.path.join(FIX, "skeleton_v2_narration.json")))
        p1, p2 = SD2.build_plan(nar, seed=11), SD2.build_plan(nar, seed=11)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))
        self.assertEqual(len(p1["shots"]), 20)
        self.assertTrue(45 <= p1["duration"] <= 60)
        for s in p1["shots"]:
            for a in s["actions"]:
                self.assertIn(a["action"], M.ACTIONS)
                self.assertNotIn("frame", a)
                self.assertNotIn("rotation", a)
        tg = {a.get("target") for s in p1["shots"] for a in s["actions"] if isinstance(a.get("target"), str)}
        self.assertTrue({"PHONE", "PERSON_D", "PERSON_A", "CAMERA"} <= tg)

    def test_narration_alignment(self):
        nar = json.load(open(os.path.join(FIX, "skeleton_v2_narration.json")))
        segs = nar["segments"]
        last = -1.0
        for s in segs:
            self.assertGreater(s["start"], last - 1e-6)
            self.assertGreater(s["end"], s["start"])
            ws = s["words"]
            self.assertEqual(len(ws), len(s["text"].split()))
            for a, b in zip(ws, ws[1:]):
                self.assertLessEqual(a["end"], b["start"] + 1e-6)
            last = s["end"]
        plan = SD2.build_plan(nar, seed=11)
        for sh in plan["shots"][1:]:
            beat = next(x for x in segs if x["id"] == sh["beats"][0])
            self.assertAlmostEqual(beat["start"] - sh["t0"], 0.12, places=2)         # every cut lands 0.12 s before its beat


if __name__ == "__main__":
    unittest.main()
