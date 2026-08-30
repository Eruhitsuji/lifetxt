"""Tests for lifetxt.server_report / lifetxt.server_report_cli.

systemctl calls are exercised through a fake `server_update._run` rather
than a real systemd, matching the existing test_server_init.py/
test_server_update.py convention: this suite is about the plan/apply
orchestration logic, not about systemd itself.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import server_report, server_report_cli


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_app_config(root, reports):
    path = os.path.join(root, ".lifetxt.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"paths": ["life.txt"], "reports": reports}, handle)
    return path


_WEEKLY_PROFILE = {
    "weekly": {
        "period": "weekly",
        "output": "reports/{iso_year}-W{iso_week}.md",
        "sections": [{"type": "review"}],
    }
}

_WEEKLY_WITH_EMAIL_PROFILE = {
    "weekly": {
        "period": "weekly",
        "sections": [{"type": "review"}],
        "email": {
            "to": "me@example.com",
            "smtp_host_env": "LIFETXT_SMTP_HOST",
            "smtp_user_env": "LIFETXT_SMTP_USER",
            "smtp_pass_env": "LIFETXT_SMTP_PASS",
        },
    }
}

_ENVIRONMENT_FILE = "/etc/lifetxt/mail.env"


class BuildPlanTests(unittest.TestCase):
    def test_plan_contains_two_unit_files_with_correct_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
        self.assertEqual(len(plan["steps"]), 2)
        service_step, timer_step = plan["steps"]
        self.assertTrue(service_step["path"].endswith("lifetxt-report-weekly.service"))
        self.assertIn("report run weekly --previous", service_step["content"])
        self.assertIn("User=lifetxt", service_step["content"])
        self.assertTrue(timer_step["path"].endswith("lifetxt-report-weekly.timer"))
        self.assertIn("OnCalendar=Mon *-*-* 00:10:00", timer_step["content"])
        self.assertEqual(plan["conflicts"], [])

    def test_unknown_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            with self.assertRaisesRegex(server_report.ServerReportError, "not defined"):
                server_report.build_plan("nope", config_path, "lifetxt", "lifetxt")

    def test_invalid_profile_definition_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(
                tmp, {"weekly": {"period": "not-a-real-period"}}
            )
            with self.assertRaisesRegex(
                server_report.ServerReportError, "failed validation"
            ):
                server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")

    def test_data_root_defaults_to_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
        self.assertIn(tmp, plan["steps"][0]["content"])

    def test_conflict_detected_when_existing_content_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            unit_dir = os.path.join(tmp, "systemd")
            os.makedirs(unit_dir)
            with open(
                os.path.join(unit_dir, "lifetxt-report-weekly.service"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write("not a generated unit\n")
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
        self.assertEqual(len(plan["conflicts"]), 1)

    def test_no_send_email_plan_has_no_environment_file_or_second_exec_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
        self.assertFalse(plan["send_email"])
        self.assertIsNone(plan["environment_file"])
        content = plan["steps"][0]["content"]
        self.assertNotIn("EnvironmentFile", content)
        self.assertEqual(content.count("ExecStart="), 1)

    def test_send_email_adds_environment_file_and_second_exec_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            plan = server_report.build_plan(
                "weekly",
                config_path,
                "lifetxt",
                "lifetxt",
                send_email=True,
                environment_file=_ENVIRONMENT_FILE,
            )
        self.assertTrue(plan["send_email"])
        self.assertEqual(plan["environment_file"], _ENVIRONMENT_FILE)
        content = plan["steps"][0]["content"]
        self.assertIn("EnvironmentFile=%s\n" % _ENVIRONMENT_FILE, content)
        self.assertEqual(content.count("ExecStart="), 2)
        self.assertIn("report run weekly --previous", content)
        self.assertIn("report send weekly --previous", content)
        # The run line must precede the send line so systemd only attempts
        # delivery after local report generation has already succeeded.
        self.assertLess(
            content.index("report run weekly"), content.index("report send weekly")
        )
        # Never the secret contents of the environment file, only its path.
        self.assertNotIn("LIFETXT_SMTP_PASS", content)

    def test_send_email_requires_profile_with_email_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            with self.assertRaisesRegex(
                server_report.ServerReportError, "no .email. configuration"
            ):
                server_report.build_plan(
                    "weekly",
                    config_path,
                    "lifetxt",
                    "lifetxt",
                    send_email=True,
                    environment_file=_ENVIRONMENT_FILE,
                )

    def test_send_email_requires_environment_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            with self.assertRaisesRegex(
                server_report.ServerReportError, "requires --environment-file"
            ):
                server_report.build_plan(
                    "weekly", config_path, "lifetxt", "lifetxt", send_email=True
                )

    def test_environment_file_without_send_email_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            with self.assertRaisesRegex(
                server_report.ServerReportError, "requires --send-email"
            ):
                server_report.build_plan(
                    "weekly",
                    config_path,
                    "lifetxt",
                    "lifetxt",
                    environment_file=_ENVIRONMENT_FILE,
                )

    def test_empty_environment_file_without_send_email_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            with self.assertRaisesRegex(
                server_report.ServerReportError, "requires --send-email"
            ):
                server_report.build_plan(
                    "weekly",
                    config_path,
                    "lifetxt",
                    "lifetxt",
                    environment_file="",
                )

    def test_environment_file_must_be_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            with self.assertRaisesRegex(
                server_report.ServerReportError, "absolute path"
            ):
                server_report.build_plan(
                    "weekly",
                    config_path,
                    "lifetxt",
                    "lifetxt",
                    send_email=True,
                    environment_file="relative/mail.env",
                )

    def test_environment_file_must_not_contain_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            with self.assertRaisesRegex(server_report.ServerReportError, "whitespace"):
                server_report.build_plan(
                    "weekly",
                    config_path,
                    "lifetxt",
                    "lifetxt",
                    send_email=True,
                    environment_file="/etc/lifetxt/my mail.env",
                )


class ApplyInstallTests(unittest.TestCase):
    def test_install_writes_both_unit_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            result = server_report.apply_install(plan)
            self.assertEqual(result["status"], "installed")
            self.assertEqual(len(result["written"]), 2)
            for path in result["written"]:
                self.assertTrue(os.path.exists(path))
            self.assertFalse(result["send_email"])
            self.assertIsNone(result["environment_file"])

    def test_install_with_send_email_reports_it_in_the_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            plan = server_report.build_plan(
                "weekly",
                config_path,
                "lifetxt",
                "lifetxt",
                send_email=True,
                environment_file=_ENVIRONMENT_FILE,
            )
            result = server_report.apply_install(plan)
            self.assertTrue(result["send_email"])
            self.assertEqual(result["environment_file"], _ENVIRONMENT_FILE)
            with open(result["written"][0], "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("EnvironmentFile=%s" % _ENVIRONMENT_FILE, content)
            self.assertEqual(content.count("ExecStart="), 2)

    def test_install_refuses_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            unit_dir = os.path.join(tmp, "systemd")
            os.makedirs(unit_dir)
            with open(
                os.path.join(unit_dir, "lifetxt-report-weekly.service"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write("not a generated unit\n")
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            with self.assertRaises(server_report.ServerReportError):
                server_report.apply_install(plan)

    def test_install_with_enable_runs_systemctl(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            with mock.patch(
                "lifetxt.server_update._run", return_value=_Completed(0)
            ) as fake_run:
                result = server_report.apply_install(plan, enable=True, start=True)
        fake_run.assert_called_once()
        argv = fake_run.call_args[0][0]
        self.assertIn("lifetxt-report-weekly.timer", argv)
        self.assertIn("--now", argv)
        self.assertEqual(len(result["commands"]), 1)

    def test_install_enable_failure_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            with mock.patch(
                "lifetxt.server_update._run",
                return_value=_Completed(1, "", "unit not found"),
            ):
                with self.assertRaises(server_report.ServerReportError):
                    server_report.apply_install(plan, enable=True)


class ApplyRemoveTests(unittest.TestCase):
    def test_remove_deletes_generated_unit_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            server_report.apply_install(plan)
            remove_plan = server_report.build_remove_plan(
                "weekly", os.path.dirname(plan["steps"][0]["path"])
            )
            with mock.patch("lifetxt.server_update._run", return_value=_Completed(0)):
                result = server_report.apply_remove(remove_plan)
        self.assertEqual(len(result["removed"]), 2)
        for path in remove_plan["paths"]:
            self.assertFalse(os.path.exists(path))

    def test_remove_skips_a_file_missing_the_generator_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = os.path.join(tmp, "systemd")
            os.makedirs(unit_dir)
            foreign_path = os.path.join(unit_dir, "lifetxt-report-weekly.service")
            with open(foreign_path, "w", encoding="utf-8") as handle:
                handle.write("not ours\n")
            remove_plan = server_report.build_remove_plan("weekly", unit_dir)
            with mock.patch("lifetxt.server_update._run", return_value=_Completed(0)):
                result = server_report.apply_remove(remove_plan)
            self.assertEqual(result["removed"], [])
            self.assertIn(foreign_path, result["skipped"])
            self.assertTrue(os.path.exists(foreign_path))

    def test_remove_tolerates_systemctl_disable_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            plan = server_report.build_plan("weekly", config_path, "lifetxt", "lifetxt")
            server_report.apply_install(plan)
            remove_plan = server_report.build_remove_plan(
                "weekly", os.path.dirname(plan["steps"][0]["path"])
            )
            with mock.patch(
                "lifetxt.server_update._run",
                side_effect=server_report.server_update.ServerUpdateError(
                    "systemctl not found", step="disable"
                ),
            ):
                result = server_report.apply_remove(remove_plan)
        self.assertEqual(len(result["removed"]), 2)

    def test_remove_missing_file_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            remove_plan = server_report.build_remove_plan("nope", tmp)
            with mock.patch("lifetxt.server_update._run", return_value=_Completed(0)):
                result = server_report.apply_remove(remove_plan)
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["skipped"], [])


def _run_cli(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = server_report_cli.main(argv)
    return out.getvalue(), code


class ServerReportCliTests(unittest.TestCase):
    def test_plan_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            out, code = _run_cli(
                [
                    "plan",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["profile"], "weekly")
        self.assertFalse(
            os.path.exists(
                os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
            )
        )

    def test_install_without_yes_is_a_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            out, code = _run_cli(
                [
                    "install",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", out)
        self.assertFalse(
            os.path.exists(
                os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
            )
        )

    def test_install_with_yes_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            out, code = _run_cli(
                [
                    "install",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(
                os.path.exists(
                    os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
                )
            )

    def test_plan_with_send_email_shows_environment_file_path_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            out, code = _run_cli(
                [
                    "plan",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                    "--send-email",
                    "--environment-file",
                    _ENVIRONMENT_FILE,
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "Scheduled email: enabled (environment file: %s)" % _ENVIRONMENT_FILE,
            out,
        )

    def test_plan_without_send_email_shows_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            out, code = _run_cli(
                [
                    "plan",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("Scheduled email: disabled", out)

    def test_install_with_send_email_writes_environment_file_and_two_exec_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            out, code = _run_cli(
                [
                    "install",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                    "--send-email",
                    "--environment-file",
                    _ENVIRONMENT_FILE,
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertIn("Scheduled email: enabled", out)
            service_path = os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
            with open(service_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("EnvironmentFile=%s" % _ENVIRONMENT_FILE, content)
            self.assertEqual(content.count("ExecStart="), 2)

    def test_send_email_without_environment_file_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_WITH_EMAIL_PROFILE)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = server_report_cli.main(
                    [
                        "plan",
                        "weekly",
                        "--app-config",
                        config_path,
                        "--service-user",
                        "lifetxt",
                        "--service-group",
                        "lifetxt",
                        "--send-email",
                    ]
                )
        self.assertEqual(code, 1)
        self.assertIn("--environment-file", err.getvalue())

    def test_send_email_without_profile_email_config_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = server_report_cli.main(
                    [
                        "plan",
                        "weekly",
                        "--app-config",
                        config_path,
                        "--service-user",
                        "lifetxt",
                        "--service-group",
                        "lifetxt",
                        "--send-email",
                        "--environment-file",
                        _ENVIRONMENT_FILE,
                    ]
                )
        self.assertEqual(code, 1)
        self.assertIn("no `email` configuration", err.getvalue())

    def test_unknown_profile_exits_nonzero_with_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = server_report_cli.main(
                    [
                        "plan",
                        "nope",
                        "--app-config",
                        config_path,
                        "--service-user",
                        "lifetxt",
                        "--service-group",
                        "lifetxt",
                    ]
                )
        self.assertEqual(code, 1)
        self.assertIn("not defined", err.getvalue())

    def test_remove_without_yes_is_a_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_app_config(tmp, _WEEKLY_PROFILE)
            _run_cli(
                [
                    "install",
                    "weekly",
                    "--app-config",
                    config_path,
                    "--service-user",
                    "lifetxt",
                    "--service-group",
                    "lifetxt",
                    "--yes",
                ]
            )
            out, code = _run_cli(["remove", "weekly", "--app-config", config_path])
            self.assertEqual(code, 0)
            self.assertIn("[dry-run]", out)
            self.assertTrue(
                os.path.exists(
                    os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
                )
            )

    def test_entrypoint_routes_server_report_command(self):
        from lifetxt import entrypoint

        with mock.patch(
            "lifetxt.server_report_cli.main", return_value=0
        ) as server_report_main:
            self.assertEqual(
                entrypoint.main(
                    ["server-report", "plan", "weekly", "--app-config", "x"]
                ),
                0,
            )
        server_report_main.assert_called_once_with(
            ["server-report", "plan", "weekly", "--app-config", "x"]
        )


if __name__ == "__main__":
    unittest.main()
