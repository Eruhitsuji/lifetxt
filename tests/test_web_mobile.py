"""Tests for the mobile Web UI.

These assert the CSS and markup that make the page usable on a phone. They are
static checks on the served page: a headless-browser suite would be stronger,
and is tracked in todo.md, but these catch the rules being removed or reverted.
"""

import re
import unittest

from lifetxt.webapp import HTML_PAGE


STYLE = "\n".join(re.findall(r"<style>(.*?)</style>", HTML_PAGE, re.S))
SCRIPT = "\n".join(re.findall(r"<script>(.*?)</script>", HTML_PAGE, re.S))


def _media_block(query):
    """Bodies of every @media block matching a query, concatenated.

    The page has several blocks for the same breakpoint, so looking at only
    the first one would miss rules that live in a later block.
    """
    bodies = []
    search_from = 0
    while True:
        start = STYLE.find(query, search_from)
        if start < 0:
            break
        index = STYLE.index("{", start)
        depth = 0
        for position in range(index, len(STYLE)):
            if STYLE[position] == "{":
                depth += 1
            elif STYLE[position] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(STYLE[index + 1:position])
                    search_from = position
                    break
        else:
            break
    return "\n".join(bodies)


class ViewportTests(unittest.TestCase):
    def test_viewport_covers_the_display_cutout(self):
        # viewport-fit=cover is what makes env(safe-area-inset-*) non-zero.
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            HTML_PAGE,
        )

    def test_safe_area_variables_are_defined(self):
        for name in ("--safe-top", "--safe-bottom", "--safe-left", "--safe-right"):
            self.assertIn(name, STYLE, name)
        self.assertIn("env(safe-area-inset-bottom", STYLE)

    def test_dynamic_viewport_height_is_used_where_supported(self):
        # Mobile browsers count the collapsing URL bar in 100vh.
        self.assertIn("@supports (height: 100dvh)", STYLE)
        self.assertIn("min-height: 100dvh", STYLE)


class TouchTests(unittest.TestCase):
    def test_selection_checkboxes_are_visible_without_hover(self):
        """A finger cannot hover.

        The desktop rule keeps `.item-check` at opacity 0 until hover, and the
        old mobile rule hid it entirely, which left no way to select a record
        and therefore nothing for bulk actions or slash commands to act on.
        """
        coarse = _media_block("@media (pointer: coarse)")

        self.assertIn(".item-check", coarse)
        self.assertIn("opacity: 1", coarse)

        narrow = _media_block("@media (max-width: 680px)")
        self.assertIn(".item-check { display: block; }", narrow)

    def test_touch_targets_have_a_minimum_height(self):
        coarse = _media_block("@media (pointer: coarse)")

        self.assertIn("min-height: 2.75rem", coarse)
        self.assertIn("button", coarse)

    def test_form_controls_avoid_the_ios_zoom_threshold(self):
        # iOS Safari zooms in on focus when an input is under 16px, and does
        # not zoom back out.
        narrow = _media_block("@media (max-width: 680px)")

        self.assertRegex(narrow, r"input, select, textarea \{\s*font-size: 16px;")


class LayoutTests(unittest.TestCase):
    def test_page_does_not_pan_sideways(self):
        self.assertIn("body { overflow-x: hidden; }", STYLE)

    def test_crowded_rows_scroll_instead_of_stacking(self):
        narrow = _media_block("@media (max-width: 680px)")

        for selector in ("header > .toolbar", ".workspace-tabs", ".quick-add-bar, .filter-bar"):
            self.assertIn(selector, narrow, selector)
        self.assertIn("overflow-x: auto", narrow)
        self.assertIn("flex-wrap: nowrap", narrow)

    def test_bulk_actions_sit_within_thumb_reach(self):
        narrow = _media_block("@media (max-width: 680px)")

        self.assertIn(".bulk-toolbar.visible", narrow)
        self.assertIn("position: fixed", narrow)
        self.assertIn("bottom: 0", narrow)
        self.assertIn("var(--safe-bottom)", narrow)

    def test_dialogs_become_bottom_sheets(self):
        narrow = _media_block("@media (max-width: 680px)")

        self.assertIn("align-items: flex-end", narrow)
        self.assertIn(".detail-modal, .modal", narrow)

    def test_command_palette_fits_a_phone(self):
        narrow = _media_block("@media (max-width: 680px)")

        self.assertIn(".cmdk", narrow)
        self.assertIn("var(--safe-top)", narrow)

    def test_content_clears_the_fixed_bottom_furniture(self):
        narrow = _media_block("@media (max-width: 680px)")

        self.assertRegex(narrow, r"padding-bottom: calc\(5\.5rem \+ var\(--safe-bottom\)\)")


class ActionButtonTests(unittest.TestCase):
    def test_button_and_menu_exist(self):
        self.assertIn('id="mobile-fab"', HTML_PAGE)
        self.assertIn('id="mobile-fab-menu"', HTML_PAGE)
        self.assertIn("toggleMobileMenu", SCRIPT)
        self.assertIn("function mobileAction", SCRIPT)

    def test_button_is_hidden_on_desktop_and_shown_on_phones(self):
        self.assertRegex(STYLE, r"\.mobile-fab \{[^}]*display: none;")
        self.assertIn(".mobile-fab { display: block; }", _media_block("@media (max-width: 680px)"))

    def test_button_is_hidden_in_kiosk_and_display_modes(self):
        self.assertIn(".kiosk-mode .mobile-fab", STYLE)
        self.assertIn(".display-mode .mobile-fab", STYLE)

    def test_menu_reaches_every_keyboard_only_entry_point(self):
        # Ctrl+K, n, q, and x do not exist on a phone.
        for action in ("command", "add", "new", "presence", "refresh"):
            self.assertIn("mobileAction('%s')" % action, HTML_PAGE, action)

    def test_command_action_opens_the_palette_in_command_mode(self):
        match = re.search(r"function mobileAction\(what\) \{(.*?)\n    \}", SCRIPT, re.S)
        self.assertTrue(match, "mobileAction not found")
        body = match.group(1)

        self.assertIn("openCmdk()", body)
        self.assertIn('"/"', body)

    def test_menu_actions_call_functions_that_exist(self):
        match = re.search(r"function mobileAction\(what\) \{(.*?)\n    \}", SCRIPT, re.S)
        body = match.group(1)
        # Exclude method calls such as document.getElementById; only bare
        # identifiers need to resolve to a function declared in the page.
        called = set(re.findall(r"(?<![.\w])([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", body))
        for name in called - {"if", "else", "return"}:
            declared = (
                re.search(r"\bfunction\s+%s\b" % re.escape(name), SCRIPT)
                or re.search(r"\b(?:const|let|var)\s+%s\b" % re.escape(name), SCRIPT)
            )
            self.assertTrue(declared, "mobileAction calls undefined %s" % name)

    def test_button_is_reachable_above_the_safe_area(self):
        self.assertRegex(STYLE, r"\.mobile-fab \{[^}]*bottom: calc\(1rem \+ var\(--safe-bottom\)\)")


class RegressionTests(unittest.TestCase):
    def test_style_and_script_blocks_stay_balanced(self):
        stripped = re.sub(r"/\*.*?\*/", "", STYLE, flags=re.S)
        self.assertEqual(stripped.count("{"), stripped.count("}"))
        self.assertEqual(SCRIPT.count("{"), SCRIPT.count("}"))

    def test_mobile_rules_come_after_the_desktop_rules_they_override(self):
        # Both blocks have equal specificity, so source order decides.
        desktop_check = STYLE.find(".item-check { display: none; }")
        mobile_check = STYLE.find(".item-check { display: block; }")

        self.assertGreater(desktop_check, -1)
        self.assertGreater(mobile_check, desktop_check)


if __name__ == "__main__":
    unittest.main()
