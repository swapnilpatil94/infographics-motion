"""API, style-seed variation, Grease Pencil stroke design, delivery reframing."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import api                                            # noqa: E402
from engine.shorts import gp_strokes as G                         # noqa: E402

FIX = os.path.join(ROOT, "tests/fixtures")


class ApiValidationTests(unittest.TestCase):
    def test_missing_fields(self):
        self.assertEqual(len(api.validate_request({})), 2)

    def test_bad_style_and_aspect(self):
        e = api.validate_request({"story": "stories/why_smart_people_fall_for_scams.md", "narration_segments": "narration/why_smart_people_fall_for_scams.wav.segments.json",
                                  "style": {"bogus": 1}, "aspect_ratio": "1:1"})
        self.assertEqual(len(e), 2)

    def test_valid_request(self):
        self.assertEqual(api.validate_request({"story": "stories/why_smart_people_fall_for_scams.md", "narration_segments": "narration/why_smart_people_fall_for_scams.wav.segments.json"}), [])

    def test_rejected_request_returns_structured_error(self):
        r = api.generate({"story": "x"})
        self.assertEqual(r["status"], "rejected")

    def test_domains_listed(self):
        self.assertIn("money_psychology", api.domains())


class StyleSeedTests(unittest.TestCase):
    """style.seed is a controlled-variation knob: same seed -> same film plan, different seed -> different people/places."""

    def _plan(self, tmp, name, seed):
        pdir = os.path.join(tmp, name, "project")
        os.makedirs(pdir)
        shutil.copy(os.path.join(FIX, "analysis_cache.json"), pdir)
        from engine.factory import pipeline
        return pipeline.build_plan(os.path.join(ROOT, "stories/why_smart_people_fall_for_scams.md"), os.path.join(ROOT, "narration/why_smart_people_fall_for_scams.wav.segments.json"),
                                   name=name, out_root=tmp, log=lambda *a, **k: None, seed_salt=seed)[1]

    def test_seed_changes_dna_not_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, a2 = self._plan(tmp, "a", "x"), self._plan(tmp, "b", "y"), self._plan(tmp, "c", "x")
        dna = lambda p: {k: v["dna"]["id"] for k, v in p["characters"].items()}
        self.assertEqual(dna(a), dna(a2))
        self.assertNotEqual(dna(a), dna(b))
        self.assertEqual([s["phase"] for s in a["shots"]], [s["phase"] for s in b["shots"]])     # same story structure


class GreasePencilDesignTests(unittest.TestCase):
    def test_at_least_12_effects(self):
        self.assertGreaterEqual(len(G.SPRITES), 12)

    def test_spec_effects_present(self):
        for e in ("arrow", "underline", "scribble", "money_flow", "network", "smoke", "dust", "sweep", "ring"):
            self.assertIn(e, G.SPRITES)

    def test_every_effect_makes_valid_strokes_and_is_deterministic(self):
        for name, sp in G.SPRITES.items():
            for v in (0, sp["variants"] - 1):
                a, b = sp["gen"](v), sp["gen"](v)
                self.assertEqual(a, b, name)
                self.assertTrue(a, name)
                for st in a:
                    self.assertGreaterEqual(len(st["pts"]), 2, name)
                    for x, y, r, al in st["pts"]:
                        self.assertTrue(0 <= al <= 1 and r > 0, (name, r, al))

    def test_boil_variants_differ(self):
        for name in ("scribble", "worry", "underline"):
            self.assertNotEqual(G.SPRITES[name]["gen"](0), G.SPRITES[name]["gen"](1), name)


class ReframeTests(unittest.TestCase):
    def test_16x9_blurpad_is_1920x1080(self):
        from engine.compositing import reframe_16x9
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, "v.mp4"), os.path.join(tmp, "w.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10:duration=1", "-pix_fmt", "yuv420p", src], check=True)
            reframe_16x9(src, dst)
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "1920,1080")


if __name__ == "__main__":
    unittest.main()
