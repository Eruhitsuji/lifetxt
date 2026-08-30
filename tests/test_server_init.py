import argparse
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import cli, server_init
from lifetxt.workspace import iter_workspace_definitions


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _config(root, **overrides):
    data = {
        "install_root": os.path.join(root, "src"),
        "data_root": os.path.join(root, "data"),
        "python": os.path.join(root, "venv", "bin", "python"),
        "service_user": "lifetxt",
        "service_group": "lifetxt",
        "systemd": {"unit_dir": os.path.join(root, "systemd")},
        "service_control": {
            "enabled": True,
            "wrapper_path": os.path.join(root, "sbin", "lifetxt-systemctl"),
            "sudoers_path": os.path.join(root, "sudoers.d", "lifetxt-server-update"),
        },
        "reverse_proxy": {
            "backend": "nginx",
            "nginx_config_path": os.path.join(root, "nginx", "lifetxt.conf"),
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            merged = dict(data[key])
            merged.update(value)
            data[key] = merged
        else:
            data[key] = value
    return data


class ServerInitTests(unittest.TestCase):
    def test_dry_run_does_not_mutate_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            report = server_init.run_server_init(config, yes=False)

            self.assertEqual(report["status"], "dry_run")
            self.assertFalse(os.path.exists(os.path.join(tmp, "data")))
            self.assertTrue(any(step["kind"] == "file" for step in report["steps"]))

    def test_apply_generates_bootstrap_artifacts_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            with mock.patch("lifetxt.server_update._run", return_value=_Completed()):
                with mock.patch(
                    "lifetxt.server_update.check_health",
                    return_value={"ok": True, "status_code": 200},
                ):
                    first = server_init.run_server_init(config, yes=True)
                    second = server_init.run_server_init(config, yes=True)

            self.assertEqual(first["status"], "ready")
            self.assertEqual(second["status"], "ready")
            self.assertEqual(
                "no-op",
                _step(second, os.path.join(tmp, "data", "server-update.json"))[
                    "action"
                ],
            )
            with open(
                os.path.join(tmp, "data", "server-update.json"),
                "r",
                encoding="utf-8",
            ) as handle:
                update_config = json.load(handle)
            self.assertEqual(update_config["installer"], "pip")
            self.assertEqual(
                update_config["service_command"],
                ["sudo", "-n", os.path.join(tmp, "sbin", "lifetxt-systemctl")],
            )
            self.assertIn("lifetxt.service", update_config["services"])
            self.assertIn(
                "proxy_pass http://127.0.0.1:8765",
                _read(os.path.join(tmp, "nginx", "lifetxt.conf")),
            )
            self.assertIn(
                "ExecStart=%s serve --host 127.0.0.1"
                % os.path.join(tmp, "venv", "bin", "lifetxt"),
                _read(os.path.join(tmp, "systemd", "lifetxt.service")),
            )
            self.assertIn(
                "is-active:lifetxt.service",
                _read(os.path.join(tmp, "sbin", "lifetxt-systemctl")),
            )

    def test_existing_different_file_refuses_before_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data"))
            with open(
                os.path.join(tmp, "data", ".lifetxt.json"), "w", encoding="utf-8"
            ) as handle:
                handle.write('{"custom": true}\n')
            config = server_init.load_config(_write_json(tmp, _config(tmp)))

            with mock.patch("lifetxt.server_update._run") as fake_run:
                report = server_init.run_server_init(config, yes=False)
                with self.assertRaises(server_init.ServerInitError):
                    server_init.run_server_init(config, yes=True)

            self.assertEqual(report["status"], "conflict")
            self.assertFalse(fake_run.called)

    def test_uv_plan_uses_uv_pip_install_with_target_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(
                    tmp,
                    _config(
                        tmp,
                        installer="uv",
                        uv_executable="/usr/local/bin/uv",
                        extras=["web", "tui"],
                    ),
                )
            )
            report = server_init.run_server_init(config, yes=False)
            install = next(
                step for step in report["steps"] if step.get("name") == "install"
            )
            self.assertEqual(
                install["argv"][:5],
                [
                    "/usr/local/bin/uv",
                    "pip",
                    "install",
                    "--python",
                    os.path.join(tmp, "venv", "bin", "python"),
                ],
            )
            self.assertIn(os.path.join(tmp, "src") + "[web,tui]", install["argv"])

    def test_requires_explicit_service_user_for_systemd(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _config(tmp, service_user=None)
            with self.assertRaisesRegex(server_init.ServerInitError, "service_user"):
                server_init.load_config(_write_json(tmp, data))

    def test_rejects_generated_unit_and_sudoers_injection_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_user = _config(tmp, service_user="lifetxt\nroot")
            with self.assertRaisesRegex(server_init.ServerInitError, "service_user"):
                server_init.load_config(_write_json(tmp, bad_user))

            bad_wrapper = _config(
                tmp,
                service_control={
                    "wrapper_path": os.path.join(tmp, "bad path", "wrapper")
                },
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "wrapper_path"):
                server_init.load_config(_write_json(tmp, bad_wrapper))

    def test_refuses_data_root_inside_install_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _config(
                tmp,
                install_root=os.path.join(tmp, "src"),
                data_root=os.path.join(tmp, "src", "data"),
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "contain"):
                server_init.load_config(_write_json(tmp, data))

    def test_health_check_runs_only_when_requested_or_service_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            report = server_init.run_server_init(config, yes=False)
            self.assertFalse(any(step["kind"] == "health" for step in report["steps"]))

            start_config = server_init.load_config(
                _write_json(tmp, _config(tmp, systemd={"start": True}))
            )
            start_report = server_init.run_server_init(start_config, yes=False)
            self.assertTrue(
                any(step["kind"] == "health" for step in start_report["steps"])
            )

    def test_cli_json_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_json(tmp, _config(tmp))
            out = io.StringIO()
            args = argparse.Namespace(
                server_config=config_path, yes=False, format="json"
            )
            with mock.patch(
                "lifetxt.cli.write_text", lambda _path, text: out.write(text)
            ):
                code = cli.command_server_init(args)

            self.assertEqual(code, 0)
            report = json.loads(out.getvalue())
            self.assertEqual(report["status"], "dry_run")


class AiWorkspaceGenerationTests(unittest.TestCase):
    """Opt-in server-init AI workspace generation (#500 Phase 6 item 14, #528)."""

    def test_disabled_by_default_produces_the_legacy_config_shape_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            app_config = server_init._application_config(config)

            self.assertEqual(["paths", "write_file", "web"], list(app_config.keys()))
            self.assertNotIn("workspaces", app_config)
            self.assertNotIn("ai_workspace", server_init._server_update_config(config))

    def test_disabled_case_omits_the_ai_inbox_plan_step_and_backup_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            report = server_init.run_server_init(config, yes=False)

            self.assertFalse(
                any("ai-inbox" in (step.get("path") or "") for step in report["steps"])
            )
            self.assertEqual(
                2, len(server_init._server_update_config(config)["backup_paths"])
            )

    def test_enabled_produces_a_workspaces_config_that_resolves_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, ai_workspace={"enabled": True}))
            )
            app_config = server_init._application_config(config)

            self.assertIn("workspaces", app_config)
            self.assertNotIn("paths", app_config)
            self.assertNotIn("write_file", app_config)

            definitions = iter_workspace_definitions(app_config)
            self.assertEqual(["default", "ai"], list(definitions))

            default_def = definitions["default"]
            self.assertEqual(
                os.path.join(tmp, "data", "life.txt"), default_def["write_file"]
            )
            self.assertEqual(
                [
                    os.path.join(tmp, "data", "life.txt"),
                    os.path.join(tmp, "data", ".generated", "google_calendar.life.txt"),
                ],
                default_def["sources"],
            )

            ai_def = definitions["ai"]
            self.assertEqual(
                os.path.join(tmp, "data", "ai-inbox.life.txt"), ai_def["write_file"]
            )
            primary_source = next(
                s
                for s in ai_def["sources"]
                if isinstance(s, dict) and s["role"] == "primary"
            )
            readonly_source = next(
                s
                for s in ai_def["sources"]
                if isinstance(s, dict) and s["role"] == "readonly"
            )
            self.assertTrue(primary_source["writable"])
            self.assertEqual(
                os.path.join(tmp, "data", "ai-inbox.life.txt"), primary_source["path"]
            )
            self.assertFalse(readonly_source["writable"])
            self.assertEqual(
                os.path.join(tmp, "data", "life.txt"), readonly_source["path"]
            )

    def test_enabled_creates_the_empty_ai_inbox_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, ai_workspace={"enabled": True}))
            )
            report = server_init.run_server_init(config, yes=False)
            ai_inbox_path = os.path.join(tmp, "data", "ai-inbox.life.txt")
            step = _step(report, ai_inbox_path)
            self.assertEqual("file", step["kind"])
            self.assertEqual("", step["content"])

            with mock.patch("lifetxt.server_update._run", return_value=_Completed()):
                with mock.patch(
                    "lifetxt.server_update.check_health",
                    return_value={"ok": True, "status_code": 200},
                ):
                    applied = server_init.run_server_init(config, yes=True)
            self.assertEqual("ready", applied["status"])
            self.assertTrue(os.path.exists(ai_inbox_path))
            self.assertEqual("", _read(ai_inbox_path))

    def test_enabled_refuses_a_conflicting_existing_ai_inbox_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data"))
            with open(
                os.path.join(tmp, "data", "ai-inbox.life.txt"), "w", encoding="utf-8"
            ) as handle:
                handle.write("[ ] T Not what server-init would write\n")
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, ai_workspace={"enabled": True}))
            )

            with mock.patch("lifetxt.server_update._run") as fake_run:
                report = server_init.run_server_init(config, yes=False)
                with self.assertRaises(server_init.ServerInitError):
                    server_init.run_server_init(config, yes=True)

            self.assertEqual("conflict", report["status"])
            self.assertFalse(fake_run.called)
            self.assertEqual(
                "[ ] T Not what server-init would write\n",
                _read(os.path.join(tmp, "data", "ai-inbox.life.txt")),
            )

    def test_enabled_adds_the_ai_inbox_path_to_backup_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, ai_workspace={"enabled": True}))
            )
            backup_paths = server_init._server_update_config(config)["backup_paths"]

            self.assertIn(os.path.join(tmp, "data", "ai-inbox.life.txt"), backup_paths)
            self.assertIn(os.path.join(tmp, "data", "life.txt"), backup_paths)
            self.assertIn(os.path.join(tmp, "data", ".lifetxt.json"), backup_paths)
            self.assertEqual(3, len(backup_paths))

    def test_write_file_colliding_with_life_txt_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _config(
                tmp,
                ai_workspace={"enabled": True, "write_file": "life.txt"},
            )
            with self.assertRaisesRegex(
                server_init.ServerInitError, "must not be the same path"
            ):
                server_init.load_config(_write_json(tmp, data))

    def test_custom_write_file_name_is_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(
                    tmp,
                    _config(
                        tmp,
                        ai_workspace={
                            "enabled": True,
                            "write_file": "assistant-inbox.life.txt",
                        },
                    ),
                )
            )
            definitions = iter_workspace_definitions(
                server_init._application_config(config)
            )
            self.assertEqual(
                os.path.join(tmp, "data", "assistant-inbox.life.txt"),
                definitions["ai"]["write_file"],
            )


_ENVIRONMENT_FILE = "/etc/lifetxt/mail.env"

_EMAIL_PROFILES = {
    "weekly": {
        "period": "weekly",
        "output": "reports/{iso_year}-W{iso_week}.md",
        "sections": [{"type": "review"}],
        "email": {
            "to": "team@example.com",
            "smtp_host_env": "LIFETXT_SMTP_HOST",
            "smtp_user_env": "LIFETXT_SMTP_USER",
            "smtp_pass_env": "LIFETXT_SMTP_PASS",
        },
    }
}


def _reporting_config(**overrides):
    profiles = {
        "weekly": {
            "period": "weekly",
            "output": "reports/{iso_year}-W{iso_week}.md",
            "sections": [{"type": "review"}],
        }
    }
    jobs = [
        {
            "name": "weekly",
            "profile": "weekly",
            "schedule": "after-period",
            "at": "00:10",
        }
    ]
    result = {"enabled": True, "profiles": profiles, "jobs": jobs}
    result.update(overrides)
    return result


class ReportingConfigGenerationTests(unittest.TestCase):
    def test_disabled_by_default_generates_no_reports_key_or_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(_write_json(tmp, _config(tmp)))
            self.assertNotIn("reports", server_init._application_config(config))
            plan = server_init.build_plan(config)
            self.assertFalse(
                any(
                    "lifetxt-report-" in (step.get("path") or "")
                    for step in plan["steps"]
                )
            )

    def test_enabled_copies_profiles_into_application_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, reporting=_reporting_config()))
            )
            app_config = server_init._application_config(config)
            self.assertIn("weekly", app_config["reports"])
            self.assertEqual(app_config["reports"]["weekly"]["period"], "weekly")

    def test_invalid_report_profile_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _reporting_config(
                profiles={"weekly": {"period": "not-a-real-period"}}
            )
            with self.assertRaises(server_init.ServerInitError):
                server_init.load_config(_write_json(tmp, _config(tmp, reporting=bad)))

    def test_job_referencing_unknown_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _reporting_config(
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "does-not-exist",
                        "schedule": "after-period",
                        "at": "00:10",
                    }
                ]
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "not defined"):
                server_init.load_config(_write_json(tmp, _config(tmp, reporting=bad)))

    def test_duplicate_job_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _reporting_config(
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "00:10",
                    },
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "01:00",
                    },
                ]
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "duplicate"):
                server_init.load_config(_write_json(tmp, _config(tmp, reporting=bad)))

    def test_invalid_time_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _reporting_config(
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "not-a-time",
                    }
                ]
            )
            with self.assertRaises(server_init.ServerInitError):
                server_init.load_config(_write_json(tmp, _config(tmp, reporting=bad)))

    def test_unsupported_schedule_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _reporting_config(
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "cron-like",
                        "at": "00:10",
                    }
                ]
            )
            with self.assertRaises(server_init.ServerInitError):
                server_init.load_config(_write_json(tmp, _config(tmp, reporting=bad)))

    def test_plan_generates_service_and_timer_units_and_enables_the_timer(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(
                    tmp,
                    _config(
                        tmp,
                        reporting=_reporting_config(),
                        systemd={"enable": True},
                    ),
                )
            )
            plan = server_init.build_plan(config)
            unit_dir = os.path.join(tmp, "systemd")
            service_step = _step(
                {"steps": plan["steps"]},
                os.path.join(unit_dir, "lifetxt-report-weekly.service"),
            )
            self.assertIn("report run weekly --previous", service_step["content"])
            timer_step = _step(
                {"steps": plan["steps"]},
                os.path.join(unit_dir, "lifetxt-report-weekly.timer"),
            )
            self.assertIn("OnCalendar=Mon *-*-* 00:10:00", timer_step["content"])
            self.assertIn("Persistent=true", timer_step["content"])
            enable_names = [
                step["name"]
                for step in plan["steps"]
                if step.get("kind") == "command"
                and "systemd:enable" in step.get("name", "")
            ]
            self.assertIn("systemd:enable:lifetxt-report-weekly.timer", enable_names)

    def test_daily_profile_uses_daily_oncalendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = {
                "daily": {
                    "period": "daily",
                    "output": "d.md",
                    "sections": [{"type": "stats"}],
                }
            }
            jobs = [
                {
                    "name": "daily",
                    "profile": "daily",
                    "schedule": "after-period",
                    "at": "23:50",
                }
            ]
            config = server_init.load_config(
                _write_json(
                    tmp,
                    _config(
                        tmp,
                        reporting={"enabled": True, "profiles": profiles, "jobs": jobs},
                    ),
                )
            )
            plan = server_init.build_plan(config)
            timer_step = _step(
                {"steps": plan["steps"]},
                os.path.join(tmp, "systemd", "lifetxt-report-daily.timer"),
            )
            self.assertIn("OnCalendar=*-*-* 23:50:00", timer_step["content"])

    def test_apply_writes_report_units_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, reporting=_reporting_config()))
            )
            with mock.patch("lifetxt.server_update._run", return_value=_Completed()):
                server_init.run_server_init(config, yes=True)
            unit_path = os.path.join(tmp, "systemd", "lifetxt-report-weekly.service")
            self.assertTrue(os.path.exists(unit_path))

    def test_default_job_has_no_environment_file_or_second_exec_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, reporting=_reporting_config()))
            )
            plan = server_init.build_plan(config)
            service_step = _step(
                {"steps": plan["steps"]},
                os.path.join(tmp, "systemd", "lifetxt-report-weekly.service"),
            )
            self.assertNotIn("EnvironmentFile=", service_step["content"])
            self.assertEqual(service_step["content"].count("ExecStart="), 1)
            self.assertNotIn("report send", service_step["content"])

    def test_send_email_job_generates_environment_file_and_two_exec_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporting = _reporting_config(
                profiles=_EMAIL_PROFILES,
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "00:10",
                        "send_email": True,
                        "environment_file": _ENVIRONMENT_FILE,
                    }
                ],
            )
            config = server_init.load_config(
                _write_json(tmp, _config(tmp, reporting=reporting))
            )
            plan = server_init.build_plan(config)
            service_step = _step(
                {"steps": plan["steps"]},
                os.path.join(tmp, "systemd", "lifetxt-report-weekly.service"),
            )
            content = service_step["content"]
            self.assertIn("EnvironmentFile=%s" % _ENVIRONMENT_FILE, content)
            self.assertEqual(content.count("ExecStart="), 2)
            run_index = content.index("report run weekly --previous")
            send_index = content.index("report send weekly --previous")
            self.assertLess(
                run_index,
                send_index,
                "report run must be scheduled before report send",
            )
            self.assertNotIn("LIFETXT_SMTP_PASS", content)

    def test_send_email_without_environment_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporting = _reporting_config(
                profiles=_EMAIL_PROFILES,
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "00:10",
                        "send_email": True,
                    }
                ],
            )
            with self.assertRaisesRegex(
                server_init.ServerInitError, "environment_file"
            ):
                server_init.load_config(
                    _write_json(tmp, _config(tmp, reporting=reporting))
                )

    def test_send_email_without_profile_email_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporting = _reporting_config(
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "00:10",
                        "send_email": True,
                        "environment_file": _ENVIRONMENT_FILE,
                    }
                ]
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "email"):
                server_init.load_config(
                    _write_json(tmp, _config(tmp, reporting=reporting))
                )

    def test_environment_file_without_send_email_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporting = _reporting_config(
                profiles=_EMAIL_PROFILES,
                jobs=[
                    {
                        "name": "weekly",
                        "profile": "weekly",
                        "schedule": "after-period",
                        "at": "00:10",
                        "environment_file": _ENVIRONMENT_FILE,
                    }
                ],
            )
            with self.assertRaisesRegex(server_init.ServerInitError, "send_email"):
                server_init.load_config(
                    _write_json(tmp, _config(tmp, reporting=reporting))
                )

    def test_report_service_unit_text_is_the_exact_function_server_report_reuses(self):
        # #617's server-init/server-report generator parity guarantee: both
        # commands must share one unit generator, not two independently
        # maintained copies that could drift apart.
        from lifetxt import server_report

        self.assertIs(
            server_report.report_service_unit_text, server_init.report_service_unit_text
        )
        self.assertIs(
            server_report.report_timer_unit_text, server_init.report_timer_unit_text
        )


def _write_json(root, data):
    path = os.path.join(root, "server-init.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return path


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _step(report, path):
    for step in report["steps"]:
        if step.get("path") == path:
            return step
    raise AssertionError("missing step for %s" % path)
