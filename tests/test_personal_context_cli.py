import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.entrypoint import main
from lifetxt.model import Item
from lifetxt.serializer import item_to_line
from lifetxt.timezone_policy import UTC, clock_context


class PersonalContextCliTests(unittest.TestCase):
    def note(self, title, **details):
        normalized = OrderedDict()
        for key, value in details.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            normalized[key] = [str(entry) for entry in values]
        return Item(status="[ ]", kind="N", title=title, details=normalized)

    def workspace(self, directory):
        life = os.path.join(directory, "life.txt")
        proposals = os.path.join(directory, "proposals.json")
        config = os.path.join(directory, "config.json")
        items = [
            self.note("Editor preference", id="pref", person="self", tag="preference", source="user", updated="2026-08-23T00:00:00+00:00"),
            self.note("Use SQLite", id="decision", person="self", tag="decision", project="demo", source="user", updated="2026-08-23T00:00:00+00:00"),
        ]
        with open(life, "w", encoding="utf-8") as handle:
            handle.write("\n".join(item_to_line(item) for item in items) + "\n")
        with open(config, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "paths": [life],
                    "write_file": life,
                    "timezone": "UTC",
                    "inbox": {"proposals_file": proposals},
                },
                handle,
            )
        return life, proposals, config

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_read_commands_route_through_entrypoint(self):
        clock = datetime.datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory, clock_context(clock):
            _life, _proposals, config = self.workspace(directory)
            commands = [
                ["context", "health", "--format", "json", "--config", config],
                ["context", "why", "pref", "--format", "json", "--config", config],
                ["context", "capsule", "--format", "json", "--config", config],
                ["decisions", "--project", "demo", "--format", "json", "--config", config],
            ]
            schemas = [
                "personal-context-health-v1",
                "personal-context-why-v1",
                "personal-context-capsule-v1",
                "personal-decision-memory-v1",
            ]
            for command, schema in zip(commands, schemas):
                code, stdout, stderr = self.run_command(command)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(json.loads(stdout)["schema"], schema)

    def test_capsule_revision_is_stable_for_unchanged_workspace(self):
        clock = datetime.datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory, clock_context(clock):
            _life, _proposals, config = self.workspace(directory)
            command = ["context", "capsule", "--format", "json", "--config", config]
            first = json.loads(self.run_command(command)[1])
            second = json.loads(self.run_command(command)[1])
            self.assertEqual(first["revision"], second["revision"])

    def test_memory_correct_stages_proposal_without_rewriting_life(self):
        with tempfile.TemporaryDirectory() as directory:
            life, proposals, config = self.workspace(directory)
            with open(life, "r", encoding="utf-8") as handle:
                before = handle.read()
            code, stdout, stderr = self.run_command(
                ["memory", "correct", "pref", "Prefer light mode", "--config", config]
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("Staged Personal Context correction proposal", stdout)
            with open(life, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), before)
            with open(proposals, "r", encoding="utf-8") as handle:
                staged = json.load(handle)
            self.assertEqual(staged[0]["changes"][0]["details"]["corrects"], ["pref"])

    def test_unknown_why_id_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            _life, _proposals, config = self.workspace(directory)
            code, _stdout, stderr = self.run_command(
                ["context", "why", "unknown", "--config", config]
            )
            self.assertEqual(code, 1)
            self.assertIn("Item ID not found", stderr)


if __name__ == "__main__":
    unittest.main()
