"""Regression coverage for project-archive safety hardening in #183."""

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint


class ProjectArchiveSafetyV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)

    def path(self, name):
        return os.path.join(self.root, name)

    def write(self, name, text):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def revision(self, path):
        return hashlib.sha256(self.read_bytes(path)).hexdigest()

    def workspace(self, text=None, create_archive=True, extra=None):
        work = self.write(
            "work.life.txt",
            text
            if text is not None
            else "[x] T Done id:t1 project:alpha done:2026-01-01\n",
        )
        archive = self.path("archive.life.txt")
        if create_archive:
            self.write("archive.life.txt", "")
        data = {
            "config_version": 1,
            "default_workspace": "work",
            "workspaces": {
                "work": {
                    "sources": [
                        {
                            "path": "work.life.txt",
                            "role": "primary",
                            "required": True,
                            "writable": True,
                        },
                        {
                            "path": "archive.life.txt",
                            "role": "archive",
                            "required": False,
                            "writable": False,
                        },
                    ],
                    "write_file": "work.life.txt",
                }
            },
        }
        if extra:
            data.update(extra)
        config = self.write("config.json", json.dumps(data, indent=2) + "\n")
        return config, work, archive

    def run_cli(self, config, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", config] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_unchanged(self, snapshots):
        for path, expected in snapshots.items():
            self.assertTrue(os.path.exists(path), path)
            self.assertEqual(expected, self.read_bytes(path), path)

    def test_dry_run_prints_exact_revision_set_without_writing(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run"
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Revision set for a live project archive:", stdout)
        self.assertIn("--revision %s=%s" % (work, self.revision(work)), stdout)
        self.assertIn("--revision %s=%s" % (archive, self.revision(archive)), stdout)
        self.assertIn("(dry run - no changes made)", stdout)
        self.assert_unchanged(before)

    def test_dry_run_rejects_empty_revision_token_without_writing(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--dry-run",
            "--revision",
            work + "=",
        )

        self.assertEqual(1, code)
        self.assertIn("--revision must use PATH=SHA256", stderr)
        self.assert_unchanged(before)

    def test_dry_run_rejects_stale_revision_without_writing(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--dry-run",
            "--revision",
            work + "=" + ("0" * 64),
        )

        self.assertEqual(1, code)
        self.assertIn("Archive revision mismatch", stderr)
        self.assert_unchanged(before)

    def test_live_project_archive_requires_complete_revision_set(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("Live project archive requires an explicit --revision", stderr)
        self.assertIn(work, stderr)
        self.assertIn(archive, stderr)
        self.assert_unchanged(before)

    def test_live_project_archive_accepts_complete_revision_set(self):
        config, work, archive = self.workspace()

        code, stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--yes",
            "--revision",
            work + "=" + self.revision(work),
            "--revision",
            archive + "=" + self.revision(archive),
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Archived", stdout)
        self.assertNotIn("Done", self.read_bytes(work).decode("utf-8"))
        self.assertIn("Done", self.read_bytes(archive).decode("utf-8"))

    def test_parser_error_is_rejected_before_archive_writes(self):
        config, work, archive = self.workspace(
            "[x] T Broken Title id:t1 project:alpha done:2026-01-01\n"
        )
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run"
        )

        self.assertEqual(1, code)
        self.assertIn("parser error", stderr)
        self.assert_unchanged(before)

    def test_empty_active_write_source_is_an_incident_signal(self):
        config, work, archive = self.workspace("")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run"
        )

        self.assertEqual(1, code)
        self.assertIn("active writable source is 0 bytes", stderr)
        self.assert_unchanged(before)

    def test_live_revision_failure_precedes_backup_side_effects(self):
        undo_dir = self.path("undo")
        backup_dir = self.path("backup")
        config, work, archive = self.workspace(
            extra={
                "undo": {"dir": undo_dir},
                "backup": {"auto": True, "dir": backup_dir},
            }
        )
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--yes",
            "--revision",
            work + "=" + ("0" * 64),
            "--revision",
            archive + "=" + self.revision(archive),
        )

        self.assertEqual(1, code)
        self.assertIn("Archive revision mismatch", stderr)
        self.assert_unchanged(before)
        self.assertFalse(os.path.exists(undo_dir))
        self.assertFalse(os.path.exists(backup_dir))

    def test_generic_archive_keeps_legacy_optional_revision_behavior(self):
        source = self.write(
            "generic.life.txt",
            "[x] T Done id:g1 project:alpha done:2026-01-01\n",
        )
        archive = self.write("generic-archive.life.txt", "")
        config = self.write("generic-config.json", "{}\n")

        code, stdout, stderr = self.run_cli(
            config, "archive", source, "--dest", archive, "--yes"
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Archived", stdout)
        self.assertNotIn("Done", self.read_bytes(source).decode("utf-8"))
        self.assertIn("Done", self.read_bytes(archive).decode("utf-8"))

    def test_project_archive_help_explains_revision_requirement(self):
        config, _work, _archive = self.workspace()

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "--help"
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Required for every scanned source", stdout)
        self.assertIn("dry-run prints the exact set", stdout)


if __name__ == "__main__":
    unittest.main()
