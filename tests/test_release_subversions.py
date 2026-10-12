import importlib.util
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lifetxt.versioning import canonical_release, release_parts, semver_metadata

ROOT = Path(__file__).resolve().parents[1]


class ReleaseSubversionTests(unittest.TestCase):
    def test_zero_alias_and_numeric_order(self):
        self.assertEqual(release_parts("1.0.4"), release_parts("1.0.4.0"))
        self.assertEqual(canonical_release("1.0.4.0"), "1.0.4")
        versions = ["1.0.4", "1.0.4.1", "1.0.4.2", "1.0.4.10", "1.0.5"]
        values = [release_parts(version) for version in versions]
        self.assertEqual(values, sorted(set(values)))

    def test_semver_is_metadata_encoding(self):
        self.assertEqual(semver_metadata("1.0.4"), "1.0.4")
        self.assertEqual(semver_metadata("1.0.4.0"), "1.0.4")
        self.assertEqual(semver_metadata("1.0.4.1"), "1.0.4+1")
        self.assertEqual(semver_metadata("1.0.5"), "1.0.5")

    def test_invalid_releases_are_rejected(self):
        for value in (
            "1.2",
            "1.2.3.4.5",
            "1.2.3.",
            "1.2.3.-1",
            "01.2.3",
            "1.2.3+1",
            "1.2.3\n",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release_parts(value)

    def run_script(self, name, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / name), *args],
            capture_output=True,
            text=True,
        )

    def fixture(self, root, version, cargo=None):
        (root / "pyproject.toml").write_text('[project]\nversion = "%s"\n' % version)
        mini = root / "lifetxt-mini"
        mini.mkdir(exist_ok=True)
        cargo = cargo or semver_metadata(version)
        (mini / "Cargo.toml").write_text(
            '[package]\nname = "lifetxt-mini"\nversion = "%s"\n' % cargo
        )
        (mini / "Cargo.lock").write_text(
            'version = 4\n[[package]]\nname = "lifetxt-mini"\nversion = "%s"\n' % cargo
        )

    def test_tag_aliases_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, "1.0.4")
            for tag, code in (("v1.0.4", 0), ("v1.0.4.0", 0), ("v1.0.4.1", 1)):
                result = self.run_script(
                    "check_release_tag_version.py", tag, "--root", tmp
                )
                self.assertEqual(result.returncode, code, result.stderr)
            self.fixture(root, "1.0.4.1")
            result = self.run_script(
                "check_release_tag_version.py", "v1.0.4.1", "--root", tmp
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_mini_metadata_and_binary_full_version(self):
        spec = importlib.util.spec_from_file_location(
            "mini_version", ROOT / "scripts/check_lifetxt_mini_version.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, "1.0.4.1")
            args = ["check", "--root", tmp, "--tag", "v1.0.4.1", "--binary", "dummy"]
            with (
                mock.patch.object(sys, "argv", args),
                mock.patch.object(
                    module.subprocess,
                    "check_output",
                    return_value="lifetxt-mini 1.0.4.1\n",
                ),
            ):
                self.assertEqual(module.main(), 0)
            for output in (
                "lifetxt-mini 1.0.4",
                "lifetxt-mini 1.0.4.1.2",
                "lifetxt-mini 1.0.4.1 extra",
            ):
                with (
                    mock.patch.object(sys, "argv", args),
                    mock.patch.object(
                        module.subprocess, "check_output", return_value=output
                    ),
                    self.assertRaises(SystemExit),
                ):
                    module.main()
            self.fixture(root, "1.0.4.1", cargo="1.0.4")
            result = self.run_script("check_lifetxt_mini_version.py", "--root", tmp)
            self.assertNotEqual(result.returncode, 0)

    def test_desktop_transport_and_apple_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "tauri.conf.json"
            config.write_text(
                json.dumps({"version": "0.1.0", "productName": "lifetxt"})
            )
            for version, expected in (("1.0.4.1", "1.0.4+1"), ("1.0.5", "1.0.5")):
                result = self.run_script(
                    "set_tauri_desktop_version.py",
                    "--config",
                    str(config),
                    "--version",
                    version,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(config.read_text())
                self.assertEqual(data["version"], expected)
                with (config.parent / data["bundle"]["macOS"]["infoPlist"]).open(
                    "rb"
                ) as handle:
                    metadata = plistlib.load(handle)
                self.assertEqual(metadata["LifetxtReleaseVersion"], version)
                self.assertEqual(
                    metadata["CFBundleShortVersionString"],
                    version.rsplit(".", 1)[0] if version.count(".") == 3 else version,
                )
            result = self.run_script(
                "set_tauri_desktop_version.py",
                "--config",
                str(config),
                "--version",
                "1.0.5.65536",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(config.read_text())["version"], "1.0.5")

    def test_docker_aliases_retain_subversion(self):
        for tag, expected in (
            ("v1.0.4.1", "1.0.4.1"),
            ("v1.0.4.0", "1.0.4"),
            ("v1.0.5", "1.0.5"),
        ):
            result = self.run_script("release_version_metadata.py", tag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("version=" + expected + "\n", result.stdout)
            self.assertIn("minor=1.0\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
