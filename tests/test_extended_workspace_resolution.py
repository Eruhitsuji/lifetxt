import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.extra_common import _load_config


class ExtendedWorkspaceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        self.config_dir = os.path.join(self.root, "config")
        self.unrelated_cwd = os.path.join(self.root, "cwd")
        os.makedirs(self.config_dir)
        os.makedirs(self.unrelated_cwd)

        self.personal_path = os.path.join(self.config_dir, "life.txt")
        self.work_path = os.path.join(self.config_dir, "work.life.txt")
        with open(self.personal_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Personal id:p1 project:personal\n")
        with open(self.work_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Work id:w1 project:work\n")

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
                        },
                        "work": {
                            "sources": [
                                {
                                    "path": "work.life.txt",
                                    "role": "primary",
                                    "required": True,
                                    "writable": True,
                                }
                            ],
                            "write_file": "work.life.txt",
                        },
                    },
                },
                handle,
            )

    def tearDown(self):
        self.tempdir.cleanup()

    @contextlib.contextmanager
    def _cwd(self, path):
        previous = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(previous)

    def _run(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint.main(argv)
        self.assertEqual(result, 0, stderr.getvalue())
        return stdout.getvalue()

    def test_default_workspace_resolves_config_relative_sources_outside_config_cwd(
        self,
    ):
        with self._cwd(self.unrelated_cwd):
            output = self._run(
                ["--config", self.config_path, "next", "--format", "json"]
            )
        self.assertIn('"id":"p1"', output)
        self.assertNotIn('"id":"w1"', output)

    def test_explicit_workspace_is_forwarded_to_extended_command(self):
        with self._cwd(self.unrelated_cwd):
            output = self._run(
                [
                    "--config",
                    self.config_path,
                    "--workspace",
                    "work",
                    "next",
                    "--format",
                    "json",
                ]
            )
        self.assertIn('"id":"w1"', output)
        self.assertNotIn('"id":"p1"', output)

    def test_workspace_equals_form_is_forwarded_to_extended_command(self):
        with self._cwd(self.unrelated_cwd):
            output = self._run(
                [
                    "--config=%s" % self.config_path,
                    "--workspace=work",
                    "next",
                    "--format",
                    "json",
                ]
            )
        self.assertIn('"id":"w1"', output)
        self.assertNotIn('"id":"p1"', output)

    def test_explicit_input_path_overrides_workspace_sources(self):
        override_path = os.path.join(self.root, "override.life.txt")
        with open(override_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Override id:o1 project:override\n")

        with self._cwd(self.unrelated_cwd):
            output = self._run(
                [
                    "--config",
                    self.config_path,
                    "--workspace",
                    "work",
                    "next",
                    override_path,
                    "--format",
                    "json",
                ]
            )
        self.assertIn('"id":"o1"', output)
        self.assertNotIn('"id":"w1"', output)
        self.assertNotIn('"id":"p1"', output)

    def test_legacy_top_level_paths_config_is_not_workspace_injected(self):
        legacy_path = os.path.join(self.config_dir, "legacy.life.txt")
        with open(legacy_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Legacy id:l1\n")
        legacy_config_path = os.path.join(self.config_dir, "legacy.json")
        with open(legacy_config_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {"paths": [legacy_path], "write_file": legacy_path},
                handle,
            )

        loaded = _load_config(legacy_config_path)
        self.assertEqual(loaded["paths"], [legacy_path])
        self.assertEqual(loaded["write_file"], legacy_path)
        self.assertNotIn("_active_workspace", loaded)

        with self._cwd(self.unrelated_cwd):
            output = self._run(
                ["--config", legacy_config_path, "next", "--format", "json"]
            )
        self.assertIn('"id":"l1"', output)

    def test_path_command_reports_workspace_scoped_notification_state(self):
        # `lifetxt path` must report the same default notification state
        # file that `lifetxt notify --watch` would actually use, so the two
        # named workspaces sharing this configuration file are shown as
        # having distinct default state files, not one shared path.
        with self._cwd(self.unrelated_cwd):
            personal_output = self._run(
                ["--config", self.config_path, "path", "--format", "json"]
            )
            work_output = self._run(
                [
                    "--config",
                    self.config_path,
                    "--workspace",
                    "work",
                    "path",
                    "--format",
                    "json",
                ]
            )
        personal_data = json.loads(personal_output)
        work_data = json.loads(work_output)
        self.assertTrue(
            personal_data["notification_state"].endswith(
                os.path.join("notifications-personal.json")
            )
        )
        self.assertTrue(
            work_data["notification_state"].endswith(
                os.path.join("notifications-work.json")
            )
        )
        self.assertNotEqual(
            personal_data["notification_state"], work_data["notification_state"]
        )

    def test_path_command_legacy_config_reports_unscoped_default(self):
        legacy_path = os.path.join(self.config_dir, "legacy.life.txt")
        with open(legacy_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Legacy id:l1\n")
        legacy_config_path = os.path.join(self.config_dir, "legacy.json")
        with open(legacy_config_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {"paths": [legacy_path], "write_file": legacy_path},
                handle,
            )

        with self._cwd(self.unrelated_cwd):
            output = self._run(
                ["--config", legacy_config_path, "path", "--format", "json"]
            )
        data = json.loads(output)
        self.assertTrue(
            data["notification_state"].endswith(os.path.join("notifications.json"))
        )
        self.assertNotIn("notifications-", data["notification_state"])


if __name__ == "__main__":
    unittest.main()
