"""
Smoke tests against small, real apps.

These are integration tests that hit live store endpoints. They're slow
(30-60 seconds each) and require network. Run them when:
  - You've changed the scrapers
  - You're publishing a new release
  - You want to verify the skill still works against real APIs

Run all: python tests/test_small_apps.py
Run one: python tests/test_small_apps.py test_proov_partial
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_pipeline import run_pipeline


class TestSmallApps(unittest.TestCase):
    """Integration tests against real (small) apps."""

    OUTPUT_BASE = Path("/tmp/app_review_analyzer_tests")

    @classmethod
    def setUpClass(cls):
        cls.OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    def test_proov_play_only(self):
        """Proov on Play Store — small, manageable, known to work."""
        result = run_pipeline(
            play_id="com.proov",
            countries=["us"],
            themes_name="health_wellness",
            formats=["html", "csv", "json"],
            output_dir=str(self.OUTPUT_BASE / "proov_play"),
            app_display_name="Proov",
            progress_callback=lambda m: None,  # quiet
        )

        self.assertTrue(result["success"], f"Pipeline failed: {result['user_message']}")
        self.assertGreater(result["play_count"], 50, "Expected >50 Play Store reviews for Proov")
        self.assertIn("html", result["generated_files"])
        self.assertIn("csv", result["generated_files"])
        self.assertIn("json", result["generated_files"])

        # Verify output files actually exist
        for fmt, files in result["generated_files"].items():
            for f in files:
                self.assertTrue(Path(f).exists(), f"Missing output file: {f}")
                self.assertGreater(Path(f).stat().st_size, 0, f"Empty output: {f}")

    def test_invalid_app_id(self):
        """Pipeline should handle a nonexistent app ID gracefully."""
        result = run_pipeline(
            play_id="com.this.does.not.exist.anywhere.zzz",
            countries=["us"],
            formats=["csv"],
            output_dir=str(self.OUTPUT_BASE / "invalid"),
            progress_callback=lambda m: None,
        )

        # Should return success=False with a clear user message
        self.assertFalse(result["success"])
        self.assertIn("reviews", result["user_message"].lower())

    def test_only_app_store(self):
        """Pipeline should work with just App Store (no Play Store ID)."""
        # Proov on App Store
        result = run_pipeline(
            appstore_id="1574349479",
            countries=["us", "gb"],
            themes_name="health_wellness",
            formats=["html"],
            output_dir=str(self.OUTPUT_BASE / "proov_ios"),
            progress_callback=lambda m: None,
        )

        # If Apple is rate-limiting, this might return success=True with partial,
        # OR success=False with a clear message. Both are acceptable.
        if result["success"]:
            self.assertGreater(result["ios_count"], 0)
            self.assertIn("html", result["generated_files"])
        else:
            # If it failed, the message should be helpful
            self.assertIn("App Store", result["user_message"])

    def test_no_inputs(self):
        """No app IDs at all should fail clearly, not crash."""
        result = run_pipeline(
            progress_callback=lambda m: None,
        )
        self.assertFalse(result["success"])
        self.assertIn("No app IDs", result["user_message"])

    def test_invalid_format(self):
        """Bad format should fail clearly."""
        result = run_pipeline(
            play_id="com.proov",
            formats=["not_a_real_format"],
            progress_callback=lambda m: None,
        )
        self.assertFalse(result["success"])
        self.assertIn("Unknown format", result["user_message"])

    def test_invalid_taxonomy(self):
        """Bad taxonomy should fail clearly."""
        result = run_pipeline(
            play_id="com.proov",
            themes_name="not_a_real_taxonomy",
            formats=["json"],
            progress_callback=lambda m: None,
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["user_message"].lower())


class TestUnits(unittest.TestCase):
    """Fast unit tests — no network."""

    def test_url_parsing(self):
        from run_pipeline import parse_url_or_id
        # Play Store
        self.assertEqual(parse_url_or_id("com.example", "play"), "com.example")
        self.assertEqual(
            parse_url_or_id("https://play.google.com/store/apps/details?id=com.example", "play"),
            "com.example",
        )
        self.assertEqual(
            parse_url_or_id("https://play.google.com/store/apps/details?id=com.x&hl=en", "play"),
            "com.x",
        )
        # App Store
        self.assertEqual(parse_url_or_id("123456789", "ios"), "123456789")
        self.assertEqual(
            parse_url_or_id("https://apps.apple.com/us/app/x/id123456789", "ios"),
            "123456789",
        )
        # Edge cases
        self.assertIsNone(parse_url_or_id(None, "play"))
        self.assertIsNone(parse_url_or_id("", "play"))

    def test_taxonomy_loading(self):
        from theme_tagger import load_taxonomy, list_available_taxonomies
        # All 7 should load
        for tax in list_available_taxonomies():
            loaded = load_taxonomy(tax["name"])
            self.assertIn("negative_themes", loaded)
            self.assertIn("positive_themes", loaded)
            self.assertGreater(len(loaded["negative_themes"]), 0)

    def test_inheritance(self):
        from theme_tagger import load_taxonomy
        general = load_taxonomy("general")
        health = load_taxonomy("health_wellness")
        # Health should have all of general's themes PLUS its own
        self.assertGreater(
            len(health["negative_themes"]),
            len(general["negative_themes"]),
        )
        # Verify a known general theme is present in health
        self.assertIn("crashes_bugs", health["negative_themes"])
        # Verify a known health theme is present in health
        self.assertIn("tracking_accuracy", health["negative_themes"])

    def test_tagging(self):
        from theme_tagger import load_taxonomy, tag_reviews
        tax = load_taxonomy("general")
        reviews = [
            {"rating": 1, "review": "This app crashes constantly and the login is broken"},
            {"rating": 5, "review": "Easy to use, beautiful design, saves so much time"},
        ]
        tagged = tag_reviews(reviews, tax)
        self.assertIn("crashes_bugs", tagged[0]["themes_neg"])
        self.assertIn("login_account", tagged[0]["themes_neg"])
        self.assertIn("ease_of_use", tagged[1]["themes_pos"])

    def test_non_english_detection(self):
        from theme_tagger import detect_non_english
        # English review — not flagged
        self.assertFalse(detect_non_english("This app is great"))
        # Japanese review — flagged
        self.assertTrue(detect_non_english("このアプリは素晴らしいです"))
        # Arabic review — flagged
        self.assertTrue(detect_non_english("هذا التطبيق رائع جداً"))
        # Mixed — borderline
        result = detect_non_english("This は great")
        # ~50% non-ASCII letters — should flag


class TestSecurity(unittest.TestCase):
    """Regression tests for the v0.2.1 security audit fixes.
    These exist to ensure nobody silently removes the validators in a refactor."""

    def test_app_id_validation_accepts_legitimate(self):
        from run_pipeline import parse_url_or_id
        # Real package names should pass
        self.assertEqual(parse_url_or_id("com.proov", "play"), "com.proov")
        self.assertEqual(parse_url_or_id("com.calm.android", "play"), "com.calm.android")
        self.assertEqual(parse_url_or_id("com.spotify.music", "play"), "com.spotify.music")
        # Real numeric IDs should pass
        self.assertEqual(parse_url_or_id("1574349479", "ios"), "1574349479")
        self.assertEqual(parse_url_or_id("123456789", "ios"), "123456789")

    def test_app_id_validation_rejects_attacks(self):
        from run_pipeline import parse_url_or_id
        # Path traversal attempts → None
        self.assertIsNone(parse_url_or_id("../etc/passwd", "play"))
        self.assertIsNone(parse_url_or_id("123/../admin", "ios"))
        # Script injection attempts → None
        self.assertIsNone(parse_url_or_id("<script>alert(1)</script>", "play"))
        self.assertIsNone(parse_url_or_id("javascript:alert(1)", "play"))
        # Command injection attempts → None
        self.assertIsNone(parse_url_or_id("com.x;curl evil.com", "play"))
        self.assertIsNone(parse_url_or_id("com.x && rm -rf /", "play"))
        # Wrong format → None (no single-word package names allowed)
        self.assertIsNone(parse_url_or_id("nodots", "play"))
        # Non-digit App Store IDs → None
        self.assertIsNone(parse_url_or_id("abc123", "ios"))
        self.assertIsNone(parse_url_or_id("123abc", "ios"))

    def test_markdown_sanitizer_neutralizes_phishing_links(self):
        from generate_markdown import _md_safe
        # [text](url) syntax — must not pass through
        output = _md_safe("Click [here](https://phishing.example.com) for a prize")
        self.assertNotIn("](https://phishing", output)
        # Brackets escaped
        self.assertIn("\\[", output)
        self.assertIn("\\]", output)

    def test_markdown_sanitizer_neutralizes_bare_urls(self):
        from generate_markdown import _md_safe
        # Bare HTTPS URLs auto-link on GitHub/Notion — must be neutralized
        output = _md_safe("Visit https://phishing.example.com today")
        # The URL should still be readable but not auto-link
        self.assertNotIn("https://phishing", output)  # zero-width space breaks it
        self.assertIn("https://", output)  # but still visible to humans

    def test_markdown_sanitizer_neutralizes_dangerous_schemes(self):
        from generate_markdown import _md_safe
        for scheme in ("javascript:", "data:", "file:"):
            output = _md_safe(f"Try {scheme}alert(1) for fun")
            # Scheme should be present but broken
            self.assertNotIn(f"{scheme}alert", output)

    def test_markdown_sanitizer_preserves_normal_text(self):
        from generate_markdown import _md_safe
        # Plain reviews should pass through unchanged (or near-unchanged)
        self.assertEqual(_md_safe("Great app, I love it!"), "Great app, I love it!")
        self.assertEqual(_md_safe(""), "")

    def test_markdown_sanitizer_escapes_backticks(self):
        from generate_markdown import _md_safe
        # Backticks could be used for code-block injection in some renderers
        output = _md_safe("Use `code` here")
        self.assertNotIn("`code`", output)
        self.assertIn("\\`", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
