import os
import subprocess
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.workspace import (
    active_workspace_name,
    default_workspace_name,
    iter_workspace_definitions,
    normalize_source,
    resolve_workspace,
    source_reason,
    workspace_doctor,
    workspace_resolution_active,
    workspace_summaries,
)
from lifetxt.config_layers import (
    effective_config,
    flatten_provenance,
    get_dotted,
    set_dotted,
    unset_dotted,
)
from lifetxt.config_registry import explain_key


class WorkspaceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.cleanup_paths = []

    def tearDown(self):
        for path in reversed(self.cleanup_paths):
            try:
                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    os.rmdir(path)
                elif os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self.temp.cleanup()

    def write(self, name, text="[ ] T Task\n"):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def config(self, extra):
        data = OrderedDict(extra)
        data["_path"] = os.path.join(self.root, ".lifetxt.json")
        return data

    def symlink(self, target, link, target_is_directory=False):
        try:
            os.symlink(target, link, target_is_directory=target_is_directory)
        except TypeError:
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError, AttributeError) as exc:
                self.skipTest("symlink fixture unavailable: %s" % exc)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest("symlink fixture unavailable: %s" % exc)
        self.cleanup_paths.append(link)
        return link

    def junction(self, target, link):
        if os.name != "nt":
            self.skipTest("Windows junction fixture unavailable on this platform")
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, target],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if completed.returncode != 0:
            reason = (completed.stderr or completed.stdout or "mklink failed").strip()
            self.skipTest("Windows junction fixture unavailable: %s" % reason)
        self.cleanup_paths.append(link)
        return link

    def codes(self, resolution):
        return {row["code"] for row in resolution["diagnostics"]}

    def test_legacy_paths_become_default_workspace(self):
        self.write("life.txt")
        config = self.config({"paths": ["life.txt"], "write_file": "life.txt"})
        definitions = iter_workspace_definitions(config)
        self.assertEqual(["default"], list(definitions))
        resolution = resolve_workspace(config)
        self.assertTrue(resolution["legacy"])
        self.assertEqual(1, len(resolution["input_paths"]))
        self.assertTrue(resolution["input_paths"][0].endswith("life.txt"))
        self.assertTrue(resolution["ok"])

    def test_relative_paths_resolve_against_config_dir_not_cwd(self):
        self.write("sub/life.txt")
        config = self.config({"workspaces": {"default": {"sources": ["sub/life.txt"]}}})
        original = os.getcwd()
        other = tempfile.mkdtemp()
        try:
            os.chdir(other)
            resolution = resolve_workspace(config)
        finally:
            os.chdir(original)
        self.assertEqual(
            os.path.normcase(os.path.join(self.root, "sub", "life.txt")),
            os.path.normcase(resolution["input_paths"][0]),
        )

    def test_required_missing_source_is_error(self):
        config = self.config(
            {
                "workspaces": {
                    "w": {"sources": [{"path": "missing.txt", "required": True}]}
                }
            }
        )
        resolution = resolve_workspace(config, "w")
        codes = {row["code"] for row in resolution["diagnostics"]}
        self.assertIn("WS001", codes)
        self.assertFalse(resolution["ok"])

    def test_duplicate_physical_file_detected(self):
        self.write("life.txt")
        config = self.config(
            {"workspaces": {"w": {"sources": ["life.txt", "./life.txt"]}}}
        )
        resolution = resolve_workspace(config, "w")
        codes = {row["code"] for row in resolution["diagnostics"]}
        self.assertIn("WS002", codes)

    def test_generated_role_excluded_from_writable_and_hidden(self):
        self.write("life.txt")
        self.write("gen.life.txt")
        config = self.config(
            {
                "workspaces": {
                    "w": {
                        "sources": [
                            "life.txt",
                            {"path": "gen.life.txt", "role": "generated"},
                        ],
                        "write_file": "life.txt",
                    }
                }
            }
        )
        resolution = resolve_workspace(config, "w")
        self.assertTrue(resolution["write_file"].endswith("life.txt"))
        self.assertEqual(1, len(resolution["generated_paths"]))
        visible = resolution["default_visible_paths"]
        self.assertTrue(all(not p.endswith("gen.life.txt") for p in visible))

    def test_glob_expansion_is_deterministic(self):
        self.write("notes/b.life.txt")
        self.write("notes/a.life.txt")
        config = self.config({"workspaces": {"w": {"sources": ["notes/*.life.txt"]}}})
        resolution = resolve_workspace(config, "w")
        names = [os.path.basename(p) for p in resolution["input_paths"]]
        self.assertEqual(["a.life.txt", "b.life.txt"], names)

    def test_unknown_workspace_name_raises(self):
        config = self.config({"workspaces": {"w": {"sources": ["life.txt"]}}})
        with self.assertRaises(ValueError):
            resolve_workspace(config, "nope")

    def test_default_workspace_name_respects_explicit(self):
        config = self.config(
            {
                "default_workspace": "b",
                "workspaces": {
                    "a": {"sources": ["a.txt"]},
                    "b": {"sources": ["b.txt"]},
                },
            }
        )
        self.assertEqual("b", default_workspace_name(config))

    def test_priority_orders_inputs(self):
        self.write("low.txt")
        self.write("high.txt")
        config = self.config(
            {
                "workspaces": {
                    "w": {
                        "sources": [
                            {"path": "low.txt", "priority": 200},
                            {"path": "high.txt", "priority": 10},
                        ]
                    }
                }
            }
        )
        resolution = resolve_workspace(config, "w")
        names = [os.path.basename(p) for p in resolution["input_paths"]]
        self.assertEqual(["high.txt", "low.txt"], names)

    def test_summaries_flag_default_and_errors(self):
        config = self.config(
            {
                "default_workspace": "ok",
                "workspaces": {
                    "ok": {"sources": ["life.txt"]},
                    "bad": {"sources": [{"path": "missing.txt", "required": True}]},
                },
            }
        )
        self.write("life.txt")
        summaries = {s["name"]: s for s in workspace_summaries(config)}
        self.assertTrue(summaries["ok"]["default"])
        self.assertTrue(summaries["ok"]["ok"])
        self.assertFalse(summaries["bad"]["ok"])

    def test_normalize_source_defaults(self):
        record = normalize_source("life.txt", self.root)
        self.assertEqual("primary", record["role"])
        self.assertTrue(record["writable"])
        self.assertTrue(record["default_visible"])
        self.assertEqual(100, record["priority"])

    def test_generated_write_target_is_error(self):
        self.write("gen.life.txt")
        config = self.config(
            {
                "workspaces": {
                    "w": {
                        "sources": [{"path": "gen.life.txt", "role": "generated"}],
                        "write_file": "gen.life.txt",
                    }
                }
            }
        )
        resolution = resolve_workspace(config, "w")
        codes = {row["code"] for row in resolution["diagnostics"]}
        self.assertIn("WS012", codes)
        self.assertFalse(resolution["ok"])

    def test_symlink_alias_detected(self):
        target = self.write("life.txt")
        link = os.path.join(self.root, "alias.txt")
        self.symlink(target, link)
        config = self.config(
            {"workspaces": {"w": {"sources": ["life.txt", "alias.txt"]}}}
        )
        resolution = resolve_workspace(config, "w")
        codes = {row["code"] for row in resolution["diagnostics"]}
        self.assertIn("WS011", codes)

    def test_self_referential_symlink_cycle_is_error(self):
        link = os.path.join(self.root, "loop")
        self.symlink(".", link, target_is_directory=True)
        config = self.config({"workspaces": {"w": {"sources": ["loop/**/*.txt"]}}})
        resolution = resolve_workspace(config, "w")
        rows = [row for row in resolution["diagnostics"] if row["code"] == "WS014"]
        self.assertEqual(1, len(rows))
        self.assertEqual(os.path.normcase(link), os.path.normcase(rows[0]["source"]))
        self.assertFalse(resolution["ok"])

    def test_sibling_symlink_is_not_reported_as_cycle(self):
        self.write("real/life.txt")
        link = os.path.join(self.root, "alias")
        self.symlink(os.path.join(self.root, "real"), link, target_is_directory=True)
        config = self.config({"workspaces": {"w": {"sources": ["alias"]}}})
        resolution = resolve_workspace(config, "w")
        self.assertNotIn("WS014", self.codes(resolution))
        self.assertEqual(1, len(resolution["input_paths"]))

    def test_windows_junction_cycle_is_error(self):
        link = os.path.join(self.root, "junction")
        self.junction(self.root, link)
        config = self.config({"workspaces": {"w": {"sources": ["junction/**/*.txt"]}}})
        resolution = resolve_workspace(config, "w")
        rows = [row for row in resolution["diagnostics"] if row["code"] == "WS014"]
        self.assertEqual(1, len(rows))
        self.assertEqual(os.path.normcase(link), os.path.normcase(rows[0]["source"]))

    def test_broken_symlink_is_not_reported_as_cycle(self):
        link = os.path.join(self.root, "broken.txt")
        self.symlink("missing.txt", link)
        config = self.config({"workspaces": {"w": {"sources": ["broken.txt"]}}})
        resolution = resolve_workspace(config, "w")
        self.assertNotIn("WS014", self.codes(resolution))

    def test_total_source_size_just_under_limit_is_ok(self):
        self.write("a.txt", "a" * 5)
        self.write("b.txt", "b" * 5)
        config = self.config(
            {
                "workspace": {"max_total_source_bytes": 10},
                "workspaces": {"w": {"sources": ["a.txt", "b.txt"]}},
            }
        )
        resolution = resolve_workspace(config, "w")
        self.assertNotIn("WS015", self.codes(resolution))
        self.assertTrue(resolution["ok"])

    def test_total_source_size_over_limit_identifies_largest_contributors(self):
        large = self.write("large.txt", "l" * 8)
        small = self.write("small.txt", "s" * 3)
        config = self.config(
            {
                "workspace": {"max_total_source_bytes": 10},
                "workspaces": {"w": {"sources": ["large.txt", "small.txt"]}},
            }
        )
        resolution = resolve_workspace(config, "w")
        rows = [row for row in resolution["diagnostics"] if row["code"] == "WS015"]
        self.assertEqual(1, len(rows))
        self.assertEqual(large, rows[0]["source"])
        self.assertIn("large.txt", rows[0]["hint"])
        self.assertIn("small.txt", rows[0]["hint"])
        self.assertFalse(resolution["ok"])

    def test_invalid_total_source_size_limit_is_error(self):
        self.write("life.txt")
        config = self.config(
            {
                "workspace": {"max_total_source_bytes": 0},
                "workspaces": {"w": {"sources": ["life.txt"]}},
            }
        )
        resolution = resolve_workspace(config, "w")
        rows = [row for row in resolution["diagnostics"] if row["code"] == "WS016"]
        self.assertEqual(1, len(rows))
        self.assertEqual("workspace.max_total_source_bytes", rows[0]["source"])
        self.assertFalse(resolution["ok"])

    def test_source_reason_describes_source(self):
        record = normalize_source(
            {"path": "notes/*.txt", "role": "reference", "required": True}, self.root
        )
        record["matched_glob"] = True
        record["exclude"] = []
        reason = source_reason(record)
        self.assertIn("role=reference", reason)
        self.assertIn("required", reason)

    def test_workspace_doctor_aggregates(self):
        self.write("life.txt")
        config = self.config(
            {
                "default_workspace": "a",
                "workspaces": {
                    "a": {"sources": ["life.txt"]},
                    "b": {"sources": ["life.txt"]},
                },
            }
        )
        report = workspace_doctor(config)
        self.assertEqual(2, report["workspace_count"])
        self.assertEqual("a", report["default_workspace"])
        # Both workspaces resolve the same physical file -> reported as shared.
        self.assertTrue(report["shared_files"])

    def test_unicode_source_path_resolves_and_reads(self):
        self.write("日本語タスク.life.txt", "[ ] T 例えば\n")
        config = self.config(
            {"workspaces": {"w": {"sources": ["日本語タスク.life.txt"]}}}
        )
        resolution = resolve_workspace(config, "w")
        self.assertTrue(resolution["ok"])
        self.assertEqual(1, len(resolution["input_paths"]))
        self.assertTrue(os.path.exists(resolution["input_paths"][0]))

    def test_unknown_top_level_config_keys_do_not_break_resolution(self):
        self.write("life.txt")
        config = self.config(
            {
                "workspaces": {"w": {"sources": ["life.txt"]}},
                "some_future_section": {"anything": True},
            }
        )
        resolution = resolve_workspace(config, "w")
        self.assertTrue(resolution["ok"])

    def test_glob_order_is_deterministic_across_mixed_priority_sources(self):
        self.write("b_glob/two.life.txt")
        self.write("b_glob/one.life.txt")
        self.write("a_literal.life.txt")
        config = self.config(
            {
                "workspaces": {
                    "w": {
                        "sources": [
                            {"path": "b_glob/*.life.txt", "priority": 50},
                            {"path": "a_literal.life.txt", "priority": 50},
                        ]
                    }
                }
            }
        )
        resolution = resolve_workspace(config, "w")
        names = [os.path.basename(p) for p in resolution["input_paths"]]
        # Equal priority falls back to path-string ordering, so the literal
        # source (path "a_literal.life.txt") sorts before the glob source
        # (path "b_glob/*.life.txt"); within the glob, matches are sorted.
        self.assertEqual(["a_literal.life.txt", "one.life.txt", "two.life.txt"], names)

    def test_repeated_resolution_of_the_same_config_is_stable(self):
        self.write("b_glob/two.life.txt")
        self.write("b_glob/one.life.txt")
        config = self.config({"workspaces": {"w": {"sources": ["b_glob/*.life.txt"]}}})
        first = resolve_workspace(config, "w")["input_paths"]
        second = resolve_workspace(config, "w")["input_paths"]
        self.assertEqual(first, second)


class LoadConfigMalformedFileTests(unittest.TestCase):
    """Covers loading a broken/malformed configuration file (todo.md P1)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_broken_json_config_reports_a_value_error_not_a_crash(self):
        from lifetxt.config import load_config

        path = os.path.join(self.temp.name, "broken.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ this is not valid json")
        with self.assertRaises(ValueError):
            load_config(path)

    def test_non_object_json_config_reports_a_value_error(self):
        from lifetxt.config import load_config

        path = os.path.join(self.temp.name, "array.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("[1, 2, 3]")
        with self.assertRaises(ValueError):
            load_config(path)

    def test_broken_json_config_produces_the_standard_cli_error_and_exit_code(self):
        import contextlib
        import io

        # Goes through the real package entry point (python -m lifetxt), not
        # lifetxt.cli.main directly: cli.main is monkey-patched in place the
        # first time any test exercises the timezone-context installer, so
        # calling it directly is order-dependent in a shared test process.
        # entrypoint.main is what users actually invoke and stays consistent
        # regardless of that patching.
        from lifetxt import entrypoint

        path = os.path.join(self.temp.name, "broken.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ this is not valid json")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", path, "check", "-"])
        self.assertEqual(1, code)
        self.assertIn("ERROR:", stderr.getvalue())


class WorkspaceResolutionActiveTests(unittest.TestCase):
    """Covers the public predicate #142 moved out of lifetxt.cli."""

    def test_inactive_for_legacy_paths_configuration(self):
        config = OrderedDict({"paths": ["life.txt"]})
        self.assertFalse(workspace_resolution_active(config))

    def test_inactive_for_non_dict_configuration_with_no_explicit_name(self):
        self.assertFalse(workspace_resolution_active(None))

    def test_active_when_workspaces_section_present(self):
        config = OrderedDict({"workspaces": {"work": {"sources": ["a.txt"]}}})
        self.assertTrue(workspace_resolution_active(config))

    def test_active_when_default_workspace_set(self):
        config = OrderedDict({"default_workspace": "work"})
        self.assertTrue(workspace_resolution_active(config))

    def test_active_for_explicit_workspace_name_regardless_of_config(self):
        self.assertTrue(workspace_resolution_active({}, "work"))
        self.assertTrue(workspace_resolution_active(None, "work"))


class ActiveWorkspaceNameTests(unittest.TestCase):
    """Covers the public accessor #142 introduced for TUI header display."""

    def test_returns_none_for_non_dict(self):
        self.assertIsNone(active_workspace_name(None))
        self.assertIsNone(active_workspace_name("not-a-dict"))

    def test_returns_none_when_key_absent(self):
        self.assertIsNone(active_workspace_name({}))
        self.assertIsNone(active_workspace_name({"paths": ["life.txt"]}))

    def test_returns_injected_workspace_name(self):
        config = {"_active_workspace": "work"}
        self.assertEqual("work", active_workspace_name(config))


class ConfigLayerTests(unittest.TestCase):
    def test_precedence_default_config_profile_env(self):
        config = OrderedDict(
            [
                ("defaults", OrderedDict([("timezone", "UTC")])),
                (
                    "profiles",
                    OrderedDict(
                        [
                            (
                                "p",
                                OrderedDict(
                                    [
                                        (
                                            "defaults",
                                            OrderedDict([("timezone", "Asia/Tokyo")]),
                                        )
                                    ]
                                ),
                            )
                        ]
                    ),
                ),
            ]
        )
        merged, prov = effective_config(config)
        self.assertEqual("UTC", merged["defaults"]["timezone"])
        self.assertEqual("config", prov["defaults.timezone"])

        merged, prov = effective_config(config, profile="p")
        self.assertEqual("Asia/Tokyo", merged["defaults"]["timezone"])
        self.assertEqual("profile:p", prov["defaults.timezone"])

        merged, prov = effective_config(
            config, env={"LIFETXT_TIMEZONE": "Europe/Paris"}
        )
        self.assertEqual("Europe/Paris", merged["defaults"]["timezone"])
        self.assertEqual("env:LIFETXT_TIMEZONE", prov["defaults.timezone"])

    def test_defaults_provide_builtin_values(self):
        merged, prov = effective_config({})
        self.assertEqual("builtin-default", prov.get("defaults.timezone"))
        self.assertIn("web", merged)
        self.assertEqual(67108864, merged["workspace"]["max_total_source_bytes"])
        self.assertEqual(
            "builtin-default", prov.get("workspace.max_total_source_bytes")
        )

    def test_dotted_get_set_unset(self):
        config = OrderedDict()
        set_dotted(config, "a.b.c", 5)
        self.assertEqual(5, get_dotted(config, "a.b.c"))
        self.assertTrue(unset_dotted(config, "a.b.c"))
        self.assertIsNone(get_dotted(config, "a.b.c"))
        self.assertFalse(unset_dotted(config, "a.b.c"))

    def test_secret_values_redacted_in_provenance_rows(self):
        config = OrderedDict(
            [
                (
                    "notifications",
                    OrderedDict([("email", OrderedDict([("password", "hunter2")]))]),
                )
            ]
        )
        rows = {path: value for path, value, _ in flatten_provenance(config)}
        self.assertEqual("***redacted***", rows["notifications.email.password"])

    def test_explain_known_and_wildcard(self):
        self.assertIsNotNone(explain_key("defaults.timezone"))
        self.assertIsNotNone(explain_key("workspaces.personal.sources"))
        self.assertEqual(
            67108864,
            explain_key("workspace.max_total_source_bytes")["default"],
        )
        self.assertIsNone(explain_key("totally.unknown.key"))


class ExampleConfigTests(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXAMPLES = os.path.join(ROOT, "examples", "config")

    def _load(self, name):
        import json

        path = os.path.join(self.EXAMPLES, name)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data["_path"] = path
        return data

    EXAMPLE_NAMES = (
        "personal.lifetxt.json",
        "work.lifetxt.json",
        "project-multi-file.lifetxt.json",
        "generated-calendar.lifetxt.json",
        "team.lifetxt.json",
        "kiosk.lifetxt.json",
        "projects.lifetxt.json",
        "remote.lifetxt.json",
        "integration-references.lifetxt.json",
        "software-ticket-workspace.lifetxt.json",
    )

    def test_examples_resolve_default_workspace(self):
        for name in self.EXAMPLE_NAMES:
            config = self._load(name)
            resolution = resolve_workspace(config)
            self.assertEqual(1, resolution["manifest_version"])
            self.assertIsNotNone(resolution["name"])

    def test_examples_pass_config_validation(self):
        from lifetxt.config_validation import validate_config

        for name in self.EXAMPLE_NAMES:
            config = self._load(name)
            errors = [
                row for row in validate_config(config) if row["severity"] == "error"
            ]
            self.assertEqual([], errors, name)

    def test_examples_validate_against_config_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Draft 2020-12 jsonschema validation not available")
        from lifetxt.safety_foundation import schema_bundle

        schema = schema_bundle()["config-v1.schema.json"]
        validator = Draft202012Validator(schema)
        for name in self.EXAMPLE_NAMES:
            config = self._load(name)
            config.pop("_path", None)
            errors = sorted(validator.iter_errors(config), key=lambda e: list(e.path))
            self.assertEqual([], [e.message for e in errors], name)

    def test_config_schema_declares_workspace_source_size_limit(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Draft 2020-12 jsonschema validation not available")
        from lifetxt.safety_foundation import schema_bundle

        schema = schema_bundle()["config-v1.schema.json"]
        validator = Draft202012Validator(schema)
        valid = {"workspace": {"max_total_source_bytes": 1}}
        self.assertEqual([], [e.message for e in validator.iter_errors(valid)])
        invalid = {"workspace": {"max_total_source_bytes": 0}}
        messages = [e.message for e in validator.iter_errors(invalid)]
        self.assertTrue(messages)


if __name__ == "__main__":
    unittest.main()
