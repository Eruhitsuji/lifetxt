"""Keep the dedicated Quick capture guides aligned with shipped semantics."""

import datetime
import unittest
from pathlib import Path

from lifetxt.shorthand import describe_date_tokens, describe_sigils, parse_capture


ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "docs" / "en" / "quick-capture.md"
JA = ROOT / "docs" / "ja" / "quick-capture.md"


class QuickCaptureDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guides = (EN.read_text(encoding="utf-8"), JA.read_text(encoding="utf-8"))

    def test_both_guides_list_every_authoritative_sigil_and_date_token(self):
        for guide in self.guides:
            for token, _meaning in describe_sigils():
                self.assertIn("`%s`" % token, guide)
            for token_group, _meaning in describe_date_tokens():
                for token in token_group.replace("..", "/").split("/"):
                    token = token.strip()
                    if token and " " not in token:
                        self.assertIn(token, guide)

    def test_documented_combination_matches_the_parser(self):
        title, details = parse_capture(
            "Buy milk @home #errand !high ^2026-10-02",
            today=datetime.date(2026, 10, 1),
        )
        self.assertEqual("Buy milk", title)
        self.assertEqual(
            {
                "project": ["home"],
                "tag": ["errand"],
                "priority": ["high"],
                "due": ["2026-10-02"],
            },
            details,
        )

    def test_guides_cover_literal_and_repeated_value_behavior(self):
        title, details = parse_capture(r"Mail a@b.com \@home #a #a @x @y")
        self.assertEqual("Mail a@b.com @home", title)
        self.assertEqual(["a", "a"], details["tag"])
        self.assertEqual(["x", "y"], details["project"])
        for guide in self.guides:
            self.assertIn("a@b.com", guide)
            self.assertIn("--no-shorthand", guide)
            self.assertIn("POST /api/items/raw", guide)

    def test_established_discovery_pages_link_to_the_guide(self):
        paths = (
            ROOT / "readme.md",
            ROOT / "docs" / "en" / "readme.md",
            ROOT / "docs" / "ja" / "readme.md",
            ROOT / "docs" / "en" / "getting-started.md",
            ROOT / "docs" / "ja" / "getting-started.md",
            ROOT / "docs" / "en" / "cli.md",
            ROOT / "docs" / "ja" / "cli.md",
            ROOT / "docs" / "en" / "web.md",
            ROOT / "docs" / "ja" / "web.md",
            ROOT / "docs" / "en" / "ai-integration.md",
            ROOT / "docs" / "ja" / "ai-integration.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn("quick-capture.md", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
