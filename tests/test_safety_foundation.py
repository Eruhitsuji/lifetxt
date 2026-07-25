import codecs
import json
import os
import socket
import tempfile
import time
import unittest

from lifetxt.safety_foundation import (
    CANON_VERSION,
    FORMAT_VERSION,
    audit_python_writes,
    canonical_issues,
    canonicalize_text,
    capability_document,
    file_directives,
    format_version_report,
    inspect_locks,
    release_gate,
    resolve_timezone_policy,
    schema_bundle,
    serve_target_diagnostic,
    stable_diagnostics,
    validate_timezone,
    write_schema_bundle,
)


class SafetyFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name):
        return os.path.join(self.temp_dir.name, name)

    def write(self, name, text, raw=False):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if raw else "w"
        kwargs = {} if raw else {"encoding": "utf-8", "newline": ""}
        with open(path, mode, **kwargs) as handle:
            handle.write(text)
        return path

    def test_format_version_current_unversioned_and_unsupported(self):
        self.assertEqual("current", format_version_report("#! format_version: 1\n")["state"])
        self.assertEqual("unversioned", format_version_report("[ ] T Task\n")["state"])
        self.assertEqual("unsupported", format_version_report("#! format-version: 9\n")["state"])

    def test_directives_normalize_names_and_report_duplicates(self):
        values, duplicates = file_directives("#! format-version: 1\n#! timezone: UTC\n#! timezone: Asia/Tokyo\n")
        self.assertEqual("1", values["format_version"])
        self.assertEqual("Asia/Tokyo", values["timezone"])
        self.assertEqual([("timezone", 3)], duplicates)

    def test_canonicalize_enforces_lf_nfc_no_trailing_whitespace(self):
        source = "Cafe\u0301  \r\n[ ] T Task\t\r\n\r\n"
        self.assertEqual("Caf\u00e9\n[ ] T Task\n", canonicalize_text(source))

    def test_canonical_issues_cover_bom_crlf_nfc_case_and_final_newline(self):
        text = "#! format_version: 1\r\n[ ] T Cafe\u0301 Project:Work"
        codes = {row["code"] for row in canonical_issues(text, raw_bytes=codecs.BOM_UTF8 + text.encode("utf-8"), bom=True)}
        self.assertTrue({"F101", "F102", "F104", "F106", "F107"}.issubset(codes))

    def test_stable_diagnostics_has_source_span_and_hint(self):
        path = self.write("life.txt", "#! format_version: 1\n[ ] T Task\n")
        report = stable_diagnostics(path)
        self.assertTrue(report["ok"])
        for diagnostic in report["diagnostics"]:
            self.assertIn("source", diagnostic)
            self.assertIn("span", diagnostic)
            self.assertIn("hint", diagnostic)

    def test_timezone_precedence_cli_file_config_host(self):
        config = {"defaults": {"timezone": "UTC"}}
        text = "#! timezone: Asia/Tokyo\n"
        self.assertEqual("cli", resolve_timezone_policy(config, text, "Europe/London")["source"])
        self.assertEqual("file", resolve_timezone_policy(config, text)["source"])
        self.assertEqual("config", resolve_timezone_policy(config, "")["source"])
        self.assertEqual(["cli", "file", "config", "host"], resolve_timezone_policy(config, text)["precedence"])

    def test_invalid_timezone_is_visible(self):
        valid, error = validate_timezone("Not/A_Real_Zone")
        self.assertFalse(valid)
        self.assertTrue(error)

    def test_serve_target_reports_mismatch_and_drive_relative_path(self):
        report = serve_target_diagnostic([self.path("read.txt")], self.path("write.txt"))
        self.assertTrue(report["mismatch"])
        self.assertEqual("warning", report["severity"])
        drive = serve_target_diagnostic([], "C:relative\\life.txt")
        self.assertTrue(drive["windows_drive_relative"])

    def test_lock_observability_reports_owner_and_stale_state(self):
        target = self.path("life.txt")
        lock = target + ".lifetxt.lock"
        with open(lock, "w", encoding="utf-8") as handle:
            json.dump({"pid": 99999999, "host": socket.gethostname(), "operation": "test"}, handle)
        old = time.time() - 600
        os.utime(lock, (old, old))
        records = inspect_locks([target], stale_after=300, now=time.time())
        self.assertEqual(1, len(records))
        self.assertTrue(records[0]["stale"])
        self.assertEqual("test", records[0]["owner"]["operation"])

    def test_write_route_audit_detects_direct_commit_boundaries(self):
        package = self.path("repo/lifetxt")
        os.makedirs(package)
        self.write("repo/lifetxt/bad.py", "import os\ndef f():\n    os.replace('a', 'b')\n    atomic_write_bytes('x', b'y')\n")
        findings = audit_python_writes(self.path("repo"))
        calls = {row["call"] for row in findings}
        self.assertIn("os.replace", calls)
        self.assertIn("atomic_write_bytes", calls)

    def test_capability_document_is_versioned_and_revision_aware(self):
        value = capability_document(read_only=True, authentication="session", writable_targets=[])
        self.assertEqual("1", value["capability_version"])
        self.assertTrue(value["read_only"])
        self.assertTrue(value["revision_preconditions"]["supported"])
        self.assertIn("acknowledge", value["operations"])

    def test_schema_bundle_has_https_ids_and_required_documents(self):
        bundle = schema_bundle()
        expected = {
            "item-v1.schema.json",
            "diagnostic-v1.schema.json",
            "capability-v1.schema.json",
            "conflict-v1.schema.json",
            "release-manifest-v1.schema.json",
            "revision-metrics-v1.schema.json",
            "timezone-policy-v1.schema.json",
            "workspace-diagnostics-v1.schema.json",
            "doctor-v1.schema.json",
            "multi-target-result-v1.schema.json",
            "json-export-v1.schema.json",
            "proposal-v1.schema.json",
            "saved-view-v1.schema.json",
            "remote-profile-v1.schema.json",
            "group-v1.schema.json",
            "delivery-state-v1.schema.json",
            "transaction-journal-v1.schema.json",
            "transaction-recovery-v1.schema.json",
            "timer-operation-v1.schema.json",
            "support-bundle-v1.schema.json",
            "revision-migration-evidence-v1.schema.json",
            "attachment-transaction-v1.schema.json",
            "transaction-policy-v1.schema.json",
            "backup-integrity-v1.schema.json",
            "semantic-write-result-v1.schema.json",
            "fault-injection-report-v1.schema.json",
            "archive-operation-v1.schema.json",
            "work-session-v1.schema.json",
            "clock-boundary-audit-v1.schema.json",
            "config-v1.schema.json",
            "workspace-source-manifest-v1.schema.json",
            "project-registry-v1.schema.json",
            "project-summary-v1.schema.json",
            "command-center-v1.schema.json",
            "area-summary-v1.schema.json",
            "editor-session-v1.schema.json",
            "directory-package-v1.schema.json",
            "attachment-open-v1.schema.json",
            "transaction-policy-admin-v1.schema.json",
            "transaction-preflight-v1.schema.json",
            "clock-skew-v1.schema.json",
            "query-plan-v1.schema.json",
            "recipient-resolution-v1.schema.json",
            "person-overview-v1.schema.json",
            "inbox-proposal-v1.schema.json",
            "delegated-mutation-proposal-v1.schema.json",
            "attachment-remote-operation-v1.schema.json",
            "attachment-chunk-v1.schema.json",
            "directory-package-inspection-v1.schema.json",
            "transaction-restore-v1.schema.json",
            "fault-drill-matrix-v1.schema.json",
            "remote-write-clock-v1.schema.json",
            "global-search-v1.schema.json",
            "ticket-v1.schema.json",
            "ticket-field-registry-v1.schema.json",
            "ticket-custom-field-registry-v1.schema.json",
            "ticket-workflow-v1.schema.json",
            "ticket-event-v1.schema.json",
            "ticket-time-entry-v1.schema.json",
            "ticket-activity-v1.schema.json",
            "ticket-version-v1.schema.json",
            "ticket-sprint-v1.schema.json",
            "ticket-planning-v1.schema.json",
            "ticket-project-report-v1.schema.json",
        }
        self.assertEqual(expected, set(bundle))
        for schema in bundle.values():
            self.assertTrue(schema["$id"].startswith("https://"))
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        directory = self.path("schemas")
        names = write_schema_bundle(directory)
        self.assertEqual(sorted(bundle), names)
        for name in names:
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                json.load(handle)

    def test_release_gate_passes_complete_fixture_repository(self):
        root = self.path("repo")
        os.makedirs(os.path.join(root, "lifetxt"))
        os.makedirs(os.path.join(root, "tests", "golden"))
        os.makedirs(os.path.join(root, "dist", "schemas"))
        self.write("repo/pyproject.toml", "[project]\nname='fixture'\n")
        self.write("repo/tests/golden/roundtrip_cases.json", '{"version": 1}\n')
        for index in range(3):
            self.write("repo/dist/schemas/%s.json" % index, "{}\n")
        report = release_gate(root)
        self.assertTrue(report["ok"], report)
        self.assertEqual(FORMAT_VERSION, report["versions"]["format"])
        self.assertEqual(CANON_VERSION, report["versions"]["canon"])


if __name__ == "__main__":
    unittest.main()
