import contextlib
import io
import os
import subprocess
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.paths import expand_paths


class ExpandPathsTests(unittest.TestCase):
    def test_directory_expansion_uses_documented_pattern_then_name_order(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            names = ("z.life.txt", "a.life.txt", "life.txt", "notes.txt")
            for name in names:
                open(os.path.join(root, name), "w", encoding="utf-8").close()

            result = expand_paths([root])

        self.assertEqual(
            [
                os.path.join(root, "life.txt"),
                os.path.join(root, "a.life.txt"),
                os.path.join(root, "z.life.txt"),
                os.path.join(root, "notes.txt"),
            ],
            result,
        )

    def test_glob_results_are_sorted_and_explicit_input_order_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            paths = [os.path.join(root, name) for name in ("c.txt", "a.txt", "b.txt")]
            for path in paths:
                open(path, "w", encoding="utf-8").close()

            glob_result = expand_paths([os.path.join(root, "*.txt")])
            explicit_result = expand_paths([paths[2], paths[0], paths[1]])

        self.assertEqual(sorted(paths), glob_result)
        self.assertEqual([paths[2], paths[0], paths[1]], explicit_result)

    def test_duplicate_paths_are_removed_by_absolute_identity(self):
        with tempfile.TemporaryDirectory(prefix="lifetxt-paths-") as root:
            path = os.path.join(root, "life.txt")
            open(path, "w", encoding="utf-8").close()
            result = expand_paths([path, os.path.join(root, ".", "life.txt")])

        self.assertEqual([path], result)


class MultiFileSourceIntegrityTests(unittest.TestCase):
    """Missing/permission-denied/symlinked input sources among several files
    (#421, the remaining scope from #322 after #415/#416/#417 shipped).

    Verified live before writing these tests: every command reaches
    ``lifetxt.entrypoint.main``, whose top-level ``try/except`` around
    ``_legacy_main``/the dispatched extra command catches both ``ValueError``
    and ``OSError``. A missing or permission-denied file among several input
    sources therefore already fails the whole operation loudly, naming the
    failing path via the underlying OS error, before any output is produced
    -- never a partial read from the remaining sources. These tests lock
    that behavior in with regression coverage; see
    ``docs/en/config.md``'s "Missing or unreadable input sources" section
    for the documented policy.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lifetxt-paths-")
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)

    def write(self, name, text="[ ] T Task id:t1\n"):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_file_among_multiple_sources_fails_loudly_before_output(self):
        good = self.write("good.life.txt")
        missing = os.path.join(self.root, "missing.life.txt")

        code, stdout, stderr = self.run_command(["check", good, missing])

        self.assertEqual(1, code)
        self.assertIn("missing.life.txt", stderr)
        self.assertIn("ERROR", stderr)
        self.assertNotIn("OK:", stdout)
        self.assertEqual("", stdout)

    def test_missing_file_among_multiple_sources_fails_loudly_for_extended_commands(
        self,
    ):
        # `next` is dispatched through the same entrypoint.main try/except as
        # `check`, but via the separate extra-command routing path -- cover
        # both so the two dispatch branches cannot silently diverge.
        good = self.write("good.life.txt")
        missing = os.path.join(self.root, "missing.life.txt")

        code, stdout, stderr = self.run_command(["next", good, missing])

        self.assertEqual(1, code)
        self.assertIn("missing.life.txt", stderr)
        self.assertEqual("", stdout)

    def test_permission_denied_file_among_multiple_sources_fails_loudly(self):
        if os.name != "nt":
            self.skipTest("icacls permission fixture is Windows-only")

        good = self.write("good.life.txt")
        locked = self.write("locked.life.txt")
        completed = subprocess.run(
            ["icacls", locked, "/deny", "%s:(R)" % os.environ.get("USERNAME", "")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if completed.returncode != 0:
            self.skipTest(
                "icacls permission fixture unavailable: %s"
                % (completed.stderr or completed.stdout or "").strip()
            )
        self.addCleanup(
            subprocess.run,
            ["icacls", locked, "/reset"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        code, stdout, stderr = self.run_command(["check", good, locked])

        self.assertEqual(1, code)
        self.assertIn("locked.life.txt", stderr)
        self.assertIn("ERROR", stderr)
        self.assertEqual("", stdout)

    def test_symlinked_input_file_is_read_as_a_distinct_source(self):
        target = self.write("real.life.txt")
        link = os.path.join(self.root, "link.life.txt")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest("symlink fixture unavailable: %s" % exc)

        code, stdout, stderr = self.run_command(["check", target, link])

        # The symlink resolves and is read like any other file rather than
        # being silently skipped or erroring; because paths.py dedupes by
        # os.path.abspath (not os.path.realpath), the real file and its
        # symlink are treated as two distinct sources, correctly producing a
        # duplicate-id warning naming both paths -- a warning, not a
        # blocking error, so the command still exits 0.
        self.assertEqual(0, code)
        self.assertIn("W213", stdout)
        self.assertIn("real.life.txt", stdout)
        self.assertIn("link.life.txt", stdout)


if __name__ == "__main__":
    unittest.main()
