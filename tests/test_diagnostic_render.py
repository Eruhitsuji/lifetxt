"""Unit tests for the rich diagnostic text renderer (#639).

`lifetxt/diagnostic_render.py` is a presentation-only layer over the stable
`Diagnostic` object; these tests exercise it directly (not through the CLI)
so the span-caret/hint/summary logic is verified independent of
`command_check`'s own wiring, which is covered separately in
`tests/test_check_rich_diagnostics.py`.
"""

import os
import tempfile
import unittest

from lifetxt.diagnostic_render import (
    _caret_marker,
    _read_source_line,
    render_diagnostic_rich,
    render_diagnostics_summary,
)
from lifetxt.model import Diagnostic


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class ReadSourceLineTests(unittest.TestCase):
    def test_reads_the_requested_one_indexed_line(self):
        path = _make_file("first\nsecond\nthird\n")
        try:
            self.assertEqual("second", _read_source_line(path, 2))
        finally:
            os.unlink(path)

    def test_returns_none_for_missing_path(self):
        self.assertIsNone(_read_source_line(None, 1))
        self.assertIsNone(_read_source_line("-", 1))

    def test_returns_none_for_missing_or_zero_line_number(self):
        path = _make_file("only line\n")
        try:
            self.assertIsNone(_read_source_line(path, None))
            self.assertIsNone(_read_source_line(path, 0))
        finally:
            os.unlink(path)

    def test_returns_none_for_out_of_range_line(self):
        path = _make_file("only line\n")
        try:
            self.assertIsNone(_read_source_line(path, 99))
        finally:
            os.unlink(path)

    def test_returns_none_for_unreadable_file(self):
        self.assertIsNone(_read_source_line("/no/such/file/at/all.txt", 1))

    def test_handles_unicode_and_tab_content(self):
        path = _make_file("[ ] T 日本語\ttab_here\n")
        try:
            line = _read_source_line(path, 1)
            self.assertIn("日本語", line)
            self.assertIn("\t", line)
        finally:
            os.unlink(path)


class CaretMarkerTests(unittest.TestCase):
    def test_single_caret_when_no_end_column(self):
        marker = _caret_marker(3, None, 1, None, 10)
        self.assertEqual("  ^", marker)

    def test_range_marker_when_end_column_on_same_line(self):
        marker = _caret_marker(3, 1, 1, 6, 10)
        self.assertEqual("  ^~~", marker)

    def test_single_caret_when_end_line_differs(self):
        marker = _caret_marker(3, 2, 1, 6, 10)
        self.assertEqual("  ^", marker)

    def test_none_when_column_missing(self):
        self.assertIsNone(_caret_marker(None, None, 1, None, 10))

    def test_range_clamped_to_line_length(self):
        marker = _caret_marker(8, 1, 1, 40, 10)
        self.assertEqual(len(marker), 10)


class RenderDiagnosticRichTests(unittest.TestCase):
    def test_no_span_fallback_has_no_source_snippet_or_caret(self):
        diagnostic = Diagnostic("warning", "W999", "Something is off")
        text = render_diagnostic_rich(diagnostic)
        self.assertNotIn("|", text)
        self.assertNotIn("^", text)
        self.assertIn("WARNING W999", text)
        self.assertIn("Something is off", text)

    def test_source_snippet_and_caret_shown_for_known_line(self):
        path = _make_file("[ ] T Buy_milk badkey:value\n")
        try:
            diagnostic = Diagnostic(
                "warning",
                "W106",
                "Unknown custom key",
                line=1,
                column=16,
                source=path,
                end_column=22,
            )
            text = render_diagnostic_rich(diagnostic)
            self.assertIn("1 | [ ] T Buy_milk badkey:value", text)
            self.assertIn("^~~~~~", text)
        finally:
            os.unlink(path)

    def test_hint_is_displayed_when_present(self):
        diagnostic = Diagnostic(
            "warning", "W106", "Unknown custom key", hint="Did you mean 'project'?"
        )
        text = render_diagnostic_rich(diagnostic)
        self.assertIn("Hint: Did you mean 'project'?", text)

    def test_no_hint_line_when_hint_is_empty(self):
        diagnostic = Diagnostic("warning", "W999", "Something is off")
        text = render_diagnostic_rich(diagnostic)
        self.assertNotIn("Hint:", text)

    def test_unreadable_source_falls_back_gracefully(self):
        diagnostic = Diagnostic(
            "error",
            "E001",
            "Parse failure",
            line=1,
            column=1,
            source="/no/such/file/at/all.txt",
        )
        text = render_diagnostic_rich(diagnostic)
        self.assertIn("ERROR E001", text)
        self.assertNotIn("|", text)

    def test_long_line_snippet_is_shown_in_full(self):
        long_body = "x" * 300
        path = _make_file("[ ] T %s\n" % long_body)
        try:
            diagnostic = Diagnostic(
                "warning", "W106", "Unknown custom key", line=1, column=1, source=path
            )
            text = render_diagnostic_rich(diagnostic)
            self.assertIn(long_body, text)
        finally:
            os.unlink(path)


class RenderDiagnosticSuggestionSectionTests(unittest.TestCase):
    def test_single_suggestion_renders_did_you_mean_line(self):
        diagnostic = Diagnostic("error", "E003", "Invalid status '[X]'.")
        text = render_diagnostic_rich(diagnostic)
        self.assertIn("Did you mean '[x]'?", text)

    def test_multiple_suggestions_render_a_bulleted_list(self):
        diagnostic = Diagnostic(
            "warning",
            "W106",
            "Detail key 'ta' is custom for type T; it will be preserved.",
        )
        text = render_diagnostic_rich(diagnostic)
        self.assertIn("Did you mean one of:", text)
        self.assertIn("  tag", text)
        self.assertIn("  team", text)

    def test_no_suggestion_section_when_none_applies(self):
        diagnostic = Diagnostic(
            "warning",
            "W106",
            "Detail key 'mood_score' is custom for type J; it will be preserved.",
        )
        text = render_diagnostic_rich(diagnostic)
        self.assertNotIn("Did you mean", text)

    def test_no_suggestion_section_for_unsupported_code(self):
        diagnostic = Diagnostic("warning", "W213", "Duplicate id:foo.")
        text = render_diagnostic_rich(diagnostic)
        self.assertNotIn("Did you mean", text)


class RenderDiagnosticCascadeRelationTests(unittest.TestCase):
    def test_no_relation_note_when_relation_is_none(self):
        diagnostic = Diagnostic("error", "E010", "Expected detail in key:value form.")
        text = render_diagnostic_rich(diagnostic, relation=None)
        self.assertNotIn("Related:", text)

    def test_root_relation_names_the_secondary_count(self):
        diagnostic = Diagnostic("error", "E010", "x", line=1, column=13)
        secondary_a = Diagnostic("error", "E010", "x", line=1, column=20)
        secondary_b = Diagnostic("error", "E010", "x", line=1, column=24)
        text = render_diagnostic_rich(
            diagnostic, relation=("root", [secondary_a, secondary_b])
        )
        self.assertIn(
            "Related: 2 other diagnostic(s) on this line may be "
            "consequences of this one (see below).",
            text,
        )

    def test_secondary_relation_names_the_root_code_and_column(self):
        root = Diagnostic("error", "E010", "x", line=1, column=13)
        secondary = Diagnostic("error", "E010", "x", line=1, column=20)
        text = render_diagnostic_rich(secondary, relation=("secondary", root))
        self.assertIn(
            "Related: possibly caused by E010 at column 13 above; fix that first.",
            text,
        )

    def test_secondary_relation_without_root_column_omits_the_column_clause(self):
        root = Diagnostic("error", "E010", "x", line=1, column=None)
        secondary = Diagnostic("error", "E010", "x", line=1, column=20)
        text = render_diagnostic_rich(secondary, relation=("secondary", root))
        self.assertIn("Related: possibly caused by E010 above; fix that first.", text)
        self.assertNotIn("at column", text)


class RenderDiagnosticsSummaryTests(unittest.TestCase):
    def test_singular_wording_for_one_of_each(self):
        diagnostics = [
            Diagnostic("error", "E001", "boom"),
            Diagnostic("warning", "W001", "hmm"),
        ]
        summary = render_diagnostics_summary(diagnostics)
        self.assertEqual("2 problems: 1 error, 1 warning", summary)

    def test_plural_wording_for_several(self):
        diagnostics = [
            Diagnostic("error", "E001", "boom"),
            Diagnostic("error", "E002", "boom2"),
            Diagnostic("warning", "W001", "hmm"),
            Diagnostic("warning", "W002", "hmm2"),
            Diagnostic("warning", "W003", "hmm3"),
        ]
        summary = render_diagnostics_summary(diagnostics)
        self.assertEqual("5 problems: 2 errors, 3 warnings", summary)

    def test_empty_list(self):
        self.assertEqual(
            "0 problems: 0 errors, 0 warnings", render_diagnostics_summary([])
        )


if __name__ == "__main__":
    unittest.main()
