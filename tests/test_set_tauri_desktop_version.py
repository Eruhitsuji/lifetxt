import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "set_tauri_desktop_version.py"


class SetTauriDesktopVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_path = Path(self.tmp.name) / "tauri.conf.json"
        self.config_path.write_text(
            json.dumps({"productName": "lifetxt Desktop", "version": "0.1.0"}),
            encoding="utf-8",
        )

    def run_cli(self, version):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--version",
                version,
                "--config",
                str(self.config_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_sets_the_version_field(self):
        result = self.run_cli("1.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "1.0.0")

    def test_preserves_other_fields(self):
        result = self.run_cli("1.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["productName"], "lifetxt Desktop")

    def test_accepts_a_prerelease_suffix(self):
        result = self.run_cli("1.0.0rc1")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "1.0.0rc1")

    def test_rejects_a_malformed_version(self):
        result = self.run_cli("not-a-version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("version", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
