import json
import unittest

from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line, items_from_jsonl_text, items_to_jsonl


class LifeTxtParserTests(unittest.TestCase):
    def test_parse_repeated_details(self):
        text = (
            "[ ] T Create_Slides project:research "
            "tag:important tag:thesis tag:presentation\n"
        )
        items, diagnostics = parse_text(text)

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(1, len(items))
        self.assertEqual("Create_Slides", items[0].title)
        self.assertEqual(["important", "thesis", "presentation"], items[0].details["tag"])

    def test_quoted_values_round_trip(self):
        text = '[ ] E "Research Meeting" loc:"Meeting Room A" note:"Use \\"life.txt\\""\n'
        items, diagnostics = parse_text(text)

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(text.strip(), item_to_line(items[0]))

    def test_invalid_detail_reports_error(self):
        items, diagnostics = parse_text("[ ] T Write Report due:2026-06-12\n")

        self.assertEqual(1, len(items))
        self.assertTrue(any(d.code == "E010" for d in diagnostics))

    def test_jsonl_round_trip(self):
        text = (
            "[ ] T Write_Report due:2026-06-12 tag:report tag:important\n"
            "[N] N Presentation_Memo note:\"Use figures\"\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        jsonl = items_to_jsonl(items)
        decoded = items_from_jsonl_text(jsonl)

        self.assertEqual(
            [json.loads(line) for line in jsonl.splitlines()],
            [item.to_dict() for item in decoded],
        )


if __name__ == "__main__":
    unittest.main()
