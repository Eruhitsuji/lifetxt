"""Shared form styles must apply outside Kiosk mode (#1520)."""

import re
import unittest

from lifetxt.web_assets import HTML_PAGE


def css_blocks():
    """Read block ancestry from shipped CSS, ignoring quoted/comment braces."""
    css = re.search(r"<style[^>]*>(.*?)</style>", HTML_PAGE, re.S).group(1)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", '""', css)
    stack = []
    start = 0
    blocks = []
    for match in re.finditer(r"[{};]", css):
        token = match.group()
        if token == "{":
            selector = css[start : match.start()].strip()
            blocks.append((selector, tuple(stack)))
            stack.append(selector)
        elif token == "}":
            if not stack:
                raise AssertionError("Unmatched CSS closing brace")
            stack.pop()
        start = match.end()
    if stack:
        raise AssertionError("Unclosed CSS block")
    return blocks


class SharedFormCssScopeTests(unittest.TestCase):
    def test_labels_and_graph_wrap_apply_in_normal_views(self):
        blocks = css_blocks()
        for selector in (
            ".web-field-label",
            ".focus-quick-add .web-field-label",
            ".web-field-label input",
        ):
            with self.subTest(selector=selector):
                self.assertTrue(
                    (selector, ()) in blocks,
                    f"Shared rule is not top-level: {selector}",
                )
        self.assertIn((".graph-toolbar", ()), blocks)
        self.assertNotIn((".graph-toolbar", (".kiosk-mode #items",)), blocks)

    def test_bulk_completion_styles_apply_outside_kiosk(self):
        blocks = css_blocks()
        for selector in (
            "#bulk-done-modal .modal",
            "#bulk-done-modal fieldset",
            "#bulk-done-modal [hidden]",
            "#bulk-done-modal .actions",
            ".bulk-done-fields",
            ".bulk-done-fields label",
            ".bulk-done-fields input, .bulk-done-fields select",
        ):
            with self.subTest(selector=selector):
                self.assertTrue(
                    (selector, ()) in blocks,
                    f"Shared rule is not top-level: {selector}",
                )

    def test_kiosk_grid_does_not_own_shared_form_rules(self):
        blocks = css_blocks()
        self.assertIn((".kiosk-mode #items", ()), blocks)
        self.assertIn((".kiosk-mode .item", ()), blocks)
        self.assertFalse(
            [
                selector
                for selector, parents in blocks
                if ".kiosk-mode #items" in parents
            ]
        )


if __name__ == "__main__":
    unittest.main()
