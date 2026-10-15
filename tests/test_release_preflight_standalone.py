"""Offline native producer contract and fail-closed frozen-payload tests."""

import copy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_standalone as standalone  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


class StandalonePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload"
        self.payload.mkdir()
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 101, 1
        )
        self.target = "standalone-linux-x86_64"
        self.binary = self.payload / standalone.TARGETS[self.target][3]
        self.binary.write_bytes(b"fixture frozen payload")
        self.sums = self.payload / (self.binary.name + ".sha256")
        self.write_checksum()
        self.artifact = {"id": 20, "name": "fixture-target-payload", "sha256": "e" * 64}

    def write_checksum(self):
        self.sums.write_bytes(standalone.checksum(self.binary).encode("ascii"))

    def report(self):
        return proof.sealed(
            {
                "schema_version": 1,
                "candidate_digest": self.candidate["digest"],
                **{
                    key: self.candidate[key]
                    for key in ("source_sha", "controller_sha", "run_id", "run_attempt")
                },
                "target": self.target,
                "observed_version": "1.0.4.2",
                "toolchain": {"python": "fixture", "pyinstaller": "fixture"},
                "checks": dict.fromkeys(proof.CONTRACTS["standalone"][1], "passed"),
                "files": [
                    {
                        "path": path.name,
                        "role": role,
                        "sha256": proof.file_digest(path),
                        "bytes": path.stat().st_size,
                    }
                    for path, role in ((self.binary, "binary"), (self.sums, "checksum"))
                ],
            }
        )

    def finish(self, report):
        return standalone.finish(
            self.candidate, report, self.payload, self.artifact, self.target
        )

    def reseal(self, report):
        return proof.sealed(
            {key: value for key, value in report.items() if key != "digest"}
        )

    def test_full_five_target_host_matrix_and_arch_aliases(self):
        self.assertEqual(
            set(standalone.TARGETS),
            {target for target in proof.TARGETS if target.startswith("standalone-")},
        )
        for target, (system, arch, _, _) in standalone.TARGETS.items():
            machine = "AMD64" if arch == "x86_64" else "aarch64"
            with (
                self.subTest(target=target),
                patch.object(standalone.platform, "system", return_value=system),
                patch.object(standalone.platform, "machine", return_value=machine),
                patch.object(standalone.struct, "calcsize", return_value=8),
            ):
                standalone.validate_host(target)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            standalone.validate_host("arbitrary")

    def test_wrong_native_host_arch_or_bitness_stops_build(self):
        for system, machine, size in (
            ("Windows", "x86_64", 8),
            ("Linux", "arm64", 8),
            ("Linux", "x86_64", 4),
        ):
            with (
                self.subTest(system=system, machine=machine, size=size),
                patch.object(standalone.platform, "system", return_value=system),
                patch.object(standalone.platform, "machine", return_value=machine),
                patch.object(standalone.struct, "calcsize", return_value=size),
                self.assertRaisesRegex(ValueError, "host/architecture"),
            ):
                standalone.validate_host(self.target)

    def test_exact_payload_and_lf_checksum_bind_to_component(self):
        binary, sums = standalone.validate_payload(self.target, self.payload)
        self.assertEqual(binary, self.binary)
        self.assertNotIn(b"\r", sums.read_bytes())
        result = self.finish(self.report())
        proof.validate_component(self.candidate, result, self.payload)
        self.assertEqual(result["target"], self.target)

    def test_crlf_wrong_hash_missing_or_extra_file_rejected(self):
        self.sums.write_bytes(self.sums.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            standalone.validate_payload(self.target, self.payload)
        self.write_checksum()
        self.binary.write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            standalone.validate_payload(self.target, self.payload)
        self.write_checksum()
        (self.payload / "extra").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            standalone.validate_payload(self.target, self.payload)
        (self.payload / "extra").unlink()
        self.sums.unlink()
        with self.assertRaisesRegex(ValueError, "inventory"):
            standalone.validate_payload(self.target, self.payload)

    def test_report_tamper_identity_target_schema_and_roles_rejected(self):
        report = self.report()
        report["run_id"] += 1
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.finish(report)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.finish(self.reseal(report))
        for key, value, message in (
            ("target", "standalone-linux-arm64", "target mismatch"),
            ("schema_version", True, "schema"),
            ("observed_version", "1.0.4.3", "version mismatch"),
        ):
            row = self.report()
            row[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, message):
                self.finish(self.reseal(row))
        row = self.report()
        row["files"][0]["role"] = "checksum"
        with self.assertRaisesRegex(ValueError, "role mismatch"):
            self.finish(self.reseal(row))

    def test_binary_and_checksum_changed_together_after_smoke_rejected(self):
        report = self.report()
        self.binary.write_bytes(b"different bytes with freshly updated checksum")
        self.write_checksum()
        with self.assertRaisesRegex(ValueError, "changed since smoke"):
            self.finish(report)

    def test_required_smoke_failed_skipped_or_missing_rejected(self):
        for result in ("failed", "skipped", "not_run"):
            report = self.report()
            report["checks"]["timezone"] = result
            with (
                self.subTest(result=result),
                self.assertRaisesRegex(ValueError, "smoke"),
            ):
                self.finish(self.reseal(report))
        report = self.report()
        del report["checks"]["init-doctor"]
        with self.assertRaisesRegex(ValueError, "checks"):
            self.finish(self.reseal(report))

    def test_frozen_smoke_runs_outside_source_with_unicode_timezone_and_private_home(
        self,
    ):
        calls = []

        def run(command, cwd, env):
            calls.append((command, cwd, env))
            if command[-1] == "--version":
                return "lifetxt 1.0.4.2"
            return "OK"

        with (
            patch.dict(os.environ, {"PYTHONPATH": str(ROOT), "PYTHONHOME": "/wrong"}),
            patch.object(standalone.core, "run", side_effect=run),
        ):
            checks = standalone.smoke(
                self.binary, ROOT / "examples/minimal_life.txt", "1.0.4.2"
            )
        self.assertTrue(all(value == "passed" for value in checks.values()))
        self.assertEqual(len(calls), 9)
        self.assertTrue(any("日本語" in str(cwd) for _, cwd, _ in calls))
        self.assertTrue(any("today" in command for command, _, _ in calls))
        self.assertTrue(any("doctor" in command for command, _, _ in calls))
        for command, cwd, env in calls:
            self.assertEqual(command[0], str(self.binary))
            self.assertNotEqual(cwd, ROOT)
            self.assertNotIn("PYTHONPATH", env)
            self.assertNotIn("PYTHONHOME", env)
            self.assertTrue(env["HOME"].endswith("home"))

    def test_wrong_version_stops_smoke_immediately(self):
        with (
            patch.object(standalone.core, "run", return_value="lifetxt 1.0.4.3") as run,
            self.assertRaisesRegex(ValueError, "version mismatch"),
        ):
            standalone.smoke(self.binary, ROOT / "examples/minimal_life.txt", "1.0.4.2")
        self.assertEqual(run.call_count, 1)

    def test_pyinstaller_failure_has_no_success_report(self):
        report = self.root / "new-report.json"
        payload = self.root / "new-payload"
        with (
            patch.object(standalone.core, "validate_context"),
            patch.object(standalone.core, "validate_source"),
            patch.object(standalone, "validate_host"),
            patch.object(
                standalone.core,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["PyInstaller"]),
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            standalone.build(
                self.candidate, ROOT, ROOT, payload, report, self.target, {}
            )
        self.assertFalse(report.exists())
        self.assertFalse(payload.exists())

    def test_workflow_has_full_matrix_read_only_no_shared_matrix_outputs(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML unavailable")
        workflow = yaml.load(
            (ROOT / ".github/workflows/release-preflight-standalone.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertNotIn("outputs", workflow["on"]["workflow_call"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["standalone"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertEqual(
            {row["target"] for row in job["strategy"]["matrix"]["include"]},
            set(standalone.TARGETS),
        )
        self.assertEqual(job["strategy"]["fail-fast"], "false")
        self.assertNotIn("environment", job)
        self.assertEqual(workflow["defaults"]["run"]["shell"], "bash")
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                self.assertEqual(step["with"]["persist-credentials"], "false")
            if step.get("uses", "").startswith("actions/upload-artifact@"):
                self.assertIn("matrix.target", step["with"]["name"])


if __name__ == "__main__":
    unittest.main()
