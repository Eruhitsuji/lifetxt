"""Fault injection for the Core non-public producer and its authority boundary."""

import copy
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_core as core  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


class CorePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload"
        self.payload.mkdir()
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 100, 1
        )
        self.wheel = self.payload / "lifetxt-1.0.4.2-py3-none-any.whl"
        self.sdist = self.payload / "lifetxt-1.0.4.2.tar.gz"
        self.archives()
        self.metadata()
        self.context = {
            "GITHUB_REPOSITORY": "Eruhitsuji/lifetxt",
            "GITHUB_RUN_ID": "100",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        self.artifact = {"id": 123, "name": "core-payload-100-1", "sha256": "e" * 64}

    def archives(self, version="1.0.4.2"):
        metadata = ("Name: lifetxt\nVersion: " + version + "\n").encode()
        with zipfile.ZipFile(self.wheel, "w") as archive:
            archive.writestr("lifetxt-1.0.4.2.dist-info/METADATA", metadata)
        with tarfile.open(self.sdist, "w:gz") as archive:
            info = tarfile.TarInfo("lifetxt-1.0.4.2/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))

    def metadata(self):
        sbom = {"metadata": {"component": {"name": "lifetxt", "version": "1.0.4.2"}}}
        self.provenance = {
            "schema": "lifetxt-release-provenance-v1",
            "package": {"name": "lifetxt", "version": "1.0.4.2"},
            "source": {"commit": "a" * 40, "tag": None},
            "workflow_run": "100",
            "artifacts": [
                {
                    "file": path.name,
                    "sha256": proof.file_digest(path),
                    "bytes": path.stat().st_size,
                }
                for path in (self.wheel, self.sdist)
            ],
        }
        (self.payload / "sbom.cdx.json").write_text(json.dumps(sbom))
        self.save_provenance()

    def save_provenance(self):
        (self.payload / "provenance.json").write_text(json.dumps(self.provenance))

    def report(self):
        roles = {
            self.wheel.name: "wheel",
            self.sdist.name: "sdist",
            "sbom.cdx.json": "sbom",
            "provenance.json": "provenance",
        }
        return proof.sealed(
            {
                "schema_version": 1,
                "candidate_digest": self.candidate["digest"],
                "source_sha": "a" * 40,
                "controller_sha": "b" * 40,
                "run_id": 100,
                "run_attempt": 1,
                "observed_version": "1.0.4.2",
                "toolchain": {"python": "fixture"},
                "checks": {
                    "metadata": "passed",
                    "clean-install": "passed",
                    "cli": "passed",
                },
                "files": [
                    {
                        "path": path.name,
                        "role": roles[path.name],
                        "sha256": proof.file_digest(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in sorted(self.payload.iterdir())
                ],
            }
        )

    def reseal(self, value):
        return proof.sealed(
            {key: item for key, item in value.items() if key != "digest"}
        )

    def test_archives_and_provenance_match_explicit_correction(self):
        self.assertEqual(
            core.validate_evidence(self.candidate, self.payload),
            (self.wheel, self.sdist),
        )
        result = core.finish(self.candidate, self.report(), self.payload, self.artifact)
        proof.validate_component(self.candidate, result, self.payload)
        self.assertEqual(result["observed_version"], "1.0.4.2")

    def test_source_controller_run_context_checked(self):
        with patch.object(core, "git", side_effect=["b" * 40, ""]):
            core.validate_context(self.candidate, self.root, self.context)
        for key in self.context:
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "context mismatch"),
            ):
                core.validate_context(
                    self.candidate, self.root, dict(self.context, **{key: "wrong"})
                )
        for outputs, message in (
            (["c" * 40], "checkout mismatch"),
            (["b" * 40, " M scripts/anything.py"], "dirty"),
        ):
            with (
                patch.object(core, "git", side_effect=outputs),
                self.assertRaisesRegex(ValueError, message),
            ):
                core.validate_context(self.candidate, self.root, self.context)

    def test_source_sha_version_and_dirty_tree_rejected(self):
        source = self.root / "source"
        source.mkdir()
        (source / "pyproject.toml").write_text(
            '[project]\nname="lifetxt"\nversion="1.0.4.2"\n'
        )
        with patch.object(core, "git", side_effect=["a" * 40, ""]):
            core.validate_source(self.candidate, source)
        for responses, message in (
            (["b" * 40], "checkout mismatch"),
            (["a" * 40, " M pyproject.toml"], "dirty"),
        ):
            with (
                patch.object(core, "git", side_effect=responses),
                self.assertRaisesRegex(ValueError, message),
            ):
                core.validate_source(self.candidate, source)
        (source / "pyproject.toml").write_text(
            '[project]\nname="lifetxt"\nversion="1.0.4.3"\n'
        )
        with (
            patch.object(core, "git", side_effect=["a" * 40, ""]),
            self.assertRaisesRegex(ValueError, "package/version mismatch"),
        ):
            core.validate_source(self.candidate, source)

    def test_metadata_mismatch_and_missing_archives(self):
        self.archives(version="1.0.4.3")
        with self.assertRaisesRegex(ValueError, "archive package/version"):
            core.validate_evidence(self.candidate, self.payload)
        self.wheel.unlink()
        with self.assertRaisesRegex(ValueError, "one wheel"):
            core.validate_evidence(self.candidate, self.payload)

    def test_provenance_source_run_and_file_hash_rejected(self):
        for key, bad in (
            ("source", {"commit": "b" * 40}),
            ("workflow_run", "101"),
            ("artifacts", []),
        ):
            previous = self.provenance[key]
            self.provenance[key] = bad
            self.save_provenance()
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "provenance"),
            ):
                core.validate_evidence(self.candidate, self.payload)
            self.provenance[key] = previous
        self.save_provenance()
        with self.wheel.open("ab") as stream:
            stream.write(b"changed-but-still-valid-zip")
        with self.assertRaisesRegex(ValueError, "hashes mismatch"):
            core.validate_evidence(self.candidate, self.payload)

    def test_sbom_and_unexpected_payloads_rejected(self):
        (self.payload / "SHA256SUMS").write_text("must stay out of Core payload")
        with self.assertRaisesRegex(ValueError, "inventory"):
            core.validate_evidence(self.candidate, self.payload)
        (self.payload / "SHA256SUMS").unlink()
        (self.payload / "sbom.cdx.json").write_text(
            '{"metadata":{"component":{"name":"lifetxt","version":"1.0.4.3"}}}'
        )
        with self.assertRaisesRegex(ValueError, "SBOM"):
            core.validate_evidence(self.candidate, self.payload)

    def test_report_mismatch_or_tamper_cannot_emit_component(self):
        report = self.report()
        report["run_id"] = 101
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            core.finish(self.candidate, report, self.payload, self.artifact)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            core.finish(
                self.candidate, self.reseal(report), self.payload, self.artifact
            )
        report = self.report()
        report["checks"]["cli"] = "failed"
        with self.assertRaisesRegex(ValueError, "smoke"):
            core.finish(
                self.candidate, self.reseal(report), self.payload, self.artifact
            )
        report = self.report()
        report["files"][0]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "changed since build"):
            core.finish(
                self.candidate, self.reseal(report), self.payload, self.artifact
            )

    def test_report_roles_and_schema_cannot_be_swapped(self):
        report = self.report()
        report["files"][0]["role"] = (
            "wheel" if report["files"][0]["role"] != "wheel" else "sdist"
        )
        with self.assertRaisesRegex(ValueError, "role mismatch"):
            core.finish(
                self.candidate, self.reseal(report), self.payload, self.artifact
            )
        report = self.report()
        report["schema_version"] = 999
        with self.assertRaisesRegex(ValueError, "schema"):
            core.finish(
                self.candidate, self.reseal(report), self.payload, self.artifact
            )

    def test_payload_cannot_change_between_smoke_and_component(self):
        report = self.report()
        path = self.payload / "sbom.cdx.json"
        sbom = proof.load(path)
        sbom["extra"] = "changed after smoke"
        path.write_text(json.dumps(sbom))
        with self.assertRaisesRegex(ValueError, "changed since build"):
            core.finish(self.candidate, report, self.payload, self.artifact)

    def test_clean_install_rejects_source_import_and_strips_pythonpath(self):
        with (
            patch.dict(os.environ, {"PYTHONPATH": str(ROOT), "PYTHONHOME": "/wrong"}),
            patch.object(
                core, "run", side_effect=["", "", str(ROOT / "lifetxt/__init__.py")]
            ) as run,
        ):
            with self.assertRaisesRegex(ValueError, "imported source"):
                core.smoke_archive(
                    self.wheel, ROOT / "examples/minimal_life.txt", "1.0.4.2"
                )
        pip_call = run.call_args_list[1]
        self.assertNotIn("PYTHONPATH", pip_call.args[2])
        self.assertNotIn("PYTHONHOME", pip_call.args[2])
        self.assertNotEqual(pip_call.args[1], ROOT)

    def test_build_failure_produces_no_report_or_upload_permission(self):
        output = self.root / "build-report.json"
        for failure in (
            ValueError("wrong source"),
            subprocess.CalledProcessError(1, ["policy"]),
        ):
            with (
                patch.object(core, "validate_context"),
                patch.object(core, "validate_source"),
                patch.object(core, "run", side_effect=failure),
                self.assertRaises(type(failure)),
            ):
                core.build(
                    self.candidate,
                    self.root,
                    self.root,
                    self.root / "new-payload",
                    output,
                    self.context,
                )
            self.assertFalse(output.exists())

    def test_cli_prepare_refuses_mismatched_run_before_checkout(self):
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(self.candidate))
        output = self.root / "checkout.env"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/release_preflight_core.py"),
                "prepare",
                "--candidate",
                str(candidate_path),
                "--controller",
                str(ROOT),
                "--output",
                str(output),
            ],
            env={**os.environ, **self.context, "GITHUB_RUN_ID": "101"},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn("context mismatch", result.stderr)

    def test_workflow_is_read_only_and_does_not_create_publication_events(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML unavailable")
        workflow = yaml.load(
            (ROOT / ".github/workflows/release-preflight-core.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        for job in workflow["jobs"].values():
            self.assertEqual(job["permissions"], {"contents": "read"})
            self.assertNotIn("environment", job)
            steps = job["steps"]
            for step in steps:
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertEqual(step["with"]["persist-credentials"], "false")
                self.assertNotIn("secrets", json.dumps(step))
            names = [step["name"] for step in steps]
            self.assertLess(
                names.index("Build and verify the exact candidate payload"),
                names.index("Upload immutable non-public Core payload"),
            )
            self.assertLess(
                names.index("Upload immutable non-public Core payload"),
                names.index("Bind upload reference to verified bytes"),
            )


if __name__ == "__main__":
    unittest.main()
