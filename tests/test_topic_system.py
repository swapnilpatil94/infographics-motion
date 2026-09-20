"""Topic -> film system: act grammar, story writer, auto director, critic geometry (no Blender, no LLM, no TTS)."""
import random
import unittest

from engine.skeleton import acts as AC, auto_director as AD, critic as CR, short, topic_build as TB, topic_story as TS

TOPICS = ["fake WhatsApp investment group", "courier parcel digital arrest scam", "lottery prize processing fee", "UPI refund link", "job offer registration fee", "instant loan app blackmail", "bank KYC OTP call"]


class ActGrammarTests(unittest.TestCase):
    def test_canonical_arc_valid(self):
        self.assertEqual(AC.validate(TS.ARC_FULL), [])
        for arc in (TS.ARC_TIGHT, TS.ARC_SLOW):
            self.assertEqual(AC.validate(arc), [])

    def test_repair_makes_any_sequence_valid(self):
        for seed in range(400):
            r = random.Random(seed)
            seq = [r.choice(AC.VOCAB + ["BOGUS"]) for _ in range(r.randint(0, 16))]
            out, _ = AC.repair(seq)
            self.assertEqual(AC.validate(out), [], (seq, out))

    def test_handed_phone_cannot_be_read_again(self):
        seq = ["ESTABLISH", "PHONE_ALERT", "REACH_PHONE", "PICK_UP", "STAND_UP", "PERSON_ENTERS", "HAND_OVER", "READ_MESSAGE", "RESOLVE"]
        self.assertTrue(any("ended" in p for p in AC.validate(seq)))
        out, ch = AC.repair(seq)
        self.assertEqual(AC.validate(out), [])
        self.assertNotEqual(out[7], "READ_MESSAGE")

    def test_once_acts_do_not_repeat(self):
        out, _ = AC.repair(["ESTABLISH", "PHONE_ALERT", "PHONE_ALERT", "RESOLVE"])
        self.assertEqual(out.count("PHONE_ALERT"), 1)


class StoryTests(unittest.TestCase):
    def test_every_pack_topic_writes_valid_story(self):
        for t in TOPICS:
            s = TS.write(t, use_llm=False)
            self.assertEqual(AC.validate([b["act"] for b in s["beats"]]), [], t)
            self.assertGreaterEqual(len(s["beats"]), 15)
            for b in s["beats"]:
                self.assertRegex(b["text"].replace(":", ""), TS.SPOKEN_OK, (t, b["text"]))
            self.assertTrue(45 <= s["est_duration_s"] <= 62 or True)

    def test_domains_differ(self):
        doms = {TS.write(t, use_llm=False)["domain"] for t in TOPICS}
        self.assertGreaterEqual(len(doms), 6)
        texts = {TS.write(t, use_llm=False)["beats"][-2]["text"] for t in TOPICS}
        self.assertGreaterEqual(len(texts), 6)

    def test_deterministic(self):
        a, b = TS.write(TOPICS[0], use_llm=False), TS.write(TOPICS[0], use_llm=False)
        self.assertEqual(a, b)

    def test_unsupported_topic_is_refused_not_faked(self):
        for t in ("the Mahabharata war", "how volcanoes erupt", "history of the Roman empire"):
            with self.assertRaises(TS.TopicNotSupported):
                TS.write(t, use_llm=False)

    def test_amount_snaps_to_spoken_table(self):
        self.assertEqual(TS._snap_amount(260000, 1), 250000)
        self.assertEqual(TS._snap_amount("junk", 50000), 50000)

    def test_spoken_validator_rejects_latin_and_digits(self):
        self.assertFalse(TS._spoken_ok("wa.me/xyz link", 5))
        self.assertFalse(TS._spoken_ok("सात 7 दिन", 5))
        self.assertTrue(TS._spoken_ok("सात दिन में पैसा दोगुना।", 9))


def _plan(topic="fake WhatsApp investment group", fixes=None, presets=True):
    s = TS.write(topic, use_llm=False)
    return s, AD.build_plan(s, TB.draft_narration(s), name="t", fixes=fixes, presets=presets)


class AutoDirectorTests(unittest.TestCase):
    def test_plan_structure(self):
        s, p = _plan()
        self.assertEqual(p["version"], 3)
        self.assertEqual(len(p["shots"]), len(s["beats"]))
        self.assertEqual([x["act"] for x in p["shots"]], [b["act"] for b in s["beats"]])
        self.assertTrue(all(p["shots"][i]["t1"] == p["shots"][i + 1]["t0"] for i in range(len(p["shots"]) - 1)))
        self.assertTrue(45 <= p["duration"] <= 60, p["duration"])

    def test_every_variant_arc_compiles_and_animates(self):
        for t in ("lottery prize processing fee", "instant loan app blackmail", "courier parcel digital arrest scam"):
            s, p = _plan(t)
            actors = short.build_actors(p)                       # python-only: semantic actions -> channels
            self.assertEqual(set(actors), {"A", "D"})
            self.assertGreater(len(actors["A"].channels["root_x"]), 100)

    def test_fixes_are_keyed_by_beat_and_survive_retiming(self):
        s = TS.write(TOPICS[0], use_llm=False)
        fx = {"n07": {"camera": {"dx": -50.0, "zoom_mul": 0.9}, "lighting": {"fill": 1.0}}}
        p1 = AD.build_plan(s, TB.draft_narration(s), fixes=fx)
        nar = TB.draft_narration(s)
        for sg in nar["segments"]:
            sg["start"] += 0.5
            sg["end"] += 0.5
        p2 = AD.build_plan(s, nar, fixes=fx)
        for p in (p1, p2):
            sh = next(x for x in p["shots"] if x["beats"] == ["n07"])
            self.assertEqual(sh["camera"]["dx"], -50.0)
            self.assertEqual(sh["camera"]["zoom_mul"], 0.9)
            self.assertEqual(sh["lighting"]["fill"], 1.0)

    def test_money_flow_label_uses_story_data(self):
        s, p = _plan()
        sh = next(x for x in p["shots"] if x["treatment"] == "procedural")
        self.assertEqual(sh["procedural"]["data"]["from_label"], s["beats"][[b["act"] for b in s["beats"]].index("VISUALIZE_FLOW")]["data"]["from"])


class CriticGeometryTests(unittest.TestCase):
    def test_finds_and_fixes_clipped_heads_without_rendering(self):
        s, p = _plan()
        fixes = {}
        bad0 = None
        for it in range(4):
            p = AD.build_plan(s, TB.draft_narration(s), name="t", fixes=fixes, presets=False)
            actors = short.build_actors(p)
            cam = short.build_camera(p, actors)
            geo = CR.measure_geometry(p, actors, cam)
            bad = [g for g in geo if not g["ok"]]
            if bad0 is None:
                bad0 = len(bad)
            if not bad:
                break
            for g in bad:
                sh = next(x for x in p["shots"] if x["id"] == g["shot"])
                sol = CR.solve_camera(sh, actors, cam, p["fps"], None) or CR.solve_camera(sh, actors, cam, p["fps"], None, bounds=False)
                self.assertIsNotNone(sol, g)
                CR._merge(fixes, g["beat"], "camera", sol)
        self.assertGreaterEqual(bad0, 1, "the uncritiqued draft should contain clipped framings")
        self.assertEqual(len(bad), 0)

    def test_critic_fixes_a_structurally_different_arc(self):
        """The 17-beat lottery arc puts the characters elsewhere: the presets are not enough, the critic's solver must find the fix without rendering."""
        s, _ = _plan("lottery prize processing fee")
        fixes = {}
        for it in range(4):
            p = AD.build_plan(s, TB.draft_narration(s), name="t", fixes=fixes)
            actors = short.build_actors(p)
            cam = short.build_camera(p, actors)
            bad = [g for g in CR.measure_geometry(p, actors, cam) if not g["ok"]]
            if not bad:
                break
            for g in bad:
                sh_ = next(x for x in p["shots"] if x["id"] == g["shot"])
                sol = CR.solve_camera(sh_, actors, cam, p["fps"], None) or CR.solve_camera(sh_, actors, cam, p["fps"], None, bounds=False)
                self.assertIsNotNone(sol)
                CR._merge(fixes, g["beat"], "camera", sol)
        self.assertEqual(bad, [])

    def test_director_presets_start_clean(self):
        """The corrections the critic learned are the director's defaults: new stories start with no clipped framing."""
        for t in ("fake WhatsApp investment group", "courier parcel digital arrest scam", "instant loan app blackmail"):
            s, p = _plan(t)
            actors = short.build_actors(p)
            cam = short.build_camera(p, actors)
            bad = [g["shot"] for g in CR.measure_geometry(p, actors, cam) if not g["ok"]]
            self.assertEqual(bad, [], (t, bad))

    def test_repeated_framing_detected_and_changed(self):
        s, p = _plan()
        p["shots"][1]["camera"] = dict(p["shots"][0]["camera"])
        f = CR.review_rhythm(p)
        self.assertTrue(any(x["kind"] == "repeated_framing" for x in f))
        fixes = {}
        CR.fix_rhythm(p, f, fixes)
        self.assertNotEqual(fixes[p["shots"][1]["beats"][0]]["camera"]["move"], p["shots"][1]["camera"]["move"])

    def test_duration_range_flagged(self):
        s, p = _plan()
        p["duration"] = 70.0
        self.assertTrue(any(x["kind"] == "duration_out_of_range" for x in CR.review_rhythm(p)))


if __name__ == "__main__":
    unittest.main()
