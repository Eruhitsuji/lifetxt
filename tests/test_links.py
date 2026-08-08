import unittest

from lifetxt.parser import parse_text
from lifetxt.links import (
    backlink_records,
    link_records,
    reference_diagnostics,
)


class ReferenceKeysCoverageTests(unittest.TestCase):
    """duplicate_of/replaced_by must get the same reference-graph treatment
    as the other REFERENCE_KEYS relations (#161)."""

    def test_duplicate_of_missing_target_warns(self):
        _items, diagnostics = parse_text(
            "[ ] T Original id:orig duplicate_of:nonexistent\n"
        )
        self.assertTrue(any(d.code == "W215" for d in diagnostics))

    def test_replaced_by_missing_target_warns(self):
        _items, diagnostics = parse_text("[ ] T Old id:old replaced_by:nonexistent\n")
        self.assertTrue(any(d.code == "W215" for d in diagnostics))

    def test_duplicate_of_self_reference_warns(self):
        _items, diagnostics = parse_text("[ ] T Self id:s duplicate_of:s\n")
        self.assertTrue(any(d.code == "W216" for d in diagnostics))

    def test_replaced_by_self_reference_warns(self):
        _items, diagnostics = parse_text("[ ] T Self id:s replaced_by:s\n")
        self.assertTrue(any(d.code == "W216" for d in diagnostics))

    def test_duplicate_of_ambiguous_target_warns(self):
        text = (
            "[ ] T First id:dup\n"
            "[ ] T Second id:dup\n"
            "[ ] T Reporter id:r duplicate_of:dup\n"
        )
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W218" for d in diagnostics))

    def test_duplicate_of_and_replaced_by_appear_in_link_records(self):
        text = (
            "[ ] T Original id:orig\n"
            "[x] T Copy id:copy duplicate_of:orig\n"
            "[ ] T Old id:old\n"
            "[ ] T New id:new replaced_by:old\n"
        )
        items, _diagnostics = parse_text(text)
        records = link_records(items)
        compact = [
            (r["relation"], r["source_id"], r["target_id"], r["status"])
            for r in records
        ]
        self.assertIn(("duplicate_of", "copy", "orig", "ok"), compact)
        self.assertIn(("replaced_by", "new", "old", "ok"), compact)

    def test_backlink_records_surfaces_duplicate_of_and_replaced_by(self):
        text = (
            "[ ] T Original id:orig\n"
            "[x] T Copy id:copy duplicate_of:orig\n"
            "[ ] T New id:new replaced_by:orig\n"
        )
        items, _diagnostics = parse_text(text)
        records = backlink_records(items, "orig")
        relations = {r["relation"] for r in records}
        self.assertIn("duplicate_of", relations)
        self.assertIn("replaced_by", relations)

    def test_reference_diagnostics_directly_covers_duplicate_of(self):
        text = "[ ] T Reporter id:r duplicate_of:nope\n"
        items, _diagnostics = parse_text(text)
        diagnostics = reference_diagnostics(items)
        self.assertTrue(any(d.code == "W215" for d in diagnostics))


class ExtendedCycleDetectionTests(unittest.TestCase):
    """Cycle detection beyond parent: (#162)."""

    def test_parent_cycle_message_is_unchanged(self):
        _items, diagnostics = parse_text(
            "[ ] T First id:a parent:b\n[ ] T Second id:b parent:a\n"
        )
        matches = [d for d in diagnostics if d.code == "W217"]
        self.assertEqual(1, len(matches))
        self.assertEqual(
            "Parent reference cycle detected: a -> b -> a.", matches[0].message
        )

    def test_depends_on_cycle_is_detected(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W227" for d in diagnostics))

    def test_mixed_depends_on_and_blocks_cycle_is_detected(self):
        # a depends_on b (a waits on b); b blocks a (a waits on b, same edge) --
        # add a second hop so the cycle is genuinely mixed: a depends_on b,
        # c blocks a (a waits on c), and c depends_on a closes the loop.
        text = (
            "[ ] T A id:a depends_on:b\n"
            "[ ] T B id:b\n"
            "[ ] T C id:c depends_on:a blocks:b\n"
        )
        _items, diagnostics = parse_text(text)
        # a -> b (depends_on), b -> c (c blocks b means b waits on c), c -> a (depends_on)
        self.assertTrue(any(d.code == "W227" for d in diagnostics))

    def test_non_cyclic_dependency_chain_has_no_cycle_warning(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:c\n[ ] T C id:c\n"
        _items, diagnostics = parse_text(text)
        self.assertFalse(any(d.code == "W227" for d in diagnostics))

    def test_duplicate_of_cycle_is_detected(self):
        text = "[ ] T A id:a duplicate_of:b\n[ ] T B id:b duplicate_of:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W228" for d in diagnostics))

    def test_replaced_by_cycle_is_detected(self):
        text = "[ ] T A id:a replaced_by:b\n[ ] T B id:b replaced_by:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W229" for d in diagnostics))

    def test_duplicate_of_and_replaced_by_cycles_are_independent(self):
        # A duplicate_of B, B replaced_by A -- not a cycle in either single
        # relation, so neither W228 nor W229 should fire.
        text = "[ ] T A id:a duplicate_of:b\n[ ] T B id:b replaced_by:a\n"
        _items, diagnostics = parse_text(text)
        self.assertFalse(any(d.code == "W228" for d in diagnostics))
        self.assertFalse(any(d.code == "W229" for d in diagnostics))

    def test_new_cycle_codes_are_categorized_as_reference(self):
        from lifetxt.diagnostic_contract import diagnostic_category
        from lifetxt.model import Diagnostic

        for code in ("W227", "W228", "W229"):
            diagnostic = Diagnostic("warning", code, "x")
            self.assertEqual("reference", diagnostic_category(diagnostic))


if __name__ == "__main__":
    unittest.main()
