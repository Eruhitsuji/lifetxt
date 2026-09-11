import os
import subprocess
import tempfile
import unittest
from unittest import mock

import lifetxt.git_commit_worker as git_commit_worker
from lifetxt.git_commit_worker import GitCommitWorkerError, run_commit


class GitCommitWorkerCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")
        self.data_path = os.path.join(self.repo, "generated", "data.json")
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        self._git("add", "generated/data.json")
        self._git("commit", "-m", "initial")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args, cwd=None):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout.strip()

    def _write_data(self, text):
        with open(self.data_path, "w", encoding="utf-8") as handle:
            handle.write(text)


class NoOpAndCommitTests(GitCommitWorkerCase):
    def test_no_op_success_when_allowlist_unchanged(self):
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("no_op", result["status"])

    def test_allowed_path_change_is_committed(self):
        self._write_data('{"a": 1}\n')
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("committed", result["status"])
        self.assertTrue(result["commit"])
        self.assertTrue(result["message"].startswith("lifetxt-auto-commit: "))
        log = self._git("log", "-1", "--pretty=%s")
        self.assertEqual(result["message"], log)
        # Working tree change is now committed; a second run is a no-op.
        second = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("no_op", second["status"])

    def test_unrelated_unstaged_changes_are_ignored(self):
        outside = os.path.join(self.repo, "unrelated.txt")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("not in the allowlist\n")
        self._git("add", "unrelated.txt")
        self._git("commit", "-m", "add unrelated tracked file")
        with open(outside, "a", encoding="utf-8") as handle:
            handle.write("modified outside the allowlist\n")
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("no_op", result["status"])
        # The unrelated file's modification must remain untouched/unstaged.
        status = self._git("status", "--porcelain")
        self.assertIn("unrelated.txt", status)
        cached = self._git("diff", "--cached", "--name-only")
        self.assertNotIn("unrelated.txt", cached)


class RefusalTests(GitCommitWorkerCase):
    def test_unrelated_pre_existing_staged_changes_refused(self):
        outside = os.path.join(self.repo, "unrelated.txt")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("staged by someone else\n")
        self._git("add", "unrelated.txt")
        self._write_data('{"a": 1}\n')
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("refused", result["status"])
        self.assertEqual("unrelated_staged_changes", result["reason"])
        cached = self._git("diff", "--cached", "--name-only")
        self.assertEqual(["unrelated.txt"], cached.splitlines())
        self.assertNotIn(
            "generated/data.json", cached, "the allowlist path must not be staged"
        )

    def test_detached_head_refused(self):
        sha = self._git("rev-parse", "HEAD")
        self._git("checkout", sha)
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("refused", result["status"])
        self.assertEqual("detached_head", result["reason"])

    def test_branch_mismatch_refused(self):
        self._git("checkout", "-b", "other")
        result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("refused", result["status"])
        self.assertEqual("branch_mismatch", result["reason"])

    def test_missing_git_identity_refused(self):
        # A host with a real global user.name/user.email (common on
        # developer machines) makes the local repo's own identity
        # unreliable to isolate via environment variables alone; the
        # deterministic unit is _identity_configured() itself, mocked here
        # so this test does not depend on the host's ambient Git config.
        with mock.patch.object(
            git_commit_worker, "_identity_configured", return_value=False
        ):
            result = run_commit(self.repo, ["generated/data.json"], "main")
        self.assertEqual("refused", result["status"])
        self.assertEqual("missing_git_identity", result["reason"])

    def test_identity_check_reads_this_repositorys_own_config(self):
        # Confirms _identity_configured() is real, not a stub: a repo with
        # local identity actually configured (setUp already did this)
        # reports True.
        self.assertTrue(git_commit_worker._identity_configured(self.repo))

    def test_not_a_git_repository_raises(self):
        with tempfile.TemporaryDirectory() as plain_dir:
            with self.assertRaises(GitCommitWorkerError) as ctx:
                run_commit(plain_dir, ["data.json"], "main")
            self.assertEqual("not_a_git_repository", ctx.exception.reason)

    def test_no_allowlisted_paths_raises(self):
        with self.assertRaises(GitCommitWorkerError) as ctx:
            run_commit(self.repo, [], "main")
        self.assertEqual("no_paths_configured", ctx.exception.reason)

    def test_path_escaping_repository_raises(self):
        with self.assertRaises(GitCommitWorkerError) as ctx:
            run_commit(self.repo, [os.path.join("..", "outside.txt")], "main")
        self.assertEqual("path_escapes_repository", ctx.exception.reason)


class ConcurrencyLockTests(GitCommitWorkerCase):
    def test_concurrent_run_is_refused_while_lock_is_held(self):
        lock_path = os.path.join(self.temp_dir.name, "worker.lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with self.assertRaises(GitCommitWorkerError) as ctx:
                run_commit(
                    self.repo, ["generated/data.json"], "main", lock_path=lock_path
                )
            self.assertEqual("lock_held", ctx.exception.reason)
        finally:
            os.close(fd)
            os.remove(lock_path)

    def test_lock_is_released_after_a_successful_run(self):
        lock_path = os.path.join(self.temp_dir.name, "worker.lock")
        run_commit(self.repo, ["generated/data.json"], "main", lock_path=lock_path)
        self.assertFalse(os.path.exists(lock_path))
        # A second run can acquire the same lock file without error.
        result = run_commit(
            self.repo, ["generated/data.json"], "main", lock_path=lock_path
        )
        self.assertEqual("no_op", result["status"])


if __name__ == "__main__":
    unittest.main()
