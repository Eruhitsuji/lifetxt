import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only where PyYAML is absent
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_winget_manifest.py"
FAKE_SHA256 = "a" * 64
FAKE_URL = (
    "https://github.com/Eruhitsuji/lifetxt/releases/download/"
    "v1.0.0/lifetxt-windows-x86_64.exe"
)


def run_cli(*extra_args, output_dir=None):
    args = [
        sys.executable,
        str(SCRIPT),
        "--version",
        "1.0.0",
        "--installer-url",
        FAKE_URL,
        "--sha256",
        FAKE_SHA256,
    ]
    if output_dir is not None:
        args += ["--output-dir", str(output_dir)]
    args += list(extra_args)
    return subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


class GenerateWingetManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_writes_three_manifests(self):
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        written = [line for line in result.stdout.splitlines() if line]
        self.assertEqual(len(written), 3)
        for path in written:
            self.assertTrue(Path(path).exists())

    def test_manifests_are_valid_yaml_with_expected_shape(self):
        if yaml is None:
            self.skipTest("PyYAML is unavailable, so the manifests cannot be parsed")
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        base = Path(self.tmp.name) / "Eruhitsuji" / "lifetxt" / "1.0.0"

        version_manifest = yaml.safe_load(
            (base / "Eruhitsuji.lifetxt.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(version_manifest["PackageIdentifier"], "Eruhitsuji.lifetxt")
        self.assertEqual(version_manifest["PackageVersion"], "1.0.0")
        self.assertEqual(version_manifest["ManifestType"], "version")

        installer_manifest = yaml.safe_load(
            (base / "Eruhitsuji.lifetxt.installer.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(installer_manifest["InstallerType"], "portable")
        self.assertEqual(len(installer_manifest["Installers"]), 1)
        installer = installer_manifest["Installers"][0]
        self.assertEqual(installer["InstallerUrl"], FAKE_URL)
        self.assertEqual(installer["InstallerSha256"], FAKE_SHA256.upper())

        locale_manifest = yaml.safe_load(
            (base / "Eruhitsuji.lifetxt.locale.en-US.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(locale_manifest["PackageLocale"], "en-US")
        self.assertEqual(locale_manifest["License"], "MIT")

    def test_rejects_a_malformed_sha256(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--version",
                "1.0.0",
                "--installer-url",
                FAKE_URL,
                "--sha256",
                "not-a-hash",
                "--output-dir",
                self.tmp.name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256", result.stderr.lower())

    def test_generation_is_idempotent(self):
        run_cli(output_dir=self.tmp.name)
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
