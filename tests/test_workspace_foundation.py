import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.workspace import (
    default_workspace_name,
    iter_workspace_definitions,
    normalize_source,
    resolve_workspace,
    source_reason,
    workspace_doctor,
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

    def tearDown(self):
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
            {"workspaces": {"w": {"sources": [{"path": "missing.txt", "required": True}]}}}
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
                "workspaces": {"a": {"sources": ["a.txt"]}, "b": {"sources": ["b.txt"]}},
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
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks not permitted in this environment")
        config = self.config({"workspaces": {"w": {"sources": ["life.txt", "alias.txt"]}}})
        resolution = resolve_workspace(config, "w")
        codes = {row["code"] for row in resolution["diagnostics"]}
        self.assertIn("WS011", codes)

    def test_source_reason_describes_source(self):
        record = normalize_source({"path": "notes/*.txt", "role": "reference", "required": True}, self.root)
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


class ConfigLayerTests(unittest.TestCase):
    def test_precedence_default_config_profile_env(self):
        config = OrderedDict(
            [
                ("defaults", OrderedDict([("timezone", "UTC")])),
                ("profiles", OrderedDict([("p", OrderedDict([("defaults", OrderedDict([("timezone", "Asia/Tokyo")]))]))])),
            ]
        )
        merged, prov = effective_config(config)
        self.assertEqual("UTC", merged["defaults"]["timezone"])
        self.assertEqual("config", prov["defaults.timezone"])

        merged, prov = effective_config(config, profile="p")
        self.assertEqual("Asia/Tokyo", merged["defaults"]["timezone"])
        self.assertEqual("profile:p", prov["defaults.timezone"])

        merged, prov = effective_config(config, env={"LIFETXT_TIMEZONE": "Europe/Paris"})
        self.assertEqual("Europe/Paris", merged["defaults"]["timezone"])
        self.assertEqual("env:LIFETXT_TIMEZONE", prov["defaults.timezone"])

    def test_defaults_provide_builtin_values(self):
        merged, prov = effective_config({})
        self.assertEqual("builtin-default", prov.get("defaults.timezone"))
        self.assertIn("web", merged)

    def test_dotted_get_set_unset(self):
        config = OrderedDict()
        set_dotted(config, "a.b.c", 5)
        self.assertEqual(5, get_dotted(config, "a.b.c"))
        self.assertTrue(unset_dotted(config, "a.b.c"))
        self.assertIsNone(get_dotted(config, "a.b.c"))
        self.assertFalse(unset_dotted(config, "a.b.c"))

    def test_secret_values_redacted_in_provenance_rows(self):
        config = OrderedDict(
            [("notifications", OrderedDict([("email", OrderedDict([("password", "hunter2")]))]))]
        )
        rows = {path: value for path, value, _ in flatten_provenance(config)}
        self.assertEqual("***redacted***", rows["notifications.email.password"])

    def test_explain_known_and_wildcard(self):
        self.assertIsNotNone(explain_key("defaults.timezone"))
        self.assertIsNotNone(explain_key("workspaces.personal.sources"))
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
            errors = [row for row in validate_config(config) if row["severity"] == "error"]
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


if __name__ == "__main__":
    unittest.main()
