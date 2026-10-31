"""Git checkout identity is bounded, read-only, and safely optional."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lifetxt import __version__
from lifetxt.web_build_info import (
    git_head_for_checkout,
    snapshot_runtime_build_info,
)


class RuntimeBuildInfoTests(unittest.TestCase):
    def test_not_a_checkout_does_not_invoke_git(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("lifetxt.web_build_info.subprocess.run") as command:
                self.assertIsNone(git_head_for_checkout(Path(directory)))
            command.assert_not_called()

    def test_checkout_head_is_exact_and_git_uses_no_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            head = "a" * 40
            result = SimpleNamespace(stdout=head + "\n", returncode=0)
            with patch("lifetxt.web_build_info.subprocess.run", return_value=result) as command:
                self.assertEqual(head, git_head_for_checkout(root))
            args, kwargs = command.call_args
            self.assertEqual(["git", "rev-parse", "--verify", "HEAD"], args[0])
            self.assertEqual(str(root), kwargs["cwd"])
            self.assertFalse(kwargs["check"])
            self.assertEqual(2, kwargs["timeout"])
            self.assertNotIn("shell", kwargs)

    def test_git_failure_or_invalid_output_has_no_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            results = [
                SimpleNamespace(stdout="", returncode=1),
                SimpleNamespace(stdout="not-a-hash", returncode=0),
                SimpleNamespace(stdout="b" * 39, returncode=0),
                SimpleNamespace(stdout="c" * 40 + "\nsecret", returncode=0),
            ]
            for result in results:
                with self.subTest(result=result.stdout):
                    with patch("lifetxt.web_build_info.subprocess.run", return_value=result):
                        self.assertIsNone(git_head_for_checkout(root))
            for error in [OSError("git not found"), subprocess.TimeoutExpired("git", 2)]:
                with self.subTest(error=type(error).__name__):
                    with patch("lifetxt.web_build_info.subprocess.run", side_effect=error):
                        self.assertIsNone(git_head_for_checkout(root))

    def test_snapshot_uses_package_version_and_only_public_keys(self):
        with patch("lifetxt.web_build_info.git_head_for_checkout", return_value=None) as head:
            snapshot = snapshot_runtime_build_info()
        self.assertEqual({"version": __version__, "git_commit": None}, snapshot)
        source_root = head.call_args.args[0]
        self.assertEqual(Path(__file__).resolve().parent.parent, source_root)


if __name__ == "__main__":
    unittest.main()
