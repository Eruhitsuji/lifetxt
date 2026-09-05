"""Tests for the diagnostic explanation catalog (#641): `known_codes()`/
`explain_record()`/text/JSON rendering, drift detection against the
existing parser/validator hint dictionaries and locale catalog, and the
`lifetxt help diagnostic [CODE]` CLI surface end to end.
"""

import json
import unittest

from lifetxt import diagnostic_catalog
from lifetxt.diagnostic_contract import DIAGNOSTIC_CATEGORIES, diagnostic_category
from lifetxt.i18n import _CATALOG as _I18N_CATALOG
from lifetxt.model import Diagnostic
from lifetxt.parser import PARSER_DIAGNOSTIC_HINTS
from lifetxt.validator import VALIDATOR_DIAGNOSTIC_HINTS
from tests.test_lifetxt import run_cli


class KnownCodeLookupTests(unittest.TestCase):
    def test_known_code_returns_full_record(self):
        record = diagnostic_catalog.explain_record("E003")
        self.assertEqual("E003", record["code"])
        self.assertEqual("syntax", record["category"])
        self.assertEqual("error", record["severity"])
        self.assertTrue(record["summary"])
        self.assertTrue(record["remediation"])
        self.assertTrue(record["examples"])

    def test_lookup_is_case_and_whitespace_tolerant(self):
        self.assertEqual(
            diagnostic_catalog.explain_record("E003"),
            diagnostic_catalog.explain_record(" e003 "),
        )

    def test_severity_derived_from_code_prefix(self):
        self.assertEqual("error", diagnostic_catalog.severity_for_code("E010"))
        self.assertEqual("warning", diagnostic_catalog.severity_for_code("W106"))

    def test_category_matches_the_shared_diagnostic_contract_helper(self):
        # category_for_code() must never hand-duplicate diagnostic_category()'s
        # own code -> category mapping.
        for code in diagnostic_catalog.known_codes():
            expected = diagnostic_category(Diagnostic("warning", code, "x"))
            self.assertEqual(expected, diagnostic_catalog.category_for_code(code))


class UnknownCodeTests(unittest.TestCase):
    def test_unknown_code_raises_value_error_naming_the_documented_set(self):
        with self.assertRaises(ValueError) as ctx:
            diagnostic_catalog.explain_record("E999")
        message = str(ctx.exception)
        self.assertIn("E999", message)
        self.assertIn("E003", message)

    def test_unknown_code_never_guesses_a_near_match(self):
        # "E0003" is one character away from the real "E003"; it must still
        # be reported as unknown, not silently resolved to E003.
        with self.assertRaises(ValueError):
            diagnostic_catalog.explain_record("E0003")


class CatalogDriftTests(unittest.TestCase):
    """Catches a catalog entry going stale: a code whose remediation
    silently degrades to empty because it was removed from the
    parser/validator hint dictionaries, or whose summary is missing from
    the locale catalog for a supported locale."""

    def test_every_catalog_code_has_a_non_empty_remediation(self):
        for code in diagnostic_catalog.known_codes():
            record = diagnostic_catalog.explain_record(code)
            self.assertTrue(record["remediation"], "empty remediation for %s" % code)

    def test_every_catalog_category_is_a_published_category(self):
        for code in diagnostic_catalog.known_codes():
            record = diagnostic_catalog.explain_record(code)
            self.assertIn(record["category"], DIAGNOSTIC_CATEGORIES)

    def test_every_catalog_code_has_registered_en_and_ja_summaries(self):
        for code in diagnostic_catalog.known_codes():
            message_id = "diagnostic.%s.summary" % code
            translations = _I18N_CATALOG.get(message_id)
            self.assertIsNotNone(
                translations, "missing summary catalog entry for %s" % code
            )
            self.assertTrue(translations.get("en"))
            self.assertTrue(translations.get("ja"))

    def test_parser_and_validator_sourced_codes_still_have_a_real_hint(self):
        # Codes without their own catalog-authored "remediation" reuse the
        # parser/validator hint dictionaries; confirm that source still
        # actually defines them (a hint removed there must not silently
        # degrade this catalog's remediation to "").
        for code in diagnostic_catalog.known_codes():
            entry = diagnostic_catalog._CATALOG_ENTRIES[code]
            if "remediation" in entry:
                continue
            self.assertTrue(
                code in PARSER_DIAGNOSTIC_HINTS or code in VALIDATOR_DIAGNOSTIC_HINTS,
                "%s has no catalog-authored remediation and no parser/validator hint"
                % code,
            )


class RenderTests(unittest.TestCase):
    def test_render_code_text_includes_core_fields(self):
        text = diagnostic_catalog.render_code_text("E003")
        self.assertIn("E003", text)
        self.assertIn("Category: syntax", text)
        self.assertIn("Severity: error", text)
        self.assertIn("Remediation:", text)
        self.assertIn("Example:", text)

    def test_render_code_json_matches_explain_record_plus_schema(self):
        payload = json.loads(diagnostic_catalog.render_code_json("E003"))
        self.assertEqual("lifetxt-diagnostic-explain-v1", payload["schema"])
        record = diagnostic_catalog.explain_record("E003")
        for key, value in record.items():
            self.assertEqual(value, payload[key])

    def test_render_overview_text_lists_every_known_code_and_hint(self):
        text = diagnostic_catalog.render_overview_text()
        for code in diagnostic_catalog.known_codes():
            self.assertIn(code, text)
        self.assertIn("help diagnostic CODE", text)

    def test_render_overview_json_schema(self):
        payload = json.loads(diagnostic_catalog.render_overview_json())
        self.assertEqual("lifetxt-diagnostic-catalog-v1", payload["schema"])
        self.assertEqual(
            set(diagnostic_catalog.known_codes()),
            {row["code"] for row in payload["codes"]},
        )


class HelpDiagnosticCliTests(unittest.TestCase):
    def test_help_diagnostic_code_text(self):
        stdout, stderr, code = run_cli("help", "diagnostic", "E003")
        self.assertEqual(0, code, stderr)
        self.assertIn("E003", stdout)
        self.assertIn("Category: syntax", stdout)

    def test_help_diagnostic_code_json(self):
        stdout, stderr, code = run_cli("help", "diagnostic", "E003", "--format", "json")
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertEqual("E003", data["code"])
        self.assertEqual("lifetxt-diagnostic-explain-v1", data["schema"])

    def test_help_diagnostic_overview_when_code_omitted(self):
        stdout, stderr, code = run_cli("help", "diagnostic")
        self.assertEqual(0, code, stderr)
        self.assertIn("Documented diagnostic codes:", stdout)
        self.assertIn("E003", stdout)

    def test_help_diagnostic_unknown_code_fails_loudly(self):
        stdout, stderr, code = run_cli("help", "diagnostic", "E999")
        self.assertEqual(1, code)
        self.assertIn("Unknown diagnostic code", stderr)

    def test_help_other_topics_are_unaffected(self):
        stdout, stderr, code = run_cli("help", "add")
        self.assertEqual(0, code, stderr)
        self.assertIn("lifetxt help quick", stdout)

    def test_bare_help_is_unaffected(self):
        stdout, stderr, code = run_cli("help")
        self.assertEqual(0, code, stderr)
        self.assertIn("Start here", stdout)

    def test_help_diagnostic_json_is_locale_invariant_for_machine_fields(self):
        out_en, _, _ = run_cli("help", "diagnostic", "E003", "--format", "json")
        out_ja, _, _ = run_cli(
            "--lang", "ja", "help", "diagnostic", "E003", "--format", "json"
        )
        data_en = json.loads(out_en)
        data_ja = json.loads(out_ja)
        self.assertEqual(data_en["code"], data_ja["code"])
        self.assertEqual(data_en["category"], data_ja["category"])
        self.assertEqual(data_en["severity"], data_ja["severity"])

    def test_help_diagnostic_text_is_localized_for_ja(self):
        stdout, stderr, code = run_cli("--lang", "ja", "help", "diagnostic", "W106")
        self.assertEqual(0, code, stderr)
        self.assertIn("W106", stdout)


if __name__ == "__main__":
    unittest.main()
