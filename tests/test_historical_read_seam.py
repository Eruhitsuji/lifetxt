"""Tests for the shared historical read seam (#725/#726) and its first two
non-Temporal-Thread consumers: ``show --revision``/``--as-of`` (#729) and
``query --revision`` (#730).

``lifetxt.historical_temporal.read_historical_snapshot`` is a thin wrapper
composing the pre-existing ``historical_snapshot``/``select_revision_as_of``
primitives -- these tests confirm it introduces no second revision/as-of
resolution policy and that both new CLI consumers never fall back to the
current working tree.
"""

import datetime
import os
import subprocess
import tempfile
import unittest

from lifetxt.historical_temporal import read_historical_snapshot
from tests.test_lifetxt import run_cli


TODAY = datetime.date(2026, 9, 9)


class _GitFixture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self.life = os.path.join(self.repo, "life.txt")
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args, env=None):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        if result.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout.strip()

    def _commit(self, content, stamp, message="snapshot"):
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        self._git("add", "life.txt")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        self._git("commit", "--allow-empty", "-m", message, env=env)
        return self._git("rev-parse", "HEAD")


class ReadHistoricalSnapshotTests(_GitFixture):
    def test_requires_exactly_one_of_revision_or_as_of(self):
        revision = self._commit("[ ] T Task id:t1\n", "2026-01-01T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "Exactly one of"):
            read_historical_snapshot([self.life], revision=None, as_of=None)
        with self.assertRaisesRegex(ValueError, "Exactly one of"):
            read_historical_snapshot(
                [self.life], revision=revision, as_of="2026-01-01T00:00:00+00:00"
            )

    def test_ref_without_as_of_is_rejected(self):
        revision = self._commit("[ ] T Task id:t1\n", "2026-01-01T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "only valid together with --as-of"):
            read_historical_snapshot([self.life], revision=revision, ref="main")

    def test_exact_revision_matches_historical_snapshot_directly(self):
        revision = self._commit("[ ] T Task id:t1\n", "2026-01-01T00:00:00+00:00")
        via_seam = read_historical_snapshot([self.life], revision=revision)
        self.assertEqual("git_exact_revision", via_seam["historical"]["mode"])
        self.assertEqual(revision, via_seam["historical"]["resolved_commit"])
        self.assertEqual(1, len(via_seam["items"]))

    def test_as_of_resolves_through_the_shared_committer_time_selector(self):
        first = self._commit("[ ] T Task id:t1\n", "2026-01-01T00:00:00+00:00")
        self._commit("[x] T Task id:t1 done:2026-02-01\n", "2026-02-01T00:00:00+00:00")
        snapshot = read_historical_snapshot(
            [self.life], as_of="2026-01-15T00:00:00+00:00"
        )
        self.assertEqual("git_as_of", snapshot["historical"]["mode"])
        self.assertEqual(first, snapshot["historical"]["selected_commit"])
        self.assertEqual("[ ]", snapshot["items"][0].status)


class HistoricalShowCliTests(_GitFixture):
    def test_show_revision_reads_only_tracked_bytes_at_that_commit(self):
        revision = self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        self._commit(
            "[x] T Buy_milk id:t1 done:2026-02-01\n[ ] T Buy_bread id:t2\n",
            "2026-02-01T00:00:00+00:00",
        )
        stdout, stderr, code = run_cli(
            "show", "t1", "life.txt", "--revision", revision, cwd=self.repo
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("[ ] T Buy_milk", stdout)
        self.assertIn("Historical revision: %s" % revision, stdout)
        self.assertNotIn("done:", stdout)

    def test_show_current_behavior_is_unchanged(self):
        self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli("show", "t1", "life.txt", cwd=self.repo)
        self.assertEqual(0, code, stderr)
        self.assertNotIn("Historical", stdout)

    def test_show_missing_target_at_revision_does_not_fall_back_to_current(self):
        revision = self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        self._commit(
            "[ ] T Buy_milk id:t1\n[ ] T Buy_bread id:t2\n",
            "2026-02-01T00:00:00+00:00",
        )
        stdout, stderr, code = run_cli(
            "show", "t2", "life.txt", "--revision", revision, cwd=self.repo
        )
        self.assertNotEqual(0, code)
        self.assertIn("t2", stderr)

    def test_show_invalid_revision_fails_loudly(self):
        self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli(
            "show", "t1", "life.txt", "--revision", "not-a-revision", cwd=self.repo
        )
        self.assertNotEqual(0, code)
        self.assertIn("Unknown or non-commit Git revision", stderr)

    def test_show_revision_and_as_of_are_mutually_exclusive(self):
        revision = self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli(
            "show",
            "t1",
            "life.txt",
            "--revision",
            revision,
            "--as-of",
            "2026-01-01T00:00:00Z",
            cwd=self.repo,
        )
        self.assertNotEqual(0, code)
        self.assertIn("Exactly one of --revision or --as-of", stderr)

    def test_show_as_of_resolves_the_newest_commit_at_or_before_cutoff(self):
        first = self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        self._commit(
            "[x] T Buy_milk id:t1 done:2026-02-01\n", "2026-02-01T00:00:00+00:00"
        )
        stdout, stderr, code = run_cli(
            "show",
            "t1",
            "life.txt",
            "--as-of",
            "2026-01-15T00:00:00Z",
            cwd=self.repo,
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("[ ] T Buy_milk", stdout)
        self.assertIn(first, stdout)


class HistoricalQueryCliTests(_GitFixture):
    def test_query_revision_evaluates_only_the_historical_snapshot(self):
        revision = self._commit(
            "[ ] T Buy_milk id:t1 tag:groceries\n",
            "2026-01-01T00:00:00+00:00",
        )
        self._commit(
            "[x] T Buy_milk id:t1 tag:groceries done:2026-02-01\n"
            "[ ] T Buy_bread id:t2 tag:groceries\n",
            "2026-02-01T00:00:00+00:00",
        )
        stdout, stderr, code = run_cli(
            "query", "tag:groceries", "life.txt", "--revision", revision, cwd=self.repo
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("Buy_milk", stdout)
        self.assertNotIn("Buy_bread", stdout)
        self.assertIn("Historical revision: %s" % revision, stdout)

    def test_query_revision_json_includes_provenance_envelope(self):
        revision = self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli(
            "query",
            "id:t1",
            "life.txt",
            "--revision",
            revision,
            "--format",
            "json",
            cwd=self.repo,
        )
        self.assertEqual(0, code, stderr)
        import json

        payload = json.loads(stdout)
        self.assertEqual(revision, payload["historical"]["resolved_commit"])
        self.assertEqual(1, len(payload["items"]))

    def test_query_current_behavior_is_unchanged_without_revision(self):
        self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli("query", "id:t1", "life.txt", cwd=self.repo)
        self.assertEqual(0, code, stderr)
        self.assertNotIn("Historical", stdout)

    def test_query_invalid_revision_fails_loudly_without_matching_current_state(self):
        self._commit("[ ] T Buy_milk id:t1\n", "2026-01-01T00:00:00+00:00")
        stdout, stderr, code = run_cli(
            "query", "id:t1", "life.txt", "--revision", "bogus", cwd=self.repo
        )
        self.assertNotEqual(0, code)
        self.assertIn("Unknown or non-commit Git revision", stderr)


if __name__ == "__main__":
    unittest.main()
