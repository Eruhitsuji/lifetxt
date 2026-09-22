import unittest
from hypothesis import given, strategies as st
from lifetxt.parser import parse_text

class ParserInvariantTests(unittest.TestCase):
    @given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=40))
    def test_parser_is_deterministic_for_generated_values(self, value):
        text = f"Task: title: {value}\n  id: stable\n"
        self.assertEqual(parse_text(text), parse_text(text))

    def test_malformed_input_returns_controlled_result(self):
        result = parse_text("Task: title: [unterminated\n")
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
