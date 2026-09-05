"""Unit tests for lifetxt.ids.resolve_item_by_id, the shared exact-then-
unique-prefix ID resolver (#653) reused by every ID-selecting command
instead of each growing its own prefix-matching logic."""

import unittest

from lifetxt.ids import AmbiguousIdPrefixError, resolve_item_by_id
from lifetxt.parser import parse_text


class ResolveItemByIdTests(unittest.TestCase):
    def test_exact_full_id_resolves(self):
        items, _ = parse_text("[ ] T One id:task_01JZY5M93PK17C7BA4M8\n")
        item = resolve_item_by_id(items, "task_01JZY5M93PK17C7BA4M8")
        self.assertEqual("One", item.title)

    def test_unique_prefix_resolves_to_the_same_item_as_the_full_id(self):
        items, _ = parse_text("[ ] T One id:task_01JZY5M93PK17C7BA4M8\n")
        by_prefix = resolve_item_by_id(items, "task_01J")
        by_full = resolve_item_by_id(items, "task_01JZY5M93PK17C7BA4M8")
        self.assertIs(by_prefix, by_full)

    def test_zero_matches_raises_value_error_naming_the_value(self):
        items, _ = parse_text("[ ] T One id:task_a12345\n")
        with self.assertRaises(ValueError) as caught:
            resolve_item_by_id(items, "nope")
        self.assertIn("nope", str(caught.exception))
        self.assertNotIsInstance(caught.exception, AmbiguousIdPrefixError)

    def test_ambiguous_prefix_raises_naming_every_candidate(self):
        items, _ = parse_text(
            "[ ] T First id:task_a12345\n[ ] T Second id:task_a16789\n"
        )
        with self.assertRaises(AmbiguousIdPrefixError) as caught:
            resolve_item_by_id(items, "task_a")
        exc = caught.exception
        self.assertEqual(["task_a12345", "task_a16789"], exc.candidate_ids)
        message = str(exc)
        self.assertIn("Ambiguous ID prefix `task_a`.", message)
        self.assertIn("task_a12345", message)
        self.assertIn("task_a16789", message)
        self.assertIn("Use a longer prefix.", message)

    def test_ambiguous_prefix_never_auto_selects_one_candidate(self):
        items, _ = parse_text(
            "[ ] T First id:task_a12345\n[ ] T Second id:task_a16789\n"
        )
        # A raised exception, not a silently-picked match, is the only
        # acceptable outcome for an ambiguous prefix (#653's own explicit
        # "never guess" acceptance criterion).
        with self.assertRaises(ValueError):
            resolve_item_by_id(items, "task_a")

    def test_exact_match_wins_even_when_it_would_also_prefix_match_another(self):
        items, _ = parse_text("[ ] T Short id:task_a\n[ ] T Long id:task_a99999\n")
        item = resolve_item_by_id(items, "task_a")
        self.assertEqual("Short", item.title)

    def test_custom_id_key_is_honored(self):
        items, _ = parse_text("[ ] T One uid:custom_prefix_123\n")
        item = resolve_item_by_id(items, "custom_prefix", key="uid")
        self.assertEqual("One", item.title)

    def test_multi_file_effective_item_set_resolves_uniquely(self):
        first, _ = parse_text("[ ] T FromA id:task_aaa111\n")
        second, _ = parse_text("[ ] T FromB id:task_bbb222\n")
        combined = first + second
        item = resolve_item_by_id(combined, "task_bbb")
        self.assertEqual("FromB", item.title)

    def test_multi_file_ambiguous_prefix_across_files_is_still_ambiguous(self):
        first, _ = parse_text("[ ] T FromA id:task_shared_1\n")
        second, _ = parse_text("[ ] T FromB id:task_shared_2\n")
        combined = first + second
        with self.assertRaises(AmbiguousIdPrefixError) as caught:
            resolve_item_by_id(combined, "task_shared")
        self.assertEqual(
            ["task_shared_1", "task_shared_2"], caught.exception.candidate_ids
        )


if __name__ == "__main__":
    unittest.main()
