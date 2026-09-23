import unittest
try:
    from hypothesis import HealthCheck, given, settings, strategies as st
except ModuleNotFoundError:
    raise unittest.SkipTest("Hypothesis is available only in the development test environment")
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
    def test_validation_switches_are_observable(self):
        duplicate = "[ ] T One id:dup\n[ ] T Two id:dup\n"
        _items, diagnostics = parse_text(duplicate)
        self.assertTrue(any(d.code == "W213" for d in diagnostics))
        _items, disabled = parse_text(duplicate, check_ids=False)
        self.assertFalse(any(d.code == "W213" for d in disabled))

        refs = "[ ] T One id:one ref:missing\n"
        _items, ref_diagnostics = parse_text(refs)
        self.assertTrue(any(d.code == "W215" for d in ref_diagnostics))
        _items, refs_disabled = parse_text(refs, check_references=False)
        self.assertFalse(any(d.code == "W215" for d in refs_disabled))

    def test_custom_identifier_key_is_used_for_duplicate_detection(self):
        text = "[ ] T One key:a\n[ ] T Two key:a\n"
        _items, diagnostics = parse_text(text, id_key="key")
        self.assertTrue(any(d.code == "W213" for d in diagnostics))