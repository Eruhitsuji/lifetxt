"""Archive CLI tests extracted from the legacy aggregate suite (#388)."""

import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


class LifeTxtArchiveCliTests(unittest.TestCase):
    SOURCE_TEXT = (
        "[x] T Done_Task id:T001 done:2026-01-15\n"
        "[-] T Canceled_Task id:T002 done:2026-03-10\n"
        "[ ] T Open_Task id:T003\n"
        "[x] T Recent_Done id:T004 done:2026-06-20\n"
    )

    def _write_source(self, temp_dir, text=None):
        src = os.path.join(temp_dir, "life.txt")
        with open(src, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text or self.SOURCE_TEXT)
        return src

    def test_archive_dry_run_shows_preview_and_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--dry-run", "--yes"
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("(dry run", stdout)
            self.assertIn("Done_Task", stdout)
            self.assertFalse(os.path.exists(dest))
            with open(src, encoding="utf-8") as handle:
                self.assertEqual(self.SOURCE_TEXT, handle.read())

    def test_archive_move_removes_items_from_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--yes")
            self.assertEqual(0, code, stderr)
            with open(src, encoding="utf-8") as handle:
                source = handle.read()
            with open(dest, encoding="utf-8") as handle:
                archived = handle.read()
            self.assertNotIn("Done_Task", source)
            self.assertIn("Open_Task", source)
            self.assertIn("Done_Task", archived)
            self.assertIn("Canceled_Task", archived)

    def test_archive_copy_keeps_items_in_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--copy", "--yes"
            )
            self.assertEqual(0, code, stderr)
            with open(src, encoding="utf-8") as handle:
                self.assertEqual(self.SOURCE_TEXT, handle.read())
            with open(dest, encoding="utf-8") as handle:
                self.assertIn("Done_Task", handle.read())

    def test_archive_before_filter_excludes_recent_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli(
                "archive",
                src,
                "--dest",
                dest,
                "--before",
                "2026-04-01",
                "--dry-run",
                "--yes",
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Done_Task", stdout)
            self.assertNotIn("Recent_Done", stdout)

    def test_archive_max_items_limits_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--max-items", "1", "--yes"
            )
            self.assertEqual(0, code, stderr)
            with open(dest, encoding="utf-8") as handle:
                self.assertEqual(1, len([line for line in handle if line.strip()]))

    def test_archive_no_match_exits_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, "[ ] T Open_Task\n")
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--yes")
            self.assertEqual(0, code, stderr)
            self.assertIn("No items", stdout)
            self.assertFalse(os.path.exists(dest))

    def test_archive_aborted_on_no_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            dest = os.path.join(temp_dir, "archive.life.txt")
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, input_text="n\n"
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Aborted", stdout)
            self.assertFalse(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
