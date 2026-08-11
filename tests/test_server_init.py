import argparse
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import cli, server_init


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
