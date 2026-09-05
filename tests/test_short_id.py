"""Unit tests for lifetxt.ids.short_id, the shared presentation-only short
ID derivation (#654) used by human-readable listings. No separate short-ID
registry exists: the value is recomputed from the full id: set every time,
and is guaranteed to round-trip through resolve_item_by_id (#653)."""

import unittest

from lifetxt.ids import resolve_item_by_id, short_id
from lifetxt.parser import parse_text


class ShortIdTests(unittest.TestCase):
    def test_unique_id_shortens_to_the_minimum_length(self):
        all_ids = {"task_a12345", "task_zzzzzz"}
        self.assertEqual("task_z", short_id(all_ids, "task_zzzzzz"))

    def test_colliding_ids_extend_past_the_minimum_length(self):
        all_ids = {"task_a12345", "task_a16789"}
        self.assertEqual("task_a12", short_id(all_ids, "task_a12345"))
        self.assertEqual("task_a16", short_id(all_ids, "task_a16789"))

    def test_short_full_id_is_returned_unchanged(self):
        all_ids = {"abc", "xyz"}
        self.assertEqual("abc", short_id(all_ids, "abc"))

    def test_empty_value_returns_empty(self):
        self.assertEqual("", short_id({"a", "b"}, ""))

    def test_deterministic_for_the_same_input(self):
        all_ids = {"task_a12345", "task_a16789", "task_zzzzzz"}
        first = short_id(all_ids, "task_a12345")
        second = short_id(all_ids, "task_a12345")
        self.assertEqual(first, second)

    def test_short_id_always_resolves_back_via_resolve_item_by_id(self):
        items, _ = parse_text(
            "[ ] T First id:task_a12345\n"
            "[ ] T Second id:task_a16789\n"
            "[ ] T Third id:task_zzzzzz\n"
        )
        all_ids = {v for item in items for v in item.details.get("id", [])}
        for item in items:
            full_id = item.details["id"][0]
            shortened = short_id(all_ids, full_id)
            resolved = resolve_item_by_id(items, shortened)
            self.assertIs(item, resolved)

    def test_multi_file_effective_item_set_still_shortens_uniquely(self):
        first_file, _ = parse_text("[ ] T FromA id:task_aaa111\n")
        second_file, _ = parse_text("[ ] T FromB id:task_bbb222\n")
        combined = first_file + second_file
        all_ids = {v for item in combined for v in item.details.get("id", [])}
        shortened = short_id(all_ids, "task_aaa111")
        resolved = resolve_item_by_id(combined, shortened)
        self.assertEqual("FromA", resolved.title)


if __name__ == "__main__":
    unittest.main()
