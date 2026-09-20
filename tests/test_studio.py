"""Kathaaya Studio (web UI backend): event folding, story / script validation, drafts + review, director options, plan identity with the CLI, shot edits, and the HTTP API with real worker subprocesses running a
SIMULATED production (real event log, real SSE, real cancel / failure / queue) - no Blender, no TTS."""
import copy
import json
import os
import shutil
import tempfile
import time
import unittest

os.environ.setdefault("KATHAYA_STUDIO_TEST", "1")
_TMP = tempfile.mkdtemp(prefix="studio_test_")
os.environ["KATHAYA_STUDIO_DIR"] = _TMP

from engine.skeleton import director_opts as DO, events as EVT, production as PR, scene_director as SD, topic_story as TS   # noqa: E402
from engine.studio import core as C, jobs as J, movie as M                                                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setUpModule():
    for k, sub in (("STUDIO_DIR", ""), ("DRAFTS", "drafts"), ("PRODS", "productions"), ("UPLOADS", "uploads")):
        setattr(C, k, os.path.join(_TMP, sub) if sub else _TMP)
    for d in (C.DRAFTS, C.PRODS, C.UPLOADS):
        os.makedirs(d, exist_ok=True)


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def ev(seq, event, stage, **k):
    return dict(seq=seq, ts=1000.0 + seq, event=event, stage=stage, **k)


class Events(unittest.TestCase):
    def test_overall_is_folded_from_real_stage_state_and_never_decreases(self):
        rep = EVT.Reporter(path=None)
        seen = []
        for st in EVT.ORDER:
            rep.start(st)
            seen.append(rep.state.overall)
            for f in (0.25, 0.5, 0.9):
                rep.progress(st, fraction=f, force=True)
                seen.append(rep.state.overall)
            rep.complete(st)
            seen.append(rep.state.overall)
        rep.emit("completed", "job")
        seen.append(rep.state.overall)
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(rep.state.overall, 1.0)
        self.assertTrue(all(s["status"] == "completed" for s in rep.state.snapshot()["stages"]))

    def test_skipped_stage_counts_as_done_and_is_labelled(self):
        rep = EVT.Reporter()
        rep.skip("narration", "provided by you")
        s = rep.state.snapshot()
        self.assertEqual(next(x for x in s["stages"] if x["id"] == "narration")["status"], "skipped")
        self.assertAlmostEqual(rep.state.overall, EVT.WEIGHTS["narration"] / sum(EVT.WEIGHTS.values()), places=3)

    def test_failure_and_cancel_are_recorded_with_the_stage(self):
        rep = EVT.Reporter()
        rep.start("audio")
        rep.fail("audio", RuntimeError("boom"))
        rep.emit("failed", "job", error=dict(stage="audio", message="boom"))
        s = rep.state.snapshot()
        self.assertEqual(s["status"], "failed")
        self.assertEqual(s["error"]["message"], "boom")
        self.assertEqual(next(x for x in s["stages"] if x["id"] == "audio")["status"], "failed")
        rep2 = EVT.Reporter()
        rep2.start("blender_render")
        rep2.emit("cancelled", "blender_render")
        rep2.emit("cancelled", "job")
        self.assertEqual(rep2.state.status, "cancelled")

    def test_qc_autofix_pass_resets_only_the_render_stages(self):
        rep = EVT.Reporter()
        for st in EVT.ORDER[:-1]:
            rep.start(st)
            rep.complete(st, **({"passed": False, "n_checks": 30, "failed_checks": ["x"]} if st == "qc" else {}))
        before = rep.state.overall
        rep.new_pass(1, ["audio: gains lowered"])
        s = rep.state.snapshot()
        self.assertEqual(s["pass_no"], 1)
        st = {x["id"]: x["status"] for x in s["stages"]}
        self.assertEqual(st["scene_direction"], "completed")
        self.assertEqual(st["blender_render"], "pending")
        self.assertGreaterEqual(rep.state.overall, before)                                        # monotone even though stages restarted
        self.assertEqual(s["passes"][1]["fixes"], ["audio: gains lowered"])

    def test_event_log_resume_and_tail_ignore_torn_lines(self):
        p = os.path.join(_TMP, "ev.jsonl")
        r = EVT.Reporter(path=p)
        r.start("story_analysis")
        r.close()
        r2 = EVT.Reporter(path=p, resume=True)
        e = r2.complete("story_analysis")
        self.assertEqual(e["seq"], 2)
        self.assertEqual(r2.state.stages["story_analysis"]["status"], "completed")
        r2.close()
        with open(p, "a") as fh:
            fh.write('{"seq": 3, "ev')                                                            # a line still being written
        evs, off = EVT.tail(p, 0)
        self.assertEqual([x["seq"] for x in evs], [1, 2])
        with open(p, "a") as fh:
            fh.write('ent": "log", "stage": null}\n')
        evs2, _ = EVT.tail(p, off)
        self.assertEqual([x["seq"] for x in evs2], [3])

    def test_null_reporter_is_free(self):
        n = EVT.current()
        n.start("audio")
        n.progress("audio", fraction=0.5)
        with n.stage("qc"):
            pass                                                                                   # no reporter installed -> no-ops, no exceptions


class Story(unittest.TestCase):
    def test_every_topic_domain_makes_a_valid_reviewable_draft(self):
        for pid, p in TS.PACKS.items():
            d = C.create_draft(dict(mode="create", topic=p["keys"][0] + " scam"))
            r = d["review"]
            self.assertTrue(r["title"] and r["hook"]["text"] and r["ending"]["text"] and r["acts"], pid)
            self.assertGreaterEqual(len(d["script"]["segments"]), 8)
            self.assertTrue(d["script"]["estimated"])
            nar = C.draft_timing([l["text"] for l in d["lines"]])
            self.assertEqual(SD.build_plan(d["graph"], nar)["version"], 4, pid)

    def test_regenerate_is_a_deterministic_new_variation(self):
        d = C.create_draft(dict(mode="create", topic="fake WhatsApp investment group"))
        a = C.edit_story(d["id"], regenerate=True)
        b = C.create_draft(dict(mode="create", topic="fake WhatsApp investment group", variation=1))
        self.assertEqual(a["variation"], 1)
        self.assertEqual([l["text"] for l in a["lines"]], [l["text"] for l in b["lines"]])
        self.assertNotEqual(a["graph"]["story_id"], d["graph"]["story_id"])

    def test_unsupported_input_is_refused_with_reasons_never_generated(self):
        cases = [(dict(mode="create", topic="ancient temple mythology"), "unsupported_topic"), (dict(mode="create", topic="scam", language="en"), "unsupported_language"), (dict(mode="create", topic="  "), "empty_input"),
                 (dict(mode="script", script_text="hello world this is english only\n" * 9), "script_invalid"), (dict(mode="script", script_text="रात हुई।\nफोन बजा।"), "unsupported_story"),
                 (dict(mode="script", script_text="\n".join(["अस्पताल में रोहन बैठा था।"] * 9)), "unsupported_story"), (dict(mode="create", topic="scam", format="4:3"), "invalid_options"), (dict(mode="production"), "narration_invalid"),
                 (dict(mode="production", segments_json="{not json"), "narration_invalid"), (dict(mode="nonsense"), "invalid_options"), (dict(mode="create", topic="scam", director=dict(pacing="warp")), "invalid_options")]
        for req, code in cases:
            with self.assertRaises(C.StudioError, msg=str(req)) as cm:
                C.create_draft(req)
            self.assertEqual(cm.exception.code, code, req)
            self.assertTrue(cm.exception.message)
        with self.assertRaises(C.StudioError) as cm:
            C.create_draft(dict(mode="script", script_text="\n".join(["रात के ग्यारह बजे। पैसे 50000 दो।"] * 9)))
        self.assertIn("50000", " ".join(cm.exception.reasons))                                    # digits cannot be narrated: refused with the offending text and a suggestion

    def test_script_mode_accepts_text_story_md_and_story_json(self):
        lines = [l["text"] for l in C.create_draft(dict(mode="create", topic="lottery prize scam"))["lines"]]
        plain = C.create_draft(dict(mode="script", script_text="\n".join(lines)))
        md = C.create_draft(dict(mode="script", script_text="# इनाम\nprotagonist: रोहन, male, young man\n---\n" + "\n".join(lines)))
        js = C.create_draft(dict(mode="script", story_json=json.dumps(dict(title="इनाम", lines=lines))))
        for d in (plain, md, js):
            self.assertEqual(len(d["lines"]), len(lines))
        self.assertEqual(md["graph"]["cast"]["protagonist"]["name"], "रोहन")
        self.assertEqual(js["graph"]["title"], "इनाम")
        self.assertIn("कहानी", " ".join(plain["warnings"]))                                        # no title given -> told the end card will use the default

    def test_production_mode_graph_is_the_cli_graph_and_plan_is_byte_identical(self):
        for key in ("a_whatsapp_investment", "b_lottery_fee", "c_atm_helper"):
            d = C.create_draft(dict(mode="production", example=key))
            g_cli, nar = PR.parse(os.path.join(ROOT, "stories/production", key, "story.md"), os.path.join(ROOT, "stories/production", key, "segments.json"))
            self.assertEqual(d["graph"]["story_id"], g_cli["story_id"], key)
            self.assertEqual([(b["id"], b["act"], b["loc"], b["time"]) for b in d["graph"]["beats"]], [(b["id"], b["act"], b["loc"], b["time"]) for b in g_cli["beats"]])
            p_ui = PR.plan_for(d["graph"], nar, 11, {})
            p_cli = PR.plan_for(g_cli, nar, 11, {})
            self.assertEqual(json.dumps(p_ui, sort_keys=True, default=list), json.dumps(p_cli, sort_keys=True, default=list), f"{key}: UI defaults must not change the plan")
            self.assertTrue(d["narration"] and d["script"]["estimated"] is False)

    def test_edits_are_validated_and_never_recast_the_film(self):
        d = C.create_draft(dict(mode="production", example="c_atm_helper"))
        g2 = C.edit_story(d["id"], edits=dict(beats={d["graph"]["beats"][2]["id"]: dict(emotion="fear")}, title="नया नाम"))["graph"]
        self.assertEqual(g2["story_id"], d["graph"]["story_id"])
        self.assertEqual(g2["beats"][2]["emotion"], "fear")
        self.assertEqual(g2["title"], "नया नाम")
        for bad in (dict(beats={"n03": dict(act="HAND_OVER")}), dict(beats={"n03": dict(act="NOT_AN_ACT")}), dict(beats={"n99": dict(emotion="fear")}), dict(beats={"n03": dict(emotion="ecstatic")}),
                    dict(beats={"n03": dict(loc="moon_base")}), dict(cast=dict(protagonist=dict(archetype="wizard")))):
            with self.assertRaises(C.StudioError, msg=str(bad)):
                C.edit_story(d["id"], edits=bad)
        self.assertEqual(C.load_draft(d["id"])["graph"]["beats"][2]["emotion"], "fear")           # a refused edit leaves the saved draft untouched

    def test_script_edit_reanalyses_and_provided_narration_is_read_only(self):
        d = C.create_draft(dict(mode="create", topic="fake WhatsApp investment group"))
        sid = d["lines"][4]["id"]
        d2 = C.edit_script(d["id"], [dict(id=sid, text="उसने धीरे से हाथ आगे बढ़ाया।")])
        self.assertEqual(next(l for l in d2["lines"] if l["id"] == sid)["text"], "उसने धीरे से हाथ आगे बढ़ाया।")
        with self.assertRaises(C.StudioError) as cm:
            C.edit_script(d["id"], [dict(id=sid, text="OTP 1234")])
        self.assertEqual(cm.exception.code, "script_invalid")
        p = C.create_draft(dict(mode="production", example="a_whatsapp_investment"))
        with self.assertRaises(C.StudioError) as cm:
            C.edit_script(p["id"], [dict(id="n01", text="x")])
        self.assertEqual(cm.exception.code, "provided_narration")

    def test_environment_and_character_preferences(self):
        d = C.create_draft(dict(mode="create", topic="lottery prize scam", environment=dict(mode="force", location="cafe"), character=dict(protagonist=dict(archetype="student", gender="female"), partner=dict(archetype="teacher"))))
        self.assertEqual({s["loc"] for s in d["review"]["scenes"]}, {"cafe"})
        self.assertEqual((d["graph"]["cast"]["protagonist"]["archetype"], d["graph"]["cast"]["protagonist"]["gender"]), ("student", "female"))
        self.assertEqual(d["graph"]["cast"]["principal"]["archetype"], "teacher")
        b = C.create_draft(dict(mode="production", example="b_lottery_fee", environment=dict(mode="force", location="bank")))
        self.assertEqual({s["loc"] for s in b["review"]["scenes"]}, {"bank"})
        self.assertEqual({s["time"] for s in b["review"]["scenes"]}, {"day"})                     # a bank is never night, even when forced
        with self.assertRaises(C.StudioError):
            C.create_draft(dict(mode="create", topic="scam", environment=dict(mode="force", location="moon_base")))

    def test_review_card_has_every_required_field(self):
        r = C.create_draft(dict(mode="production", example="c_atm_helper"))["review"]
        for k in ("title", "hook", "protagonist", "supporting", "conflict", "psychology", "acts", "ending", "est_duration_s", "scenes"):
            self.assertTrue(r[k], k)
        self.assertEqual(r["psychology"][0]["name"], "Misplaced trust in a helper")               # detected from the wording, with the cue words as evidence
        self.assertTrue(r["psychology"][0]["cues"])


class Director(unittest.TestCase):
    def setUp(self):
        d = C.create_draft(dict(mode="production", example="a_whatsapp_investment"))
        self.g, self.nar = d["graph"], PR.parse(os.path.join(ROOT, "stories/production/a_whatsapp_investment/story.md"), os.path.join(ROOT, "stories/production/a_whatsapp_investment/segments.json"))[1]

    def test_auto_changes_nothing(self):
        p = SD.build_plan(self.g, self.nar)
        q = DO.apply(copy.deepcopy(p), {"pacing": "auto", "camera": "auto", "captions": True, "audio": {"music": 1.0}})
        self.assertEqual(json.dumps(p, sort_keys=True, default=list), json.dumps(q, sort_keys=True, default=list))

    def test_pacing_and_camera_change_only_moves_never_size_target_or_cuts(self):
        p = SD.build_plan(self.g, self.nar)
        for opts in (dict(pacing="calm"), dict(pacing="intense"), dict(camera="locked"), dict(camera="push_in")):
            q = DO.apply(copy.deepcopy(p), opts)
            for a, b in zip(p["shots"], q["shots"]):
                self.assertEqual((a["t0"], a["t1"], a["id"]), (b["t0"], b["t1"], b["id"]))
                if a.get("camera"):
                    self.assertEqual((a["camera"]["size"], a["camera"]["target"]), (b["camera"]["size"], b["camera"]["target"]))
            self.assertEqual(q["director"], DO.normalize(opts))
        self.assertTrue(all(s["camera"]["move"] in ("hold", "rack_focus") for s in DO.apply(copy.deepcopy(p), dict(camera="locked"))["shots"] if s.get("camera")))
        self.assertTrue(any(a["camera"]["move"] != b["camera"]["move"] for a, b in zip(p["shots"], DO.apply(copy.deepcopy(p), dict(pacing="calm"))["shots"]) if a.get("camera")))

    def test_captions_off_and_audio_multipliers(self):
        q = DO.apply(SD.build_plan(self.g, self.nar), dict(captions=False, audio=dict(music=0.5, sfx=0.0)))
        self.assertIs(q["captions"], False)
        self.assertAlmostEqual(q["audio_cfg"]["music"], 0.15)
        self.assertEqual(q["audio_cfg"]["sfx"], 0.0)
        for bad in (dict(pacing="warp"), dict(camera="orbit"), dict(audio=dict(music=3.0))):
            with self.assertRaises(DO.OptionsInvalid):
                DO.normalize(bad)

    def test_graph_carries_director_options_into_every_replan(self):
        d = C.create_draft(dict(mode="production", example="a_whatsapp_investment", director=dict(pacing="calm", audio=dict(music=0.5)), typography=dict(captions=False)))
        self.assertEqual(d["graph"]["director"], dict(pacing="calm", captions=False, audio=dict(music=0.5)))
        p = PR.plan_for(d["graph"], self.nar, 11, {})
        self.assertIs(p["captions"], False)
        self.assertAlmostEqual(p["audio_cfg"]["music"], 0.15)
        self.assertEqual(PR.build(d["graph"], self.nar, seed=11, fixes={"_audio": {"music": 0.1}})["audio_cfg"]["music"], 0.1)   # an automatic QC fix wins over the user's level


class Movie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(ROOT, "output/production/a_whatsapp_investment")
        if not os.path.exists(os.path.join(cls.dir, "plan.json")):
            raise unittest.SkipTest("accepted film A is not rendered on this machine")
        cls.plan = json.load(open(os.path.join(cls.dir, "plan.json"), encoding="utf-8"))
        cls.graph = json.load(open(os.path.join(cls.dir, "story_graph.json"), encoding="utf-8"))
        cls.qc = json.load(open(os.path.join(cls.dir, "qc_report.json")))

    def test_shot_inspector_view_has_everything_the_screen_shows(self):
        v = M.shots_view(self.plan, self.graph, self.qc)
        self.assertEqual(len(v), len(self.plan["shots"]))
        s = next(x for x in v if x["camera"])
        for k in ("id", "duration", "characters", "location", "actions", "emotion", "camera", "audio_events", "qc", "text", "act"):
            self.assertIn(k, s)
        self.assertTrue(all(x["qc"]["state"] == "ok" for x in v))                                 # film A passed all 30 gates -> nothing flagged
        self.assertTrue(any(x["audio_events"] for x in v))

    def test_qc_evidence_flags_the_shots_it_names(self):
        f = M.flag_shots(dict(evidence=dict(framing=dict(clipped=[dict(shot="S03")], under_caption=[], too_small=["S05"]), static_shots=["S07"], ik=dict(unreachable_events=[dict(shot="S09")]))))
        self.assertEqual(sorted(f), ["S03", "S05", "S07", "S09"])

    def test_edits_are_validated_before_they_reach_the_director(self):
        g = copy.deepcopy(self.graph)
        sh = next(s for s in self.plan["shots"] if s.get("camera"))
        g2 = M._op(copy.deepcopy(g), self.plan, dict(op="camera", shot=sh["id"], size="close", move="push", dx=40))
        self.assertEqual(g2["fixes"][sh["key"]]["camera"]["size"], "close")
        for bad in (dict(op="camera", shot=sh["id"], size="huge"), dict(op="camera", shot=sh["id"], move="teleport"), dict(op="camera", shot=sh["id"], dx=9999), dict(op="camera", shot="S99"), dict(op="character", char="D", skin="skin_99"),
                    dict(op="character", char="Z", skin="skin_02"), dict(op="character", char="D", top="cape"), dict(op="frobnicate"), dict(op="director", pacing="warp")):
            with self.assertRaises(C.StudioError, msg=str(bad)):
                M._op(copy.deepcopy(g), self.plan, bad)

    def test_one_shot_camera_edit_re_renders_only_that_shot(self):
        sh = next(s for s in self.plan["shots"] if s.get("camera") and s["id"] == "S07")
        g = M._op(copy.deepcopy(self.graph), self.plan, dict(op="camera", shot=sh["id"], size="close" if sh["camera"]["size"] != "close" else "medium", dx=40))
        from engine.skeleton import narration_io as NI
        new = PR.plan_for(g, NI.load(os.path.join(ROOT, "stories/production/a_whatsapp_investment/segments.json")), 11, g["fixes"])
        self.assertEqual(M.validate_plan(new), [])
        imp, _, _ = M.impact(self.plan, new)
        self.assertGreater(imp["frames_changed"], 0)
        self.assertLess(imp["frames_changed"], 0.15 * imp["frames_total"])
        self.assertEqual(imp["shots_affected"], ["S07"])
        self.assertFalse(imp["audio_remixed"])


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from engine.studio import server as SV
        cls.app = SV.create_app(test_mode=True, max_running=1)
        cls.c = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        for pid in list(SV_MGR().procs):
            try:
                SV_MGR().cancel(pid)
            except Exception:                                                                       # noqa: BLE001
                pass
        SV_MGR().shutdown()

    def draft(self):
        r = self.c.post("/api/story", json=dict(mode="production", example="a_whatsapp_investment"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def wait(self, pid, until=("completed", "failed", "cancelled"), t=40):
        end = time.time() + t
        while time.time() < end:
            s = self.c.get(f"/api/production/{pid}/status").json()
            if s["status"] in until:
                return s
            time.sleep(0.2)
        self.fail(f"production {pid} did not reach {until}: {s['status']}")

    def test_options_and_routes_exist_with_and_without_api_prefix(self):
        o = self.c.get("/api/options").json()
        self.assertEqual([m["id"] for m in o["modes"]], ["create", "script", "production"])
        self.assertEqual(self.c.get("/options").json()["levels"], ["simple", "director", "expert"])
        self.assertIn("Kathaaya", self.c.get("/").text)
        self.assertEqual(self.c.get("/static/app.js").status_code, 200)

    def test_story_validation_returns_422_with_the_reasons(self):
        r = self.c.post("/api/story", json=dict(mode="create", topic="ancient temple mythology"))
        self.assertEqual(r.status_code, 422)
        e = r.json()["error"]
        self.assertEqual(e["code"], "unsupported_topic")
        self.assertTrue(e["reasons"] and e["hint"])
        r = self.c.post("/api/script", json=dict(script_text="रात हुई।\nफोन बजा।"))
        self.assertEqual(r.status_code, 422)
        self.assertIn("8-40", " ".join(r.json()["error"]["reasons"]))
        self.assertEqual(self.c.get("/api/draft/d_00000000").status_code, 404)
        self.assertEqual(self.c.get("/api/production/nope/status").status_code, 404)

    def test_create_script_and_production_modes_produce_reviewable_drafts(self):
        a = self.c.post("/api/story", json=dict(mode="create", topic="OTP bank KYC call scam")).json()
        lines = "\n".join(s["text"] for s in a["script"]["segments"])
        b = self.c.post("/api/script", json=dict(script_text="# मेरी कहानी\n" + lines)).json()
        c = self.c.post("/api/story", json=dict(mode="production", example="c_atm_helper")).json()
        for d in (a, b, c):
            self.assertTrue(d["review"]["title"] and d["script"]["segments"])
        self.assertEqual(b["review"]["title"], "मेरी कहानी")
        e = self.c.post("/api/script", json=dict(draft_id=a["id"], segments=[dict(id="n05", text="उसने काँपता हाथ बढ़ाया।")])).json()
        self.assertEqual(e["script"]["segments"][4]["text"], "उसने काँपता हाथ बढ़ाया।")

    def test_production_events_are_structured_ordered_and_stream_over_sse(self):
        pid = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.02))).json()["production_id"]
        msgs = []
        with self.c.stream("GET", f"/api/production/{pid}/events") as r:
            self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
            for line in r.iter_lines():
                if line.startswith("data:"):
                    msgs.append(json.loads(line[5:]))
        evs = [m["event"] for m in msgs]
        self.assertEqual([e["seq"] for e in evs], list(range(1, len(evs) + 1)))
        self.assertEqual(evs[0]["stage"], "job")
        self.assertEqual(evs[-1]["event"], "completed")
        started = [e["stage"] for e in evs if e["event"] == "started" and e["stage"] != "job"]
        self.assertEqual(started, EVT.ORDER)
        prog = [e for e in evs if e["event"] == "progress" and e["stage"] == "blender_render"]
        self.assertTrue(prog)
        for k in ("shot", "total_shots", "frame", "total_frames", "fps", "elapsed_seconds", "eta_seconds", "status", "overall"):
            self.assertIn(k, prog[0])
        ov = [e["overall"] for e in evs]
        self.assertEqual(ov, sorted(ov))
        self.assertEqual(msgs[-1]["state"]["status"], "completed")
        s = self.c.get(f"/api/production/{pid}/status").json()
        self.assertEqual((s["status"], s["overall"]), ("completed", 1.0))
        after = [json.loads(l[5:])["event"]["seq"] for l in self._sse(pid, after=len(evs) - 1)]
        self.assertEqual(after, [len(evs)])                                                        # reconnect with ?after=<seq> replays only what was missed

    def _sse(self, pid, after=0):
        out = []
        with self.c.stream("GET", f"/api/production/{pid}/events?after={after}") as r:
            out = [l for l in r.iter_lines() if l.startswith("data:")]
        return out

    def test_cancel_stops_a_running_production_and_frees_the_slot(self):
        pid = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.4))).json()["production_id"]
        self.wait(pid, ("running",))
        time.sleep(1.5)
        r = self.c.post("/api/cancel", json=dict(production_id=pid)).json()
        self.assertEqual(r["status"], "cancelled")
        self.assertTrue(any(s["status"] == "cancelled" for s in r["stages"]))
        pgid = int(open(os.path.join(J.pdir(pid), "worker.pid")).read())
        self.assertFalse(SV_MGR()._alive(pid, None, pgid))                                        # the worker process (and its children) are really gone
        self.assertEqual(self.c.post("/api/cancel", json=dict(production_id=pid)).status_code, 409)
        nxt = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.01))).json()["production_id"]
        self.assertEqual(self.wait(nxt)["status"], "completed")

    def test_a_failing_stage_is_reported_with_stage_and_reason(self):
        pid = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.02, fail_at="compositing"))).json()["production_id"]
        s = self.wait(pid)
        self.assertEqual(s["status"], "failed")
        self.assertEqual(s["error"]["stage"], "compositing")
        self.assertIn("simulated failure", s["error"]["message"])
        self.assertEqual(next(x for x in s["stages"] if x["id"] == "compositing")["status"], "failed")
        self.assertEqual(next(x for x in s["stages"] if x["id"] == "qc")["status"], "pending")

    def test_second_production_waits_in_the_queue_and_a_queued_one_can_be_cancelled(self):
        a = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.3))).json()["production_id"]
        self.wait(a, ("running",))
        b = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.01))).json()
        self.assertEqual(b["status"]["status"], "queued")
        self.assertEqual(b["status"]["queue_position"], 1)
        r = self.c.post("/api/cancel", json=dict(production_id=b["production_id"])).json()
        self.assertEqual(r["status"], "cancelled")
        self.c.post("/api/cancel", json=dict(production_id=a))

    def test_a_worker_that_dies_without_a_terminal_event_is_marked_failed(self):
        pid = self.c.post("/api/generate", json=dict(draft_id=self.draft(), approve=True, test=dict(step=0.5))).json()["production_id"]
        self.wait(pid, ("running",))
        time.sleep(0.8)
        import signal
        os.killpg(int(open(os.path.join(J.pdir(pid), "worker.pid")).read()), signal.SIGKILL)       # crash: no chance to write anything
        s = self.wait(pid, ("failed", "cancelled"))
        self.assertEqual(s["status"], "failed")
        self.assertEqual(s["error"]["type"], "WorkerExited")

    def test_restart_recovery_marks_orphaned_running_productions_failed(self):
        d = os.path.join(C.PRODS, "p_orphan_test")
        os.makedirs(d, exist_ok=True)
        json.dump(dict(id="p_orphan_test", mode="production", title="x", settings={}), open(os.path.join(d, "job.json"), "w"))
        r = EVT.Reporter(path=os.path.join(d, "events.jsonl"))
        r.emit("started", "job")
        r.start("blender_render")
        r.close()
        J.Manager(max_running=1, test_mode=True).shutdown()
        s = EVT.fold(EVT.read(os.path.join(d, "events.jsonl")))
        self.assertEqual(s.status, "failed")
        self.assertEqual(s.error["type"], "ServerRestart")

    def test_upload_accepts_only_declared_types(self):
        r = self.c.post("/api/upload?kind=audio&name=x.wav", content=b"RIFF0000")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.post("/api/upload?kind=audio&name=x.exe", content=b"MZ").status_code, 422)


def SV_MGR():
    from engine.studio import server as SV
    return SV.mgr()


if __name__ == "__main__":
    unittest.main()
