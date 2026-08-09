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

    def test_dictionary_covers_contextual_help_strings(self):
        # CONTROL_HELP, VIEW_HELP, and the inline data-help attributes are
        # read verbatim by showUiHelp(); each one needs its own dictionary
        # entry or the tooltip silently stays English.
        for text in (
            # CONTROL_HELP
            "Toggle light and dark theme. Add ?theme=light or ?theme=dark to force a wall-display theme.",
            "High-contrast mode increases borders and text contrast for low-visibility displays.",
            "Reduced motion disables most transitions and animation-heavy feedback.",
            "Compact density hides long body previews and fits more records on small screens.",
            "Use browser fullscreen for kiosk or display boards. Press f to toggle.",
            "Open notification records and optionally request browser notification permission.",
            "Reload the active view from disk/API without changing filters. Press r as a shortcut.",
            "Switch Status between active records only and latest status per person.",
            "Cycle Agenda blocker filtering: all, only blocked, or hide blocked records.",
            "Download the current Items result as CSV, JSON, or Markdown.",
            "Group the Items list without changing the source file.",
            "Sort visible Items by line, time, title, type, status, or source.",
            "Choose ascending or descending sort order.",
            "Limit the number of visible Items. Leave empty for all matching records.",
            "Search title, raw line, and detail values. Shortcut: /.",
            # VIEW_HELP
            "Dashboard: overview KPI tiles, attention list, completions, and project progress.",
            "Items: searchable record list with filters, grouping, edit modal, bulk actions, and exports.",
            "Agenda: date-range list for due, do, at, from/to, on, and notify_at records.",
            "Timeline: chronological board for today, next 24 hours, or week with an updated now line.",
            "Calendar: month/week grid of dated records; click a day for Agenda or an entry for details.",
            "Focus: reduced-noise list of overdue, due-today, and in-progress work.",
            "Review: weekly/monthly/custom period summary with Markdown copy.",
            "Messages: type M records, sender/recipient filters, and notification-oriented conversations.",
            "Team: presence, workload, and recent messages grouped by person.",
            "Status: latest or active presence records for each person.",
            "Notifications: due messages/reminders, acknowledge, snooze, and browser alert controls.",
            "Stats: charts, heatmaps, and type/status breakdowns.",
            "Graph: id, parent, ref, depends_on, blocks, and related links.",
            "Display: read-focused wall mode that hides editing controls. Use Back or Exit Display to leave.",
            "Kiosk: always-on board with clock, auto-refresh, optional kiosk_filter, and auto-scroll.",
            # Inline data-help attributes
            "Create a life.txt record. Pick a status, type, title, and detail keys; press n to open this editor from the keyboard.",
            "Workflow state: [ ] open, [/] active, [x] done, [-] cancelled, [>] deferred, [?] maybe, [N] note.",
            "Record kind: T task, E event, D deadline, R reminder, H habit, N note, S presence status, M message, J journal.",
            "Short human-readable record text. Use quotes in raw life.txt if the title contains spaces.",
            "One key:value per line. Repeat the same key for multiple values. Use body: or | continuation lines for longer text.",
        ):
            self.assertIn(text, self.dictionary)


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


class CommandTokenProtectionTests(unittest.TestCase):
    # Slash-command names are executable syntax, not prose: the generic
    # translator peels a leading "/" as punctuation and can then match the
    # bare word "stats" in the dictionary, rendering "/stats" as "/統計".
    # These spans must opt out with data-no-i18n rather than rely on the
    # word "stats" never appearing in the dictionary.

    def test_command_palette_label_and_alias_are_protected(self):
        body = PAGE[PAGE.index("function renderCmdkCommands") :]
        body = body[: body.index("function openCmdk")]
        self.assertIn("<span data-no-i18n>${escapeHtml(entry.label)}</span>", body)
        self.assertIn(
            'style="margin-left:auto;color:var(--muted);font-size:.78rem" data-no-i18n>${escapeHtml(entry.hint)}',
            body,
        )
        # The summary branch is ordinary prose and must stay translatable.
        self.assertIn(
            'style="margin-left:auto;color:var(--muted);font-size:.78rem">${escapeHtml(entry.summary)}',
            body,
        )

    def test_help_modal_command_usage_is_protected(self):
        body = PAGE[PAGE.index("async function renderHelpModalCommands") :]
        body = body[: body.index("function _runHelpModalCommand")]
        self.assertIn('<span class="help-command-usage" data-no-i18n>', body)
        # The summary column is ordinary prose and must stay translatable.
        self.assertIn('<span class="help-command-summary">', body)


class DynamicLabelTranslationTests(unittest.TestCase):
    def test_notif_button_label_is_translated_at_construction(self):
        # "Notifications ✕" is not a dictionary key and the suffix-peel rule
        # only strips a trailing "(...)", so a bare-literal assignment would
        # stay English forever even with a "Notifications" dictionary entry;
        # the runtime label must be built through t() instead.
        body = PAGE[PAGE.index("function updateNotifBtnLabel") :]
        body = body[: body.index("\n    }")]
        self.assertIn('t("Notifications") + indicator', body)
        self.assertNotIn('"Notifications" + indicator', body)


class ContextualHelpTranslationTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = _ja_dictionary()

    def test_show_ui_help_translates_at_display_time(self):
        # data-help is read directly by showUiHelp() and was never routed
        # through I18N_ATTRIBUTES or t(), so a hover/focus tooltip stayed
        # English regardless of language.
        body = PAGE[PAGE.index("function showUiHelp") :]
        body = body[: body.index("\n    }")]
        self.assertIn("tooltip.textContent = t(text);", body)

    def test_every_data_help_source_string_has_a_translation(self):
        # Structural check over the actual served markup/JS, independent of
        # the hardcoded list in DictionaryTests: every data-help="..." value
        # and every CONTROL_HELP/VIEW_HELP value must be a dictionary key.
        inline = re.findall(r'data-help="((?:[^"\\]|\\.)*)"', PAGE)
        self.assertGreaterEqual(len(inline), 5)
        control_block = PAGE[PAGE.index("const CONTROL_HELP") :]
        control_block = control_block[: control_block.index("\n    };")]
        view_block = PAGE[PAGE.index("const VIEW_HELP") :]
        view_block = view_block[: view_block.index("\n    };")]
        control_and_view = re.findall(
            r'"((?:[^"\\]|\\.)*)",\n', control_block + "\n" + view_block
        )
        self.assertGreaterEqual(len(control_and_view), 25)
        for text in inline + control_and_view:
            self.assertIn(text, self.dictionary, text)


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
