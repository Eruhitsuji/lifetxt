"""Labeled form rows align actions with the inputs (#1522)."""

import re
import unittest

from lifetxt.web_assets import HTML_PAGE


class FormAlignmentTests(unittest.TestCase):
    def rules(self, selector):
        return re.findall(re.escape(selector) + r"\s*\{([^{}]*)\}", HTML_PAGE)

    def test_labeled_rows_align_at_bottom(self):
        for selector in (".focus-quick-add", ".review-range-bar", ".graph-toolbar"):
            with self.subTest(selector=selector):
                alignment = [
                    value.strip()
                    for rule in self.rules(selector)
                    for value in re.findall(r"align-items:\s*([^;]+)", rule)
                ]
                self.assertEqual(["flex-end"], alignment)

    def test_wrapping_and_mobile_review_stack_remain(self):
        for selector in (".review-range-bar", ".graph-toolbar"):
            self.assertTrue(any("flex-wrap: wrap" in r for r in self.rules(selector)))
        self.assertTrue(
            any("flex: 1 1 100%" in r for r in self.rules(".review-range-bar > *"))
        )

    def test_inputs_keep_visible_associated_labels(self):
        for field in (
            "focus-quick-title",
            "review-project",
            "review-from",
            "review-to",
            "graph-root",
            "graph-depth",
        ):
            with self.subTest(field=field):
                self.assertRegex(
                    HTML_PAGE,
                    rf'<label[^>]*for="{field}"><span>[^<]+</span><input id="{field}"',
                )
