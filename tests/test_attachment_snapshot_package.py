import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_attachment_snapshot_helper import (
    build_helper,
    NAME,
    MANIFEST,
    SOURCE,
)


class SnapshotPackageTests(unittest.TestCase):
    def test_unsupported_build_does_not_run_compiler(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run") as run,
        ):
            with self.assertRaises(RuntimeError):
                build_helper(Path("unused") / NAME)
            run.assert_not_called()

    def test_explicit_build_manifest_and_rebuild(self):
        if platform.system() != "Linux" or not shutil.which("cc"):
            self.skipTest("Linux build-time compiler unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / NAME
            first = build_helper(output)
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(), first["helper_sha256"]
            )
            self.assertEqual(
                hashlib.sha256(SOURCE.read_bytes()).hexdigest(), first["source_sha256"]
            )
            self.assertEqual(first, json.loads((output.parent / MANIFEST).read_text()))
            self.assertTrue(output.stat().st_mode & 0o100)
            self.assertEqual(first, build_helper(output))

    def test_only_fixed_name_installed(self):
        if platform.system() != "Linux" or not shutil.which("cc"):
            self.skipTest("Linux build-time compiler unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                build_helper(Path(temporary) / "other-name")
