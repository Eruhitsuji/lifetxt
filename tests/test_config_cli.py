"""Configuration CLI tests extracted from the legacy aggregate suite (#388)."""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


class LifeTxtConfigCliTests(unittest.TestCase):
    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle)
            handle.write("\n")

    def test_config_init_and_show(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".lifetxt.json")

            stdout, stderr, code = run_cli("config", "init", "-o", config_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Wrote", stdout)
            self.assertTrue(os.path.exists(config_path))

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "show",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual("life.txt", data["write_file"])
            self.assertEqual("self", data["user"]["name"])

    def test_config_explain_describes_config_write_require_revision(self):
        stdout, stderr, code = run_cli(
            "config", "explain", "config.write.require_revision"
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("config.write.require_revision", stdout)
        self.assertIn("Require configuration writes", stdout)
        self.assertIn("default:", stdout)
        self.assertIn("False", stdout)

    def test_config_set_on_workspace_config_does_not_bake_in_resolved_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(temp_dir, "work.txt"), "w", encoding="utf-8"
            ) as handle:
                handle.write("- [ ] sample item\n")
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            self._write_json(
                config_path,
                {
                    "workspaces": {
                        "work": {"sources": [{"path": "work.txt", "role": "primary"}]}
                    },
                    "default_workspace": "work",
                },
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "set",
                "defaults.person",
                "alice",
                cwd=temp_dir,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(config_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual("alice", written["defaults"]["person"])
            self.assertNotIn("paths", written)
            self.assertNotIn("write_file", written)
            self.assertIn("workspaces", written)
            self.assertEqual("work", written["default_workspace"])

    def test_config_unset_on_workspace_config_does_not_bake_in_resolved_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(temp_dir, "work.txt"), "w", encoding="utf-8"
            ) as handle:
                handle.write("- [ ] sample item\n")
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            self._write_json(
                config_path,
                {
                    "workspaces": {
                        "work": {"sources": [{"path": "work.txt", "role": "primary"}]}
                    },
                    "default_workspace": "work",
                    "defaults": {"person": "alice"},
                },
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "unset",
                "defaults.person",
                cwd=temp_dir,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(config_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertNotIn("person", written.get("defaults") or {})
            self.assertNotIn("paths", written)
            self.assertNotIn("write_file", written)

    def test_config_migrate_on_workspace_config_does_not_bake_in_resolved_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(temp_dir, "work.txt"), "w", encoding="utf-8"
            ) as handle:
                handle.write("- [ ] sample item\n")
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            self._write_json(
                config_path,
                {
                    "workspaces": {
                        "work": {"sources": [{"path": "work.txt", "role": "primary"}]}
                    },
                    "default_workspace": "work",
                },
            )

            stdout, stderr, code = run_cli(
                "--config", config_path, "config", "migrate", cwd=temp_dir
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(config_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(1, written["config_version"])
            self.assertNotIn("paths", written)
            self.assertNotIn("write_file", written)
            self.assertIn("workspaces", written)

    def test_config_set_on_legacy_paths_config_is_unaffected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(temp_dir, "work.txt"), "w", encoding="utf-8"
            ) as handle:
                handle.write("- [ ] sample item\n")
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            self._write_json(
                config_path,
                {"paths": ["work.txt"], "write_file": "work.txt"},
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "set",
                "defaults.person",
                "bob",
                cwd=temp_dir,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(config_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(["work.txt"], written["paths"])
            self.assertEqual("work.txt", written["write_file"])
            self.assertEqual("bob", written["defaults"]["person"])

    def test_config_require_revision_still_allows_same_file_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            self._write_json(
                config_path,
                {
                    "config_version": 1,
                    "config": {"write": {"require_revision": True}},
                    "web": {"port": 8000},
                },
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "set",
                "web.port",
                "8100",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Set web.port", stdout)
            with open(config_path, encoding="utf-8") as handle:
                self.assertEqual(8100, json.load(handle)["web"]["port"])

    def test_config_require_revision_refuses_output_without_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            output_path = os.path.join(temp_dir, "copy.lifetxt.json")
            self._write_json(
                config_path,
                {
                    "config_version": 1,
                    "config": {"write": {"require_revision": True}},
                    "web": {"port": 8000},
                },
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "set",
                "web.port",
                "8100",
                "--output",
                output_path,
            )

            self.assertEqual("", stdout)
            self.assertEqual(1, code)
            self.assertIn("requires an expected revision", stderr)
            self.assertFalse(os.path.exists(output_path))

    def test_config_require_revision_disabled_allows_output_without_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".lifetxt.json")
            output_path = os.path.join(temp_dir, "copy.lifetxt.json")
            self._write_json(
                config_path,
                {
                    "config_version": 1,
                    "web": {"port": 8000},
                },
            )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "set",
                "web.port",
                "8100",
                "--output",
                output_path,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Set web.port", stdout)
            with open(output_path, encoding="utf-8") as handle:
                self.assertEqual(8100, json.load(handle)["web"]["port"])
