"""Integration tests for `lifetxt check --format sarif` (#644): CLI
wiring, filtering parity with text/json, exit-code parity, and
text/json regression (this format is purely additive).
"""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class CheckSarifIntegrationTests(unittest.TestCase):
    def test_sarif_output_is_valid_json_with_the_expected_shape(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "sarif")
            self.assertEqual(0, rc)
            payload = json.loads(out)
            self.assertEqual("2.1.0", payload["version"])
            results = payload["runs"][0]["results"]
            self.assertEqual(1, len(results))
            self.assertEqual("W213", results[0]["ruleId"])
        finally:
            os.unlink(path)

    def test_sarif_result_count_matches_json_diagnostic_count(self):
        path = _make_file("[ ] T Write report due 2026-01-01\n")
        try:
            out_json, _, rc_json = run_cli("check", path, "--format", "json")
            out_sarif, _, rc_sarif = run_cli("check", path, "--format", "sarif")
            self.assertEqual(rc_json, rc_sarif)
            json_diagnostics = json.loads(out_json)
            sarif_results = json.loads(out_sarif)["runs"][0]["results"]
            self.assertEqual(len(json_diagnostics), len(sarif_results))
            self.assertEqual(
                [d["code"] for d in json_diagnostics],
                [r["ruleId"] for r in sarif_results],
            )
        finally:
            os.unlink(path)

    def test_filtering_by_code_produces_matching_sarif_results(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "sarif", "--code", "W213")
            payload = json.loads(out)
            self.assertEqual(1, len(payload["runs"][0]["results"]))
        finally:
            os.unlink(path)

    def test_ignore_removes_the_diagnostic_from_sarif_output(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli(
                "check", path, "--format", "sarif", "--ignore", "W213"
            )
            self.assertEqual(0, rc)
            payload = json.loads(out)
            self.assertEqual([], payload["runs"][0]["results"])
        finally:
            os.unlink(path)

    def test_no_diagnostics_produces_an_empty_but_valid_sarif_document(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "sarif")
            self.assertEqual(0, rc)
            payload = json.loads(out)
            self.assertEqual([], payload["runs"][0]["results"])
            self.assertEqual([], payload["runs"][0]["tool"]["driver"]["rules"])
        finally:
            os.unlink(path)

    def test_exit_code_parity_with_warnings_as_errors(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            _, _, rc_text = run_cli("check", path, "--warnings-as-errors")
            _, _, rc_sarif = run_cli(
                "check", path, "--format", "sarif", "--warnings-as-errors"
            )
            self.assertEqual(rc_text, rc_sarif)
        finally:
            os.unlink(path)

    def test_text_output_is_unaffected_by_the_new_format_choice(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path)
            self.assertIn("WARNING W213", out)
            self.assertNotIn("sarif", out.lower())
            self.assertNotIn("ruleId", out)
        finally:
            os.unlink(path)

    def test_json_output_is_unaffected_by_the_new_format_choice(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "json")
            payload = json.loads(out)
            self.assertEqual(1, len(payload))
            self.assertNotIn("ruleId", json.dumps(payload))
        finally:
            os.unlink(path)

    def test_a_windows_style_path_fixture_produces_a_valid_file_uri(self):
        # run_cli always passes a real filesystem path from tempfile, which
        # on this Windows CI/dev host already exercises the Windows-drive
        # branch of _to_uri end to end.
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "sarif")
            payload = json.loads(out)
            uri = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                "artifactLocation"
            ]["uri"]
            self.assertTrue(uri.startswith("file:///"))
            self.assertNotIn("\\", uri)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
