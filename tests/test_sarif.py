"""Unit tests for the SARIF 2.1.0 export adapter (#644):
`lifetxt/sarif.py`'s pure serialization functions, exercised directly
against synthetic `Diagnostic` objects. CLI-level integration (`check
--format sarif`, filtering parity, text/json regression) is covered
separately in `tests/test_check_sarif.py`.
"""

import json
import unittest

from lifetxt.model import Diagnostic
from lifetxt.sarif import (
    SARIF_VERSION,
    _to_uri,
    render_sarif,
    sarif_document,
)


class ToUriTests(unittest.TestCase):
    def test_windows_absolute_path(self):
        self.assertEqual(
            "file:///C:/Users/me/life.txt", _to_uri("C:\\Users\\me\\life.txt")
        )

    def test_windows_absolute_path_already_forward_slashed(self):
        self.assertEqual(
            "file:///C:/Users/me/life.txt", _to_uri("C:/Users/me/life.txt")
        )

    def test_posix_absolute_path(self):
        self.assertEqual("file:///home/me/life.txt", _to_uri("/home/me/life.txt"))

    def test_relative_path_is_used_as_is(self):
        self.assertEqual("life.txt", _to_uri("life.txt"))

    def test_relative_path_with_backslashes_is_normalized(self):
        self.assertEqual("sub/life.txt", _to_uri("sub\\life.txt"))

    def test_stdin_marker_and_none_have_no_uri(self):
        self.assertIsNone(_to_uri("-"))
        self.assertIsNone(_to_uri(None))

    def test_spaces_and_hash_are_percent_encoded(self):
        # A CodeX review finding: an unescaped "#" would be read by a
        # strict URI consumer as introducing a fragment identifier
        # (silently discarding everything after it as "the fragment"
        # rather than part of the path), and a literal space makes the
        # URI outright invalid.
        self.assertEqual(
            "file:///C:/My%20Files/life%20%231.txt",
            _to_uri("C:\\My Files\\life #1.txt"),
        )
        self.assertEqual("sub%20dir/life%20%231.txt", _to_uri("sub dir/life #1.txt"))

    def test_non_ascii_characters_are_percent_encoded(self):
        self.assertEqual(
            "file:///home/me/%E6%97%A5%E6%9C%AC%E8%AA%9E/life.txt",
            _to_uri("/home/me/日本語/life.txt"),
        )

    def test_unc_path_uses_the_server_as_the_uri_authority(self):
        # The server name is its own URI authority component (RFC 8089's
        # Windows UNC-path appendix), not folded into the path -- the
        # original version produced a non-standard four-slash
        # file:////server/... by treating the whole normalized UNC path
        # as an ordinary POSIX-absolute one.
        self.assertEqual(
            "file://server/share/life.txt", _to_uri("\\\\server\\share\\life.txt")
        )

    def test_unc_path_with_no_share_still_uses_the_server_as_authority(self):
        self.assertEqual("file://server", _to_uri("\\\\server"))


class SarifDocumentStructureTests(unittest.TestCase):
    def test_top_level_shape(self):
        doc = sarif_document([])
        self.assertEqual(SARIF_VERSION, doc["version"])
        self.assertIn("$schema", doc)
        self.assertEqual(1, len(doc["runs"]))
        self.assertEqual("lifetxt", doc["runs"][0]["tool"]["driver"]["name"])
        self.assertEqual([], doc["runs"][0]["results"])
        self.assertEqual([], doc["runs"][0]["tool"]["driver"]["rules"])

    def test_single_error_result(self):
        diagnostic = Diagnostic(
            "error",
            "E003",
            "Invalid status '[X]'.",
            line=1,
            column=1,
            source="life.txt",
            hint="Use one of [ ], [/], [x].",
        )
        doc = sarif_document([diagnostic])
        results = doc["runs"][0]["results"]
        self.assertEqual(1, len(results))
        result = results[0]
        self.assertEqual("E003", result["ruleId"])
        self.assertEqual("error", result["level"])
        self.assertEqual("Invalid status '[X]'.", result["message"]["text"])
        self.assertEqual(
            "life.txt",
            result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
        )
        self.assertEqual(
            1, result["locations"][0]["physicalLocation"]["region"]["startLine"]
        )
        self.assertEqual("Use one of [ ], [/], [x].", result["properties"]["hint"])

    def test_single_warning_result_level(self):
        diagnostic = Diagnostic("warning", "W213", "Duplicate id:foo.")
        doc = sarif_document([diagnostic])
        self.assertEqual("warning", doc["runs"][0]["results"][0]["level"])

    def test_start_only_location_has_no_end_region(self):
        diagnostic = Diagnostic("error", "E010", "x", line=1, column=13)
        doc = sarif_document([diagnostic])
        region = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "region"
        ]
        self.assertNotIn("endLine", region)
        self.assertNotIn("endColumn", region)

    def test_precise_span_has_an_end_region(self):
        diagnostic = Diagnostic(
            "error",
            "E018",
            "Unclosed quoted title.",
            line=1,
            column=7,
            end_line=1,
            end_column=20,
        )
        doc = sarif_document([diagnostic])
        region = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "region"
        ]
        self.assertEqual(20, region["endColumn"])
        self.assertEqual(1, region["endLine"])

    def test_no_location_when_diagnostic_has_neither_source_nor_line(self):
        diagnostic = Diagnostic("warning", "W999", "Something is off")
        doc = sarif_document([diagnostic])
        self.assertNotIn("locations", doc["runs"][0]["results"][0])

    def test_no_hint_property_when_hint_is_empty(self):
        diagnostic = Diagnostic("warning", "W999", "Something is off")
        doc = sarif_document([diagnostic])
        self.assertNotIn("properties", doc["runs"][0]["results"][0])

    def test_multiple_same_code_results_dedup_rule_metadata(self):
        diagnostics = [
            Diagnostic("error", "E010", "x", line=1, column=13, source="a.txt"),
            Diagnostic("error", "E010", "x", line=1, column=20, source="a.txt"),
            Diagnostic("error", "E010", "x", line=1, column=24, source="a.txt"),
        ]
        doc = sarif_document(diagnostics)
        rules = doc["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual(1, len(rules))
        self.assertEqual("E010", rules[0]["id"])
        self.assertEqual(3, len(doc["runs"][0]["results"]))

    def test_distinct_codes_each_get_their_own_rule_in_first_seen_order(self):
        diagnostics = [
            Diagnostic("warning", "W213", "x"),
            Diagnostic("error", "E003", "y"),
            Diagnostic("warning", "W213", "z"),
        ]
        doc = sarif_document(diagnostics)
        rule_ids = [rule["id"] for rule in doc["runs"][0]["tool"]["driver"]["rules"]]
        self.assertEqual(["W213", "E003"], rule_ids)

    def test_rule_category_reuses_diagnostic_contract_not_a_second_mapping(self):
        diagnostic = Diagnostic("warning", "W213", "Duplicate id:foo.")
        doc = sarif_document([diagnostic])
        rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertEqual("id", rule["properties"]["category"])

    def test_documented_code_gets_a_short_description_from_the_catalog(self):
        diagnostic = Diagnostic("error", "E003", "Invalid status '[X]'.")
        doc = sarif_document([diagnostic])
        rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertIn("shortDescription", rule)

    def test_undocumented_code_has_no_short_description(self):
        diagnostic = Diagnostic("warning", "W999", "Something undocumented.")
        doc = sarif_document([diagnostic])
        rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertNotIn("shortDescription", rule)


class RenderSarifTests(unittest.TestCase):
    def test_render_sarif_is_valid_json_matching_the_document(self):
        diagnostic = Diagnostic("error", "E003", "Invalid status '[X]'.")
        text = render_sarif([diagnostic])
        parsed = json.loads(text)
        self.assertEqual(sarif_document([diagnostic]), parsed)


if __name__ == "__main__":
    unittest.main()
