import unittest
from lifetxt.parser import parse_text

class CoreBoundaryTests(unittest.TestCase):
    def test_unknown_custom_keys_and_unicode_survive(self):
        text = "Task: title: \u65e5\u672c\u8a9e\n  id: x1\n  custom_key: value\n"
        items, diagnostics = parse_text(text)
        self.assertEqual([], diagnostics)
        self.assertEqual("\u65e5\u672c\u8a9e", items[0].get("title"))
        self.assertEqual("value", items[0].get("custom_key"))

    def test_empty_input_is_valid(self):
        items, diagnostics = parse_text("")
        self.assertEqual([], items)
        self.assertEqual([], diagnostics)