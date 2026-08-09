import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.ids import id_audit
from lifetxt.parser import parse_text


class GeneratedRecordValidationTests(unittest.TestCase):
    def _codes(self, text):
        _items, diagnostics = parse_text(text)
        return [diagnostic.code for diagnostic in diagnostics]

    def test_project_record_owned_fields_do_not_emit_generic_custom_or_presence_warnings(self):
        codes = self._codes(
            "[N] N project_meta record:project project:demo state:active "
            "owner:self id:project_meta\n"
        )
        self.assertNotIn("W106", codes)
        self.assertNotIn("W207", codes)

    def test_ticket_record_owned_fields_do_not_emit_generic_custom_warnings(self):
        codes = self._codes(
            "[ ] T ticket record:ticket id:TK-1 tracker:task ticket_status:new "
            "priority:normal severity:minor project:demo assignee:self\n"
        )
        self.assertNotIn("W106", codes)

    def test_generic_note_custom_key_still_warns(self):
        codes = self._codes("[N] N note id:n1 custom_thing:value\n")
        self.assertIn("W106", codes)

    def test_unknown_record_marker_does_not_gain_built_in_field_status(self):
        codes = self._codes("[N] N note id:n1 record:custom custom_thing:value\n")
        self.assertGreaterEqual(codes.count("W106"), 2)

    def test_presence_state_validation_is_unchanged(self):
        codes = self._codes(
            "[/] S presence from:2026-08-09T10:00 state:not-a-presence-state "
            "person:self\n"
        )
        self.assertIn("W207", codes)


class CaptureContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        self.config_dir = os.path.join(self.root, "config")
        self.cwd = os.path.join(self.root, "cwd")
        os.makedirs(self.config_dir)
        os.makedirs(self.cwd)
        self.life_path = os.path.join(self.config_dir, "life.txt")
        with open(self.life_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Base id:base project:demo\n")
        self.config_path = os.path.join(self.config_dir, ".lifetxt.json")
        with open(self.config_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "config_version": 1,
                    "default_workspace": "personal",
                    "workspaces": {
                        "personal": {
                            "sources": [
                                {
                                    "path": "life.txt",
                                    "role": "primary",
                                    "required": True,
                                    "writable": True,
                                }
                            ],
                            "write_file": "life.txt",
                        }
                    },
                    "ids": {"auto": True, "key": "id"},
                },
                handle,
            )

    def tearDown(self):
        self.tempdir.cleanup()

    @contextlib.contextmanager
    def _unrelated_cwd(self):
        previous = os.getcwd()
        os.chdir(self.cwd)
        try:
            yield
        finally:
            os.chdir(previous)

    def _run(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_project_new_applies_auto_id_without_creating_generic_warnings(self):
        with self._unrelated_cwd():
            result, stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "project",
                    "new",
                    "demo-project",
                    "--owner",
                    "self",
                    "--state",
                    "active",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertNotIn("W106", stderr)
        self.assertNotIn("W207", stderr)
        self.assertIn("id:note_", stdout)

        with open(self.life_path, "r", encoding="utf-8") as handle:
            items, diagnostics = parse_text(handle.read())
        self.assertFalse([d for d in diagnostics if d.code in ("W106", "W207")])
        project_items = [
            item for item in items if "project" in item.details.get("record", [])
        ]
        self.assertEqual(len(project_items), 1)
        self.assertTrue(project_items[0].details.get("id"))
        self.assertEqual(id_audit(items)["missing_count"], 0)

    def test_quick_resolves_existing_reference_from_named_workspace(self):
        with self._unrelated_cwd():
            result, _stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "quick",
                    "Dependent",
                    "--id",
                    "dependent",
                    "--project",
                    "demo",
                    "--depends_on",
                    "base",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertNotIn("W215", stderr)

        with open(self.life_path, "r", encoding="utf-8") as handle:
            _items, diagnostics = parse_text(handle.read())
        self.assertNotIn("W215", [diagnostic.code for diagnostic in diagnostics])

    def test_quick_still_warns_for_truly_missing_reference(self):
        with self._unrelated_cwd():
            result, _stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "quick",
                    "Missing dependency",
                    "--id",
                    "missing-dependent",
                    "--depends_on",
                    "does-not-exist",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertIn("W215", stderr)


if __name__ == "__main__":
    unittest.main()
