"""Plan-first Ubuntu Server bootstrap for lifetxt deployments.

This module deliberately stays smaller than a configuration-management system:
it turns an explicit JSON configuration into a reviewable plan, writes only the
requested repository-owned artifacts on ``yes=True``, and refuses conflicting
existing files by default.
"""

import json
import os
import re
from collections import OrderedDict

from . import server_update


class ServerInitError(Exception):
    def __init__(self, message, step="server_init", report=None):
        super().__init__(message)
        self.step = step
        self.report = report


DEFAULT_CONFIG = {
    "install_root": None,
    "data_root": None,
    "python": None,
    "installer": "pip",
    "pip_install_args": None,
    "uv_executable": "uv",
    "uv_install_args": None,
    "conda_executable": "conda",
    "conda_env_name": None,
    "conda_env_prefix": None,
    "conda_install_args": None,
    "extras": ["web"],
    "service_user": None,
    "service_group": None,
    "application_config_path": None,
    "life_txt_path": None,
    "server_update_config_path": None,
    "backup_dir": None,
    "lock_path": None,
    "web": {"enabled": True, "bind": "127.0.0.1", "port": 8765},
    "calendar_sync": {"enabled": False},
    "systemd": {
        "enabled": True,
        "unit_dir": None,
        "install_units": True,
        "daemon_reload": False,
        "enable": False,
        "start": False,
        "service_command": ["systemctl"],
    },
    "service_control": {
        "enabled": False,
        "wrapper_path": None,
        "sudoers_path": None,
        "sudo_user": None,
    },
    "reverse_proxy": {"backend": "none", "nginx_config_path": None},
    "ai_workspace": {"enabled": False, "write_file": "ai-inbox.life.txt"},
    "integrity_checks": ["workspace_validate", "check", "ids"],
    "validation_commands": [],
    "health_url": None,
}

_POSIX_ACCOUNT_RE = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$")


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except ValueError as exc:
            raise ServerInitError(
                "Config %s is not valid JSON: %s" % (path, exc),
                step="load_config",
            )
    if not isinstance(data, dict):
        raise ServerInitError(
            "Config %s must contain a JSON object at the top level." % path,
            step="load_config",
        )
    config = dict(DEFAULT_CONFIG)
    config.update(data)
    for key in (
        "web",
        "calendar_sync",
        "systemd",
        "service_control",
        "reverse_proxy",
        "ai_workspace",
    ):
        merged = dict(DEFAULT_CONFIG[key])
        merged.update(config.get(key) or {})
        config[key] = merged
    _validate_config(config, path)
    return config


def _validate_config(config, source_path):
    for key in ("install_root", "data_root"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ServerInitError(
                "Config %s is missing required string key %r." % (source_path, key),
                step="load_config",
            )
    _validate_separate_roots(config["install_root"], config["data_root"], source_path)
    server_update_config = _server_update_config(config)
    try:
        server_update._validate_argv_list(
            config.get("validation_commands"), "validation_commands", source_path
        )
        server_update._normalize_integrity_checks(
            server_update_config, source_path=source_path
        )
        _validate_server_update_config(server_update_config, source_path)
    except server_update.ServerUpdateError as exc:
        raise ServerInitError(str(exc), step=exc.step)
    if config["web"].get("enabled") and config["web"].get("bind") != "127.0.0.1":
        raise ServerInitError(
            "Config %s: web.bind must remain 127.0.0.1 for server-init." % source_path,
            step="load_config",
        )
    if config["systemd"].get("enabled") and (
        not config.get("service_user") or not config.get("service_group")
    ):
        raise ServerInitError(
            "Config %s: service_user and service_group are required when "
            "systemd.enabled is true; server-init does not assume a username."
            % source_path,
            step="load_config",
        )
    if config.get("service_user"):
        _validate_posix_account(config["service_user"], "service_user", source_path)
    if config.get("service_group"):
        _validate_posix_account(config["service_group"], "service_group", source_path)
    if config["service_control"].get("sudo_user"):
        _validate_posix_account(
            config["service_control"]["sudo_user"],
            "service_control.sudo_user",
            source_path,
        )
    _validate_optional_safe_path(
        config["systemd"].get("unit_dir"), "systemd.unit_dir", source_path
    )
    _validate_optional_safe_path(
        config["reverse_proxy"].get("nginx_config_path"),
        "reverse_proxy.nginx_config_path",
        source_path,
    )
    if config["service_control"].get("enabled"):
        _validate_required_absolute_nowhitespace_path(
            config["service_control"].get("wrapper_path"),
            "service_control.wrapper_path",
            source_path,
        )
        _validate_required_absolute_nowhitespace_path(
            config["service_control"].get("sudoers_path"),
            "service_control.sudoers_path",
            source_path,
        )
    if config["reverse_proxy"].get("backend") not in ("none", "nginx"):
        raise ServerInitError(
            'Config %s: reverse_proxy.backend must be "none" or "nginx".' % source_path,
            step="load_config",
        )
    if config.get("extras") is not None and (
        not isinstance(config["extras"], list)
        or not all(isinstance(v, str) for v in config["extras"])
    ):
        raise ServerInitError(
            "Config %s: extras must be a JSON array of strings." % source_path,
            step="load_config",
        )
    if config["ai_workspace"].get("enabled"):
        _validate_optional_safe_path(
            config["ai_workspace"].get("write_file"),
            "ai_workspace.write_file",
            source_path,
        )
        if os.path.normcase(
            os.path.normpath(_ai_inbox_path(config))
        ) == os.path.normcase(os.path.normpath(_life_txt_path(config))):
            raise ServerInitError(
                "Config %s: ai_workspace.write_file must not be the same path as "
                "life_txt_path." % source_path,
                step="load_config",
            )


def _validate_single_line(value, key, source_path):
    if any(ch in value for ch in "\r\n\0"):
        raise ServerInitError(
            "Config %s: %s must not contain control characters." % (source_path, key),
            step="load_config",
        )


def _validate_posix_account(value, key, source_path):
    _validate_single_line(value, key, source_path)
    if not _POSIX_ACCOUNT_RE.match(value):
        raise ServerInitError(
            "Config %s: %s must be an explicit POSIX account/group name."
            % (source_path, key),
            step="load_config",
        )


def _validate_optional_safe_path(value, key, source_path):
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise ServerInitError(
            "Config %s: %s must be a non-empty string." % (source_path, key),
            step="load_config",
        )
    _validate_single_line(value, key, source_path)


def _validate_required_absolute_nowhitespace_path(value, key, source_path):
    _validate_optional_safe_path(value, key, source_path)
    if not os.path.isabs(value):
        raise ServerInitError(
            "Config %s: %s must be an absolute path." % (source_path, key),
            step="load_config",
        )
    if any(ch.isspace() for ch in value):
        raise ServerInitError(
            "Config %s: %s must not contain whitespace." % (source_path, key),
            step="load_config",
        )


def _validate_separate_roots(install_root, data_root, source_path):
    install_abs = os.path.abspath(install_root)
    data_abs = os.path.abspath(data_root)
    if install_abs == data_abs:
        raise ServerInitError(
            "Config %s: install_root and data_root must be separate paths."
            % source_path,
            step="load_config",
        )
    try:
        common = os.path.commonpath([install_abs, data_abs])
    except ValueError:
        return
    if common == install_abs or common == data_abs:
        raise ServerInitError(
            "Config %s: install_root and data_root must not contain each other."
            % source_path,
            step="load_config",
        )


def _validate_server_update_config(config, source_path):
    if not config.get("python") and config.get("installer") != "conda-pip":
        raise ServerInitError(
            'Config %s is missing required key "python".' % source_path,
            step="load_config",
        )
    if config.get("installer") not in ("pip", "uv", "conda-pip"):
        raise ServerInitError(
            'Config %s: installer must be "pip", "uv", or "conda-pip".' % source_path,
            step="load_config",
        )
    if config.get("conda_env_name") and config.get("conda_env_prefix"):
        raise ServerInitError(
            "Config %s: conda_env_name and conda_env_prefix are mutually exclusive."
            % source_path,
            step="load_config",
        )
    if config.get("installer") == "conda-pip" and not (
        config.get("conda_env_name") or config.get("conda_env_prefix")
    ):
        raise ServerInitError(
            "Config %s: conda-pip requires conda_env_name or conda_env_prefix."
            % source_path,
            step="load_config",
        )
    server_update._validate_argv(
        config.get("service_command"), "service_command", source_path
    )
    server_update._validate_argv_list(
        config.get("service_preflight_commands"),
        "service_preflight_commands",
        source_path,
    )
    server_update._validate_argv_list(
        config.get("validation_commands"), "validation_commands", source_path
    )
    server_update._normalize_integrity_checks(config, source_path=source_path)


def _path(config, key, default_name):
    return config.get(key) or os.path.join(config["data_root"], default_name)


def _life_txt_path(config):
    return _path(config, "life_txt_path", "life.txt")


def _ai_inbox_path(config):
    """Resolved AI-workspace write target, only meaningful when
    `ai_workspace.enabled` is true. Mirrors `_path()`'s own
    explicit-value-or-data-root-relative-default resolution, scoped to the
    nested `ai_workspace` section rather than a top-level config key."""
    write_file = config["ai_workspace"].get("write_file") or "ai-inbox.life.txt"
    if os.path.isabs(write_file):
        return write_file
    return os.path.join(config["data_root"], write_file)


def _application_config_path(config):
    return _path(config, "application_config_path", ".lifetxt.json")


def _server_update_config_path(config):
    return _path(config, "server_update_config_path", "server-update.json")


def _backup_dir(config):
    return config.get("backup_dir") or os.path.join(
        config["data_root"], "backups", "server-update"
    )


def _lock_path(config):
    return config.get("lock_path") or os.path.join(
        config["data_root"], ".locks", "server-update.lock"
    )


def _install_args(config):
    extras = config.get("extras") or []
    target = config["install_root"]
    if extras:
        target += "[" + ",".join(extras) + "]"
    return ["-e", target]


def _server_update_config(config):
    systemd = config.get("systemd") or {}
    service_control = config.get("service_control") or {}
    calendar = config.get("calendar_sync") or {}
    web = config.get("web") or {}
    services = []
    if systemd.get("enabled") and web.get("enabled"):
        services.append("lifetxt.service")
    if systemd.get("enabled") and calendar.get("enabled"):
        services.append("lifetxt-sync-ics.timer")
    service_command = (
        ["sudo", "-n", service_control["wrapper_path"]]
        if service_control.get("enabled") and service_control.get("wrapper_path")
        else list(systemd.get("service_command") or ["systemctl"])
    )
    preflight = (
        [["sudo", "-n", "-l", service_control["wrapper_path"]]]
        if service_control.get("enabled") and service_control.get("wrapper_path")
        else []
    )
    backup_paths = [_life_txt_path(config), _application_config_path(config)]
    if config["ai_workspace"].get("enabled"):
        backup_paths.append(_ai_inbox_path(config))
    config_out = OrderedDict(
        [
            ("install_root", config["install_root"]),
            ("python", config.get("python")),
            ("life_txt_path", _life_txt_path(config)),
            ("backup_paths", backup_paths),
            ("backup_dir", _backup_dir(config)),
            ("lock_path", _lock_path(config)),
            ("services", services),
            ("service_command", service_command),
            ("service_preflight_commands", preflight),
            ("integrity_checks", config.get("integrity_checks") or []),
            ("application_config", _application_config_path(config)),
            (
                "health_url",
                config.get("health_url")
                or (
                    "http://127.0.0.1:%s/api/health" % web.get("port")
                    if web.get("enabled")
                    else None
                ),
            ),
            ("installer", config.get("installer") or "pip"),
            (
                "pip_install_args",
                config.get("pip_install_args") or _install_args(config),
            ),
            ("uv_executable", config.get("uv_executable") or "uv"),
            ("uv_install_args", config.get("uv_install_args") or _install_args(config)),
            ("conda_executable", config.get("conda_executable") or "conda"),
            ("conda_env_name", config.get("conda_env_name")),
            ("conda_env_prefix", config.get("conda_env_prefix")),
            (
                "conda_install_args",
                config.get("conda_install_args") or _install_args(config),
            ),
            ("validation_commands", config.get("validation_commands") or []),
        ]
    )
    return config_out


def _application_config(config):
    generated = os.path.join(
        config["data_root"], ".generated", "google_calendar.life.txt"
    )
    web_section = OrderedDict(
        [("host", "127.0.0.1"), ("port", config["web"].get("port", 8765))]
    )
    if not config["ai_workspace"].get("enabled"):
        return OrderedDict(
            [
                ("paths", [_life_txt_path(config), generated]),
                ("write_file", _life_txt_path(config)),
                ("web", web_section),
            ]
        )
    # ai_workspace.enabled switches to the `workspaces`-shaped config #500's
    # own "AI-safe workspaces" example describes: `default` resolves to
    # exactly what the legacy shape above would have (same sources, same
    # write target), and `ai` adds a read-only reference to the primary
    # life.txt plus a confined, writable AI-inbox source. See
    # lifetxt.workspace.iter_workspace_definitions() for how this is read.
    return OrderedDict(
        [
            (
                "workspaces",
                OrderedDict(
                    [
                        (
                            "default",
                            OrderedDict(
                                [
                                    (
                                        "sources",
                                        [_life_txt_path(config), generated],
                                    ),
                                    ("write_file", _life_txt_path(config)),
                                ]
                            ),
                        ),
                        (
                            "ai",
                            OrderedDict(
                                [
                                    (
                                        "sources",
                                        [
                                            OrderedDict(
                                                [
                                                    ("path", _life_txt_path(config)),
                                                    ("role", "readonly"),
                                                    ("writable", False),
                                                ]
                                            ),
                                            OrderedDict(
                                                [
                                                    ("path", _ai_inbox_path(config)),
                                                    ("role", "primary"),
                                                    ("writable", True),
                                                ]
                                            ),
                                        ],
                                    ),
                                    ("write_file", _ai_inbox_path(config)),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            ("web", web_section),
        ]
    )


def _lifetxt_executable(config):
    python = config.get("python")
    if not python:
        return "lifetxt"
    return os.path.join(os.path.dirname(python), "lifetxt")


def _systemd_web_unit(config):
    web = config["web"]
    return """# Generated by lifetxt server-init from contrib/systemd/lifetxt.service.
[Unit]
Description=lifetxt Web UI / API (loopback only)
Documentation=https://github.com/Eruhitsuji/lifetxt/blob/main/docs/deployment/ubuntu-server.md
After=network.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={data_root}
ExecStart={exe} serve --host 127.0.0.1 --port {port} --config {app_config}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={data_root}

[Install]
WantedBy=multi-user.target
""".format(
        user=config["service_user"],
        group=config["service_group"],
        data_root=config["data_root"],
        exe=_lifetxt_executable(config),
        port=int(web.get("port", 8765)),
        app_config=_application_config_path(config),
    )


def _sync_service_unit(config):
    generated = os.path.join(
        config["data_root"], ".generated", "google_calendar.life.txt"
    )
    cache = os.path.join(config["data_root"], ".cache", "lifetxt")
    return """# Generated by lifetxt server-init from contrib/systemd/lifetxt-sync-ics.service.
[Unit]
Description=lifetxt Calendar / ICS sync
Documentation=https://github.com/Eruhitsuji/lifetxt/blob/main/docs/deployment/ubuntu-server.md

[Service]
Type=oneshot
User={user}
Group={group}
WorkingDirectory={data_root}
EnvironmentFile={env_file}
ExecStart={exe} sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o {generated} --cache-dir {cache} --merge-existing --soft-delete-missing --tag google
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={data_root}
""".format(
        user=config["service_user"],
        group=config["service_group"],
        data_root=config["data_root"],
        env_file=os.path.join(config["data_root"], "lifetxt.env"),
        exe=_lifetxt_executable(config),
        generated=generated,
        cache=cache,
    )


def _sync_timer_unit():
    return """# Generated by lifetxt server-init from contrib/systemd/lifetxt-sync-ics.timer.
[Unit]
Description=Periodic timer for lifetxt-sync-ics.service
Documentation=https://github.com/Eruhitsuji/lifetxt/blob/main/docs/deployment/ubuntu-server.md

[Timer]
OnBootSec=5m
OnUnitActiveSec=30m
Persistent=true
Unit=lifetxt-sync-ics.service

[Install]
WantedBy=timers.target
"""


def _service_wrapper(config):
    units = ["lifetxt.service"]
    if config["calendar_sync"].get("enabled"):
        units.append("lifetxt-sync-ics.timer")
    cases = []
    for unit in units:
        cases.extend(
            [
                "  is-active:%s|stop:%s|start:%s) ;;" % (unit, unit, unit),
            ]
        )
    return """#!/bin/sh
case "$1:$2" in
{cases}
  *) echo "refusing service action: $1 $2" >&2; exit 64 ;;
esac
exec /bin/systemctl --no-ask-password "$1" "$2"
""".format(cases="\n".join(cases))


def _sudoers(config):
    service_control = config["service_control"]
    sudo_user = service_control.get("sudo_user") or config.get("service_user")
    return "%s ALL=(root) NOPASSWD: %s\n" % (sudo_user, service_control["wrapper_path"])


def _nginx_config(config):
    port = int(config["web"].get("port", 8765))
    return """# Generated by lifetxt server-init from contrib/nginx/lifetxt.conf.example.
# Replace REPLACE_ME placeholders before enabling this site.
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name REPLACE_ME.example.com;

    ssl_certificate     /etc/letsencrypt/live/REPLACE_ME.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/REPLACE_ME.example.com/privkey.pem;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 1h;
        proxy_buffering off;
    }}
}}
""".format(port=port)


def _json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_plan(config):
    plan = OrderedDict([("status", "planned"), ("steps", [])])
    steps = plan["steps"]

    for path in (
        config["install_root"],
        config["data_root"],
        os.path.join(config["data_root"], "archive"),
        os.path.join(config["data_root"], ".generated"),
        os.path.join(config["data_root"], ".locks"),
        _backup_dir(config),
    ):
        steps.append({"kind": "directory", "path": path, "mode": "0750"})

    steps.append(
        {"kind": "file", "path": _life_txt_path(config), "mode": "0640", "content": ""}
    )
    if config["ai_workspace"].get("enabled"):
        steps.append(
            {
                "kind": "file",
                "path": _ai_inbox_path(config),
                "mode": "0640",
                "content": "",
            }
        )
    steps.append(
        {
            "kind": "file",
            "path": _application_config_path(config),
            "mode": "0640",
            "content": _json_text(_application_config(config)),
        }
    )
    steps.append(
        {
            "kind": "file",
            "path": _server_update_config_path(config),
            "mode": "0640",
            "content": _json_text(_server_update_config(config)),
        }
    )
    if config["systemd"].get("enabled") and config["systemd"].get("install_units"):
        unit_dir = config["systemd"].get("unit_dir") or os.path.join(
            config["data_root"], "systemd"
        )
        if config["web"].get("enabled"):
            steps.append(
                {
                    "kind": "file",
                    "path": os.path.join(unit_dir, "lifetxt.service"),
                    "mode": "0644",
                    "content": _systemd_web_unit(config),
                }
            )
        if config["calendar_sync"].get("enabled"):
            steps.append(
                {
                    "kind": "file",
                    "path": os.path.join(unit_dir, "lifetxt-sync-ics.service"),
                    "mode": "0644",
                    "content": _sync_service_unit(config),
                }
            )
            steps.append(
                {
                    "kind": "file",
                    "path": os.path.join(unit_dir, "lifetxt-sync-ics.timer"),
                    "mode": "0644",
                    "content": _sync_timer_unit(),
                }
            )
    if config["service_control"].get("enabled"):
        sc = config["service_control"]
        if not sc.get("wrapper_path") or not sc.get("sudoers_path"):
            raise ServerInitError(
                "service_control.enabled requires wrapper_path and sudoers_path.",
                step="build_plan",
            )
        steps.append(
            {
                "kind": "file",
                "path": sc["wrapper_path"],
                "mode": "0755",
                "content": _service_wrapper(config),
            }
        )
        steps.append(
            {
                "kind": "file",
                "path": sc["sudoers_path"],
                "mode": "0440",
                "content": _sudoers(config),
            }
        )
    if config["reverse_proxy"].get("backend") == "nginx":
        nginx_path = config["reverse_proxy"].get("nginx_config_path")
        if not nginx_path:
            raise ServerInitError(
                "reverse_proxy.backend=nginx requires nginx_config_path.",
                step="build_plan",
            )
        steps.append(
            {
                "kind": "file",
                "path": nginx_path,
                "mode": "0644",
                "content": _nginx_config(config),
            }
        )

    install_config = _server_update_config(config)
    steps.append(
        {
            "kind": "command",
            "name": "install",
            "argv": server_update.install_command(install_config),
            "cwd": config["install_root"],
        }
    )
    for entry in server_update._normalize_integrity_checks(install_config):
        builder = server_update._INTEGRITY_CHECK_BUILDERS[entry["name"]]
        argv = server_update._lifetxt_command_prefix(
            server_update.python_command_prefix(install_config),
            entry.get("application_config"),
        ) + builder(entry)
        steps.append(
            {"kind": "command", "name": "integrity:%s" % entry["name"], "argv": argv}
        )
    should_check_health = bool(config.get("health_url")) or bool(
        config["systemd"].get("start")
    )
    if install_config.get("health_url") and should_check_health:
        steps.append({"kind": "health", "url": install_config["health_url"]})
    if config["systemd"].get("enabled") and config["systemd"].get("daemon_reload"):
        steps.append(
            {
                "kind": "command",
                "name": "systemd:daemon-reload",
                "argv": list(config["systemd"].get("service_command") or ["systemctl"])
                + ["daemon-reload"],
            }
        )
    if config["systemd"].get("enabled") and (
        config["systemd"].get("enable") or config["systemd"].get("start")
    ):
        action = "--now" if config["systemd"].get("start") else ""
        for unit in install_config["services"]:
            argv = list(config["systemd"].get("service_command") or ["systemctl"]) + [
                "enable"
            ]
            if action:
                argv.append(action)
            argv.append(unit)
            steps.append(
                {"kind": "command", "name": "systemd:enable:%s" % unit, "argv": argv}
            )
    for index, entry in enumerate(config.get("validation_commands") or []):
        name, argv, cwd, timeout = server_update._command_entry(entry, index)
        steps.append(
            {
                "kind": "command",
                "name": "validation:%s" % name,
                "argv": argv,
                "cwd": cwd,
                "timeout": timeout,
            }
        )
    return plan


def _classify_path(step):
    path = step["path"]
    if step["kind"] == "directory":
        if os.path.isfile(path):
            return "conflict"
        if os.path.isdir(path):
            return "no-op"
        return "create"
    content = step["content"]
    if os.path.isdir(path):
        return "conflict"
    if not os.path.exists(path):
        return "create"
    with open(path, "r", encoding="utf-8") as handle:
        existing = handle.read()
    return "no-op" if existing == content else "conflict"


def annotate_plan(plan):
    conflicts = []
    for step in plan["steps"]:
        if step["kind"] in ("directory", "file"):
            step["action"] = _classify_path(step)
            if step["action"] == "conflict":
                conflicts.append(step["path"])
    plan["conflicts"] = conflicts
    return plan


def _apply_directory(step):
    os.makedirs(step["path"], exist_ok=True)
    if os.name != "nt":
        os.chmod(step["path"], int(step.get("mode", "0750"), 8))


def _apply_file(step):
    path = step["path"]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if step.get("action") == "no-op":
        return
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    mode = int(step.get("mode", "0640"), 8)
    create_mode = 0o600 if os.name == "nt" else mode
    fd = os.open(path, flags, create_mode)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(step["content"])
    if os.name != "nt":
        os.chmod(path, mode)


def apply_plan(plan, command_timeout=30):
    if plan.get("conflicts"):
        raise ServerInitError(
            "Refusing to apply server-init plan because existing path(s) differ: %s"
            % ", ".join(plan["conflicts"]),
            step="preflight",
            report=plan,
        )
    for step in plan["steps"]:
        if step["kind"] == "directory" and step.get("action") == "create":
            _apply_directory(step)
        elif step["kind"] == "file" and step.get("action") == "create":
            _apply_file(step)
        elif step["kind"] == "command":
            result = server_update._run(
                step["argv"],
                step="command:%s" % step.get("name", "command"),
                cwd=step.get("cwd"),
                timeout=step.get("timeout") or command_timeout,
            )
            if result.returncode != 0:
                raise ServerInitError(
                    "%s failed: %s"
                    % (
                        step.get("name", "command"),
                        (result.stderr or result.stdout or "").strip(),
                    ),
                    step="command",
                    report=plan,
                )
        elif step["kind"] == "health":
            result = server_update.check_health(step["url"], command_timeout)
            step["result"] = result
            if result and not result.get("ok"):
                raise ServerInitError(
                    "Health check failed: %s" % result.get("error"),
                    step="health",
                    report=plan,
                )


def run_server_init(config, yes=False):
    plan = annotate_plan(build_plan(config))
    if plan.get("conflicts"):
        plan["status"] = "conflict"
        plan["message"] = (
            "server-init refused conflicting existing path(s): %s"
            % ", ".join(plan["conflicts"])
        )
        if yes:
            raise ServerInitError(plan["message"], step="preflight", report=plan)
        return plan
    if not yes:
        plan["status"] = "dry_run"
        plan["message"] = (
            "Dry run only. Re-run with --yes to create or change the planned paths."
        )
        return plan
    apply_plan(plan)
    plan["status"] = "ready"
    plan["message"] = "Server deployment ready."
    return plan
