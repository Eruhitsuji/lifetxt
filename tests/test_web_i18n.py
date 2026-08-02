"""Tests for the Web UI language layer.

The browser does the translating, so these tests assert on the pieces the page
ships: the dictionary, the pattern table, the record-content exclusions, and
the wiring that keeps asynchronously rendered views translated.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifetxt import webapp


PAGE = webapp.HTML_PAGE


def _ja_dictionary():
    """Extract the Japanese dictionary literal from the served page."""
    start = PAGE.index("const UI_STRINGS")
    ja = PAGE.index("ja: {", start)
    depth = 0
    for index in range(ja + 4, len(PAGE)):
        if PAGE[index] == "{":
            depth += 1
        elif PAGE[index] == "}":
            depth -= 1
            if depth == 0:
                body = PAGE[ja + 5 : index]
                break
    else:
        raise AssertionError("ja dictionary not terminated")
    return dict(re.findall(r'"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)"', body))


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = _ja_dictionary()

    def test_dictionary_covers_every_view_guide(self):
        # A partly translated page was the original complaint, so each view's
        # descriptive guide must have an entry rather than falling back.
        for guide in (
            "A compact overview of open work, agenda pressure, messages, and presence.",
            "Prioritize open, actionable work and reduce noisy context while planning.",
            "Explore dependencies, references, parent-child links, and related records.",
            "Summarize completed, carried, blocked, and planned work for a chosen period.",
        ):
            self.assertIn(guide, self.dictionary)

    def test_dictionary_covers_navigation_and_toolbar(self):
        for label in (
            "Go to Agenda",
            "Go to Timeline",
            "Refresh calendar",
            "Clear selection",
            "Command palette",
            "New item",
            "Export items as CSV",
            "Toggle dark mode",
        ):
            self.assertIn(label, self.dictionary)

    def test_translations_are_actually_japanese(self):
        # An entry that maps English to English would silently pass a
        # presence-only check while leaving the interface untranslated.
        japanese = re.compile(r"[぀-ヿ一-鿿]")
        untranslated = [
            key for key, value in self.dictionary.items() if not japanese.search(value)
        ]
        self.assertEqual([], untranslated)

    def test_dictionary_is_large_enough_to_be_useful(self):
        self.assertGreater(len(self.dictionary), 250)


class PatternTests(unittest.TestCase):
    def test_patterns_exist_for_labels_that_embed_values(self):
        # These can never be dictionary keys because they carry a live date or
        # count, so without patterns they stay English forever.
        self.assertIn("I18N_PATTERNS", PAGE)
        for fragment in ("in Agenda", "View all", "more$", "overdue"):
            self.assertIn(fragment, PAGE)

    def test_pattern_regexes_are_not_double_escaped(self):
        # A generator once emitted /^\\+(\\d+)/, which matches a literal
        # backslash and therefore never fires.
        block = PAGE[PAGE.index("const I18N_PATTERNS") :]
        block = block[: block.index("];")]
        self.assertNotIn("\\\\d", block)
        self.assertNotIn("\\\\+", block)

    def test_placeholders_are_referenced_by_the_replacer(self):
        self.assertIn("function translateByPattern", PAGE)


class RecordProtectionTests(unittest.TestCase):
    def test_record_containers_opt_out_of_translation(self):
        # Record text is user data. Translating an item titled "Done" would
        # rewrite the user's own words back at them.
        for container in (
            'id="items"',
            'id="drawer-body"',
            'id="diagnostics"',
            'id="focus-list"',
            'id="team-board"',
            'id="notifications"',
        ):
            index = PAGE.index(container)
            tag_end = PAGE.index(">", index)
            tag_start = PAGE.rindex("<", 0, index)
            self.assertIn("data-no-i18n", PAGE[tag_start : tag_end + 1], container)

    def test_record_classes_are_excluded_in_mixed_views(self):
        # Views such as the calendar interleave chrome and records in one
        # subtree, so the class list is what keeps records out.
        self.assertIn("I18N_RECORD_CLASSES", PAGE)
        for name in (
            "cal-entry-title",
            "dash-row-title",
            "person-status-title",
            "tl-card-title",
            "title",
            "meta",
        ):
            self.assertIn('"%s"' % name, PAGE)

    def test_walker_consults_the_record_class_list(self):
        self.assertIn("I18N_RECORD_CLASSES.some", PAGE)


class ObserverWiringTests(unittest.TestCase):
    def test_observer_starts_once_at_init(self):
        # It was previously only re-armed from inside its own callback, so it
        # never started and every asynchronously rendered view stayed English.
        calls = re.findall(r"^\s*startLanguageObserver\(\);", PAGE, re.M)
        self.assertEqual(1, len(calls))

    def test_observer_is_not_recreated_inside_its_own_callback(self):
        body = PAGE[PAGE.index("function startLanguageObserver") :]
        body = body[: body.index("\n    }")]
        self.assertNotIn("startLanguageObserver();", body)

    def test_observer_watches_attributes_as_well_as_nodes(self):
        # Titles and placeholders are set as views render, not only at load.
        body = PAGE[PAGE.index("function startLanguageObserver") :]
        body = body[: body.index("\n    }")]
        self.assertIn("attributeFilter", body)
        self.assertIn("childList: true", body)


class LanguageSelectionTests(unittest.TestCase):
    def test_language_comes_from_url_or_config(self):
        self.assertIn("function currentLanguage", PAGE)
        self.assertIn('get("lang")', PAGE)

    def test_english_has_no_dictionary_and_therefore_no_rewriting(self):
        # English is the source language: the absence of an `en` key is what
        # makes applyLanguage a no-op rather than a lookup that misses.
        block = PAGE[PAGE.index("const UI_STRINGS") :]
        block = block[: block.index("\n    };")]
        self.assertNotIn("en: {", block)


if __name__ == "__main__":
    unittest.main()
