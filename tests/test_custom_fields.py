"""Tests for the generic typed custom-field registry (#596).

Covers: registry validation, kind/project applicability, ordinary-validator
integration (W106 suppression plus CF0xx constraint diagnostics),
undeclared-key regression, record:ticket isolation, and the Query/Saved
View integration that makes ``filterable: true`` fields dynamic Query
fields with no separate Saved View implementation.
"""

import unittest
from collections import OrderedDict

from lifetxt import config_registry
from lifetxt.custom_fields import (
    custom_field_registry_report,
    field_applies,
    filterable_field_names,
    generic_custom_field_diagnostics,
    install_custom_fields_config_registry,
)
from lifetxt.parser import parse_text
from lifetxt.query import parse_query, run_query
from lifetxt.saved_views import run_saved_view, validate_saved_views
from lifetxt.schema_extensions_v5 import schema_bundle_v5


def _config(custom_fields):
    return {"custom_fields": custom_fields}


class RegistryReportTests(unittest.TestCase):
    def test_no_custom_fields_key_is_valid_and_empty(self):
        report = custom_field_registry_report({})
        self.assertTrue(report["valid"])
        self.assertEqual(report["definitions"], OrderedDict())
        self.assertEqual(report["diagnostics"], [])

    def test_none_config_is_valid_and_empty(self):
        report = custom_field_registry_report(None)
        self.assertTrue(report["valid"])

    def test_non_dict_registry_is_invalid(self):
        report = custom_field_registry_report({"custom_fields": ["not", "a", "dict"]})
        self.assertFalse(report["valid"])
        self.assertEqual(report["diagnostics"][0]["code"], "CF001")

    def test_invalid_field_name_reports_cf002(self):
        report = custom_field_registry_report(
            _config({"bad name!": {"type": "string"}})
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF002", codes)

    def test_reserved_name_reports_cf003(self):
        report = custom_field_registry_report(_config({"due": {"type": "string"}}))
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF003", codes)

    def test_record_is_reserved(self):
        report = custom_field_registry_report(_config({"record": {"type": "string"}}))
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF003", codes)

    def test_unsupported_type_reports_cf004_and_falls_back_to_string(self):
        report = custom_field_registry_report(_config({"energy": {"type": "wat"}}))
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF004", codes)
        self.assertEqual(report["definitions"]["energy"]["type"], "string")

    def test_unknown_metadata_key_reports_cf001(self):
        report = custom_field_registry_report(
            _config({"energy": {"type": "string", "privacy": "secret"}})
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_enum_type_without_values_reports_cf001(self):
        report = custom_field_registry_report(_config({"energy": {"type": "enum"}}))
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_minimum_greater_than_maximum_reports_cf001(self):
        report = custom_field_registry_report(
            _config({"rating": {"type": "number", "minimum": 5, "maximum": 0}})
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_min_length_greater_than_max_length_reports_cf001(self):
        report = custom_field_registry_report(
            _config(
                {
                    "label": {
                        "type": "string",
                        "min_length": 10,
                        "max_length": 2,
                    }
                }
            )
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_invalid_pattern_reports_cf001(self):
        report = custom_field_registry_report(
            _config({"label": {"type": "string", "pattern": "["}})
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_invalid_kinds_reports_cf001(self):
        report = custom_field_registry_report(
            _config({"energy": {"type": "string", "kinds": ["N", "Q"]}})
        )
        codes = [d["code"] for d in report["diagnostics"]]
        self.assertIn("CF001", codes)

    def test_valid_definition_normalizes_cleanly(self):
        report = custom_field_registry_report(
            _config(
                {
                    "energy": {
                        "type": "enum",
                        "values": ["low", "medium", "high"],
                        "kinds": ["J", "N"],
                        "filterable": True,
                    }
                }
            )
        )
        self.assertTrue(report["valid"])
        self.assertEqual(report["diagnostics"], [])
        definition = report["definitions"]["energy"]
        self.assertEqual(definition["type"], "enum")
        self.assertEqual(definition["enum"], ["low", "medium", "high"])
        self.assertEqual(definition["kinds"], ["J", "N"])
        self.assertTrue(definition["filterable"])
        self.assertEqual(definition["label"], "energy")
        self.assertFalse(definition["repeatable"])
        self.assertFalse(definition["required"])

    def test_minimum_and_maximum_round_trip_as_decimal_text(self):
        report = custom_field_registry_report(
            _config({"rating": {"type": "number", "minimum": 0, "maximum": 5}})
        )
        definition = report["definitions"]["rating"]
        self.assertEqual(definition["minimum"], "0")
        self.assertEqual(definition["maximum"], "5")

    def test_string_type_shorthand_definition(self):
        report = custom_field_registry_report(_config({"energy": "string"}))
        self.assertTrue(report["valid"])
        self.assertEqual(report["definitions"]["energy"]["type"], "string")

    def test_filterable_field_names_only_includes_filterable_true(self):
        config = _config(
            {
                "energy": {"type": "string", "filterable": True},
                "internal_note": {"type": "string", "filterable": False},
            }
        )
        self.assertEqual(filterable_field_names(config), frozenset({"energy"}))


class FieldAppliesTests(unittest.TestCase):
    def _item(self, line):
        items, _diagnostics = parse_text(line + "\n")
        return items[0]

    def test_ticket_item_never_applies(self):
        definition = {"kinds": None, "projects": None}
        item = self._item('[ ] T "Bug" record:ticket id:t1')
        self.assertFalse(field_applies(definition, item))

    def test_no_kinds_or_projects_applies_to_any_ordinary_item(self):
        definition = {"kinds": None, "projects": None}
        item = self._item('[N] N "Note"')
        self.assertTrue(field_applies(definition, item))

    def test_kinds_restriction_excludes_other_kinds(self):
        definition = {"kinds": ["J"], "projects": None}
        note = self._item('[N] N "Note"')
        journal = self._item('[N] J "Journal"')
        self.assertFalse(field_applies(definition, note))
        self.assertTrue(field_applies(definition, journal))

    def test_projects_restriction_excludes_other_projects(self):
        definition = {"kinds": None, "projects": ["home"]}
        home = self._item('[N] N "Note" project:home')
        work = self._item('[N] N "Note" project:work')
        self.assertTrue(field_applies(definition, home))
        self.assertFalse(field_applies(definition, work))


class GenericCustomFieldDiagnosticsIntegrationTests(unittest.TestCase):
    def _diagnostics_by_code(self, diagnostics, code):
        return [d for d in diagnostics if str(getattr(d, "code", "")) == code]

    def test_declared_applicable_field_suppresses_w106_and_stays_valid(self):
        config = _config(
            {"energy": {"type": "enum", "values": ["low", "high"], "kinds": ["N"]}}
        )
        items, diagnostics = parse_text('[N] N "Afternoon" energy:high\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(self._diagnostics_by_code(result, "W106"), [])
        self.assertEqual(self._diagnostics_by_code(result, "CF006"), [])

    def test_invalid_enum_value_reports_cf006(self):
        config = _config(
            {"energy": {"type": "enum", "values": ["low", "high"], "kinds": ["N"]}}
        )
        items, diagnostics = parse_text('[N] N "Afternoon" energy:extreme\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        cf006 = self._diagnostics_by_code(result, "CF006")
        self.assertEqual(len(cf006), 1)
        self.assertIn("energy", cf006[0].message)

    def test_out_of_range_number_reports_cf006(self):
        config = _config(
            {"rating": {"type": "number", "minimum": 0, "maximum": 5, "kinds": ["J"]}}
        )
        items, diagnostics = parse_text('[N] J "Daily review" rating:9\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(len(self._diagnostics_by_code(result, "CF006")), 1)

    def test_non_repeatable_field_with_multiple_values_reports_cf007(self):
        config = _config(
            {"rating": {"type": "number", "repeatable": False, "kinds": ["J"]}}
        )
        items, diagnostics = parse_text('[N] J "Daily review" rating:1 rating:2\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(len(self._diagnostics_by_code(result, "CF007")), 1)

    def test_repeatable_field_with_multiple_values_is_fine(self):
        config = _config(
            {"tag_like": {"type": "string", "repeatable": True, "kinds": ["N"]}}
        )
        items, diagnostics = parse_text('[N] N "Note" tag_like:a tag_like:b\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(self._diagnostics_by_code(result, "CF007"), [])

    def test_required_field_missing_reports_cf008(self):
        config = _config(
            {"energy": {"type": "string", "required": True, "kinds": ["N"]}}
        )
        items, diagnostics = parse_text('[N] N "Note"\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(len(self._diagnostics_by_code(result, "CF008")), 1)

    def test_required_field_present_does_not_report_cf008(self):
        config = _config(
            {"energy": {"type": "string", "required": True, "kinds": ["N"]}}
        )
        items, diagnostics = parse_text('[N] N "Note" energy:high\n')
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        self.assertEqual(self._diagnostics_by_code(result, "CF008"), [])

    def test_undeclared_custom_key_keeps_w106_unaffected(self):
        config = _config({"energy": {"type": "string", "kinds": ["N"]}})
        items, diagnostics = parse_text('[N] N "Note" energy:high mystery_key:1\n')
        before = self._diagnostics_by_code(diagnostics, "W106")
        self.assertTrue(any("mystery_key" in d.message for d in before))
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        remaining = self._diagnostics_by_code(result, "W106")
        self.assertTrue(any("mystery_key" in d.message for d in remaining))
        self.assertFalse(any("energy" in d.message for d in remaining))

    def test_field_used_outside_declared_kinds_is_left_untouched(self):
        config = _config({"energy": {"type": "string", "kinds": ["N"]}})
        # energy: is declared but this item is a Task (T), outside "kinds".
        items, diagnostics = parse_text('[ ] T "Task" energy:high\n')
        before_w106 = self._diagnostics_by_code(diagnostics, "W106")
        self.assertTrue(any("energy" in d.message for d in before_w106))
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        after_w106 = self._diagnostics_by_code(result, "W106")
        self.assertTrue(any("energy" in d.message for d in after_w106))
        self.assertEqual(self._diagnostics_by_code(result, "CF006"), [])

    def test_ticket_item_is_not_governed_by_the_generic_registry(self):
        config = _config({"energy": {"type": "enum", "values": ["low", "high"]}})
        items, diagnostics = parse_text(
            '[ ] T "Bug" record:ticket id:t1 energy:extreme\n'
        )
        result = generic_custom_field_diagnostics(items, diagnostics, config)
        # No generic constraint diagnostic is added for a record:ticket item,
        # even though "energy" is declared and would otherwise be invalid.
        self.assertEqual(self._diagnostics_by_code(result, "CF006"), [])

    def test_no_registry_configured_leaves_diagnostics_unchanged(self):
        items, diagnostics = parse_text('[N] N "Note" mystery_key:1\n')
        result = generic_custom_field_diagnostics(items, diagnostics, {})
        self.assertEqual(len(result), len(diagnostics))
        self.assertEqual([d.code for d in result], [d.code for d in diagnostics])

    def test_malformed_registry_reports_a_single_cf001(self):
        items, diagnostics = parse_text('[N] N "Note"\n')
        result = generic_custom_field_diagnostics(
            items, diagnostics, {"custom_fields": "not-an-object"}
        )
        cf001 = self._diagnostics_by_code(result, "CF001")
        self.assertEqual(len(cf001), 1)


class QuerySavedViewIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.config = _config(
            {
                "energy": {
                    "type": "enum",
                    "values": ["low", "medium", "high"],
                    "kinds": ["N"],
                    "filterable": True,
                },
                "internal_note": {"type": "string", "filterable": False},
            }
        )
        self.items, _diagnostics = parse_text(
            '[N] N "Afternoon" energy:high\n[N] N "Morning" energy:low\n'
        )

    def test_filterable_field_is_recognized_with_no_q001(self):
        _plan, diagnostics = parse_query("energy:high", self.config)
        codes = [d["code"] for d in diagnostics]
        self.assertNotIn("Q001", codes)

    def test_unknown_field_without_config_reports_q001(self):
        _plan, diagnostics = parse_query("energy:high")
        codes = [d["code"] for d in diagnostics]
        self.assertIn("Q001", codes)

    def test_non_filterable_configured_field_still_reports_q001(self):
        _plan, diagnostics = parse_query("internal_note:secret", self.config)
        codes = [d["code"] for d in diagnostics]
        self.assertIn("Q001", codes)

    def test_run_query_filters_by_the_filterable_custom_field(self):
        filtered, diagnostics = run_query(self.items, "energy:high", self.config)
        self.assertFalse(any(d["severity"] == "error" for d in diagnostics))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Afternoon")

    def test_existing_query_behavior_is_unchanged_without_a_registry(self):
        plan, diagnostics = parse_query("type:N")
        self.assertEqual(diagnostics, [])
        self.assertIn("type", plan["membership"])

    def test_saved_view_using_a_filterable_field_validates_and_runs(self):
        config = dict(self.config)
        config["saved_views"] = {"high-energy": {"query": "energy:high"}}
        errors = validate_saved_views(config)
        self.assertEqual(errors, [])
        filtered, _diagnostics = run_saved_view(self.items, config, "high-energy")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Afternoon")

    def test_saved_view_using_a_non_filterable_field_still_treats_it_as_unknown(self):
        # internal_note is declared but filterable:false, so the query engine
        # still reports Q001 (a warning, not a saved-view V002 error) rather
        # than silently treating it as a recognized filter field.
        config = dict(self.config)
        config["saved_views"] = {"bad-view": {"query": "internal_note:secret"}}
        self.assertEqual(validate_saved_views(config), [])
        _plan, diagnostics = parse_query("internal_note:secret", config)
        codes = [d["code"] for d in diagnostics]
        self.assertIn("Q001", codes)


class ConfigRegistryAndSchemaTests(unittest.TestCase):
    """The `Configuration Setting Completion` rule: registry metadata and
    the config-v1 schema must agree on the shape of `custom_fields`."""

    def test_registry_metadata_covers_the_generic_definition_keys(self):
        install_custom_fields_config_registry()
        metadata = config_registry.explain_key("custom_fields.energy.type")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["default"], "string")
        self.assertIn("enum", metadata["allowed_values"])
        filterable = config_registry.explain_key("custom_fields.energy.filterable")
        self.assertFalse(filterable["default"])

    def test_generated_config_schema_declares_custom_fields(self):
        generated = schema_bundle_v5()["config-v1.schema.json"]
        definition_schema = generated["properties"]["custom_fields"][
            "additionalProperties"
        ]
        variants = definition_schema["oneOf"]
        # a bare type-string shorthand, and the full object shape.
        self.assertEqual(variants[0]["type"], "string")
        object_schema = variants[1]
        self.assertFalse(object_schema["additionalProperties"])
        self.assertIn("filterable", object_schema["properties"])
        self.assertIn("kinds", object_schema["properties"])
        self.assertNotIn("privacy", object_schema["properties"])
        self.assertNotIn("trackers", object_schema["properties"])


if __name__ == "__main__":
    unittest.main()
