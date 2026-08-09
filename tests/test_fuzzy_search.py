import time
import unittest

from lifetxt.agenda import filter_items
from lifetxt.fuzzy_search import (
    DEFAULT_THRESHOLD,
    MIN_FUZZY_QUERY_LENGTH,
    fuzzy_contains,
    is_exact_match,
    normalize_text,
    similarity,
)
from lifetxt.parser import parse_text


class NormalizationTests(unittest.TestCase):
    def test_full_width_and_half_width_are_equivalent(self):
        # NFKC folds the full-width Japanese digits/letters used in some
        # imported records to the same form as their half-width ASCII
        # equivalents.
        self.assertEqual(normalize_text("ｓｔａｔｓ"), normalize_text("stats"))

    def test_latin_case_is_folded(self):
        self.assertEqual(normalize_text("Stats"), normalize_text("STATS"))

    def test_empty_and_none_normalize_to_empty_string(self):
        self.assertEqual("", normalize_text(""))
        self.assertEqual("", normalize_text(None))


class SimilarityTests(unittest.TestCase):
    def test_equal_strings_score_one(self):
        self.assertEqual(1.0, similarity("stats", "stats"))

    def test_exact_substring_outranks_any_fuzzy_only_score(self):
        # "stat" is an exact substring of "statistics dashboard", so it
        # must score above a merely-similar (but not substring) match.
        substring_score = similarity("stat", "statistics dashboard")
        fuzzy_only_score = similarity("statz", "a totally different field")
        self.assertGreater(substring_score, fuzzy_only_score)
        self.assertEqual(0.999, substring_score)

    def test_empty_query_scores_zero(self):
        self.assertEqual(0.0, similarity("", "anything"))
        self.assertEqual(0.0, similarity(None, "anything"))

    def test_queries_shorter_than_the_minimum_only_match_exact_substring(self):
        # A 2-character query is too short for edit-distance scoring to be
        # meaningful; it must fall back to substring-only.
        short_query = "s" * (MIN_FUZZY_QUERY_LENGTH - 1)
        self.assertEqual(0.0, similarity(short_query, "an unrelated field entirely"))
        self.assertEqual(
            0.999, similarity(short_query, "a field containing " + short_query)
        )

    def test_a_single_letter_typo_scores_above_the_default_threshold(self):
        # "sttats" (an extra letter) vs "stats" -- the class of near-miss
        # this feature exists for. Margin kept comfortably above the
        # threshold rather than exactly on it, so the test does not depend
        # on the scoring formula's exact boundary behavior.
        self.assertGreater(similarity("sttats", "stats"), DEFAULT_THRESHOLD + 0.1)

    def test_an_unrelated_string_scores_below_the_default_threshold(self):
        self.assertLess(
            similarity("quarterly review", "completely unrelated text"),
            DEFAULT_THRESHOLD,
        )

    def test_typo_is_found_within_a_longer_multi_word_field(self):
        # Token-level scoring: the typo'd word must be found even though
        # it is embedded in a longer title, not the whole field.
        self.assertGreater(
            similarity("sttats", "Weekly stats and review notes"),
            DEFAULT_THRESHOLD + 0.1,
        )

    def test_determinism_same_input_twice(self):
        self.assertEqual(
            similarity("stats", "statistics"), similarity("stats", "statistics")
        )

    def test_result_is_a_float_between_zero_and_one(self):
        for query, text in (
            ("", ""),
            ("a", "a"),
            ("stats", "unrelated"),
            ("x" * 500, "y" * 500),
        ):
            score = similarity(query, text)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_comparison_cost_is_bounded_for_pathological_input(self):
        # A single comparison must stay fast even against a very long
        # field with no separators (worst case for the token splitter).
        long_text = "a" * 5000
        start = time.time()
        similarity("mismatched query text", long_text)
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0)


class FuzzyContainsTests(unittest.TestCase):
    def test_exact_substring_always_matches(self):
        self.assertTrue(fuzzy_contains("stat", "statistics"))

    def test_near_miss_matches_at_default_threshold(self):
        self.assertTrue(fuzzy_contains("sttats", "stats"))

    def test_unrelated_text_does_not_match(self):
        self.assertFalse(fuzzy_contains("stats", "a totally unrelated sentence"))

    def test_custom_threshold_is_honored(self):
        # A very high threshold should reject a near-miss that the default
        # threshold accepts.
        self.assertFalse(fuzzy_contains("sttats", "stats", threshold=0.999))


class IsExactMatchTests(unittest.TestCase):
    def test_true_for_a_normalized_substring(self):
        self.assertTrue(is_exact_match("STATS", "weekly stats review"))

    def test_false_for_a_near_miss(self):
        self.assertFalse(is_exact_match("stast", "weekly stats review"))

    def test_false_for_an_empty_query(self):
        self.assertFalse(is_exact_match("", "anything"))


class FilterItemsFuzzyIntegrationTests(unittest.TestCase):
    """filter_items()'s text filter, opted into fuzzy matching."""

    def setUp(self):
        items, diagnostics = parse_text(
            '[ ] T "Weekly stats review" id:T-1\n'
            '[ ] T "Quarterly planning session" id:T-2\n'
        )
        self.assertEqual([], diagnostics)
        self.items = items

    def test_default_behavior_is_unchanged_for_a_typo(self):
        self.assertEqual([], filter_items(self.items, text="sttats"))

    def test_fuzzy_true_matches_a_typo(self):
        matched = filter_items(self.items, text="sttats", fuzzy=True)
        self.assertEqual(1, len(matched))
        self.assertEqual("T-1", matched[0].details["id"][0])

    def test_fuzzy_true_still_matches_an_exact_substring(self):
        matched = filter_items(self.items, text="stats", fuzzy=True)
        self.assertEqual(1, len(matched))

    def test_fuzzy_true_does_not_match_unrelated_text(self):
        self.assertEqual(
            [], filter_items(self.items, text="completely unrelated", fuzzy=True)
        )

    def test_default_fuzzy_false_is_explicit(self):
        # fuzzy defaults to False; passing it explicitly must behave
        # identically to omitting it.
        self.assertEqual(
            filter_items(self.items, text="stats"),
            filter_items(self.items, text="stats", fuzzy=False),
        )


if __name__ == "__main__":
    unittest.main()
