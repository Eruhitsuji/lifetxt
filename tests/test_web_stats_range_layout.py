"""Stats breakdown date controls reuse the shared form layout (#1524)."""

import re
import unittest
from html.parser import HTMLParser
from lifetxt.web_assets import HTML_PAGE


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class StatsRangeLayoutTests(unittest.TestCase):
    def test_dates_have_visible_associated_shared_labels(self):
        for field, text in (("breakdown-from", "From"), ("breakdown-to", "To")):
            self.assertRegex(
                HTML_PAGE,
                rf'<label class="web-field-label" for="{field}"><span>{text}</span><input',
            )

    def test_controls_retain_handlers_and_use_shared_sizes(self):
        parser = Controls()
        parser.feed(HTML_PAGE)
        for field in ("breakdown-from", "breakdown-to"):
            control = next(a for tag, a in parser.tags if a.get("id") == field)
            self.assertEqual("date", control["type"])
            self.assertEqual("loadStatsBreakdown()", control["oninput"])
            self.assertNotIn("style", control)
        button = next(
            a
            for tag, a in parser.tags
            if tag == "button"
            and "getElementById('breakdown-from').value=''" in a.get("onclick", "")
        )
        self.assertIn(
            "getElementById('breakdown-to').value='';loadStatsBreakdown()",
            button["onclick"],
        )
        self.assertNotIn("style", button)

    def test_range_bar_wraps_and_aligns_to_input_bottom(self):
        rule = re.search(r"\.stats-range-bar\s*\{([^}]+)\}", HTML_PAGE)
        self.assertIsNotNone(rule)
        for value in ("display: flex", "align-items: flex-end", "flex-wrap: wrap"):
            self.assertIn(value, rule.group(1))
