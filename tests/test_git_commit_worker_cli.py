import os
import subprocess
import sys
import tempfile
import unittest


class GitCommitWorkerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")
        self.data_path = os.path.join(self.repo, "data.json")
        with open(self.data_path, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        self._git("add", "data.json")
        self._git("commit", "-m", "initial")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout.strip()

    def _run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "lifetxt", "git-commit-worker"] + list(args),
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def test_run_reports_no_op_when_nothing_changed(self):
        result = self._run_cli(
            "run",
            "--repo-root",
            self.repo,
            "--path",
            "data.json",
            "--branch",
            "main",
            "--format",
            "json",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"no_op"', result.stdout)

    def test_run_commits_a_real_change(self):
        with open(self.data_path, "w", encoding="utf-8") as handle:
            handle.write('{"a": 1}\n')
        result = self._run_cli(
            "run",
            "--repo-root",
            self.repo,
            "--path",
            "data.json",
            "--branch",
            "main",
            "--format",
            "json",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"committed"', result.stdout)
        log = self._git("log", "-1", "--pretty=%s")
        self.assertTrue(log.startswith("lifetxt-auto-commit: "))

    def test_run_exits_non_zero_on_refusal(self):
        self._git("checkout", "-b", "other")
        result = self._run_cli(
            "run",
            "--repo-root",
            self.repo,
            "--path",
            "data.json",
            "--branch",
            "main",
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("branch_mismatch", result.stdout)

    def test_help(self):
        result = self._run_cli("--help")
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
