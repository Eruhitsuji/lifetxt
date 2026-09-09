"""CLI wiring tests for `lifetxt temporal` (#481/#485)."""

import json
import os
import subprocess
import tempfile
import unittest

from tests.test_lifetxt import run_cli


SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] T Ship_report due:2000-01-01 id:t1\n"
    "[ ] T Review_draft due:2000-01-02 id:t2\n"
)

THREAD_SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] E Plan id:plan on:2000-01-01\n"
    "[x] E Actual id:actual on:1999-12-31 realizes:plan\n"
    "[ ] E Next id:next on:2000-02-01 follows:actual\n"
    "[ ] E Previous id:previous on:2000-01-02\n"
    "[ ] E Conflict id:conflict on:2000-01-01 follows:previous\n"
)


class TemporalCliTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=SAMPLE):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_temporal_text_output_shows_facts_and_related_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "t1", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Temporal context for t1", stdout)
            self.assertIn("overdue_by", stdout)
            self.assertIn("t2", stdout)
            self.assertIn("Review_draft", stdout)

    def test_temporal_json_output_matches_the_canonical_schema_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "t1", src, "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("temporal-context-v1", data["schema"])
            self.assertEqual("t1", data["target_id"])
            self.assertEqual(["t2"], [edge["target_id"] for edge in data["related"]])

    def test_temporal_unknown_id_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "nope", src)
            self.assertNotEqual(0, code)
            self.assertIn("No item with id", stderr)

    def test_temporal_window_and_limit_flags_are_honoured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "temporal", "t1", src, "--window", "0", "--json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            # t2 is one day away; a zero-day window excludes it.
            self.assertEqual([], data["related"])

    def test_thread_json_exposes_the_shared_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("thread", "actual", src, "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("temporal-thread-v1", data["schema"])
            self.assertEqual(
                ["plan"], [r["id"] for r in data["relations"]["realized_plans"]]
            )
            self.assertEqual(
                ["next"], [r["id"] for r in data["relations"]["successors"]]
            )

    def test_thread_human_output_names_lifecycle_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("thread", "actual", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Temporal thread for actual", stdout)
            self.assertIn("Realized plans", stdout)
            self.assertIn("Successors", stdout)

    def test_thread_text_and_json_share_consistency_warnings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("thread", "conflict", src, "--json")
            self.assertEqual(0, code, stderr)
            warning = json.loads(stdout)["consistency"]["warnings"][0]
            self.assertEqual("follows", warning["relation"])

            stdout, stderr, code = run_cli("thread", "conflict", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Consistency warnings", stdout)
            self.assertIn(warning["source_id"], stdout)
            self.assertIn(warning["target_id"], stdout)

    def test_check_reports_the_shared_consistency_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("check", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("WARNING W244", stdout)
            self.assertIn("conflict", stdout)
            self.assertIn("previous", stdout)

    def _git(self, repo, *args, env=None):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def _historical_repo(self, temp_dir):
        self._git(temp_dir, "init", "-b", "main")
        self._git(temp_dir, "config", "user.name", "Test User")
        self._git(temp_dir, "config", "user.email", "test@example.invalid")
        src = self._write_source(
            temp_dir,
            "[ ] E Old id:old on:2026-09-10\n"
            "[ ] E Target id:target on:2026-09-01 follows:old\n",
        )
        self._git(temp_dir, "add", "life.txt")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = "2026-01-01T00:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = "2026-01-01T00:00:00+00:00"
        self._git(temp_dir, "commit", "-m", "before", env=env)
        before = self._git(temp_dir, "rev-parse", "HEAD")
        self._write_source(
            temp_dir,
            "[ ] E Target id:target on:2026-09-11\n"
            "[ ] E Next id:next on:2026-09-12 follows:target\n",
        )
        self._git(temp_dir, "add", "life.txt")
        env["GIT_AUTHOR_DATE"] = "2026-01-02T00:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = "2026-01-02T00:00:00+00:00"
        self._git(temp_dir, "commit", "-m", "after", env=env)
        after = self._git(temp_dir, "rev-parse", "HEAD")
        return src, before, after

    def test_thread_exact_revision_text_and_json_use_historical_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src, before, _after = self._historical_repo(temp_dir)
            stdout, stderr, code = run_cli(
                "thread", "target", src, "--revision", before[:12], "--json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(before, data["historical"]["resolved_commit"])
            self.assertEqual("Old", data["explicit"]["nodes"][1]["title"])

            stdout, stderr, code = run_cli(
                "thread", "target", src, "--revision", before[:12]
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Historical revision", stdout)
            self.assertIn("git-exact-revision", stdout)

    def test_thread_semantic_diff_text_and_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src, before, after = self._historical_repo(temp_dir)
            spec = "%s..%s" % (before, after)
            stdout, stderr, code = run_cli(
                "thread", "target", src, "--diff", spec, "--json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("temporal-diff-v1", data["schema"])
            self.assertEqual(["next"], [item["id"] for item in data["items"]["added"]])
            self.assertEqual(1, len(data["consistency"]["resolved_warnings"]))

            stdout, stderr, code = run_cli("thread", "target", src, "--diff", spec)
            self.assertEqual(0, code, stderr)
            self.assertIn("Temporal diff for target", stdout)
            self.assertIn("Relations added", stdout)

    def test_thread_as_of_reuses_selected_exact_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src, before, _after = self._historical_repo(temp_dir)
            stdout, stderr, code = run_cli(
                "thread",
                "target",
                src,
                "--as-of",
                "2026-01-01T09:00:00+09:00",
                "--ref",
                "main",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("git_as_of", data["historical"]["mode"])
            self.assertEqual(before, data["historical"]["selected_commit"])
            self.assertEqual("committer", data["historical"]["time_policy"])

    def test_thread_historical_argument_errors_fail_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src, _before, _after = self._historical_repo(temp_dir)
            _stdout, stderr, code = run_cli(
                "thread", "target", src, "--as-of", "2026-01-01"
            )
            self.assertNotEqual(0, code)
            self.assertIn("offset-aware", stderr)

            _stdout, stderr, code = run_cli(
                "thread", "target", src, "--revision", "HEAD", "--ref", "main"
            )
            self.assertNotEqual(0, code)
            self.assertIn("--ref is only valid", stderr)


if __name__ == "__main__":
    unittest.main()
