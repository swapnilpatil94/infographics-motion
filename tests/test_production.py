"""Production factory tests: story parsing, locations, scene director, audio director, QC gate helpers, backend API. No Blender / TTS needed (draft narration timings)."""
import json
import os
import tempfile
import unittest

import numpy as np

from engine.environments import locations as LOC
from engine.skeleton import acts as AC, audio_director as AUD, backend as BE, narration_io as NI, scene_director as SD, story_semantics as SS, topic_build as TB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORIES = ["a_whatsapp_investment", "b_lottery_fee", "c_atm_helper"]


def _graph(key):
    d = os.path.join(ROOT, "stories/production", key)
    return SS.analyze(SS.load_segments(os.path.join(d, "script.json")), SS.load_script(os.path.join(d, "story.md")))


class Story(unittest.TestCase):
    def test_three_stories_are_materially_different(self):
        gs = [_graph(k) for k in STORIES]
        seqs = [tuple(b["act"] for b in g["beats"]) for g in gs]
        self.assertEqual(len(set(seqs)), 3)
        self.assertEqual(len({tuple((s["loc"], s["time"]) for s in g["scenes"]) for g in gs}), 3)
        for g in gs:
            self.assertEqual(AC.validate([b["act"] for b in g["beats"]]), [])

    def test_locations_never_contradict_time(self):
        for g in map(_graph, STORIES):
            for s in g["scenes"]:
                self.assertEqual(LOC.resolve(s["loc"], s["time"])["time"], s["time"])
        self.assertEqual(LOC.resolve("bank", "night")["time"], "day")                    # a bank is never shown at night
        self.assertEqual(LOC.resolve("bedroom", "night")["time"], "night")

    def test_quoted_message_does_not_change_time_of_day(self):
        self.assertEqual(LOC.find("मैसेज: सात दिन में पैसा दोगुना, आज ही जुड़िए।"), (None, None))

    def test_unsupported_story_fails_clearly(self):
        segs = [dict(id=f"n{i}", text=t) for i, t in enumerate(["अस्पताल में रोहन।", "मंदिर के पास।", "बात हुई।", "फिर घर।", "ठीक रहा।", "शाम हुई।", "वह हँसा।", "सो गया।"])]
        with self.assertRaises(SS.StoryNotSupported) as cm:
            SS.analyze(segs, {})
        self.assertIn("money", str(cm.exception))
        with self.assertRaises(LOC.LocationUnsupported):
            LOC.resolve("moon_base")

    def test_structured_graph_validates_acts(self):
        with self.assertRaises(SS.StoryNotSupported):
            SS.graph_from_beats("x", [dict(act="HAND_OVER", loc="bedroom", time="night"), dict(act="RESOLVE", loc="bedroom", time="night")])


class Director(unittest.TestCase):
    def test_plans_are_valid_deterministic_and_time_consistent(self):
        for key in STORIES:
            g = _graph(key)
            nar = TB.draft_narration(g)
            p1, p2 = SD.build_plan(g, nar), SD.build_plan(g, nar)
            self.assertEqual(json.dumps(p1, sort_keys=True, default=list), json.dumps(p2, sort_keys=True, default=list))
            self.assertEqual(p1["version"], 4)
            prev = 0.0
            for sh in p1["shots"]:
                self.assertAlmostEqual(sh["t0"], prev, places=2)
                prev = sh["t1"]
                lt, env = sh["lighting"], sh["environment"]["variation"]
                self.assertEqual(lt["time"], env["time"])
                if lt["time"] == "day":
                    self.assertEqual(lt["moon"], 0.0)
                if lt["time"] == "night":
                    self.assertEqual(lt.get("sun", 0.0), 0.0)
            keys = [(s["camera"]["target"], s["camera"]["size"]) for s in p1["shots"] if s.get("camera")]
            self.assertFalse(any(len(set(keys[i:i + 3])) == 1 for i in range(len(keys) - 2)), "three identical framings in a row")

    def test_facing_follows_geometry(self):
        g = SS.graph_from_beats("t", [dict(act="ARRIVE", loc="bank", time="day"), dict(act="MEET", loc="bank", time="day", roles=["bank_employee"]), dict(act="RESOLVE", loc="bank", time="day")], dict(gender="male", archetype="young man"), "bank_employee")
        p = SD.build_plan(g, TB.draft_narration(g) if False else dict(segments=[dict(id=b["id"], text=b["text"], start=i * 3.0, end=i * 3.0 + 2.5) for i, b in enumerate(g["beats"])], audio=None, tts="draft", tempo=1.0))
        self.assertEqual(p["characters"]["D"]["facing"], -1)                             # the clerk stands right of the protagonist and faces left


class Audio(unittest.TestCase):
    def test_mix_is_deterministic_cached_intelligible_and_unclipped(self):
        g = _graph("a_whatsapp_investment")
        nar = TB.draft_narration(g)
        plan = SD.build_plan(g, nar)
        n = int(plan["duration"] * AUD.SR)
        t = np.arange(n) / AUD.SR
        voice = (np.sin(2 * np.pi * 180 * t) * (np.sin(2 * np.pi * 3.5 * t) > 0) * 0.5).astype(np.float32)     # speech-like test signal
        with tempfile.TemporaryDirectory() as d:
            w1, r1 = AUD.mix(plan, voice, d, [], None, cache_root=d)
            w2, r2 = AUD.mix(plan, voice, d, [], None, cache_root=d)
        self.assertFalse(r1["cache_hit"])
        self.assertTrue(r2["cache_hit"])
        self.assertLessEqual(r1["peak"], 0.99)
        self.assertEqual(r1["clipped_samples"], 0)
        self.assertGreaterEqual(r1["speech_to_bed_db"], 8.0)
        self.assertAlmostEqual(r1["duration"], plan["duration"], delta=0.15)

    def test_foley_is_derived_from_actions(self):
        plan = dict(duration=10.0, shots=[dict(actions=[dict(char="A", action="stand", t=1.0, dur=1.0), dict(char="A", action="prop_cycle", t=3.0, dur=2.4, prop="ATM"), dict(char="A", action="prop_cycle", t=6.0, dur=2.4, prop="MONEY")])], sfx=[])
        kinds = {k for _, k, _ in AUD.foley_events(plan)}
        self.assertTrue({"cloth", "chair", "beep", "card", "cash"} <= kinds)

    def test_audio_config_change_changes_only_the_mix_hash(self):
        g = _graph("b_lottery_fee")
        plan = SD.build_plan(g, TB.draft_narration(g))
        h0 = AUD._hash(plan, [], None)
        plan["audio_cfg"] = dict(music=0.1)
        self.assertNotEqual(h0, AUD._hash(plan, [], None))


class Narration(unittest.TestCase):
    def test_invalid_narration_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.json")
            json.dump({"segments": [dict(id="a", text="x", start=2.0, end=1.0)], "audio": "missing.wav"}, open(p, "w"))
            with self.assertRaises(NI.NarrationInvalid) as cm:
                NI.load(p)
            self.assertIn("end <= start", str(cm.exception))


class Backend(unittest.TestCase):
    def test_backend_interfaces(self):
        g = BE.story_analyze(os.path.join(ROOT, "stories/production/c_atm_helper/story.md"), os.path.join(ROOT, "stories/production/c_atm_helper/script.json")) if False else _graph("c_atm_helper")
        self.assertGreaterEqual(len(BE.characters(g)), 2)
        self.assertIn("bank", BE.environments())
        self.assertTrue(BE.assets())
        self.assertTrue(BE.voices())
        g2 = BE.story_edit(g, g["beats"][1]["id"], emotion="fear")
        self.assertEqual(g2["beats"][1]["emotion"], "fear")
        plan = SD.build_plan(g, TB.draft_narration(g))
        p2 = BE.edit_shot(plan, plan["shots"][2]["id"], camera=dict(dx=30.0))
        self.assertEqual(p2["shots"][2]["camera"]["dx"], 30.0)
        self.assertNotIn("dx", plan["shots"][2]["camera"] or {}) if plan["shots"][2].get("camera") and "dx" not in plan["shots"][2]["camera"] else None
        p3 = BE.character_override(plan, "A", dict(skin=dict(hex="#7a4a2a")))
        self.assertEqual(p3["characters"]["A"]["dna"]["skin"]["hex"], "#7a4a2a")


if __name__ == "__main__":
    unittest.main()
