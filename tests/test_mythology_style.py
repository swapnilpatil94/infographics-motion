"""Regression tests for the KATHAAYA mythology style profile."""
import tempfile
import unittest

from kathaya import pipeline, styles


class MythologyStyleTests(unittest.TestCase):
    def test_default_style_remains_available_and_has_no_forced_mythology_rules(self):
        profile = styles.get_style("kathaya_default")
        self.assertEqual(profile["label"], "KATHAAYA Story")
        self.assertEqual(profile["guidance"], "")

    def test_mythology_profile_requires_source_aware_ink_direction(self):
        profile = styles.get_style("mythology_ink")
        self.assertIn("MYTHOLOGY INK MODE", profile["guidance"])
        self.assertIn("never silently replace", profile["guidance"])
        self.assertIn("narration is the source of truth", profile["guidance"].lower())

    def test_user_direction_is_preserved_after_profile_guidance(self):
        direction = styles.direct_for_style("mythology_ink", "Keep the opening close-up.")
        self.assertIn("MYTHOLOGY INK MODE", direction)
        self.assertTrue(direction.endswith("Keep the opening close-up."))

    def test_unknown_style_fails_with_supported_options(self):
        with self.assertRaisesRegex(ValueError, "kathaya_default.*mythology_ink"):
            styles.get_style("made_up_style")

    def test_pipeline_accepts_mythology_profile_and_persists_it(self):
        original_projects = pipeline.PROJECTS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pipeline.PROJECTS = tmp
                project = pipeline.create("द्रौपदी का सवाल", style="mythology_ink")
                self.assertEqual(project["input"]["style"], "mythology_ink")
        finally:
            pipeline.PROJECTS = original_projects

    def test_pipeline_rejects_unknown_profile_before_creating_project(self):
        with self.assertRaises(pipeline.ProjectError) as raised:
            pipeline.create("test story", style="made_up_style")
        self.assertEqual(raised.exception.code, "invalid_options")


if __name__ == "__main__":
    unittest.main()
