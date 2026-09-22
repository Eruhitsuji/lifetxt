import unittest
from hypothesis import given, strategies as st
from lifetxt.parser import parse_text

class ParserInvariantTests(unittest.TestCase):
    @staticmethod
    def semantic(result):
        items, diagnostics = result
        return ([item.to_dict() for item in items], [(d.code, d.severity, d.message) for d in diagnostics])

    @given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=40))
    def test_parser_is_deterministic_for_generated_values(self, value):
        text = f"[ ] T {value}\n"
        self.assertEqual(self.semantic(parse_text(text)), self.semantic(parse_text(text)))

    def test_malformed_input_returns_controlled_result(self):
        result = parse_text("[ ] T [unterminated\n")
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))