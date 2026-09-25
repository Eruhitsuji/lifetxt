import copy
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import server_init
from lifetxt import cli


class ServerMaintenanceScheduleTests(unittest.TestCase):
    def test_disabled_by_default_generates_no_maintenance_units(self):
        with tempfile.TemporaryDirectory() as directory:
            config = copy.deepcopy(server_init.DEFAULT_CONFIG)
            config.update({"install_root": directory, "data_root": directory})
            plan = server_init.build_plan(config)
            self.assertFalse(any("lifetxt-maintenance" in step.get("path", "") for step in plan["steps"]))

    def test_plan_mode_generates_persistent_timer_and_non_mutating_service(self):
        with tempfile.TemporaryDirectory() as directory:
            config = copy.deepcopy(server_init.DEFAULT_CONFIG)
            config.update({"install_root": directory, "data_root": directory,
                           "service_user": "lifetxt", "service_group": "lifetxt"})
            config["maintenance_schedule"].update({"enabled": True, "mode": "plan", "project": "web"})
            plan = server_init.build_plan(config)
            service = next(step["content"] for step in plan["steps"] if step.get("path", "").endswith("lifetxt-maintenance.service"))
            timer = next(step["content"] for step in plan["steps"] if step.get("path", "").endswith("lifetxt-maintenance.timer"))
            self.assertIn("maintenance run --mode plan", service)
            self.assertIn("Persistent=true", timer)
            self.assertNotIn("archive --apply", service)

    def test_auto_mode_is_explicit_and_serialized_by_the_same_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            config = copy.deepcopy(server_init.DEFAULT_CONFIG)
            config.update({"install_root": directory, "data_root": directory,
                           "service_user": "lifetxt", "service_group": "lifetxt"})
            config["maintenance_schedule"].update({"enabled": True, "mode": "auto", "project": "web"})
            plan = server_init.build_plan(config)
            service = next(step["content"] for step in plan["steps"] if step.get("path", "").endswith("lifetxt-maintenance.service"))
            self.assertIn("maintenance run --mode auto", service)
            self.assertNotIn("archive --apply", service)

    def test_auto_apply_failure_is_observable_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "life.txt")
            result_path = os.path.join(directory, "result.json")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("[x] T Done project:web id:t1\n")
            args = type("Args", (), {"mode": "auto", "paths": [source], "archive": [],
                                     "project": "web", "emit_plan": os.path.join(directory, "plan.json"),
                                     "result": result_path, "config": None, "workspace": None})()
            health = {"status": "maintenance_recommended", "reasons": [], "mutated": False}
            with mock.patch("lifetxt.storage_health.measure", return_value=health), \
                    mock.patch.object(cli, "command_maintenance_plan", return_value=0), \
                    mock.patch.object(cli, "_project_archive_apply_plan", side_effect=ValueError("stale plan")):
                self.assertEqual(cli.command_maintenance_run(args), 1)
            with open(result_path, encoding="utf-8") as handle:
                report = json.load(handle)
            self.assertEqual(report["outcome"], "blocked")
            self.assertIn("stale plan", report["error"])


if __name__ == "__main__":
    unittest.main()
