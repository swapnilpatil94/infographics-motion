"""Asset-utilisation audit: the generalised prop primitive, the run cycle, the reach guard, the combination matrix, art-direction styles and the audit's own data files (no Blender)."""
import json
import math
import os
import unittest

from engine.skeleton import dna2, lab, lab_dna as LD, motion as M, motion_v2 as MV, parts_art2 as PA2, props4 as P4, rig_def as R, short, styles as ST, topic_build as TB, topic_story as TS, auto_director as AD

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DNA = LD.production_characters()["A"]


def _actor(start="stand"):
    plan = lab._plan([dict(dna=DNA, view="three_quarter", start=start)], 4.0)
    return short.build_actors(plan)["c000"]


class PropPrimitiveTests(unittest.TestCase):
    def test_all_ten_props_contact_and_reach(self):
        a = _actor()
        an = a.man["hand_anchors"]
        for prop in [p for p in P4.PROPS if p not in P4.EXTRA]:
            a = _actor()
            recs = P4.perform(a.perf, an, prop, 0.3, "R", False)
            for r in recs:
                self.assertTrue(r["reachable"], (prop, r["phase"]))
                self.assertLessEqual(r["contact_err_px"], 3.0, (prop, r["phase"]))

    def test_fk_contact_matches_solver(self):
        a = _actor()
        an = a.man["hand_anchors"]
        recs = P4.perform(a.perf, an, "CUP", 0.3, "R", False)
        c = next(r for r in recs if r["phase"] == "CONTACT")
        t_arrive = c["t"] + P4.DUR["CONTACT"] * 0.98
        fk, _ = P4.grip_point(a.perf, an, c["pose"], "grip", t_arrive)
        self.assertLess(math.dist(fk, c["target"]), 3.0)


class ReachGuardTests(unittest.TestCase):
    def test_hands_never_beyond_reach_or_inside_elbow_limit(self):
        a = _actor()
        M.perform(a.perf, "point", 0.2, 1.0, "neutral", 0.6, hand="R")
        M.perform(a.perf, "run", 1.4, 1.5, "neutral", 0.6, speed_scale=0.55)
        a.channels = M.sample(a.perf, 30, 0.0, 4.0)
        short._clamp_reach(a, 30)
        arm = a.P["upper_arm"] + a.P["forearm"]
        for f in range(len(a.channels["root_x"])):
            sx, sy = a.perf.shoulder(f / 30)
            for s in "LR":
                d = math.hypot(a.channels[f"hand_{s}_x"][f] - sx - a.perf.so["s" + s], a.channels[f"hand_{s}_y"][f] - sy)
                self.assertLessEqual(d, 0.985 * arm + 0.01)
                self.assertGreaterEqual(d, 0.32 * arm - 0.01)


class RunCycleTests(unittest.TestCase):
    def test_run_legs_reachable_with_flight_phase(self):
        a = _actor()
        M.perform(a.perf, "run", 0.2, 2.0, "neutral", 0.6, speed_scale=0.55)
        L = a.P["thigh"] + a.P["shin"]
        airborne = 0
        for f in range(0, 75):
            t = f / 30
            hx, hy = a.perf.hip(t)
            ys = []
            for s in "LR":
                fy = a.perf.v(f"foot_{s}_y", t)
                ys.append(fy)
                self.assertLessEqual(math.hypot(a.perf.v(f"foot_{s}_x", t) - hx, fy - hy), 0.99 * L + 1)
            airborne += min(ys) > a.P["foot_h"] + 3
        self.assertGreater(airborne, 3, "a run has frames where both feet are off the ground")

    def test_creomoto_cycle_data(self):
        d = json.load(open(os.path.join(ROOT, "assets/library/creomoto_run_cycle.json")))
        self.assertEqual(d["frames"], 20)
        self.assertIn("CC0", d["source"])


class FaceAtomTests(unittest.TestCase):
    def test_atom_ids_and_action(self):
        self.assertEqual(len(PA2.FACE_ATOMS), 20)
        self.assertEqual(sorted(PA2.FACE_ATOM_IDS.values()), list(range(1, 21)))
        a = _actor()
        M.perform(a.perf, "face_atom", 0.5, 1.0, "neutral", 0.5, name="fear")
        self.assertEqual(round(a.perf.v("face_atom_id", 0.4)), 0)
        self.assertEqual(round(a.perf.v("face_atom_id", 1.0)), PA2.FACE_ATOM_IDS["fear"])
        self.assertEqual(round(a.perf.v("face_atom_id", 1.7)), 0)

    def test_atom_svg_bakes_on_the_head_canvas(self):
        man = PA2.bake_face_atoms(DNA, "three_quarter", ["fear", "smile"])
        self.assertIn("faceatom_fear", man["parts"])
        self.assertEqual(man["parts"]["faceatom_fear"]["res"], man["parts"]["skull"]["res"])


class CombinationMatrixTests(unittest.TestCase):
    def test_existing_seeded_characters_unchanged(self):
        self.assertEqual(dna2.make("x:1", "young_man")["id"], "cdna_9c86892076")           # extending the vocabulary must not change any existing character

    def test_new_roles_valid(self):
        for r in ("delivery_worker", "security_guard", "teacher", "parent", "customer"):
            self.assertEqual(dna2.validate(dna2.make("t:1", r)), [])

    def test_every_open_peeps_head_is_reachable_through_overrides(self):
        reach = dna2.FEM_HAIR | dna2.MASC_HAIR | dna2.EXTRA_HAIR_MASC | dna2.EXTRA_HAIR_FEM | dna2.NOVELTY_HAIR | {"Gray Medium"}
        atoms = json.load(open(os.path.join(ROOT, "docs/asset_audit/openpeeps_atoms.json")))["atoms"]
        heads = {a["name"] for a in atoms if a["category"] == "head"}
        self.assertEqual(len(heads), 46)
        self.assertEqual(heads - reach, set())

    def test_selection_is_structural_never_colour(self):
        pool = LD.pool(120, "t")
        chosen, rep = LD.select_distinct(pool, 20, min_axes=5)
        self.assertGreaterEqual(rep["min_axes_differing"], 5)
        # a pure palette change is not a different character
        a = dna2.make("c:1", "young_man")
        b = dna2.make("c:1", "young_man", {"wardrobe.palette": "rust"})
        self.assertEqual(LD.distance(LD.features(a), LD.features(b)), 0)

    def test_15_archetypes_and_3_production_characters(self):
        self.assertEqual(len(LD.ARCHETYPES), 15)
        for n in LD.ARCHETYPES:
            self.assertEqual(dna2.validate(LD.archetype(n)), [], n)
        p = LD.production_characters()
        self.assertEqual(set(p), {"A", "B", "C"})
        self.assertEqual(len({LD.features(d)["head"] for d in p.values()}), 3)


class StyleTests(unittest.TestCase):
    def test_two_topics_differ_by_system(self):
        sa = TS.write("fake WhatsApp investment group", use_llm=False)
        sb = TS.write("lottery prize processing fee scam", use_llm=False)
        pa = AD.build_plan(sa, TB.draft_narration(sa), name="a")
        pb = AD.build_plan(sb, TB.draft_narration(sb), name="b")
        self.assertNotEqual(pa["environment"]["family"], pb["environment"]["family"])
        self.assertNotEqual(sa["cast"]["protagonist"]["gender"], sb["cast"]["protagonist"]["gender"])
        self.assertNotEqual(pa["targets"]["PHONE"], pb["targets"]["PHONE"])
        self.assertNotEqual(pa["characters"]["A"]["origin"], pb["characters"]["A"]["origin"])
        self.assertNotEqual([s["camera"]["size"] for s in pa["shots"] if s.get("camera")][:6], [s["camera"]["size"] for s in pb["shots"] if s.get("camera")][:6])
        self.assertNotEqual(len(sa["beats"]), len(sb["beats"]))                            # different act arc
        self.assertGreater(pb["shots"][2]["lighting"].get("sun", 0), 0)                    # daylight vs moonlight
        self.assertTrue(any(a["action"] == "face_atom" for s in pb["shots"] for a in s.get("actions", [])))
        self.assertFalse(any(a["action"] == "face_atom" for s in pa["shots"] for a in s.get("actions", [])))

    def test_styled_plans_animate(self):
        s = TS.write("lottery prize processing fee scam", use_llm=False)
        p = AD.build_plan(s, TB.draft_narration(s), name="b")
        TB.bake_cast(p)
        actors = short.build_actors(p)
        self.assertEqual(set(actors), {"A", "D"})


class AuditDataTests(unittest.TestCase):
    def test_inventory_covers_every_registry_record(self):
        inv = json.load(open(os.path.join(ROOT, "docs/asset_audit/inventory.json")))
        reg = json.load(open(os.path.join(ROOT, "assets/registry/asset_registry.json")))["assets"]
        ids = {r["id"] for r in inv["records"]}
        self.assertEqual({r["asset_id"] for r in reg} - ids, set())
        for r in inv["records"]:
            for k in ("source", "license", "vector_or_raster", "blender_compat", "grease_pencil_compat", "rig_compat", "modifiable", "production_use", "reason_unused", "classes"):
                self.assertIn(k, r)

    def test_open_peeps_atlas_counts(self):
        a = json.load(open(os.path.join(ROOT, "docs/asset_audit/openpeeps_atoms.json")))["summary"]
        self.assertEqual({k: a[k]["n"] for k in ("head", "face", "facial-hair", "accessories", "body")}, {"head": 46, "face": 30, "facial-hair": 17, "accessories": 9, "body": 30})

    def test_usage_trace_only_reads_a_few_atoms(self):
        tr = json.load(open(os.path.join(ROOT, "docs/asset_audit/usage_trace.json")))["files"]
        atoms = [k for k in tr if "Separate Atoms" in k]
        self.assertLess(len(atoms), 12)                                                   # the finding: production reads a tiny fraction of the 1074 SVGs


if __name__ == "__main__":
    unittest.main()
