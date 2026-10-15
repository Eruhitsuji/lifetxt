"""Desktop generated-checkout, bundle mapping and fail-closed evidence tests."""

import copy
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_desktop as desktop  # noqa: E402
import release_preflight_proof as proof  # noqa: E402
import set_tauri_desktop_version as setter  # noqa: E402


class DesktopPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "generated"
        self.target = "desktop-linux-x86_64"
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 102, 1
        )
        config = self.work / desktop.CONFIG
        config.parent.mkdir(parents=True)
        config.write_bytes((ROOT / desktop.CONFIG).read_bytes())
        setter.set_version(config, "1.0.4.2")
        self.runtime = desktop.runtime_path(self.work, self.target)
        self.runtime.parent.mkdir(parents=True)
        self.runtime.write_bytes(b"fixture bundled Core")
        (self.runtime.parent / ".gitkeep").write_bytes(b"")
        self.bundle = self.work / "desktop/src-tauri/target/release/bundle/deb"
        self.bundle.mkdir(parents=True)
        self.installer = self.bundle / "lifetxt Desktop_1.0.4+2_amd64.deb"
        self.installer.write_bytes(b"!<arch>\nfixture-deb")
        self.payload = self.root / "payload"
        self.installers = desktop.collect(self.work, self.payload, self.target)
        with patch.object(desktop.core, "git", side_effect=["a" * 40, desktop.CONFIG]):
            self.metadata = desktop.validate_work(
                self.candidate, self.work, self.target
            )
        self.stage = {
            "schema_version": 1,
            "candidate_digest": self.candidate["digest"],
            **{
                key: self.candidate[key]
                for key in ("source_sha", "controller_sha", "run_id", "run_attempt")
            },
            "target": self.target,
            "metadata": self.metadata,
            "runtime_sha256": proof.file_digest(self.runtime),
            "runtime_checks": dict.fromkeys(proof.CONTRACTS["standalone"][1], "passed"),
            "toolchain": {"python": "fixture", "pyinstaller": "fixture"},
        }
        self.artifact = {
            "id": 30,
            "name": "fixture-desktop-payload",
            "sha256": "e" * 64,
        }

    def report(self):
        return proof.sealed(
            {
                **copy.deepcopy(self.stage),
                "checks": dict.fromkeys(proof.CONTRACTS["desktop"][1], "passed"),
                "installers": self.installers,
                "files": [
                    {
                        "path": path.name,
                        "role": "bundled-core"
                        if path.name == "bundled-core"
                        else "installer",
                        "sha256": proof.file_digest(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in sorted(self.payload.iterdir())
                ],
                "not_verified": list(desktop.NOT_VERIFIED),
            }
        )

    def reseal(self, value):
        return proof.sealed(
            {key: item for key, item in value.items() if key != "digest"}
        )

    def finish(self, report):
        return desktop.finish(
            self.candidate, report, self.payload, self.artifact, self.target
        )

    def test_public_name_preserved_via_safe_payload_alias(self):
        self.assertEqual(
            self.installers,
            [
                {
                    "path": "installer-001.deb",
                    "public_name": self.installer.name,
                    "format": ".deb",
                }
            ],
        )
        self.assertEqual(
            (self.payload / "installer-001.deb").read_bytes(),
            self.installer.read_bytes(),
        )
        component = self.finish(self.report())
        proof.validate_component(self.candidate, component, self.payload)
        self.assertEqual(
            {row["role"] for row in component["files"]}, {"bundled-core", "installer"}
        )

    def test_three_targets_use_existing_native_validation(self):
        self.assertEqual(
            set(desktop.TARGETS),
            {target for target in proof.TARGETS if target.startswith("desktop-")},
        )
        for target, (native, _) in desktop.TARGETS.items():
            with patch.object(desktop.standalone, "validate_host") as validate:
                desktop.validate_target(target)
            validate.assert_called_once_with(native)

    def test_generated_checkout_only_changes_version_config(self):
        with patch.object(desktop.core, "git", side_effect=["a" * 40, desktop.CONFIG]):
            metadata = desktop.validate_work(self.candidate, self.work, self.target)
        self.assertEqual(metadata["release_version"], "1.0.4.2")
        self.assertEqual(metadata["mapped_version"], "1.0.4+2")
        for sha, diff in (("c" * 40, ""), ("a" * 40, "desktop/src-tauri/Cargo.lock")):
            with (
                patch.object(desktop.core, "git", side_effect=[sha, diff]),
                self.assertRaises(ValueError),
            ):
                desktop.validate_work(self.candidate, self.work, self.target)

    def test_config_version_resources_and_apple_identity_checked(self):
        path = self.work / desktop.CONFIG
        original = proof.load(path)
        for key, value in (("version", "1.0.4+3"), ("bundle", {"resources": {}})):
            data = copy.deepcopy(original)
            data[key] = value
            path.write_text(json.dumps(data))
            with (
                patch.object(
                    desktop.core, "git", side_effect=["a" * 40, desktop.CONFIG]
                ),
                self.assertRaises(ValueError),
            ):
                desktop.validate_work(self.candidate, self.work, self.target)
        path.write_text(json.dumps(original))
        (path.parent / ".release-version.plist").write_bytes(b"bad plist")
        with (
            patch.object(desktop.core, "git", side_effect=["a" * 40, desktop.CONFIG]),
            self.assertRaises(plistlib.InvalidFileException),
        ):
            desktop.validate_work(self.candidate, self.work, self.target)

    def test_installer_magic_per_native_format(self):
        examples = [
            ("desktop-windows-x86_64", ".msi", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
            ("desktop-windows-x86_64", ".exe", b"MZfixture"),
            (self.target, ".AppImage", b"\x7fELFfixture"),
            (self.target, ".rpm", b"\xed\xab\xee\xdbfixture"),
            ("desktop-macos-arm64", ".dmg", b"koly" + b"\0" * 508),
            ("desktop-macos-arm64", ".app.tar.gz", b"\x1f\x8bfixture"),
        ]
        for target, suffix, content in examples:
            path = self.root / ("native" + suffix)
            path.write_bytes(content)
            self.assertEqual(desktop.installer_format(path, target), suffix)
            path.write_bytes(b"bad")
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                desktop.installer_format(path, target)

    def test_duplicate_public_names_and_missing_installers_rejected(self):
        other = self.bundle.parent / "duplicate"
        other.mkdir()
        (other / self.installer.name).write_bytes(self.installer.read_bytes())
        with self.assertRaisesRegex(ValueError, "duplicate public"):
            desktop.collect(self.work, self.root / "duplicate-payload", self.target)
        self.installer.unlink()
        (other / self.installer.name).unlink()
        with self.assertRaisesRegex(ValueError, "no Desktop installer"):
            desktop.collect(self.work, self.root / "missing-payload", self.target)

    def test_unsafe_public_names_and_mapping_collisions_rejected(self):
        for name in ("../bad.deb", "a/b.deb", "a\\b.deb", "x\nb.deb", "trailing."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                desktop.public_name(name)
        report = self.report()
        report["installers"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate installer"):
            self.finish(self.reseal(report))

    def test_runtime_checksum_and_post_bundle_installer_tamper_rejected(self):
        report = self.report()
        (self.payload / "bundled-core").write_bytes(b"different Core")
        with self.assertRaisesRegex(ValueError, "Core changed"):
            self.finish(report)
        (self.payload / "bundled-core").write_bytes(self.runtime.read_bytes())
        with (self.payload / "installer-001.deb").open("ab") as stream:
            stream.write(b"different installer bytes")
        with self.assertRaisesRegex(ValueError, "changed since bundle"):
            self.finish(report)

    def test_report_identity_target_role_and_schema_rejected(self):
        for key, value in (
            ("run_id", 103),
            ("target", "desktop-macos-arm64"),
            ("schema_version", True),
        ):
            report = self.report()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.finish(self.reseal(report))
        report = self.report()
        report["files"][0]["role"] = "installer"
        with self.assertRaisesRegex(ValueError, "role mismatch"):
            self.finish(self.reseal(report))

    def test_smoke_bundle_failure_and_manual_state_not_hidden(self):
        for field in ("checks", "runtime_checks"):
            report = self.report()
            report[field][next(iter(report[field]))] = "failed"
            with self.assertRaises(ValueError):
                self.finish(self.reseal(report))
        report = self.report()
        report["not_verified"] = []
        with self.assertRaisesRegex(ValueError, "manual verification"):
            self.finish(self.reseal(report))

    def test_successful_fixture_bundle_binds_full_report_and_component(self):
        payload = self.root / "fixture-native-payload"
        output = self.root / "fixture-native-report.json"
        with (
            patch.object(desktop.core, "validate_context"),
            patch.object(desktop.core, "validate_source"),
            patch.object(desktop, "validate_target"),
            patch.object(desktop, "validate_work", return_value=self.metadata),
            patch.object(desktop.subprocess, "run"),
            patch.object(desktop.core, "run", return_value="fixture-tool-version"),
        ):
            result = desktop.bundle(
                self.candidate,
                proof.sealed(self.stage),
                ROOT,
                ROOT,
                self.work,
                payload,
                output,
                self.target,
                {},
            )
        self.assertEqual(proof.load(output), result)
        component = desktop.finish(
            self.candidate, result, payload, self.artifact, self.target
        )
        proof.validate_component(self.candidate, component, payload)
        self.assertEqual(result["installers"][0]["public_name"], self.installer.name)
        self.assertEqual(result["not_verified"], desktop.NOT_VERIFIED)

    def test_cargo_failure_emits_no_success_report(self):
        output = self.root / "never-created.json"
        with (
            patch.object(desktop.core, "validate_context"),
            patch.object(desktop.core, "validate_source"),
            patch.object(desktop, "validate_target"),
            patch.object(desktop, "validate_work", return_value=self.metadata),
            patch.object(
                desktop.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["cargo"]),
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            desktop.bundle(
                self.candidate,
                proof.sealed(self.stage),
                ROOT,
                ROOT,
                self.work,
                self.root / "new-payload",
                output,
                self.target,
                {},
            )
        self.assertFalse(output.exists())

    def test_workflow_uses_read_only_three_target_matrix(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML unavailable")
        workflow = yaml.load(
            (ROOT / ".github/workflows/release-preflight-desktop.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["desktop"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertNotIn("environment", job)
        self.assertEqual(
            {row["target"] for row in job["strategy"]["matrix"]["include"]},
            set(desktop.TARGETS),
        )
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                self.assertEqual(step["with"]["persist-credentials"], "false")
        self.assertIn("public-name mapping", job["steps"][-1]["name"])


if __name__ == "__main__":
    unittest.main()
