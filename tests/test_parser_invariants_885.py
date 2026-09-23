import unittest
from hypothesis import HealthCheck, given, settings, strategies as st
from lifetxt.parser import parse_text

class ParserInvariantTests(unittest.TestCase):
    @staticmethod
    def semantic(result):
        items, diagnostics = result
        return ([item.to_dict() for item in items], [(d.code, d.severity, d.message) for d in diagnostics])

    @settings(max_examples=25, derandomize=True, suppress_health_check=[HealthCheck.differing_executors])
    @given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=40))
    def test_parser_is_deterministic_for_generated_values(self, value):
        text = f"[ ] T {value}\n"
        self.assertEqual(self.semantic(parse_text(text)), self.semantic(parse_text(text)))

    def test_malformed_input_returns_controlled_result(self):
        result = parse_text("[ ] T [unterminated\n")
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
    # Regression: #886 review of historical parser edge cases.
    def test_round_trip_preserves_quoted_and_custom_values(self):
        result = parse_text('[ ] T "Research Meeting" note:"Use \\"life.txt\\"" custom:value\r\n')
        items, diagnostics = result
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual("Research Meeting", items[0].title)
        self.assertEqual(["value"], items[0].details["custom"])

    # Regression: #886; CRLF is a supported interchange boundary.
    def test_crlf_and_continuation_are_semantically_stable(self):
        text = "[ ] T Review \\\r\n  due:2026-06-12 custom:value\r\n"
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(["2026-06-12"], items[0].details["due"])
        self.assertEqual(["value"], items[0].details["custom"])