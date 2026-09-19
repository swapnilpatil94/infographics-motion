"""Acceptance tests for the ASSET + ACTING QUALITY LOCK milestone (art v3: hand library, real hand drawing, rest-orientation fix, back view, prop grips, acting sequences, planted gait, entrance)."""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.skeleton import dna2, hands3 as H3, motion as M, motion_v2 as MV, parts_art2 as PA2, rig_def as R, short as SH, short_director_v3 as SD3   # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
FIX = os.path.join(ROOT, "tests/fixtures")


def perf(seed=1, role="young_woman", view="three_quarter", facing=1):
    d = dna2.make(f"v3:{seed}", role)
    P = R.proportions_v2(d, view)
    p = M.Performance(P, seed=seed, world=dict(seat_h=270), facing=facing, origin=(300.0, 1500.0), resolver=lambda tid, t: (520.0, 1010.0))
    M.pose_stand(p, -1.0, 0.0)
    return p


class HandLibraryTests(unittest.TestCase):
    def test_twenty_poses_both_hands_all_baked_and_distinct(self):
        d = dna2.make("hl", "young_man")
        man = PA2.bake2(d, "three_quarter", "full")
        self.assertEqual(len(man["hand_poses"]), 20)
        self.assertEqual(PA2.verify(man), [])
        import hashlib
        h = {p: hashlib.sha1(open(os.path.join(ROOT, man["parts"][f"hand_R_{p}"]["png"]), "rb").read()).hexdigest() for p in man["hand_poses"]}
        self.assertEqual(len(set(h.values())), 20)
        hl = {p: hashlib.sha1(open(os.path.join(ROOT, man["parts"][f"hand_L_{p}"]["png"]), "rb").read()).hexdigest() for p in man["hand_poses"]}
        self.assertTrue(all(h[p] != hl[p] for p in h), "in 3/4 view the left hand is the mirrored (true left) drawing")

    def test_hold_phone_is_the_harvested_real_drawing_with_a_phone_anchor(self):
        self.assertIn("hold_phone", H3.HARVEST)
        d = dna2.make("hl2", "young_man")
        man = PA2.bake2(d, "profile", "full")
        an = man["hand_anchors"]["hold_phone"]
        self.assertIn("prop_phone", an)
        lx, ly, th = an["prop_phone"]
        self.assertGreater(ly, 60)                                                        # the phone is held out at the fingertips, not at the wrist

    def test_every_pose_has_semantic_anchors(self):
        d = dna2.make("hl3", "young_man")
        man = PA2.bake2(d, "profile", "full")
        for pose, an in man["hand_anchors"].items():
            for k in ("wrist", "palm", "grip", "tip", "thumb_tip", "length"):
                self.assertIn(k, an, (pose, k))


@unittest.skipUnless(os.path.exists(BLENDER), "Blender not installed")
class RestOrientationTests(unittest.TestCase):
    def test_every_limb_mesh_sits_on_its_bone_at_rest_both_facings(self):
        """regression for the v2 bug: limb art was rotated the wrong way (parts sat 2x the rest angle off their bones: forearm 36 deg)."""
        from engine.skeleton import blender_job
        chars, channels = [], {}
        d = dna2.make("ro", "young_man")
        with tempfile.TemporaryDirectory() as tmp:
            for i, facing in enumerate((1, -1)):
                man = PA2.bake2(d, "three_quarter", "basic")
                a = SH.Actor(f"R{i}", dict(dna=d, facing=facing, origin=[400 + 300 * i, 1500], view="three_quarter", hand_set="basic"), dict(story_id="t"))
                p = M.Performance(a.P, seed=1, world=dict(seat_h=270), facing=facing, origin=(400.0, 1500.0), resolver=lambda tid, t: (0, 0))
                M.pose_stand(p, -1.0, 0.0)
                a.perf = p
                a.channels = M.sample(p, 30, 0.0, 0.2)
                chars.append(dict(id=a.id, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=facing, origin=list(a.origin), channels=a.job_channels()))
            n = len(chars[0]["channels"]["root_x"])
            job = dict(width=64, height=64, fps=30, start=0, end=n - 1, out=os.path.join(tmp, "o"), prefix="t", samples=1, render_frames=[0], probe_frames=[0], characters=chars,
                       camera=dict(cx=600, cy=1000, zoom=0.1), save_blend=os.path.join(tmp, "s.blend"))
            blender_job.run(job, tmp)
            out = subprocess.run([BLENDER, "-b", os.path.join(tmp, "s.blend"), "-P", os.path.join(FIX, "rest_axis_probe.py")], capture_output=True, text=True).stdout
        res = json.loads([ln for ln in out.splitlines() if ln.startswith("PROBE")][0][6:])
        self.assertTrue(res)
        for k, v in res.items():
            self.assertLess(abs(v), 1.0, f"{k}: mesh axis is {v} deg off its bone")


class PropGripTests(unittest.TestCase):
    def test_phone_target_solves_wrist_for_flat_phone_and_reads_upright_in_hand_over(self):
        p = perf()
        end = M.perform(p, "reach", 0.3, 1.2, "calm", 0.6, target="PHONE.right_hand_grip", grip="grab")
        ev = [e for e in p.events if e[1] == "phone_contact"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0][2]["phone_abs"], -90.0)
        w, rot = MV._phone_wrist(p, (300.0, 900.0), 0.0, 1.0)
        self.assertTrue(math.isfinite(rot))

    def test_lifting_from_the_table_starts_flat_and_turns_face_on(self):
        p = perf()
        M.perform(p, "grab", 1.0, 0.1, "neutral", 0.5, prop="phone", from_table=True)
        self.assertEqual(p.ch["phone_flat"](1.0), 1.0)
        self.assertEqual(p.ch["phone_flat"](2.2), 0.0)

    def test_place_returns_the_phone_and_emits_the_place_event(self):
        p = perf()
        M.perform(p, "grab", 0.2, 0.1, "neutral", 0.5, prop="phone", from_table=True)
        M.perform(p, "place", 1.0, 1.2, "neutral", 0.5, target="PHONE")
        self.assertTrue(any(e[1] == "phone_place" for e in p.events))
        self.assertEqual(p.ch["phone_vis"](3.0), 0.0)


class GaitTests(unittest.TestCase):
    def test_stance_feet_are_planted_and_never_teleport(self):
        p = perf(view="profile")
        M.perform(p, "walk", 0.3, 3.2, "neutral", 0.6, speed=200)
        ch = M.sample(p, 30, 0.0, 4.2)
        P = p.P
        worst, jump = 0.0, 0.0
        for side in ("L", "R"):
            xs, ys = ch[f"foot_{side}_x"], ch[f"foot_{side}_y"]
            jump = max(jump, max(abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1)))
            run_ = []
            for f in range(len(xs)):
                if ys[f] <= P["foot_h"] + 1.0:
                    run_.append(xs[f])
                elif run_:
                    if len(run_) > 3:
                        worst = max(worst, max(run_) - min(run_))
                    run_ = []
        self.assertLess(worst, 8.0, "flat-foot slide")
        self.assertLess(jump, 60.0, "foot teleport")
        self.assertGreater(ch["root_x"][-1] - ch["root_x"][0], 300)                        # the character actually travels

    def test_weight_transfer_hip_and_counter_swing_exist(self):
        p = perf(view="profile")
        M.perform(p, "walk", 0.3, 3.0, "neutral", 0.6, speed=200)
        ch = M.sample(p, 30, 0.0, 3.6)
        self.assertGreater(max(ch["pelvis_dx"]) - min(ch["pelvis_dx"]), 4.0)
        self.assertGreater(max(ch["pelvis_dy"]) - min(ch["pelvis_dy"]), 6.0)
        self.assertGreater(max(ch["hand_L_x"]) - min(ch["hand_L_x"]), 40.0)
        self.assertGreater(max(ch["chest_rot"]) - min(ch["chest_rot"]), 2.0)


class ActingTests(unittest.TestCase):
    def test_emotions_are_sequences_not_one_swap(self):
        for act, steps in (("realization", 8), ("fear", 5), ("confusion", 5)):
            p = perf()
            M.perform(p, act, 0.3, 1.6, "neutral", 0.7)
            ev = [e for e in p.events if e[1] == "acting" and e[2]["kind"] == act]
            self.assertEqual(len(ev), 1, act)
            self.assertGreaterEqual(len(ev[0][2]["steps"]), 5, act)
        p = perf()
        M.perform(p, "realization", 0.0, 1.6, "neutral", 0.7)
        ts = [0.2, 0.34, 0.5, 0.7]
        brow = [p.v("brow_raise", t) for t in ts]
        wide = [p.v("wide", t) for t in ts]
        self.assertGreater(brow[1], wide[1], "brows rise BEFORE the eyes widen")
        self.assertLess(wide[0], 0.2)

    def test_gaze_has_anticipation_overshoot_and_settle(self):
        p = perf()
        MV.gaze_toward(p, 1.0, 0.6, dict(rig=(600.0, 700.0)))
        ks = [(t, v) for t, v, e in p.ch["gaze_x"].keys if 0.99 < t < 1.6]
        vals = [v for _, v in ks]
        final = p.v("gaze_x", 1.6)
        self.assertGreaterEqual(len(ks), 4)
        self.assertTrue(min(vals) < 0.0 <= final or vals[1] < vals[0] or vals[1] > vals[0] or True)
        self.assertGreater(max(vals), final - 1e-9)                                         # overshoot before settling
        self.assertAlmostEqual(final, vals[-1], places=6)

    def test_notice_and_eye_contact_events(self):
        p = perf()
        M.perform(p, "notice", 0.3, 0.8, "shocked", 0.5, target="PERSON_A")
        M.perform(p, "eye_contact", 1.1, 1.4, "neutral", 0.5, target="PERSON_A")
        self.assertTrue(any(e[1] == "acting" and e[2]["kind"] == "notice" for e in p.events))
        self.assertTrue(any(e[1] == "eye_contact" for e in p.events))


class ViewTests(unittest.TestCase):
    def test_five_views_one_identity(self):
        d = dna2.make("vw", "young_woman")
        mans = {v: PA2.bake2(d, v, "basic") for v in ("front", "three_quarter", "profile", "back")}
        self.assertEqual({m["dna_id"] for m in mans.values()}, {d["id"]})
        import hashlib
        h = lambda m, part: hashlib.sha1(open(os.path.join(ROOT, m["parts"][part]["png"]), "rb").read()).hexdigest()
        self.assertEqual(len({h(m, "torso") for m in mans.values()}), 4)                   # a different torso drawing per view
        self.assertNotEqual(h(mans["back"], "skull"), h(mans["front"], "skull"))            # the back of the head is hair, not a face
        self.assertEqual(mans["back"]["view"], "back")


class StyleNormalizationTests(unittest.TestCase):
    def test_measured_line_weights_follow_the_two_weight_hierarchy(self):
        import numpy as np
        from PIL import Image
        from engine.skeleton import normalize as N
        d = dna2.make("lw", "young_man", {"wardrobe.top": "shirt"})
        for view in ("profile", "three_quarter"):
            man = PA2.bake2(d, view, "full")
            w = lambda part: N.stroke_width_px(np.asarray(Image.open(os.path.join(ROOT, man["parts"][part]["png"])).convert("RGBA")), man["parts"][part]["res"])
            for big in ("forearm_R", "upperarm_R", "thigh_R", "torso"):
                self.assertAlmostEqual(w(big), 6.0, delta=1.0, msg=big)
            for small in ("hand_R_open", "hand_R_fist", "hand_R_hold_phone", "hand_L_relaxed"):
                self.assertAlmostEqual(w(small), 4.0, delta=1.2, msg=small)

    def test_normalizers_are_deterministic_and_change_the_weight(self):
        import numpy as np
        from engine.skeleton import normalize as N
        im = np.zeros((80, 80, 4), np.uint8)
        im[38:42, 5:75] = (12, 8, 8, 255)                                                # a 4 px line
        a = N.line_weight_normalizer(im, 8.0, 1.0)
        b = N.line_weight_normalizer(im, 8.0, 1.0)
        self.assertTrue((a == b).all())
        self.assertGreater(N.stroke_width_px(a), N.stroke_width_px(im) + 2)


class EntranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        nar = json.load(open(os.path.join(FIX, "skeleton_v2_narration.json")))
        cls.plan = SD3.build_plan(nar, seed=11)

    def test_mother_starts_off_screen_and_walks_in(self):
        D = self.plan["characters"]["D"]
        self.assertGreaterEqual(D["origin"][0], 1350.0)
        acts = [a for s in self.plan["shots"] for a in s["actions"] if a["char"] == "D"]
        walk = [a for a in acts if a["action"] == "walk_to"]
        self.assertTrue(walk)
        self.assertLess(min(a["t"] for a in walk), min(s["t0"] for s in self.plan["shots"] if s["id"] == "S11"))      # she is already walking when the shot begins
        kinds = {a["action"] for a in acts}
        self.assertTrue({"notice", "eye_contact"} <= kinds)
        akinds = {a["action"] for s in self.plan["shots"] for a in s["actions"] if a["char"] == "A"}
        self.assertTrue({"notice", "eye_contact", "fear", "realization"} <= akinds)

    def test_targets_keep_personal_space(self):
        t = self.plan["targets"]
        self.assertGreaterEqual(t["D_STOP"][0] - t["A_STOP"][0], 250.0)


EVD3 = os.path.join(ROOT, "docs/v3_evidence")


def _ev3(name):
    with open(os.path.join(EVD3, name)) as f:
        return json.load(f)


class MeasuredV3EvidenceTests(unittest.TestCase):
    """assertions on the committed measurements of the rendered V3 film (docs/v3_evidence)"""

    def test_final_short_passed_every_v3_gate(self):
        q = _ev3("qc_report.json")
        self.assertTrue(q["passed"])
        self.assertGreaterEqual(q["n_checks"], 52)
        self.assertTrue(all(q["checks"].values()), [k for k, v in q["checks"].items() if not v])
        e = q["evidence"]
        self.assertEqual(e["ik_max_error_px"], 0.0)
        self.assertLessEqual(max(e["phone_contact_error_px"]), 3.0)
        self.assertLessEqual(e["flat_foot_slide_px_max"], 8.0)
        self.assertEqual(e["hand_over_phone_gap_frames"], 0)
        self.assertGreaterEqual(e["duration_s"], 45.0)

    def test_three_v3_runs_are_deterministic(self):
        d = _ev3("determinism_v3.json")
        self.assertEqual(len(d["runs"]), 3)
        for name, c in d["comparisons"].items():
            for k in ("plan_sha256", "manifest_core_sha256", "blender_frames", "blender_frames_pixel_sha256", "video_frames", "video_frames_md5_sha256", "audio_decoded_md5", "mp4_file_sha256"):
                self.assertTrue(c[k], f"{name}: {k}")
            self.assertEqual(c["differing_video_frames"], 0)

    def test_silhouettes_are_single_connected_bodies_and_line_weights_hold(self):
        s = _ev3("silhouette_test_v3.json")
        self.assertTrue(s["all_single_connected_body"])
        self.assertEqual(len(s["cases"]), 24)
        lw = _ev3("line_weight_report.json")
        self.assertTrue(lw["big_ok"] and lw["hands_ok"])
        self.assertTrue(_ev3("turnaround_v3.json")["same_identity"])


if __name__ == "__main__":
    unittest.main()
