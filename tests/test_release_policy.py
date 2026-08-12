import json
import os
import tempfile

try:
    import tomllib
except ImportError:  # Python 3.10 compatibility
    import tomli as tomllib
import unittest

from lifetxt.release_policy import (
    golden_policy_report,
    packaging_metadata_report,
    release_manifest,
    schema_validation_report,
    translation_coverage_report,
    write_route_baseline_report,
)
from lifetxt.release_policy_compat import (
    release_policy_definition_report,
    translation_policy_report,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ReleasePolicyTests(unittest.TestCase):
    def test_optional_dependency_ranges_match_supported_api_policy(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as handle:
            project = tomllib.load(handle)["project"]
        extras = project["optional-dependencies"]
        self.assertEqual(
            extras["web"], ["fastapi>=0.95,<1.0", "uvicorn[standard]>=0.22,<1.0"]
        )
        self.assertEqual(extras["tui"], ["textual>=0.24,<1.0", "watchdog>=3,<7"])

    def test_repository_packaging_metadata_matches_runtime_version_and_script(self):
        report = packaging_metadata_report(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["name"], "lifetxt")
        self.assertEqual(report["console_script"], "lifetxt.entrypoint:main")
        self.assertIn("web", report["extras"])
        self.assertIn("tui", report["extras"])

    def test_versioned_golden_policy_matches_corpus(self):
        report = golden_policy_report(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["policy_version"], 1)
        self.assertGreaterEqual(report["case_count"], 9)
        self.assertEqual(len(report["case_names"]), len(set(report["case_names"])))

    def test_schema_bundle_is_checked_with_validator_when_available(self):
        optional = schema_validation_report(ROOT, require_validator=False)
        self.assertTrue(optional["ok"], optional)
        if optional["validator_available"]:
            strict = schema_validation_report(ROOT, require_validator=True)
            self.assertTrue(strict["ok"], strict)
            self.assertEqual(strict["draft"], "2020-12")
            self.assertEqual(strict["schema_count"], strict["sample_count"])

    def test_translation_report_parses_dictionary_and_separates_authored_content(self):
        report = translation_coverage_report()
        self.assertNotIn("error", report, report)
        self.assertGreater(report["dictionary_entries"], 100)
        self.assertGreater(report["chrome_strings"], 10)
        self.assertGreaterEqual(report["excluded_record_nodes"], 1)
        self.assertIsInstance(report["missing"], list)

    def test_translation_report_detects_new_untranslated_chrome(self):
        html = """
        <html><body><button title="Create item">Create item</button>
        <div data-no-i18n>Authored title</div>
        <script>
        const UI_STRINGS = {ja: {"Create item": "作成"}};
        const value = t("Dynamic label");
        </script></body></html>
        """
        report = translation_coverage_report(html)
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing"], ["Dynamic label"])
        self.assertEqual(report["excluded_record_nodes"], 1)

    def test_translation_report_accepts_complete_static_and_dynamic_chrome(self):
        html = """
        <html><body><button title="Create item">Create item</button>
        <script>
        const UI_STRINGS = {ja: {"Create item": "作成", "Dynamic label": "動的"}};
        const value = t("Dynamic label");
        </script></body></html>
        """
        report = translation_coverage_report(html)
        self.assertTrue(report["ok"], report)

    def test_repository_translation_baseline_allows_known_debt_but_no_new_gap(self):
        report = translation_policy_report(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["new_missing"], [])
        self.assertGreater(len(report["known_missing"]), 0)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["all_missing"], report["known_missing"])

    def test_write_route_baseline_rejects_new_path_call_pairs(self):
        with tempfile.TemporaryDirectory() as root:
            package = os.path.join(root, "lifetxt")
            policy = os.path.join(root, "config", "release")
            os.makedirs(package)
            os.makedirs(policy)
            path = os.path.join(package, "writer.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    'def save(path):\n    with open(path, "w") as stream:\n        stream.write("x")\n'
                )
            baseline_path = os.path.join(policy, "write-route-baseline-v1.json")
            with open(baseline_path, "w", encoding="utf-8") as handle:
                json.dump({"baseline_version": 1, "allowed": []}, handle)
            report = write_route_baseline_report(root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["new_findings"][0]["path"], "lifetxt/writer.py")
            with open(baseline_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "baseline_version": 1,
                        "allowed": [{"path": "lifetxt/writer.py", "call": "open(w)"}],
                    },
                    handle,
                )
            report = write_route_baseline_report(root)
            self.assertTrue(report["ok"], report)

    def test_repository_write_route_baseline_has_no_new_pairs(self):
        report = write_route_baseline_report(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["new_findings"], [])
        self.assertGreater(report["finding_count"], 0)

    def test_release_policy_definition_lists_available_required_checks(self):
        manifest = release_manifest(ROOT, require_validator=False)
        report = release_policy_definition_report(ROOT, manifest["checks"])
        self.assertTrue(report["ok"], report)
        self.assertFalse(report["errors"])

    def test_release_manifest_has_deterministic_fingerprint(self):
        first = release_manifest(ROOT, require_validator=False)
        second = release_manifest(ROOT, require_validator=False)
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["release_policy_version"], "1")
        self.assertIn("translation_coverage", first["checks"])
        self.assertIn("write_route_baseline", first["checks"])
        self.assertIn("release_policy_definition", first["checks"])


if __name__ == "__main__":
    unittest.main()
