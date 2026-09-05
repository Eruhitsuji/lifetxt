"""Unit tests for the bounded, read-only "Did you mean?" suggestion helper
(#640). Exercises `suggestions_for_diagnostic` directly against synthetic
`Diagnostic` objects so the extraction/candidate logic is verified
independent of the parser/validator and the CLI wiring, which are covered
separately in `tests/test_check_rich_diagnostics.py`.
"""

import unittest

from lifetxt.diagnostic_suggestions import suggestions_for_diagnostic
from lifetxt.model import Diagnostic


def _diag(code, message):
    return Diagnostic("error", code, message)


class StatusSuggestionTests(unittest.TestCase):
    def test_case_insensitive_typo_is_a_unique_suggestion(self):
        self.assertEqual(
            ["[x]"], suggestions_for_diagnostic(_diag("E003", "Invalid status '[X]'."))
        )

    def test_alias_word_is_a_unique_suggestion(self):
        self.assertEqual(
            ["[x]"],
            suggestions_for_diagnostic(_diag("E003", "Invalid status '[done]'.")),
        )

    def test_alias_word_todo_maps_to_open(self):
        self.assertEqual(
            ["[ ]"],
            suggestions_for_diagnostic(_diag("E003", "Invalid status '[todo]'.")),
        )

    def test_unrecognizable_token_has_no_suggestion(self):
        self.assertEqual(
            [], suggestions_for_diagnostic(_diag("E003", "Invalid status '[zz]'."))
        )

    def test_validator_code_e101_uses_the_same_extraction(self):
        self.assertEqual(
            ["[x]"], suggestions_for_diagnostic(_diag("E101", "Invalid status '[X]'."))
        )

    def test_malformed_message_yields_no_suggestion(self):
        self.assertEqual(
            [], suggestions_for_diagnostic(_diag("E003", "Something unrelated."))
        )


class TypeSuggestionTests(unittest.TestCase):
    def test_case_insensitive_typo_is_a_unique_suggestion(self):
        self.assertEqual(
            ["T"],
            suggestions_for_diagnostic(
                _diag("E005", "Invalid type 't'. Use T, E, D, R, H, N, S, M, or J.")
            ),
        )

    def test_alias_word_is_a_unique_suggestion(self):
        self.assertEqual(
            ["T"],
            suggestions_for_diagnostic(
                _diag("E005", "Invalid type 'task'. Use T, E, D, R, H, N, S, M, or J.")
            ),
        )

    def test_unrecognizable_token_has_no_suggestion(self):
        self.assertEqual(
            [],
            suggestions_for_diagnostic(
                _diag("E005", "Invalid type 'z'. Use T, E, D, R, H, N, S, M, or J.")
            ),
        )

    def test_validator_code_e102_uses_the_same_extraction(self):
        self.assertEqual(
            ["T"], suggestions_for_diagnostic(_diag("E102", "Invalid type 't'."))
        )


class DetailKeySuggestionTests(unittest.TestCase):
    def test_common_typo_is_a_unique_suggestion(self):
        self.assertEqual(
            ["project"],
            suggestions_for_diagnostic(
                _diag(
                    "W106",
                    "Detail key 'proj' is custom for type T; it will be preserved.",
                )
            ),
        )

    def test_another_common_typo_is_a_unique_suggestion(self):
        self.assertEqual(
            ["priority"],
            suggestions_for_diagnostic(
                _diag(
                    "W106",
                    "Detail key 'priorty' is custom for type T; it will be preserved.",
                )
            ),
        )

    def test_genuinely_custom_key_yields_no_suggestion(self):
        # A key with no close canonical match must not be forced into a
        # typo suggestion -- it is preserved as documented custom data.
        self.assertEqual(
            [],
            suggestions_for_diagnostic(
                _diag(
                    "W106",
                    "Detail key 'mood_score' is custom for type J; it will be preserved.",
                )
            ),
        )

    def test_ambiguous_key_returns_every_plausible_candidate_not_one_forced_pick(self):
        result = suggestions_for_diagnostic(
            _diag("W106", "Detail key 'ta' is custom for type T; it will be preserved.")
        )
        self.assertEqual(2, len(result))
        self.assertIn("tag", result)
        self.assertIn("team", result)


class StateSuggestionTests(unittest.TestCase):
    def test_typo_is_a_unique_suggestion(self):
        self.assertEqual(
            ["busy"],
            suggestions_for_diagnostic(
                _diag(
                    "W207",
                    "state: 'buzy' should usually be one of: available, busy, away.",
                )
            ),
        )

    def test_case_mismatch_is_a_unique_suggestion(self):
        self.assertEqual(
            ["busy"],
            suggestions_for_diagnostic(
                _diag(
                    "W207",
                    "state: 'Busy' should usually be one of: available, busy, away.",
                )
            ),
        )

    def test_unrecognizable_value_has_no_suggestion(self):
        self.assertEqual(
            [],
            suggestions_for_diagnostic(
                _diag(
                    "W207",
                    "state: 'xyz123' should usually be one of: available, busy, away.",
                )
            ),
        )


class UnsupportedCodeTests(unittest.TestCase):
    def test_unrelated_code_returns_no_suggestions(self):
        self.assertEqual(
            [], suggestions_for_diagnostic(_diag("W213", "Duplicate id:foo."))
        )

    def test_missing_code_returns_no_suggestions(self):
        self.assertEqual([], suggestions_for_diagnostic(_diag(None, "anything")))


if __name__ == "__main__":
    unittest.main()
