"""Unit tests for every factory subsystem. Run:  .venv/bin/python -m unittest discover -s tests -v
No LLM, no network, no Blender required. Rendering tests use a single 1080x1920 frame from a fixed mini plan."""
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.animation import grammar as MG                          # noqa: E402
from engine.assets import library as LIB                            # noqa: E402
from engine.camera import grammar as CG                             # noqa: E402
from engine.characters import dna as DNA                            # noqa: E402
from engine.crowd.factory import Crowd                              # noqa: E402
from engine.dsl import schema as DSL, variation as VAR              # noqa: E402
from engine.environments import factory as EF                       # noqa: E402
from engine.licensing import policy                                 # noqa: E402
from engine.props import factory as PF                              # noqa: E402
from engine.factory.render import REST_A, REST_B                    # noqa: E402
from engine.shorts import performance as P                          # noqa: E402


def new_perf(seed=1):
    perf = P.Performance(seed=seed)
    P.init_arms(perf, REST_A, REST_B)
    return perf

DOMAIN = json.load(open(os.path.join(ROOT, "domains/money_psychology/domain.json")))
FIX = os.path.join(ROOT, "tests/fixtures")
PLAN = os.path.join(FIX, "mini_plan.json")


class LicensingTests(unittest.TestCase):
    def test_permissive_accepted(self):
        for l in ("CC0-1.0", "MIT", "Apache-2.0", "OFL-1.1"):
            self.assertEqual(policy.decide(l)["decision"], "ACCEPT", l)

    def test_noncommercial_rejected(self):
        for l in ("CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-ND-4.0", "Non-Commercial"):
            self.assertEqual(policy.decide(l)["decision"], "REJECT", l)

    def test_unknown_quarantined(self):
        for l in (None, "", "NOASSERTION", "something-bespoke"):
            self.assertEqual(policy.decide(l)["decision"], "QUARANTINE", repr(l))
        self.assertEqual(policy.decide("MIT", has_license_file=False)["decision"], "QUARANTINE")

    def test_attribution_and_sharealike(self):
        self.assertEqual(policy.decide("CC-BY-4.0")["decision"], "QUARANTINE")           # attribution text missing
        d = policy.decide("CC-BY-SA-4.0", attribution_text="OpenMoji")
        self.assertEqual(d["decision"], "ACCEPT_WITH_OBLIGATIONS")
        self.assertTrue(d["share_alike"] and d["attribution_required"])

    def test_gpl_code_never_enters_core(self):
        d = policy.decide("GPL-3.0", kind="code")
        self.assertEqual(d["decision"], "QUARANTINE")
        self.assertIn("core", d["reason"])


class AssetLibraryTests(unittest.TestCase):
    def test_committed_index_is_valid_and_not_rejected(self):
        lib = LIB.load()
        self.assertGreater(len(lib["assets"]), 20)
        for a in lib["assets"]:
            self.assertEqual(LIB.validate(a), [], a["id"])
            self.assertNotEqual(policy.decide(a["license"], attribution_text=a.get("attribution_text") or a.get("author") or "n/a")["decision"], "REJECT", a["id"])

    def test_invalid_record_rejected(self):
        self.assertTrue(LIB.validate(dict(id="x")))

    def test_resolve_returns_reason(self):
        found, how = LIB.resolve("prop", ("definitely-not-a-real-tag-xyz",), LIB.load())
        self.assertIsNone(found)
        self.assertTrue(how)


class VariationTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(VAR.rng("s", "sh", "a").random(), VAR.rng("s", "sh", "a").random())
        self.assertEqual(VAR.seed_int("s", "sh"), VAR.seed_int("s", "sh"))

    def test_seed_changes_result(self):
        self.assertNotEqual(VAR.seed_int("story1", "sh"), VAR.seed_int("story2", "sh"))
        self.assertNotEqual(VAR.seed_int("s", "sh1"), VAR.seed_int("s", "sh2"))


class CharacterDNATests(unittest.TestCase):
    def test_same_seed_same_dna(self):
        self.assertEqual(DNA.make("office_worker", "a:1"), DNA.make("office_worker", "a:1"))

    def test_variations_are_different_people_same_role(self):
        v = DNA.variations("office_worker", "s", 8)
        self.assertGreater(len({d["id"] for d in v}), 5)
        self.assertTrue(all(d["archetype"] == "office_worker" for d in v))

    def test_all_archetypes_build(self):
        for a in DNA.ARCHETYPES:
            d = DNA.make(a, 1)
            self.assertTrue(DNA.outfit(d), a)
            self.assertEqual(d["archetype"], a)

    def test_skin_tones_are_diverse(self):
        self.assertGreaterEqual(len({DNA.make("customer", i)["skin"] for i in range(30)}), 3)


class CrowdTests(unittest.TestCase):
    def test_deterministic_members(self):
        a, b = Crowd(5, 6), Crowd(5, 6)
        self.assertEqual([m["x"] for m in a.members], [m["x"] for m in b.members])
        self.assertNotEqual([m["x"] for m in a.members], [m["x"] for m in Crowd(6, 6).members])

    def test_far_first_depth_order(self):
        ys = [m["y"] for m in Crowd(3, 10).members]
        self.assertEqual(ys, sorted(ys))

    def test_members_are_varied(self):
        self.assertGreater(len({m["dna"]["id"] for m in Crowd(2, 12).members}), 6)


class EnvironmentTests(unittest.TestCase):
    def test_families_available(self):
        av = set(EF.available())
        for f in ("office_day", "street_dusk", "night_bedroom", "bank_branch", "call_centre", "indian_living_room", "atm_area"):
            self.assertIn(f, av)

    def test_resolve_deterministic_and_variation_differs(self):
        a = EF.resolve(dict(family="office_day", variation=dict(hue=25), seed=1))
        b = EF.resolve(dict(family="office_day", variation=dict(hue=25), seed=1))
        c = EF.resolve(dict(family="office_day", variation=dict(hue=-25), seed=1))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class PropTests(unittest.TestCase):
    def test_at_least_20_props(self):
        self.assertGreaterEqual(len(PF.PROPS), 20)

    def test_every_prop_renders_nonempty(self):
        for name in PF.PROPS:
            L = PF.make_layer(name, 540, 900, 0.8, seed=1)
            self.assertGreater(int(L.base[..., 3].sum()), 0, name)

    def test_recolor_changes_pixels(self):
        a = PF.make_layer("smartphone", 540, 900, 0.8, params=dict(screen="#3b82f6"), seed=1)
        b = PF.make_layer("smartphone", 540, 900, 0.8, params=dict(screen="#ef4444"), seed=1)
        self.assertFalse((a.base == b.base).all())

    def test_screen_variation(self):
        a = PF.make_layer("laptop", 540, 900, 0.8, seed=1)
        b = PF.make_layer("laptop", 540, 900, 0.8, seed=2)
        self.assertFalse(a.base.shape == b.base.shape and (a.base == b.base).all())


class MotionGrammarTests(unittest.TestCase):
    def test_every_action_style_combination_performs(self):
        actions, styles = MG.supported()
        for act in actions:
            for st in styles:
                perf = new_perf()
                MG.perform(perf, act, 1.0, 1.6, st, 0.7)
                perf.state(2.0)                                     # evaluates without error

    def test_unknown_action_raises(self):
        with self.assertRaises(KeyError):
            MG.perform(new_perf(), "moonwalk", 0, 1)

    def test_intensity_changes_motion(self):
        def state_at(i):
            perf = new_perf()
            MG.perform(perf, "reach_for_phone", 0.5, 1.2, "nervous", i)
            return json.dumps(perf.state(1.0), default=str, sort_keys=True)
        self.assertNotEqual(state_at(0.2), state_at(1.0))

    def test_emotion_changes_motion(self):
        def state_at(e):
            perf = new_perf()
            MG.perform(perf, "talk", 0.5, 1.5, e, 0.8)
            return json.dumps(perf.state(1.2), default=str, sort_keys=True)
        self.assertNotEqual(state_at("angry"), state_at("relieved"))

    def test_spec_actions_present(self):
        actions, _ = MG.supported()
        for a in ("talk", "listen", "type", "walk", "point", "reach_for_phone", "hold_phone", "turn", "stand", "sit", "shrug", "hesitate", "look_at"):
            self.assertIn(a, actions)


class CameraGrammarTests(unittest.TestCase):
    def test_intent_mapping(self):
        self.assertEqual(CG.intent_for("fear", "fear", "REVEAL", 5), "realization")
        self.assertEqual(CG.intent_for("isolated", "solemn", "SETUP", 2), "isolation")
        self.assertEqual(CG.intent_for("formal", "calm", "CLIMAX", 2), "authority")

    def test_build_keyframes_valid(self):
        for it in CG.INTENTS:
            g = CG.build(dict(size="medium", intent=it), 0.0, 4.0, seed=3)
            self.assertGreaterEqual(len(g["kf"]), 2)
            self.assertLess(g["kf"][0]["t"], g["kf"][-1]["t"])

    def test_deterministic(self):
        self.assertEqual(CG.build(dict(size="wide", intent="fear"), 0, 3, 7), CG.build(dict(size="wide", intent="fear"), 0, 3, 7))

    def test_push_and_pull(self):
        push = CG.build(dict(size="medium", intent="fear", move="push"), 0, 3, 1)["kf"]
        self.assertGreater(push[-1]["zoom"], push[0]["zoom"])
        pull = CG.build(dict(size="medium", intent="isolation", move="pull"), 0, 3, 1)["kf"]
        self.assertLess(pull[-1]["zoom"], pull[0]["zoom"])


class DSLValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.load(open(PLAN))

    def test_valid_plan_passes(self):
        self.assertTrue(DSL.validate_plan(self.plan, DOMAIN))

    def _bad(self, mutate):
        p = copy.deepcopy(self.plan)
        mutate(p)
        with self.assertRaises(DSL.DSLError):
            DSL.validate_plan(p, DOMAIN)

    def _perf(self, p):
        return next(s for s in p["shots"] if s["treatment"] == "performance")

    def test_rejects_unknown_treatment(self):
        self._bad(lambda p: p["shots"][0].__setitem__("treatment", "blender_python"))

    def test_rejects_gap(self):
        self._bad(lambda p: p["shots"][1].__setitem__("t0", p["shots"][1]["t0"] + 1.0))

    def test_rejects_unknown_action(self):
        self._bad(lambda p: self._perf(p).__setitem__("actions", [dict(action="explode", t=0.1, dur=1)]))

    def test_rejects_unknown_prop(self):
        self._bad(lambda p: self._perf(p).__setitem__("props", [dict(prop="rocket_launcher", at="desk_left")]))

    def test_rejects_bad_intensity(self):
        self._bad(lambda p: self._perf(p).__setitem__("actions", [dict(action="talk", t=0.1, dur=1, intensity=4)]))

    def test_rejects_unknown_camera_intent(self):
        self._bad(lambda p: self._perf(p)["camera"].__setitem__("intent", "dutch_angle_of_doom"))

    def test_rejects_missing_keys(self):
        self._bad(lambda p: p.pop("shots"))

    def test_plan_is_plain_data_no_code(self):
        s = json.dumps(self.plan)
        for bad in ("import bpy", "exec(", "__import__"):
            self.assertNotIn(bad, s)


class DirectorDeterminismTests(unittest.TestCase):
    """Same story + narration + cached analysis -> byte-identical shot plan (no LLM in this path); a different story id changes the variation."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _build(self, name):
        from engine.factory import pipeline
        pdir = os.path.join(self.tmp, name, "project")
        os.makedirs(pdir, exist_ok=True)
        shutil.copy(os.path.join(FIX, "analysis_cache.json"), pdir)
        pj, plan, ar, tl, cont, analysis = pipeline.build_plan(os.path.join(ROOT, "stories/why_smart_people_fall_for_scams.md"),
                                                                 os.path.join(ROOT, "narration/why_smart_people_fall_for_scams.wav.segments.json"),
                                                                 name=name, out_root=self.tmp, log=lambda *a, **k: None)
        return plan

    def test_plan_stable_and_seeded(self):
        a, b = self._build("run_a"), self._build("run_b")
        strip = lambda p: json.dumps({k: v for k, v in p.items() if k not in ("narration_audio",)}, sort_keys=True, default=str, ensure_ascii=False)
        self.assertEqual(hashlib.sha256(strip(a).encode()).hexdigest(), hashlib.sha256(strip(b).encode()).hexdigest())
        self.assertEqual(DSL.validate_plan(a, DOMAIN), True)
        self.assertTrue(a["characters"])
        for ch in a["characters"].values():
            self.assertIn("dna", ch)


class RegressionSceneTests(unittest.TestCase):
    """Frames from the fixed mini plan (2 performance shots + procedural) must render at 1080x1920, be non-blank and byte-deterministic."""

    def test_frames_deterministic_and_nonblank(self):
        import numpy as np
        from engine.factory import render as R
        plan = json.load(open(PLAN))
        quiet = lambda *a, **k: None
        for t in (2.0, 12.5, 22.0):
            f1 = R.Renderer(plan, quiet).frame_at(t, int(t * 30))
            f2 = R.Renderer(plan, quiet).frame_at(t, int(t * 30))
            self.assertEqual(f1.shape[:2], (1920, 1080), t)
            self.assertGreater(float(f1.std()) * 255, 8.0, t)
            self.assertTrue(np.array_equal(f1, f2), f"frame at t={t} is not deterministic")


if __name__ == "__main__":
    unittest.main()
