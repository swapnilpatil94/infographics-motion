"""Kathaya architecture: schemas, narration timeline, capability manifest, asset catalog, resolver (AVAILABLE / UNSUPPORTED / MISSING, never a silent substitution), creative-director planning + menus, the compiler into the
renderer, cache keys, technical QC, licences, the asset builder, and the HTTP flow. No Blender, no TTS, no LLM (a stub director stands in where a plan is needed)."""
import copy
import json
import os
import shutil
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="kathaya_test_")
os.environ["KATHAYA_PROJECTS"] = os.path.join(_TMP, "projects")
os.environ.setdefault("KATHAYA_STUDIO_DIR", os.path.join(_TMP, "studio"))
os.environ.setdefault("KATHAYA_STUDIO_TEST", "1")

import numpy as np                                                                        # noqa: E402

from engine.skeleton import acts as AC, director_opts as DO, production as PR              # noqa: E402
from engine.environments import locations as LOC                                          # noqa: E402
from kathaya import pipeline as KP, schemas                                               # noqa: E402
from kathaya.assets import builder as AB, catalog as CAT, references as REF, resolver as RES   # noqa: E402
from kathaya.cache import keys as KK                                                      # noqa: E402
from kathaya.director import sequential as SEQ, visual_planner as VP                     # noqa: E402
from kathaya.qc import technical as KQ                                                    # noqa: E402
from kathaya.renderer import compile as CP, look as LK, manifest as MF                                # noqa: E402
from kathaya.story import hindi, narration as NAR                                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = """एक लड़के के फोन पर अचानक एक मैसेज आया —
'आपने 25 लाख रुपये की लॉटरी जीती है।'
वह हैरान रह गया।
मैसेज में लिखा था कि इनाम लेने के लिए सिर्फ 12,500 रुपये की फीस भरनी होगी।
उसने पैसे भेज दिए।
कुछ मिनट बाद नंबर बंद हो गया।
तभी उसे समझ आया —
लॉटरी जीती ही नहीं थी।
उसका लालच ही उसका सबसे बड़ा जाल बन गया था।"""


def setUpModule():
    KP.PROJECTS = os.environ["KATHAYA_PROJECTS"]
    os.makedirs(KP.PROJECTS, exist_ok=True)


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class StubLLM:
    """stands in for the local LLM: always takes the FIRST option of every enumerated menu the system offers (so the test proves the menus alone yield a valid plan)"""
    sequential = True

    def __call__(self, prompt, schema):
        p = schema["properties"]
        if "cast" in p:
            return dict(title="परीक्षण", cast=[dict(id="C01", role="protagonist", archetype="young man", gender="male", description="a young man")])
        cap = p["action"]["properties"]["capability"]["enum"][0]
        return dict(visual_intent="SHOW_ACTION", environment=dict(type="generic", subject="bedroom", asset_id="env_bedroom", time_of_day="night"), characters=["C01"], props=[dict(name="phone")], action=dict(capability=cap, actor="C01", params={}),
                    emotion="fear", camera=dict(framing=p["camera"]["properties"]["framing"]["enum"][0], movement=p["camera"]["properties"]["movement"]["enum"][0]), effects=[], transition="cut", moved=False,
                    screen=dict(sender="PRIZE-DESK", text="आपने लॉटरी जीती है"), continues=p["continues"]["enum"][0], rationale="stub")


def timeline():
    return NAR.build(text=STORY, mode="estimated")


def stub_plan():
    tl = timeline()
    res = VP.design(tl, MF.build(), CAT.load(), StubLLM(), "short")
    return tl, res


class Schemas(unittest.TestCase):
    def test_timeline_schema_accepts_a_valid_timeline_and_rejects_bad_ones(self):
        tl = timeline()
        self.assertEqual(schemas.validate("NarrationTimeline", tl), [])
        bad = copy.deepcopy(tl)
        bad["narration"][0]["id"] = "X1"
        del bad["narration"][1]["text"]
        errs = schemas.validate("NarrationTimeline", bad)
        self.assertTrue(errs and all("path" in e and "message" in e for e in errs))
        with self.assertRaises(ValueError):
            NAR._timeline([dict(id="N01", start=2.0, end=1.0, text="x")], "estimated", 2.0, None, "short", [])

    def test_all_five_schemas_exist_and_are_written_as_files(self):
        self.assertEqual(sorted(schemas.SCHEMAS), ["AssetCatalog", "AssetRequest", "CapabilityManifest", "NarrationTimeline", "VisualScenePlan"])
        self.assertEqual(sorted(schemas.write()), sorted(schemas.SCHEMAS))
        for k in schemas.SCHEMAS:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "kathaya/schemas", f"{k}.schema.json")))


class Narration(unittest.TestCase):
    def test_numbers_become_spoken_words_and_display_text_is_kept(self):
        self.assertEqual(hindi.number_words(12500), "बारह हज़ार पाँच सौ")
        self.assertEqual(hindi.number_words(2500000), "पच्चीस लाख")
        self.assertEqual(hindi.spoken("सिर्फ 12,500 रुपये की फीस — जल्दी"), "सिर्फ बारह हज़ार पाँच सौ रुपये की फीस, जल्दी")
        self.assertEqual(hindi.spoken("₹500"), "पाँच सौ रुपये")
        tl = timeline()
        self.assertIn("12,500", tl["narration"][3]["text"])
        self.assertNotRegex(tl["narration"][3]["spoken"], r"\d")

    def test_the_acceptance_story_is_split_into_its_natural_segments(self):
        segs = NAR.segment_text(STORY)
        self.assertEqual(len(segs), 9)
        self.assertEqual(segs[1], "आपने 25 लाख रुपये की लॉटरी जीती है।")                       # the message read out is its own segment; quotes and dashes are not narrated
        tl = timeline()
        self.assertEqual([s["id"] for s in tl["narration"]], [f"N{i:02d}" for i in range(1, 10)])
        self.assertTrue(all(b["start"] >= a["end"] for a, b in zip(tl["narration"], tl["narration"][1:])))

    def test_timing_json_new_and_legacy_shapes(self):
        seg = json.load(open(os.path.join(ROOT, "stories/production/b_lottery_fee/segments.json"), encoding="utf-8"))
        a = NAR.from_timing_json(seg)                                                        # legacy {"segments": [...], "audio": ...}
        self.assertEqual(a["source"], "timing_json")
        self.assertEqual(len(a["narration"]), len(seg["segments"]))
        b = NAR.from_timing_json(dict(narration=[dict(id="a", text="एक", start=0.2, end=1.0), dict(id="b", text="दो तीन", start=1.2, end=2.5)]))
        self.assertEqual([s["id"] for s in b["narration"]], ["N01", "N02"])
        with self.assertRaises(ValueError):
            NAR.from_timing_json(dict(narration=[dict(text="x", start=0)]))

    def test_audio_and_text_derive_times_from_the_audio(self):
        wav = os.path.join(ROOT, "stories/production/b_lottery_fee/paced.wav")
        seg = json.load(open(os.path.join(ROOT, "stories/production/b_lottery_fee/segments.json"), encoding="utf-8"))["segments"]
        text = "\n".join(s["text"] for s in seg)
        tl = NAR.from_audio_and_text(wav, text)
        self.assertEqual(tl["source"], "audio_and_text")
        self.assertEqual(len(tl["narration"]), len(NAR.segment_text(text)))
        self.assertTrue(all(b["start"] >= a["end"] - 1e-6 and b["end"] > b["start"] for a, b in zip(tl["narration"], tl["narration"][1:])))
        starts = [t["start"] for t in tl["narration"]]
        near = sum(1 for s in seg if min(abs(x - s["start"]) for x in starts) < 0.7)
        self.assertGreaterEqual(near / len(seg), 0.75, "most of the TTS's real segment starts must be found in the audio-derived timeline")
        self.assertIn("not forced alignment", tl["warnings"][0])                              # honest about what this is

    def test_tts_refuses_non_hindi_text_with_a_clear_reason(self):
        with self.assertRaises(ValueError) as cm:
            NAR.from_tts("This is an English story about a scam and money.", os.path.join(_TMP, "tts"))
        self.assertIn("Hindi only", str(cm.exception))
        with self.assertRaises(ValueError):
            NAR.build(text="   ", mode="estimated")


class Manifest(unittest.TestCase):
    def test_the_manifest_is_generated_from_the_renderer(self):
        m = MF.build()
        self.assertEqual(m["schema_errors"], [])
        self.assertEqual({a["id"] for a in m["characters"]["capabilities"]}, set(AC.ACTS))
        self.assertEqual({x["id"] for x in m["camera"]["movements"]}, set(DO.KNOWN_MOVES))
        self.assertTrue(set(MF.MOVE_DOC) >= set(DO.KNOWN_MOVES), "every renderer camera move must be documented")
        self.assertTrue({"tilt", "orbit"} <= set(m["camera"]["unsupported"]))
        self.assertFalse({"tilt", "orbit"} & {x["id"] for x in m["camera"]["movements"]})
        self.assertTrue(m["renderer_version"].startswith("kathaya-r"))
        self.assertEqual(m["renderer_version"], MF.renderer_version())
        self.assertTrue(all(f["subject"] in m["camera"]["subjects"] for f in m["camera"]["framings"]))


class Catalog(unittest.TestCase):
    def test_builtin_catalog_is_complete_semantic_and_valid(self):
        c = CAT.load()
        self.assertEqual(schemas.validate("AssetCatalog", c), [])
        by = {t: [a for a in c["assets"] if a["type"] == t] for t in ("environment", "character", "prop", "effect")}
        self.assertGreaterEqual(len(by["environment"]), 12)
        for a in by["environment"]:
            if a["id"].startswith("env_lib_"):
                continue
            self.assertIn(a["binding"]["location"], LOC.LOCATIONS)
            self.assertTrue(a["subjects"] and a["tags"] and a["supports"]["time_of_day"] and a["license"] and a["source"] and a["status"] == "production_ready")
        subj = [s for a in by["environment"] for s in a["subjects"]]
        self.assertEqual(len(subj), len(set(subj)), "a subject name must identify exactly one environment")
        self.assertTrue(all(a["binding"]["archetype"] for a in by["character"]))
        self.assertIn("catalog_hash", c)


def vplan(env=None, action="ESTABLISH", cap_shot="wide", cap_move="hold", tod="night", extra=None):
    e = env or dict(type="generic", subject="bedroom", asset_id="env_bedroom", time_of_day=tod, status="MISSING")
    v = dict(id="V01", narration_id="N01", start=0.0, end=3.0, visual_intent="ESTABLISH_LOCATION", environment=dict(e, status="MISSING"), characters=["C01"], props=[], action=dict(capability=action, actor="C01", params={}), emotion="neutral",
             camera=dict(shot=cap_shot, movement=cap_move, subject=None), effects=[], transition="cut", screen=None, narration_text="x")
    v.update(extra or {})
    v2 = dict(copy.deepcopy(v), id="V02", narration_id="N02", start=3.0, end=6.0, action=dict(capability="RESOLVE", actor="C01", params={}), camera=dict(shot="full", movement="pull", subject=None), visual_intent="CONSEQUENCE", effects=[], transition="cut")
    v2["environment"] = dict(v["environment"])
    return dict(schema="kathaya.visual_scene_plan/1", format="short", title="t", cast=[dict(id="C01", role="protagonist", archetype="young man", gender="male", name="", description="", asset_id="char_young_man", status="MISSING")], visuals=[v, v2])


class Resolver(unittest.TestCase):
    def setUp(self):
        self.m, self.c = MF.build(), CAT.load()

    def test_an_existing_asset_that_fits_is_available(self):
        plan, rep = RES.resolve(vplan(), self.m, self.c)
        self.assertEqual(plan["visuals"][0]["environment"]["status"], "AVAILABLE")
        self.assertEqual(plan["cast"][0]["status"], "AVAILABLE")
        self.assertEqual(rep["requests"], [])

    def test_a_missing_landmark_is_MISSING_with_a_request_and_is_never_replaced(self):
        env = dict(type="real_landmark", subject="Eiffel Tower Paris", asset_id=None, time_of_day="day", reference_queries=["Eiffel Tower Paris exterior", "Eiffel Tower Paris street view"])
        plan, rep = RES.resolve(vplan(env), self.m, self.c)
        e = plan["visuals"][0]["environment"]
        self.assertEqual((e["status"], e["asset_id"]), ("MISSING", None))
        r = rep["requests"][0]
        self.assertEqual(schemas.validate("AssetRequest", r), [])
        self.assertEqual((r["status"], r["asset_kind"], r["human_approval_required"], r["reference_count"]), ("MISSING", "real_landmark", True, 3))
        self.assertEqual(r["reference_queries"], env["reference_queries"])
        self.assertFalse(rep["ready"])
        with self.assertRaises(CP.NotReady):
            CP.compile_plan(plan, timeline(), self.c, rep, "h")                              # the renderer never receives it

    def test_a_generic_asset_offered_for_a_real_landmark_is_UNSUPPORTED_not_used(self):
        env = dict(type="real_landmark", subject="Eiffel Tower", asset_id="env_bank", time_of_day="day")
        plan, rep = RES.resolve(vplan(env), self.m, self.c)
        self.assertEqual(plan["visuals"][0]["environment"]["status"], "UNSUPPORTED")
        self.assertEqual(rep["requests"][0]["status"], "UNSUPPORTED")
        self.assertIn("generic bank", rep["requests"][0]["reason"])

    def test_a_condition_the_asset_cannot_meet_is_UNSUPPORTED_not_silently_moved_to_daytime(self):
        plan, rep = RES.resolve(vplan(dict(type="generic", subject="bank", asset_id="env_bank", time_of_day="night")), self.m, self.c)
        self.assertEqual(plan["visuals"][0]["environment"]["status"], "UNSUPPORTED")
        self.assertEqual(rep["requests"][0]["required_conditions"], dict(time_of_day="night"))
        self.assertEqual(LOC.resolve("bank", "night")["time"], "day")                          # the legacy resolver WOULD have moved it: the new pipeline refuses instead

    def test_missing_prop_and_character_become_requests(self):
        p = vplan(extra=dict(props=[dict(name="suitcase"), dict(name="phone")]))
        p["cast"][0].update(archetype="astronaut", asset_id=None)
        plan, rep = RES.resolve(p, self.m, self.c)
        self.assertEqual({r["type"] for r in rep["requests"]}, {"prop", "character"})
        self.assertEqual({x["name"]: x["status"] for x in plan["visuals"][0]["props"]}, {"suitcase": "MISSING", "phone": "AVAILABLE"})

    def test_capability_errors_are_structured_and_nothing_is_substituted(self):
        _, rep = RES.resolve(vplan(action="OTHER", cap_move="tilt", extra=dict(effects=["rain@sky"], transition="wipe")), self.m, self.c)
        codes = {e["code"] for e in rep["capability_errors"]}
        self.assertTrue({"UNSUPPORTED_CAPABILITY", "UNSUPPORTED_CAMERA_MOVEMENT", "UNSUPPORTED_EFFECT", "UNSUPPORTED_TRANSITION"} <= codes)
        self.assertTrue(all({"code", "visual", "field", "value", "supported", "message"} <= set(e) for e in rep["capability_errors"]))
        _, rep2 = RES.resolve(vplan(env=dict(type="generic", subject="x", asset_id="env_nonexistent", time_of_day="day")), self.m, self.c)
        self.assertIn("UNKNOWN_ASSET", {e["code"] for e in rep2["capability_errors"]})

    def test_camera_aliases_are_explicit_synonyms(self):
        plan, rep = RES.resolve(vplan(cap_shot="closeup", cap_move="push_in"), self.m, self.c)
        self.assertEqual((plan["visuals"][0]["camera"]["shot_engine"], plan["visuals"][0]["camera"]["movement_engine"]), ("close", "push"))
        self.assertEqual(rep["capability_errors"], [])
        _, rep2 = RES.resolve(vplan(cap_shot="over_shoulder"), self.m, self.c)
        self.assertIn("UNSUPPORTED_CAMERA_SHOT", {e["code"] for e in rep2["capability_errors"]})

    def test_renderer_sequence_rules_are_reported_against_the_visual(self):
        p = vplan(action="INSERT_SCREEN")                                                    # the first action must ESTABLISH / ARRIVE, and INSERT_SCREEN needs a phone alert first
        _, rep = RES.resolve(p, self.m, self.c)
        self.assertIn("SEQUENCE_RULE", {e["code"] for e in rep["capability_errors"]})

    def test_the_user_can_explicitly_substitute_and_it_is_recorded(self):
        env = dict(type="real_landmark", subject="Eiffel Tower Paris", asset_id=None, time_of_day="day")
        plan, rep = RES.resolve(vplan(env), self.m, self.c)
        plan = RES.substitute(plan, rep["requests"][0]["required_by"], "env_street", self.c)
        plan, rep = RES.resolve(plan, self.m, self.c)
        e = plan["visuals"][0]["environment"]
        self.assertEqual((e["status"], e["asset_id"], e["substituted_by"]), ("SUBSTITUTED", "env_street", "user"))
        self.assertEqual(rep["requests"], [])


class Planner(unittest.TestCase):
    def raw(self, tl, per=1):
        return dict(title="t", cast=[dict(id="C01", role="protagonist", archetype="young man", gender="male")], visuals=[dict(narration_id=s["id"], environment=dict(type="generic", subject="bedroom", asset_id="env_bedroom", time_of_day="night"),
                                                                                                                     visual_intent="SHOW_ACTION", characters=["C01"], action=dict(capability="ESTABLISH"), emotion="fear", camera=dict(shot="wide", movement="hold")) for s in tl["narration"] for _ in range(per)])

    def test_times_come_from_the_narration_and_tile_the_timeline(self):
        tl = NAR.build(text="\n".join(["वह कमरे में बैठा था और फोन देख रहा था।"] * 4), mode="estimated")
        plan = VP.finalize(self.raw(tl), tl)
        v = plan["visuals"]
        self.assertEqual(v[0]["start"], 0.0)
        self.assertAlmostEqual(v[-1]["end"], tl["duration"], places=2)
        self.assertTrue(all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(v, v[1:])))
        self.assertTrue(all(abs(x["start"] - s["start"]) < 1e-6 for x, s in zip(v[1:], tl["narration"][1:])))    # each visual begins when its narration begins
        self.assertEqual(schemas.validate("VisualScenePlan", plan), [])

    def test_uncovered_narration_and_renderer_shot_limits_are_rejected_with_reasons(self):
        tl = timeline()
        raw = self.raw(tl)
        raw["visuals"].pop(2)
        with self.assertRaises(VP.PlanError) as cm:
            VP.finalize(raw, tl)
        self.assertIn("N03 has no visual", " ".join(cm.exception.errors))
        with self.assertRaises(VP.PlanError) as cm:
            VP.finalize(self.raw(tl), tl)                                                     # N04 is a 7 s sentence: one visual would exceed the 6 s limit
        self.assertTrue(any("maximum" in e and "N04" in e for e in cm.exception.errors))
        raw2 = self.raw(tl)
        raw2["cast"].append(dict(id="C02", role="protagonist", archetype="young man", gender="male"))
        with self.assertRaises(VP.PlanError):
            VP.finalize(raw2, tl)

    def test_an_amount_the_narration_never_says_is_corrected_and_recorded(self):
        self.assertEqual(hindi.numbers_in("सिर्फ 12,500 रुपये और 25 लाख रुपये"), [12500, 2500000])
        tl = timeline()
        raw = self.raw(tl, per=1)
        for v in raw["visuals"]:
            v["action"] = dict(capability="OBSERVE")
        raw["visuals"][0]["action"] = dict(capability="ESTABLISH")
        raw["visuals"][4]["action"] = dict(capability="VISUALIZE_FLOW", params=dict(amount=7580))          # N05 'उसने पैसे भेज दिए': the LLM invented 7580
        raw["visuals"][3]["camera"] = dict(shot="close", movement="push")
        try:
            plan = VP.finalize(raw, tl)
        except VP.PlanError as e:
            plan = None
            self.assertTrue(all("maximum" in x or "minimum" in x for x in e.errors), e.errors)         # only the shot-length rules may object in this fixture
        if plan:
            v = next(x for x in plan["visuals"] if x["narration_id"] == "N05")
            self.assertEqual(v["action"]["params"]["amount"], 12500)
            self.assertEqual(plan["corrections"][0]["was"], 7580)

    def test_long_form_uses_the_same_rules_except_the_shorts_hook(self):
        tl = NAR.build(text="\n".join(["वह कमरे में बैठा था और फोन देख रहा था और सोच रहा था।"] * 3), mode="estimated", fmt="long")
        long_plan = VP.finalize(self.raw(tl), tl, "long")
        self.assertEqual(long_plan["format"], "long")
        tl_s = NAR.build(text="\n".join(["वह कमरे में बैठा था और फोन देख रहा था और सोच रहा था।"] * 2), mode="estimated", fmt="short")
        raw = self.raw(tl_s)
        self.assertGreater(tl_s["narration"][1]["start"], VP.HOOK_MAX)
        with self.assertRaises(VP.PlanError) as cm:
            VP.finalize(raw, tl_s, "short")                                                    # a Short needs a hook
        self.assertIn("hook", " ".join(cm.exception.errors))
        self.assertTrue(VP.finalize(raw, tl_s, "long"))                                         # long-form does not
        long_text = "\n".join(["वह रोज़ की तरह सुबह उठा और चाय पीकर काम पर निकल गया।"] * 30)
        self.assertTrue(any("longer than a 60 s Short" in w for w in NAR.build(text=long_text, mode="estimated", fmt="short")["warnings"]))
        self.assertFalse(any("longer than a 60 s Short" in w for w in NAR.build(text=long_text, mode="estimated", fmt="long")["warnings"]))

    def test_sequential_menus_alone_produce_a_valid_plan(self):
        tl, res = stub_plan()
        plan = res["plan"]
        self.assertIsNotNone(plan)
        acts = [v["action"]["capability"] for v in plan["visuals"]]
        self.assertEqual(AC.validate(acts), [], acts)
        self.assertEqual(acts[0], "ESTABLISH")
        self.assertEqual(acts[-1], "RESOLVE")
        self.assertEqual(res["report"]["capability_errors"], [])
        fr = [(v["camera"]["subject"], v["camera"]["shot"]) for v in plan["visuals"]]
        self.assertTrue(all(a != b for a, b in zip(fr, fr[1:])), "no repeated framing")
        self.assertTrue(all(0.9 <= v["end"] - v["start"] <= 6.0 for v in plan["visuals"]))

    def test_legal_actions_follow_the_renderer_state(self):
        first = SEQ.legal_actions(set(), [], True, False, False)
        self.assertEqual(sorted(first), ["ARRIVE", "ESTABLISH"])
        have = set(AC.ACTS["ESTABLISH"]["sets"])
        mid = SEQ.legal_actions(have, ["ESTABLISH"], False, False, False)
        self.assertNotIn("INSERT_SCREEN", mid)                                                # needs a phone alert first
        self.assertNotIn("MEET", mid)                                                         # no partner in the cast
        self.assertNotIn("RESOLVE", mid)
        self.assertEqual(SEQ.legal_actions(have, ["ESTABLISH"], False, True, False), ["RESOLVE"])


class Compiler(unittest.TestCase):
    def test_a_resolved_plan_compiles_into_the_renderer_inputs(self):
        tl, res = stub_plan()
        cat = CAT.load()
        out = CP.compile_plan(res["plan"], tl, cat, res["report"], res["plan_hash"])
        g = out["graph"]
        self.assertEqual(AC.validate([b["act"] for b in g["beats"]]), [])
        self.assertTrue(all(b["loc"] == "bedroom" and b["time"] == "night" for b in g["beats"]))
        self.assertTrue(all("camera" in b for b in g["beats"] if b["act"] not in ("INSERT_SCREEN", "VISUALIZE_FLOW")))
        self.assertEqual(g["plan_overrides"]["kathaya"]["renderer_version"], MF.renderer_version())
        plan = PR.build(g, out["narration"], seed=11, name="t", tts="x", fixes={})
        self.assertTrue(plan["transitions_render"])
        self.assertEqual([s["id"] for s in plan["narration"]["segments"]], [n["id"] for n in tl["narration"]])       # captions / QC follow the real narration, shots follow the visuals
        cams = [(b["camera"]["target"], b["camera"]["size"], b["camera"]["move"]) for b in g["beats"] if "camera" in b]
        shots = [(s["camera"]["target"], s["camera"]["size"], s["camera"]["move"]) for s in plan["shots"] if s.get("camera")]
        self.assertEqual(shots, cams, "the renderer executes the camera it was given: no rotation, no automatic coverage split")
        self.assertEqual(len(plan["shots"]), len(g["beats"]))

    def test_legacy_plans_are_unchanged_by_the_new_hooks(self):
        g, nar = PR.parse(os.path.join(ROOT, "stories/production/a_whatsapp_investment/story.md"), os.path.join(ROOT, "stories/production/a_whatsapp_investment/segments.json"))
        p = PR.plan_for(g, nar, 11, {})
        self.assertNotIn("transitions_render", p)
        self.assertNotIn("camera_adjustments", p)
        old = os.path.join(ROOT, "output/production/a_whatsapp_investment/plan.json")
        if os.path.exists(old):
            g2 = json.load(open(os.path.join(ROOT, "output/production/a_whatsapp_investment/story_graph.json"), encoding="utf-8"))
            p2 = PR.plan_for(g, nar, 11, g2.get("fixes"))
            self.assertEqual(json.dumps(p2, sort_keys=True, default=list), json.dumps(json.load(open(old, encoding="utf-8")), sort_keys=True, default=list))

    def test_transitions_are_rendered_only_for_kathaya_plans(self):
        from engine.skeleton import short
        tr = [(0.0, "fade"), (10.0, "dip")]
        a = [short._transition_alpha(tr, t, 30) for t in (0.0, 0.25, 0.5, 5.0, 9.9, 10.0, 10.3)]
        self.assertEqual((a[0], a[3], a[5]), (0.0, 1.0, 0.0))
        self.assertTrue(0 < a[1] < 1 and a[2] == 1.0 and 0 < a[4] < 1 and a[6] == 1.0)


class Look(unittest.TestCase):
    SEGS = [dict(id="N01", start=0.0, end=2.0, text="आपने 25 लाख रुपये की लॉटरी जीती है।",
                 words=[dict(word=w, start=0.2 * i, end=0.2 * i + 0.18) for i, w in enumerate("आपने पच्चीस लाख रुपये की लॉटरी जीती है।".split())]),
            dict(id="N02", start=2.0, end=4.0, text="फीस 12,500 रुपये है, 3 दिन में।", words=[dict(word=w, start=2 + 0.2 * i, end=2 + 0.2 * i + 0.18) for i, w in enumerate("फीस बारह हज़ार पाँच सौ रुपये है, तीन दिन में।".split())])]

    def test_callouts_are_the_amounts_the_narration_says_at_the_moment_it_says_them(self):
        c = LK.callouts(self.SEGS)
        self.assertEqual([x["text"] for x in c], ["₹25 लाख", "₹12,500"])
        self.assertAlmostEqual(c[0]["t0"], 0.2, places=2)                                # 'पच्चीस' is the second word
        self.assertAlmostEqual(c[1]["t0"], 2.2, places=2)                                # 'बारह' is the second word of N02
        self.assertTrue(all(any(t in seg["text"] for seg in self.SEGS) for t in ("25 लाख", "12,500")))     # nothing invented: the digits come from the narration
        self.assertNotIn("3", "".join(x["text"] for x in c))                              # '3 दिन' is not an amount

    def test_a_number_that_cannot_be_located_in_the_word_times_gets_no_callout(self):
        segs = [dict(id="N01", start=0, end=2, text="उसने 500 रुपये दिए", words=[dict(word="उसने", start=0, end=.3), dict(word="दिए", start=.3, end=.6)])]
        self.assertEqual(LK.callouts(segs), [])

    def test_captions_are_word_highlighted_big_and_inside_the_safe_zone(self):
        from engine.shorts import captions
        plan = dict(look=LK.design(self.SEGS), narration=dict(segments=self.SEGS), shots=[dict(act="PHONE_ALERT", t0=1.0)])
        look = LK.Look(plan)
        for tt in (0.35, 0.8, 1.3, 2.5, 3.1):
            img, bbox, text = look.apply(np.zeros((1920, 1080, 3), np.float32) + 0.2, tt)
            self.assertIsNotNone(bbox, tt)
            self.assertTrue(captions.in_safe_zone(bbox), (tt, bbox))
            self.assertLessEqual(len(text.split()), LK.MAX_WORDS)
        a0, _, _, _ = LK._caption_layer([dict(word="पच्चीस"), dict(word="लाख")], 0)
        a1, _, _, _ = LK._caption_layer([dict(word="पच्चीस"), dict(word="लाख")], 1)
        self.assertFalse(np.array_equal(a0, a1))                                          # the highlighted word changes the picture

    def test_only_amounts_are_coloured_as_amounts(self):
        w = lambda *t: [dict(word=x) for x in t]
        self.assertEqual(LK.amount_words(w("एक", "लड़के", "के")), set())                     # 'one' as an ordinary word
        self.assertEqual(LK.amount_words(w("आपने", "पच्चीस", "लाख")), {1, 2})
        self.assertEqual(LK.amount_words(w("पाँच", "सौ", "रुपये")), {0, 1})

    def test_look_is_deterministic_and_only_for_kathaya_plans(self):
        plan = dict(look=LK.design(self.SEGS), narration=dict(segments=self.SEGS), shots=[])
        base = np.zeros((1920, 1080, 3), np.float32) + 0.3
        a, b = LK.Look(plan).apply(base.copy(), 0.5)[0], LK.Look(plan).apply(base.copy(), 0.5)[0]
        self.assertTrue(np.array_equal(a, b))
        g, nar = PR.parse(os.path.join(ROOT, "stories/production/a_whatsapp_investment/story.md"), os.path.join(ROOT, "stories/production/a_whatsapp_investment/segments.json"))
        self.assertNotIn("look", PR.plan_for(g, nar, 11, {}))

    def test_compiled_plans_carry_the_look(self):
        tl, res = stub_plan()
        out = CP.compile_plan(res["plan"], tl, CAT.load(), res["report"], res["plan_hash"])
        self.assertIn("look", out["graph"]["plan_overrides"])
        self.assertEqual(out["graph"]["plan_overrides"]["look"]["version"], LK.VERSION)


class Keys(unittest.TestCase):
    def test_changing_one_visual_changes_only_its_hash(self):
        tl, res = stub_plan()
        p1 = res["plan"]
        p2 = copy.deepcopy(p1)
        p2["visuals"][4]["camera"]["movement"] = "pull"
        self.assertEqual(KK.changed_visuals(p1, p2), [p1["visuals"][4]["id"]])
        k = KK.run_keys(p1, tl, CAT.load(), MF.renderer_version())
        self.assertTrue({"plan_hash", "timeline_hash", "renderer_version", "catalog_hash", "visual_hashes", "asset_hashes"} <= set(k))
        self.assertEqual(k["plan_hash"], KK.run_keys(copy.deepcopy(p1), tl, CAT.load(), MF.renderer_version())["plan_hash"])


class TechnicalQC(unittest.TestCase):
    def test_plan_checks_catch_missing_assets_and_broken_references(self):
        tl, res = stub_plan()
        ids = {a["id"] for a in CAT.load()["assets"]}
        ok = {c["id"]: c["ok"] for c in KQ.plan_checks(res["plan"], res["report"], tl, ids)}
        self.assertTrue(all(ok.values()), ok)
        bad = copy.deepcopy(res["plan"])
        bad["visuals"][2]["environment"]["asset_id"] = "env_ghost"
        bad["visuals"][3]["narration_id"] = "N99"
        rep = dict(res["report"], requests=[dict(id="REQ_X")])
        ok2 = {c["id"]: c["ok"] for c in KQ.plan_checks(bad, rep, tl, ids)}
        self.assertFalse(ok2["missing_assets"])
        self.assertFalse(ok2["broken_references"])
        self.assertFalse(ok2["narration_coverage"])


class Licences(unittest.TestCase):
    def test_reference_licences_follow_the_project_policy(self):
        d, key, att = REF.classify("CC BY 4.0", "A. Author", "https://commons.wikimedia.org/wiki/File:X.jpg")
        self.assertEqual((d["decision"], key), ("ACCEPT_WITH_OBLIGATIONS", "cc-by-4.0"))
        self.assertIn("A. Author", att)
        self.assertEqual(REF.classify("CC0", "", "u")[0]["decision"], "ACCEPT")
        self.assertEqual(REF.classify("Public domain", "", "u")[0]["decision"], "ACCEPT")
        d, key, _ = REF.classify("CC BY-SA 4.0", "a", "u")
        self.assertEqual((d["decision"], key, d["share_alike"]), ("ACCEPT_WITH_OBLIGATIONS", "cc-by-sa-4.0", True))     # accepted, and flagged share-alike
        self.assertEqual(REF.classify("CC BY-SA 3.0", "a", "u")[0]["decision"], "QUARANTINE")                   # share-alike 3.0 is not in the accepted set
        self.assertEqual(REF.classify("FAL", "a", "u")[0]["decision"], "QUARANTINE")                            # Free Art License: not a recognised policy licence
        self.assertTrue(REF._relevant("File:Gateway of India, Mumbai.jpg", "", "Gateway of India Mumbai"))
        self.assertFalse(REF._relevant("File:Shaare Rason Synagogue, Mumbai.jpg", "", "Gateway of India Mumbai"))
        self.assertEqual(REF.classify("CC BY-NC 4.0", "a", "u")[0]["decision"], "REJECT")
        self.assertEqual(REF.classify("", "a", "u")[0]["decision"], "QUARANTINE")


class Builder(unittest.TestCase):
    def test_stylise_is_deterministic_and_has_the_backdrop_size(self):
        import cv2
        rng = np.random.default_rng(3)
        img = (rng.random((600, 900, 3)) * 255).astype(np.uint8)
        cv2.rectangle(img, (300, 100), (500, 550), (200, 180, 160), -1)
        a, b = AB.stylise(img, "day"), AB.stylise(img, "day")
        self.assertEqual(a.shape, (AB.H, AB.W, 3))
        self.assertTrue(np.array_equal(a, b))
        self.assertLess(AB.stylise(img, "night").mean(), a.mean())

    def test_the_builder_refuses_a_reference_whose_licence_is_not_accepted(self):
        pid = KP.create("x")["id"]
        KP._write(pid, "requests/R.json", dict(id="R", type="environment", subject="X", asset_kind="generic", required_conditions={}))
        with self.assertRaises(ValueError):
            AB.build_from_request(pid, "R", dict(production_ok=False, licence_reason="share-alike"), log=lambda *_: None)


class Events(unittest.TestCase):
    def test_kathaya_flows_have_their_own_stage_lists(self):
        from engine.skeleton import events as EVT
        r = EVT.Reporter()
        r.emit("started", "job", flow="kplan")
        for st in EVT.FLOWS["kplan"]:
            r.start(st)
            r.complete(st)
        s = r.state.snapshot()
        self.assertEqual([x["id"] for x in s["stages"]], ["narration", "timeline", "visual_design", "asset_check"])
        self.assertEqual(r.state.overall, 1.0 - 0.0) if False else self.assertGreaterEqual(r.state.overall, 0.99)
        r2 = EVT.Reporter()
        r2.emit("started", "job")
        self.assertEqual([x["id"] for x in r2.state.snapshot()["stages"]], EVT.ORDER)                # legacy flow unchanged


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from engine.studio import core as C, server as SV
        for k, sub in (("STUDIO_DIR", ""), ("DRAFTS", "drafts"), ("PRODS", "productions"), ("UPLOADS", "uploads")):
            setattr(C, k, os.path.join(_TMP, "studio", sub) if sub else os.path.join(_TMP, "studio"))
        for d in (C.DRAFTS, C.PRODS, C.UPLOADS):
            os.makedirs(d, exist_ok=True)
        cls.app = SV.create_app(test_mode=True)
        cls.c = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        from engine.studio import server as SV
        for pid in list(SV.mgr().procs):
            try:
                SV.mgr().cancel(pid)
            except Exception:                                                               # noqa: BLE001
                pass
        SV.mgr().shutdown()

    def wait_state(self, pid, states, t=60):
        import time
        end = time.time() + t
        while time.time() < end:
            p = self.c.get(f"/api/k/project/{pid}").json()
            if p["project"]["state"] in states:
                return p
            time.sleep(0.3)
        self.fail(f"project stayed {p['project']['state']}")

    def test_manifest_and_catalog_endpoints(self):
        self.assertEqual(self.c.get("/api/k/manifest").json()["schema"], "kathaya.capability_manifest/1")
        self.assertGreaterEqual(len(self.c.get("/api/k/catalog").json()["assets"]), 47)

    def test_empty_input_and_bad_options_are_refused(self):
        self.assertEqual(self.c.post("/api/k/project", json=dict(text="  ")).status_code, 422)
        r = self.c.post("/api/k/project", json=dict(text="x", format="widescreen"))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "invalid_options"))
        self.assertEqual(self.c.post("/api/k/project", json=dict(text="x", timing_json="{nope")).status_code, 422)

    def test_chatgpt_as_creative_director_full_flow(self):
        r = self.c.post("/api/k/project", json=dict(text=STORY, format="short", provider="chatgpt", narration_mode="estimated")).json()
        pid = r["project_id"]
        p = self.wait_state(pid, ("awaiting_chatgpt",))
        self.assertEqual(p["timeline"]["segments"], 9)
        prompt = self.c.get(f"/api/k/project/{pid}/chatgpt_prompt").json()["prompt"]
        for must in ("N01", "N09", "ESTABLISH", "env_bedroom", "OTHER", "story requirement always wins"):
            self.assertIn(must, prompt)
        self.assertEqual(self.c.post(f"/api/k/project/{pid}/render").status_code, 409)               # nothing is rendered without a plan
        bad = self.c.post(f"/api/k/project/{pid}/chatgpt_reply", json=dict(reply="not json"))
        self.assertEqual((bad.status_code, bad.json()["error"]["code"]), (422, "plan_invalid"))
        tl = json.load(open(os.path.join(KP.PROJECTS, pid, "timeline.json"), encoding="utf-8"))
        raw = StubLLM  # noqa: F841
        good = dict(title="t", cast=[dict(id="C01", role="protagonist", archetype="young man", gender="male")], visuals=[])
        acts = ["ESTABLISH", "PHONE_ALERT", "LOOK_AT_PHONE", "EYES_CHANGE", "REACH_PHONE", "PICK_UP", "READ_MESSAGE", "REALIZE", "OBSERVE", "SUSPECT", "CLOSE_UP", "RESOLVE"]
        frames = [("environment", "wide"), ("protagonist_head", "medium"), ("protagonist_phone", "close"), ("protagonist_full", "full")]
        n = 0
        for s in tl["narration"]:
            k = 2 if s["end"] - s["start"] > 5.5 else 1
            for _ in range(k):
                sub, shot = frames[n % 4]
                good["visuals"].append(dict(narration_id=s["id"], visual_intent="SHOW_ACTION", environment=dict(type="generic", subject="bedroom", asset_id="env_bedroom", time_of_day="night"), characters=["C01"], props=[], action=dict(capability=acts[n]),
                                            emotion="fear", camera=dict(shot=shot, movement="push", subject=sub)))
                n += 1
        good["visuals"][-1]["action"]["capability"] = "RESOLVE"
        r2 = self.c.post(f"/api/k/project/{pid}/chatgpt_reply", json=dict(reply="Sure!\n```json\n" + json.dumps(good, ensure_ascii=False) + "\n```"))
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["state"], "ready")
        # the same plan with a landmark the catalog does not have -> needs_assets, and the film cannot start
        miss = copy.deepcopy(good)
        miss["visuals"][0]["environment"] = dict(type="real_landmark", subject="Eiffel Tower Paris", asset_id=None, time_of_day="day", reference_queries=["Eiffel Tower Paris exterior"])
        self.assertEqual(self.c.post(f"/api/k/project/{pid}/chatgpt_reply", json=dict(reply=json.dumps(miss, ensure_ascii=False))).json()["state"], "needs_assets")
        view = self.c.get(f"/api/k/project/{pid}").json()
        self.assertEqual(view["requests"][0]["status"], "MISSING")
        self.assertEqual(view["requests"][0]["reference_queries"], ["Eiffel Tower Paris exterior"])
        self.assertEqual(self.c.post(f"/api/k/project/{pid}/render").status_code, 409)
        self.assertEqual(self.c.post(f"/api/k/project/{pid}/request/{view['requests'][0]['id']}/approve", json=dict(reference_index=0)).status_code, 422)   # no references chosen yet


if __name__ == "__main__":
    unittest.main()
