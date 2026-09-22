import unittest
from lifetxt.parser import parse_text

class CoreBoundaryTests(unittest.TestCase):
    def test_unknown_custom_keys_and_unicode_survive(self):
        text = "[ ] T \u65e5\u672c\u8a9e custom_key:value id:x1\n"
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual("\u65e5\u672c\u8a9e", items[0].title)
        self.assertEqual(["value"], items[0].details["custom_key"])

    def test_empty_input_is_valid(self):
        items, diagnostics = parse_text("")
        self.assertEqual([], items)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))