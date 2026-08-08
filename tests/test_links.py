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


if __name__ == "__main__":
    unittest.main()
