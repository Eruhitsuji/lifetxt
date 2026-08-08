"""Covers #142: the CLI-wide timezone-context bootstrap becomes workspace-aware.

``cli_timezone_candidate_paths`` (the shared candidate-file resolver) has
dedicated unit coverage in ``tests/test_timezone_policy_v2.py``. This module
covers the surrounding integration: the installer closure that is actually
wired into the package at import time (``lifetxt.runtime_safety_v2
.install_cli_timezone_context``, replaced by ``lifetxt.safety_compat_v2`` --
see that module's ``_patch_cli_timezone_installer``), the real CLI's
unknown-workspace error behavior, and the claim that the TUI and notifier
consume the ambient timezone context rather than establishing their own.
"""

import contextlib
import datetime
import io
import json
import os
import tempfile
import types
import unittest

from lifetxt import runtime_safety_v2
from lifetxt.notifier import notification_records
from lifetxt.parser import parse_text
from lifetxt.timezone_policy import (
    clock_context,
    current_timezone_name,
    timezone_context,
)
from lifetxt.tui_app import _completion_value


class _FakeState(object):
    def __init__(self, config_data=None):
        self.args = types.SimpleNamespace(config_data=config_data or {})


class CliTimezoneContextWorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)
        self._env_patch = None

    def write(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def config_path(self, data):
        path = os.path.join(self.root, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    @contextlib.contextmanager
    def env_config(self, path):
        previous = os.environ.get("LIFETXT_CONFIG")
        os.environ["LIFETXT_CONFIG"] = path
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("LIFETXT_CONFIG", None)
            else:
                os.environ["LIFETXT_CONFIG"] = previous

    def probe_module(self, seen):
        module = types.SimpleNamespace()

        def main(argv=None):
            seen["timezone"] = current_timezone_name()
            return 0

        module.main = main
        return module

    def test_named_workspace_directive_wins_over_legacy_paths(self):
        self.write("legacy.life.txt", "[ ] T Legacy\n")
        workspace_file = self.write(
            "work.life.txt", "#!timezone: Asia/Tokyo\n[ ] T Work\n"
        )
        config = self.config_path(
            {
                "paths": ["legacy.life.txt"],
                "workspaces": {"work": {"sources": [workspace_file]}},
            }
        )
        seen = {}
        module = self.probe_module(seen)
        runtime_safety_v2.install_cli_timezone_context(module)
        with self.env_config(config):
            module.main(["--workspace", "work", "tui", "--plain"])
        self.assertEqual("Asia/Tokyo", seen["timezone"])

    def test_default_workspace_directive_used_without_explicit_flag(self):
        workspace_file = self.write(
            "work.life.txt", "#!timezone: Pacific/Auckland\n[ ] T Work\n"
        )
        config = self.config_path(
            {
                "default_workspace": "work",
                "workspaces": {"work": {"sources": [workspace_file]}},
            }
        )
        seen = {}
        module = self.probe_module(seen)
        runtime_safety_v2.install_cli_timezone_context(module)
        with self.env_config(config):
            module.main(["tui", "--plain"])
        self.assertEqual("Pacific/Auckland", seen["timezone"])

    def test_legacy_configuration_is_unaffected(self):
        legacy = self.write(
            "legacy.life.txt", "#!timezone: America/New_York\n[ ] T Legacy\n"
        )
        config = self.config_path({"paths": [legacy]})
        seen = {}
        module = self.probe_module(seen)
        runtime_safety_v2.install_cli_timezone_context(module)
        with self.env_config(config):
            module.main(["tui", "--plain"])
        self.assertEqual("America/New_York", seen["timezone"])

    def test_unknown_workspace_name_falls_back_without_raising_in_the_bootstrap(self):
        legacy = self.write(
            "legacy.life.txt", "#!timezone: America/New_York\n[ ] T Legacy\n"
        )
        config = self.config_path({"paths": [legacy]})
        seen = {}
        module = self.probe_module(seen)
        runtime_safety_v2.install_cli_timezone_context(module)
        with self.env_config(config):
            module.main(["--workspace", "does-not-exist", "tui", "--plain"])
        self.assertEqual("America/New_York", seen["timezone"])

    def test_unknown_workspace_name_still_produces_the_clis_own_error(self):
        workspace_file = self.write("work.life.txt", "[ ] T Work\n")
        config = self.config_path(
            {"workspaces": {"work": {"sources": [workspace_file]}}}
        )
        from lifetxt import entrypoint

        with self.env_config(config):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = entrypoint.main(
                    ["--workspace", "does-not-exist", "tui", "--plain"]
                )
        self.assertEqual(1, exit_code)
        self.assertIn("Unknown workspace", stderr.getvalue())


class TuiAndNotifierInheritAmbientTimezoneContextTests(unittest.TestCase):
    """Requirement 2: neither the TUI nor the notifier establishes its own
    timezone context; both must reflect whatever the CLI bootstrap set."""

    def test_tui_done_now_timestamp_reflects_the_ambient_timezone_context(self):
        frozen = datetime.datetime(2026, 1, 1, 0, 30, tzinfo=datetime.timezone.utc)
        state = _FakeState()
        with clock_context(frozen):
            with timezone_context("Asia/Tokyo"):
                tokyo_stamp = _completion_value(state, "now")
            with timezone_context("UTC"):
                utc_stamp = _completion_value(state, "now")
        self.assertEqual("2026-01-01T09:30", tokyo_stamp)
        self.assertEqual("2026-01-01T00:30", utc_stamp)
        self.assertNotEqual(tokyo_stamp, utc_stamp)

    def test_notification_matching_reflects_the_ambient_timezone_context(self):
        items, diagnostics = parse_text(
            "[ ] M Reminder id:msg_001 sender:bob recipient:self "
            "notify_at:2026-01-01T09:00\n"
        )
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        frozen = datetime.datetime(2026, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        with clock_context(frozen):
            with timezone_context("Asia/Tokyo"):
                tokyo_records = notification_records(items)
            with timezone_context("UTC"):
                utc_records = notification_records(items)
        # At the frozen instant, local wall time is 09:00 in Tokyo (+9) but
        # 00:00 in UTC; the notify_at:09:00 item is due only under Tokyo.
        self.assertEqual(1, len(tokyo_records))
        self.assertEqual(0, len(utc_records))


if __name__ == "__main__":
    unittest.main()
