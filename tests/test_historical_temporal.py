import datetime
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.historical_temporal import (
    historical_snapshot,
    historical_temporal_thread,
    historical_temporal_thread_as_of,
    parse_cutoff,
    select_revision_as_of,
)


TODAY = datetime.date(2026, 9, 9)


class GitHistoryCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self.life = os.path.join(self.repo, "life.txt")
        self.extra = os.path.join(self.repo, "extra.life.txt")
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args, env=None, cwd=None):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or self.repo,
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

    def _commit(self, content, stamp, message="snapshot", extra=None):
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if extra is not None:
            with open(self.extra, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(extra)
        self._git("add", "life.txt")
        if extra is not None:
            self._git("add", "extra.life.txt")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        self._git("commit", "--allow-empty", "-m", message, env=env)
        return self._git("rev-parse", "HEAD")


class HistoricalTemporalTests(GitHistoryCase):
    def test_exact_revision_uses_only_tracked_bytes(self):
        revision = self._commit(
            "[ ] E Historical id:target on:2026-01-01\n",
            "2026-01-01T00:00:00+00:00",
        )
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] E Working_tree id:target on:2026-09-09\n")

        result = historical_temporal_thread([self.life], "target", TODAY, revision[:12])

        self.assertEqual("Historical", result["target"]["title"])
        self.assertEqual(revision, result["historical"]["resolved_commit"])
        self.assertEqual("git_exact_revision", result["historical"]["mode"])
        self.assertTrue(result["historical"]["evidence_complete"])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        from lifetxt.schema_extensions_v27 import temporal_thread_v1_historical_schema

        self.assertEqual(
            [],
            list(
                Draft202012Validator(
                    temporal_thread_v1_historical_schema()
                ).iter_errors(result)
            ),
        )

    def test_missing_secondary_path_is_explicitly_partial(self):
        revision = self._commit(
            "[ ] E Historical id:target\n",
            "2026-01-01T00:00:00+00:00",
        )
        snapshot = historical_snapshot([self.life, self.extra], revision)
        self.assertEqual(["life.txt"], snapshot["historical"]["loaded_paths"])
        self.assertEqual(["extra.life.txt"], snapshot["historical"]["missing_paths"])
        self.assertFalse(snapshot["historical"]["evidence_complete"])

    def test_invalid_revision_and_missing_target_do_not_fallback(self):
        revision = self._commit(
            "[ ] E Historical id:other\n",
            "2026-01-01T00:00:00+00:00",
        )
        with self.assertRaisesRegex(ValueError, "Unknown or non-commit"):
            historical_snapshot([self.life], "does-not-exist")
        with self.assertRaisesRegex(ValueError, "No item with id"):
            historical_temporal_thread([self.life], "target", TODAY, revision)
        with self.assertRaisesRegex(ValueError, "None of the requested"):
            historical_snapshot([self.extra], revision)

    def test_non_git_and_option_like_refs_fail_loudly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] E Item id:item\n")
            with self.assertRaisesRegex(ValueError, "not inside a Git repository"):
                historical_snapshot([path], "HEAD")
        self._commit(
            "[ ] E First id:target\n",
            "2026-01-01T00:00:00+00:00",
        )
        with self.assertRaisesRegex(ValueError, "must not begin"):
            select_revision_as_of([self.life], "2026-01-02T00:00:00Z", ref="--all")

    def test_as_of_uses_committer_time_and_offset_equivalent_cutoffs(self):
        first = self._commit(
            "[ ] E First id:target\n",
            "2026-01-01T00:00:00+00:00",
            "first",
        )
        self._commit(
            "[ ] E Second id:target\n",
            "2026-01-02T00:00:00+00:00",
            "second",
        )
        utc = select_revision_as_of([self.life], "2026-01-01T00:00:00Z", ref="main")
        offset = select_revision_as_of(
            [self.life], "2026-01-01T09:00:00+09:00", ref="main"
        )
        self.assertEqual(first, utc["selected_commit"])
        self.assertEqual(first, offset["selected_commit"])
        self.assertEqual("committer", utc["time_policy"])
        self.assertEqual(self._git("rev-parse", "main"), utc["selection_root"])
        result = historical_temporal_thread_as_of(
            [self.life],
            "target",
            TODAY,
            "2026-01-01T09:00:00+09:00",
            ref="main",
        )
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        from lifetxt.schema_extensions_v27 import temporal_thread_v1_historical_schema

        self.assertEqual(
            [],
            list(
                Draft202012Validator(
                    temporal_thread_v1_historical_schema()
                ).iter_errors(result)
            ),
        )

    def test_as_of_has_no_oldest_or_working_tree_fallback(self):
        self._commit(
            "[ ] E First id:target\n",
            "2026-01-02T00:00:00+00:00",
        )
        with self.assertRaisesRegex(ValueError, "No commit"):
            select_revision_as_of([self.life], "2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "offset-aware"):
            parse_cutoff("2026-01-01")
        with self.assertRaisesRegex(ValueError, "Unknown or non-commit"):
            select_revision_as_of([self.life], "2026-01-03T00:00:00Z", ref="missing")

    def test_same_timestamp_tie_break_is_full_sha(self):
        stamp = "2026-01-01T00:00:00+00:00"
        first = self._commit("[ ] E First id:target\n", stamp, "first")
        second = self._commit("[ ] E Second id:target\n", stamp, "second")
        selection = select_revision_as_of([self.life], "2026-01-01T00:00:00Z")
        self.assertEqual(max(first, second), selection["selected_commit"])
        self.assertEqual("maximum_full_sha", selection["tie_break"])

    def test_shallow_history_is_not_claimed_complete(self):
        self._commit(
            "[ ] E First id:target\n",
            "2026-01-01T00:00:00+00:00",
        )
        self._commit(
            "[ ] E Second id:target\n",
            "2026-01-02T00:00:00+00:00",
        )
        clone_root = tempfile.mkdtemp(dir=self.repo)
        clone = os.path.join(clone_root, "shallow")
        self._git(
            "clone",
            "--depth",
            "1",
            Path(self.repo).as_uri(),
            clone,
            cwd=self.repo,
        )
        clone_life = os.path.join(clone, "life.txt")
        selection = select_revision_as_of([clone_life], "2026-01-03T00:00:00Z")
        self.assertFalse(selection["history_complete"])
        self.assertIn("shallow_or_unverifiable_history", selection["limitations"])


if __name__ == "__main__":
    unittest.main()
