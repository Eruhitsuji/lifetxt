import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_scoop_manifest.py"
FAKE_SHA256 = "b" * 64
FAKE_URL = (
    "https://github.com/Eruhitsuji/lifetxt/releases/download/"
    "v1.0.0/lifetxt-windows-x86_64.exe"
)


def run_cli(sha256=FAKE_SHA256, output=None):
    args = [
        sys.executable,
        str(SCRIPT),
        "--version",
        "1.0.0",
        "--installer-url",
        FAKE_URL,
        "--sha256",
        sha256,
    ]
    if output is not None:
        args += ["--output", str(output)]
    return subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


class GenerateScoopManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_path = Path(self.tmp.name) / "lifetxt.json"

    def test_writes_valid_json_with_expected_shape(self):
        result = run_cli(output=self.output_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.0.0")
        self.assertEqual(manifest["url"], FAKE_URL)
        self.assertEqual(manifest["hash"], "sha256:" + FAKE_SHA256)
        self.assertEqual(manifest["license"], "MIT")

    def test_bin_renames_the_platform_qualified_artifact_to_lifetxt_exe(self):
        result = run_cli(output=self.output_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["bin"], [["lifetxt-windows-x86_64.exe", "lifetxt.exe"]]
        )

    def test_rejects_a_malformed_sha256(self):
        result = run_cli(sha256="not-a-hash", output=self.output_path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256", result.stderr.lower())
        self.assertFalse(self.output_path.exists())

    def test_autoupdate_url_uses_the_scoop_dollar_version_placeholder(self):
        result = run_cli(output=self.output_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertIn("$version", manifest["autoupdate"]["url"])


if __name__ == "__main__":
    unittest.main()
