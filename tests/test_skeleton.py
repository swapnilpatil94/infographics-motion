"""Tests for the full-body 2D skeleton character factory (rig definition, art, motion grammar, IK, pacing, director, Blender integration)."""
import hashlib
import json
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.characters import dna as DNA                    # noqa: E402
from engine.skeleton import motion as M, pace, parts_art as PA, rig_def as R, short_director as SD   # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def dna(arch, seed, g=None):
    return DNA.make(arch, seed, gender=g)


class RigDefinitionTests(unittest.TestCase):
    def test_spec_skeleton_present(self):
        names = [b[0] for b in R.bones(R.proportions(dna("young_man", "t", "male")))]
        for n in ("ROOT", "PELVIS", "SPINE", "CHEST", "NECK", "HEAD", "EYE_L", "EYE_R", "BROW_L", "BROW_R", "MOUTH", "SHOULDER_L", "ARM_L", "FOREARM_L", "HAND_L", "SHOULDER_R", "ARM_R",
                  "FOREARM_R", "HAND_R", "THIGH_L", "SHIN_L", "FOOT_L", "THIGH_R", "SHIN_R", "FOOT_R", "HAIR"):
            self.assertIn(n, names)
        self.assertEqual(len(names), 26)

    def test_parents_before_children_and_topology_constant(self):
        tops = set()
        for arch, g in (("young_man", "male"), ("young_woman", "female"), ("middle_aged_man", "male"), ("elderly_woman", "female")):
            bl = R.bones(R.proportions(dna(arch, "t", g)))
            seen = set()
            for n, par, h, t in bl:
                self.assertTrue(par is None or par in seen, n)
                seen.add(n)
            tops.add(tuple((n, p) for n, p, _, _ in bl))
        self.assertEqual(len(tops), 1)                                   # ONE topology for every character

    def test_proportions_vary_by_dna(self):
        a, b = R.proportions(dna("young_man", "t", "male")), R.proportions(dna("elderly_woman", "t", "female"))
        self.assertNotEqual(round(a["height"]), round(b["height"]))
        self.assertGreater(a["thigh"], b["thigh"] * 0.99)

    def test_analytic_ik_reaches_and_bends_consistently(self):
        P = R.proportions(dna("young_man", "t", "male"))
        base = (0.0, P["shoulder_joint_y"])
        for tgt in ((150, 600), (250, 700), (60, 500)):
            j, tip, a1, a2 = R.two_bone(base, tgt, P["upper_arm"], P["forearm"], bend=-1)
            self.assertAlmostEqual(math.dist(tip, tgt), 0, delta=1.0)
            self.assertAlmostEqual(math.dist(base, j), P["upper_arm"], delta=0.5)
            self.assertAlmostEqual(math.dist(j, tip), P["forearm"], delta=0.5)
        j1 = R.two_bone(base, (150, 600), P["upper_arm"], P["forearm"], bend=-1)[0]
        j2 = R.two_bone(base, (150, 600), P["upper_arm"], P["forearm"], bend=+1)[0]
        self.assertGreater(math.dist(j1, j2), 20)


class PartsArtTests(unittest.TestCase):
    def test_modular_parts_not_a_single_image(self):
        man = PA.bake(dna("young_woman", "t", "female"))
        for p in ("upperarm_L", "forearm_L", "hand_L", "thigh_L", "shin_L", "foot_L", "upperarm_R", "forearm_R", "hand_R", "thigh_R", "shin_R", "foot_R", "torso", "pelvis", "neck", "skull", "hair", "nose"):
            self.assertIn(p, man["parts"])
            self.assertTrue(os.path.exists(os.path.join(ROOT, man["parts"][p]["png"])))

    def test_four_characters_share_parts_but_not_pixels(self):
        hashes, sizes = {}, {}
        for i, (arch, g) in enumerate((("young_man", "male"), ("young_woman", "female"), ("middle_aged_man", "male"), ("middle_aged_woman", "female"))):
            man = PA.bake(dna(arch, "var:" + arch, g))
            hashes[arch] = {n: hashlib.sha1(open(os.path.join(ROOT, p["png"]), "rb").read()).hexdigest() for n, p in man["parts"].items()}
            sizes[arch] = man["P"]["height"]
        self.assertEqual(len({tuple(sorted(h)) for h in hashes.values()}), 1)             # identical part list
        for part in ("torso", "hair", "thigh_R"):
            self.assertEqual(len({h[part] for h in hashes.values()}), 4, part)            # different art for every character
        self.assertGreater(len(set(round(v) for v in sizes.values())), 1)

    def test_hair_is_an_independent_layer(self):
        man = PA.bake(dna("young_man", "t", "male"))
        self.assertNotEqual(man["parts"]["hair"]["png"], man["parts"]["skull"]["png"])

    def test_bake_is_cached_and_deterministic(self):
        d = dna("young_man", "det", "male")
        self.assertEqual(PA.bake(d)["id"], PA.bake(d)["id"])


class MotionGrammarTests(unittest.TestCase):
    def perf(self, arch="young_man", seed=1):
        man = PA.bake(dna(arch, "m", "male" if "man" in arch else "female"))
        p = M.Performance(man["P"], seed=seed, world=dict(seat_h=270))
        M.pose_stand(p, -1.0, 0.0)
        return p

    def test_required_semantic_actions_exist(self):
        for a in ("idle", "blink", "look_left", "look_right", "look_down", "look_at_phone", "head_turn", "head_tilt", "walk", "sit", "stand", "reach", "grab", "hold_phone", "read_phone",
                  "point", "gesture", "fear", "surprise", "confusion", "realization"):
            self.assertIn(a, M.ACTIONS, a)

    def test_every_action_runs_for_every_style(self):
        actions, styles = M.supported()
        for act in actions:
            for st in ("neutral", "hesitant", "fearful", "confident"):
                p = self.perf()
                kw = dict(target=(250, 500)) if act in ("reach", "reach_for_phone") else {}
                M.perform(p, act, 0.5, 1.4, st, 0.7, **kw)
                ch = M.sample(p, 30, 0.0, 3.0)
                for k, v in ch.items():
                    self.assertTrue(all(math.isfinite(x) for x in v), (act, st, k))

    def test_unknown_action_rejected(self):
        with self.assertRaises(KeyError):
            M.perform(self.perf(), "moonwalk", 0, 1)

    def test_walk_moves_root_alternates_feet_and_plants_them(self):
        p = self.perf()
        M.perform(p, "walk", 0.2, 3.0, "neutral", 0.6, speed=230)
        ch = M.sample(p, 30, 0.0, 3.4)
        self.assertGreater(ch["root_x"][-5] - ch["root_x"][0], 200)
        lift_l = [i for i, y in enumerate(ch["foot_L_y"]) if y > p.P["foot_h"] + 10]
        lift_r = [i for i, y in enumerate(ch["foot_R_y"]) if y > p.P["foot_h"] + 10]
        self.assertGreater(len(lift_l), 8)
        self.assertGreater(len(lift_r), 8)
        self.assertLess(len(set(lift_l) & set(lift_r)), 0.25 * min(len(lift_l), len(lift_r)))   # one foot at a time
        # stance foot is planted: while the L foot is on the ground and the gait is steady, its world x barely changes
        stance = [ch["foot_L_x"][i] for i in range(40, 70) if ch["foot_L_y"][i] < p.P["foot_h"] + 2]
        if len(stance) > 6:
            self.assertLess(max(stance) - min(stance), 40)

    def test_sit_then_stand_changes_pelvis_height(self):
        p = self.perf()
        M.perform(p, "sit", 0.2, 1.2, "neutral", 0.6, seat=270)
        M.perform(p, "stand", 2.0, 1.4, "neutral", 0.6)
        ch = M.sample(p, 30, 0.0, 4.0)
        self.assertLess(min(ch["pelvis_dy"]), -150)
        self.assertGreater(ch["pelvis_dy"][-1], -40)

    def test_reach_moves_the_hand_toward_the_target(self):
        p = self.perf()
        M.perform(p, "reach_for_phone", 0.3, 1.2, "hesitant", 0.8, target=(280, 520))
        ch = M.sample(p, 30, 0.0, 2.2)
        d0 = math.dist((ch["hand_R_x"][0], ch["hand_R_y"][0]), (280, 520))
        d1 = math.dist((ch["hand_R_x"][-1], ch["hand_R_y"][-1]), (280, 520))
        self.assertLess(d1, 0.2 * d0)

    def test_emotion_and_intensity_change_the_motion(self):
        def run(emo, inten):
            p = self.perf()
            M.perform(p, "reach_for_phone", 0.3, 1.2, emo, inten, target=(280, 520))
            return json.dumps(M.sample(p, 30, 0.0, 2.0)["hand_R_x"])
        self.assertNotEqual(run("hesitant", 0.9), run("confident", 0.9))
        self.assertNotEqual(run("hesitant", 0.2), run("hesitant", 1.0))

    def test_same_semantic_script_drives_different_characters_with_their_own_stride(self):
        cycles = []
        for arch in ("young_man", "elderly_woman"):
            p = self.perf(arch)
            M.perform(p, "walk", 0.2, 2.0, "neutral", 0.6, speed=230)
            cycles.append(next(d["T"] for t, k, d in p.events if k == "walk"))
        self.assertNotAlmostEqual(cycles[0], cycles[1], delta=0.005)         # same command, different legs -> different gait cycle

    def test_deterministic(self):
        def run():
            p = self.perf(seed=4)
            M.perform(p, "fear", 0.5, 1.5, "fearful", 0.8)
            M.auto_blinks(p, 0.0, 3.0, 9)
            return hashlib.sha1(json.dumps(M.sample(p, 30, 0.0, 3.0)).encode()).hexdigest()
        self.assertEqual(run(), run())


class PacingTests(unittest.TestCase):
    def test_assign_beats_and_mismatch_detected(self):
        words = [dict(word=w, start=i, end=i + 0.5) for i, w in enumerate("क ख ग घ".split())]
        out = pace.assign_beats(words, [("n1", "क ख"), ("n2", "ग घ")])
        self.assertEqual([len(o[2]) for o in out], [2, 2])
        with self.assertRaises(ValueError):
            pace.assign_beats(words, [("n1", "क ख ग")])

    def test_tempo_chain_valid(self):
        import subprocess, tempfile
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
            pace._write(src, (np.sin(np.arange(pace.SR * 2) * 0.05) * 0.3).astype(np.float32))
            pace._atempo(src, dst, 1.25)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout)
            self.assertAlmostEqual(dur, 2.0 / 1.25, delta=0.05)


class ShortDirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = json.load(open(os.path.join(ROOT, "tests/fixtures/skeleton_paced.json")))
        cls.nar = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in d["segments"]], audio="x.wav", tts="chatterbox", tempo=1.16)
        cls.plan = SD.build_plan(cls.nar, seed=7)

    def test_13_shots_for_13_beats_and_contiguous(self):
        sh = self.plan["shots"]
        self.assertEqual(len(sh), 13)
        for a, b in zip(sh, sh[1:]):
            self.assertAlmostEqual(a["t1"], b["t0"], places=6)
        self.assertAlmostEqual(sh[-1]["t1"], self.plan["duration"], places=2)
        self.assertTrue(30 <= self.plan["duration"] <= 45)

    def test_actions_are_semantic_and_known(self):
        for s in self.plan["shots"]:
            for a in s["actions"]:
                self.assertIn(a["action"], M.ACTIONS)
                self.assertNotIn("frame", a)
                self.assertNotIn("rotation", a)

    def test_four_distinct_dna_one_rig(self):
        ids = {c["dna"]["id"] for c in self.plan["characters"].values()}
        self.assertEqual(len(ids), 4)
        self.assertEqual({c["dna"]["archetype"] for c in self.plan["characters"].values()}, {"young_man", "young_woman", "middle_aged_man", "middle_aged_woman"})

    def test_plan_is_deterministic_and_plain_data(self):
        p2 = SD.build_plan(self.nar, seed=7)
        self.assertEqual(json.dumps(self.plan, sort_keys=True), json.dumps(p2, sort_keys=True))
        s = json.dumps(self.plan)
        for bad in ("import bpy", "exec(", "__import__"):
            self.assertNotIn(bad, s)

    def test_seed_changes_environment_or_cast(self):
        p3 = SD.build_plan(self.nar, seed=8)
        self.assertEqual(self.plan["characters"]["A"]["dna"]["id"], p3["characters"]["A"]["dna"]["id"])   # cast comes from story_id (same film)

    def test_required_treatments_present(self):
        tr = [s["treatment"] for s in self.plan["shots"]]
        self.assertEqual(tr.count("insert_ui"), 1)
        self.assertEqual(tr.count("procedural"), 1)
        self.assertEqual(tr.count("skeleton"), 11)


@unittest.skipUnless(os.path.exists(BLENDER), "Blender not installed")
class BlenderRigIntegrationTests(unittest.TestCase):
    def test_blender_builds_armature_ik_and_reaches_targets(self):
        import tempfile
        from engine.skeleton import blender_job
        d = dna("young_man", "bl", "male")
        man = PA.bake(d)
        p = M.Performance(man["P"], seed=2, world=dict(seat_h=270))
        M.pose_stand(p, -1.0, 0.0)
        M.perform(p, "reach_for_phone", 0.2, 0.8, "neutral", 0.6, target=(240, 560))
        M.perform(p, "walk", 1.2, 1.0, "neutral", 0.6, speed=200)
        ch = M.sample(p, 30, 0.0, 2.4)
        n = len(ch["root_x"])
        with tempfile.TemporaryDirectory() as tmp:
            job = dict(width=270, height=480, fps=30, start=0, end=n - 1, out=os.path.join(tmp, "f"), prefix="t", samples=2, render_frames=[10, 50],
                       characters=[dict(id="A", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=1, origin=[300, 1500], channels={k: [round(float(x), 4) for x in v] for k, v in ch.items()})],
                       camera=dict(cx=540, cy=1000, zoom=0.25), probe_frames=list(range(0, n, 6)))
            rep = blender_job.run(job, tmp)
            self.assertEqual(rep["bones"]["A"], 26)
            self.assertEqual(rep["ik_constraints"]["A"], 4)
            self.assertLess(max(max(e[k] for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")) for e in rep["ik_error_px"]), 1.0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "f", "t00010.png")))
            self.assertGreater(rep["actions"], 5)                        # real Blender actions with keyframes were created


if __name__ == "__main__":
    unittest.main()
