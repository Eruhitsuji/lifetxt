"""Shared-helper-layer coverage for lifetxt/custom_field_primitives.py (#596).

Both lifetxt/ticket_custom_fields.py (``ticketing.custom_fields``) and
lifetxt/custom_fields.py (the generic ``custom_fields`` registry) delegate
to this module for type coercion and constraint evaluation. These tests
exercise it directly so equivalent primitive inputs cannot silently drift
between the two registries.
"""

import unittest
from decimal import Decimal

from lifetxt.custom_field_primitives import (
    SUPPORTED_TYPES,
    decimal_text,
    definition_boolean,
    definition_decimal,
    definition_integer,
    normalize_boolean,
    normalize_typed_value,
    string_list,
)


class SupportedTypesTests(unittest.TestCase):
    def test_supported_types_matches_the_documented_set(self):
        self.assertEqual(
            SUPPORTED_TYPES,
            (
                "string",
                "integer",
                "number",
                "boolean",
                "date",
                "datetime",
                "duration",
                "enum",
            ),
        )


class StringListTests(unittest.TestCase):
    def test_none_and_empty_string_produce_an_empty_list(self):
        self.assertEqual(string_list(None), [])
        self.assertEqual(string_list(""), [])

    def test_scalar_is_wrapped(self):
        self.assertEqual(string_list("low"), ["low"])

    def test_list_is_deduplicated_preserving_order(self):
        self.assertEqual(
            string_list(["low", "medium", "low", "", "high"]),
            ["low", "medium", "high"],
        )


class DecimalTextTests(unittest.TestCase):
    def test_integral_decimal_has_no_trailing_zeros(self):
        self.assertEqual(decimal_text(Decimal("5")), "5")
        self.assertEqual(decimal_text(Decimal("5.00")), "5")

    def test_fractional_decimal_is_trimmed(self):
        self.assertEqual(decimal_text(Decimal("4.50")), "4.5")

    def test_zero_renders_as_zero(self):
        self.assertEqual(decimal_text(Decimal("0")), "0")


class NormalizeBooleanTests(unittest.TestCase):
    def test_recognized_true_forms(self):
        for raw in ("1", "true", "TRUE", "yes", "on"):
            normalized, comparable = normalize_boolean(raw)
            self.assertEqual(normalized, "true")
            self.assertEqual(comparable, Decimal(1))

    def test_recognized_false_forms(self):
        for raw in ("0", "false", "FALSE", "no", "off"):
            normalized, comparable = normalize_boolean(raw)
            self.assertEqual(normalized, "false")
            self.assertEqual(comparable, Decimal(0))

    def test_unrecognized_value_raises(self):
        with self.assertRaises(ValueError):
            normalize_boolean("maybe")


class DefinitionMetadataDiagCallbackTests(unittest.TestCase):
    """The ``diag`` callback lets each registry keep its own diagnostic
    shape while sharing one coercion implementation."""

    def test_definition_boolean_default_when_absent(self):
        diagnostics = []
        self.assertFalse(definition_boolean(None, "repeatable", "energy", diagnostics))
        self.assertEqual(diagnostics, [])

    def test_definition_boolean_passes_through_a_real_boolean(self):
        diagnostics = []
        self.assertTrue(definition_boolean(True, "repeatable", "energy", diagnostics))
        self.assertEqual(diagnostics, [])

    def test_definition_boolean_invalid_calls_diag_with_message_and_field(self):
        diagnostics = []
        calls = []

        def diag(message, field):
            calls.append((message, field))
            return {"message": message, "field": field}

        result = definition_boolean(
            "yes", "repeatable", "energy", diagnostics, diag=diag
        )
        self.assertFalse(result)
        self.assertEqual(len(calls), 1)
        message, field = calls[0]
        self.assertEqual(field, "energy")
        self.assertIn("repeatable", message)
        self.assertIn("boolean", message)
        self.assertEqual(diagnostics, [{"message": message, "field": "energy"}])

    def test_definition_boolean_without_diag_is_silent(self):
        diagnostics = []
        result = definition_boolean("yes", "repeatable", "energy", diagnostics)
        self.assertFalse(result)
        self.assertEqual(diagnostics, [])

    def test_definition_integer_valid(self):
        diagnostics = []
        self.assertEqual(
            definition_integer("3", "min_length", "energy", diagnostics), 3
        )
        self.assertEqual(diagnostics, [])

    def test_definition_integer_absent_is_none(self):
        diagnostics = []
        self.assertIsNone(definition_integer(None, "min_length", "energy", diagnostics))

    def test_definition_integer_non_numeric_reports_via_diag(self):
        diagnostics = []
        calls = []
        definition_integer(
            "abc",
            "min_length",
            "energy",
            diagnostics,
            diag=lambda message, field: calls.append((message, field)),
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("integer", calls[0][0])

    def test_definition_integer_negative_reports_zero_or_greater(self):
        diagnostics = []
        calls = []
        definition_integer(
            "-1",
            "min_length",
            "energy",
            diagnostics,
            diag=lambda message, field: calls.append((message, field)),
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("zero or greater", calls[0][0])

    def test_definition_integer_boolean_input_is_rejected(self):
        diagnostics = []
        calls = []
        definition_integer(
            True,
            "min_length",
            "energy",
            diagnostics,
            diag=lambda message, field: calls.append((message, field)),
        )
        self.assertEqual(len(calls), 1)

    def test_definition_decimal_valid(self):
        diagnostics = []
        self.assertEqual(
            definition_decimal("4.5", "minimum", "rating", diagnostics),
            Decimal("4.5"),
        )

    def test_definition_decimal_absent_is_none(self):
        diagnostics = []
        self.assertIsNone(definition_decimal(None, "minimum", "rating", diagnostics))

    def test_definition_decimal_invalid_reports_via_diag(self):
        diagnostics = []
        calls = []
        definition_decimal(
            "not-a-number",
            "minimum",
            "rating",
            diagnostics,
            diag=lambda message, field: calls.append((message, field)),
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("number", calls[0][0])


class NormalizeTypedValueTests(unittest.TestCase):
    def test_string_type_is_passed_through(self):
        self.assertEqual(normalize_typed_value("hello", {"type": "string"}), "hello")

    def test_enum_type_accepts_a_listed_value(self):
        definition = {"type": "enum", "enum": ["low", "medium", "high"]}
        self.assertEqual(normalize_typed_value("high", definition), "high")

    def test_enum_type_rejects_an_unlisted_value(self):
        definition = {"type": "enum", "enum": ["low", "medium", "high"]}
        with self.assertRaises(ValueError):
            normalize_typed_value("extreme", definition)

    def test_integer_type_normalizes_and_rejects_non_integers(self):
        self.assertEqual(normalize_typed_value("+007", {"type": "integer"}), "7")
        with self.assertRaises(ValueError):
            normalize_typed_value("7.5", {"type": "integer"})

    def test_integer_type_enforces_minimum_and_maximum(self):
        definition = {"type": "integer", "minimum": 0, "maximum": 10}
        self.assertEqual(normalize_typed_value("10", definition), "10")
        with self.assertRaises(ValueError):
            normalize_typed_value("11", definition)
        with self.assertRaises(ValueError):
            normalize_typed_value("-1", definition)

    def test_number_type_normalizes_and_rejects_non_finite(self):
        definition = {"type": "number"}
        self.assertEqual(normalize_typed_value("4.50", definition), "4.5")
        with self.assertRaises(ValueError):
            normalize_typed_value("not-a-number", definition)
        with self.assertRaises(ValueError):
            normalize_typed_value("Infinity", definition)

    def test_boolean_type_normalizes_recognized_forms(self):
        definition = {"type": "boolean"}
        self.assertEqual(normalize_typed_value("yes", definition), "true")
        self.assertEqual(normalize_typed_value("0", definition), "false")
        with self.assertRaises(ValueError):
            normalize_typed_value("maybe", definition)

    def test_date_type_requires_a_bare_date(self):
        definition = {"type": "date"}
        self.assertEqual(normalize_typed_value("2026-08-29", definition), "2026-08-29")
        with self.assertRaises(ValueError):
            normalize_typed_value("2026-08-29T10:00", definition)
        with self.assertRaises(ValueError):
            normalize_typed_value("not-a-date", definition)

    def test_datetime_type_requires_date_and_time(self):
        definition = {"type": "datetime"}
        normalized = normalize_typed_value("2026-08-29T10:00", definition)
        self.assertTrue(normalized.startswith("2026-08-29T10:00"))
        with self.assertRaises(ValueError):
            normalize_typed_value("2026-08-29", definition)

    def test_duration_type_normalizes_and_rejects_garbage(self):
        definition = {"type": "duration"}
        self.assertEqual(normalize_typed_value("30m", definition), "30m")
        with self.assertRaises(ValueError):
            normalize_typed_value("not-a-duration", definition)

    def test_unsupported_type_raises(self):
        with self.assertRaises(ValueError):
            normalize_typed_value("x", {"type": "wat"})

    def test_string_length_constraints(self):
        definition = {"type": "string", "min_length": 2, "max_length": 4}
        self.assertEqual(normalize_typed_value("abc", definition), "abc")
        with self.assertRaises(ValueError):
            normalize_typed_value("a", definition)
        with self.assertRaises(ValueError):
            normalize_typed_value("abcde", definition)

    def test_pattern_constraint(self):
        definition = {"type": "string", "pattern": "^[a-z0-9_-]+$"}
        self.assertEqual(normalize_typed_value("bug-123", definition), "bug-123")
        with self.assertRaises(ValueError):
            normalize_typed_value("Bug 123", definition)


if __name__ == "__main__":
    unittest.main()
