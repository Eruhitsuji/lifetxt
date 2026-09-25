import copy
import tempfile
import unittest

from lifetxt import server_init


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


if __name__ == "__main__":
    unittest.main()
