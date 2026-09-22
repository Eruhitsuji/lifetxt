import unittest
from lifetxt.parser import parse_text

class ParserInvariantTests(unittest.TestCase):
    def test_parser_is_deterministic_for_generated_safe_inputs(self):
        values = ["alpha", "日本語", "with spaces", "quote ' value"]
        for value in values:
            text = f"Task: title: {value}\\n  id: stable\\n"
            first = parse_text(text)
            second = parse_text(text)
            self.assertEqual(first, second)

    def test_malformed_input_returns_controlled_result(self):
        result = parse_text("Task: title: [unterminated\\n")
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
