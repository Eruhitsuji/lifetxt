import json
import os
from collections import OrderedDict


DEFAULT_CONFIG_CANDIDATES = (".lifetxt.json", "lifetxt.config.json")


def config_template():
    data = OrderedDict()
    data["paths"] = ["life.txt", ".generated/google_calendar.life.txt"]
    data["write_file"] = "life.txt"
    data["config"] = OrderedDict(
        [
            ("write", OrderedDict([("require_revision", False)])),
        ]
    )
    data["workspace"] = OrderedDict(
        [
            ("max_total_source_bytes", 67108864),
        ]
    )
    data["user"] = OrderedDict(
        [
            ("name", "self"),
            ("display_name", "Self"),
            ("aliases", ["me"]),
            ("teams", []),
        ]
    )
    data["users"] = OrderedDict(
        [
            (
                "self",
                OrderedDict(
                    [
                        ("display_name", "Self"),
                        ("aliases", ["me"]),
                        ("teams", []),
                    ]
                ),
            )
        ]
    )
    data["teams"] = OrderedDict(
        [
            (
                "default",
                OrderedDict(
                    [
                        ("display_name", "Default Team"),
                        ("members", ["self"]),
                        ("aliases", []),
                    ]
                ),
            )
        ]
    )
    data["tags"] = OrderedDict(
        [
            ("aliases", OrderedDict()),
            ("groups", OrderedDict()),
        ]
    )
    data["groups"] = OrderedDict(
        [
            (
                "oncall",
                OrderedDict(
                    [
                        ("members", ["self"]),
                        ("disabled_members", []),
                        ("visibility", "shared"),
                    ]
                ),
            )
        ]
    )
    data["inbox"] = OrderedDict(
        [
            ("proposals_file", ".cache/lifetxt/proposals.json"),
        ]
    )
    data["ticketing"] = OrderedDict(
        [
            ("id_prefix", "TK"),
            ("trackers", ["bug", "feature", "task", "support"]),
            ("priorities", ["low", "normal", "high", "urgent", "immediate"]),
            ("severities", ["trivial", "minor", "major", "critical", "blocker"]),
            ("components", []),
            ("required_fields", []),
            ("defaults", OrderedDict([("tracker", "task"), ("priority", "normal")])),
        ]
    )
    data["defaults"] = OrderedDict(
        [
            ("person", "self"),
            ("timezone", "Asia/Tokyo"),
        ]
    )
    data["message"] = OrderedDict(
        [
            ("default_sender", ""),
            ("default_channel", "lifetxt"),
        ]
    )
    data["timer"] = OrderedDict(
        [
            ("state_file", "~/.lifetxt_timer.json"),
        ]
    )
    data["tui"] = OrderedDict(
        [
            ("theme", "auto"),
            ("keymap", "vim"),
            ("limit", 10),
            ("agenda_window", "12h"),
        ]
    )
    data["notifications"] = OrderedDict(
        [
            ("enabled", True),
            ("recipient", ""),
            ("lookahead", "0m"),
            ("grace", "2m"),
            ("poll_seconds", 30),
            ("state_file", ".cache/lifetxt/notifications.json"),
            ("snooze_default", "10m"),
            ("desktop", False),
            ("web", True),
            (
                "email",
                OrderedDict(
                    [
                        ("enabled", False),
                        ("to", ""),
                        ("subject", "lifetxt notifications"),
                        ("smtp_host_env", "LIFETXT_SMTP_HOST"),
                        ("smtp_user_env", "LIFETXT_SMTP_USER"),
                        ("smtp_pass_env", "LIFETXT_SMTP_PASS"),
                    ]
                ),
            ),
        ]
    )
    data["api"] = OrderedDict(
        [
            ("id_key", "id"),
            ("allow_id_writes", True),
        ]
    )
    data["ids"] = OrderedDict(
        [
            ("auto", True),
            ("key", "id"),
            (
                "prefixes",
                OrderedDict(
                    [
                        ("T", "task"),
                        ("E", "event"),
                        ("D", "deadline"),
                        ("R", "reminder"),
                        ("H", "habit"),
                        ("N", "note"),
                        ("S", "status"),
                        ("M", "msg"),
                        ("J", "journal"),
                    ]
                ),
            ),
        ]
    )
    data["web"] = OrderedDict(
        [
            ("host", "127.0.0.1"),
            ("port", 8000),
            ("display_refresh", 60),
            ("notification_poll_seconds", 30),
            ("notification_lookahead", "0m"),
            ("default_limit", ""),
            ("default_sort", "line"),
            ("default_order", "asc"),
            ("due_soon_days", 3),
            (
                "theme",
                OrderedDict(
                    [
                        ("accent", "#0e7a65"),
                        ("accent_hover", "#0a6252"),
                        ("accent_soft", "#e0f0ea"),
                        ("accent_ink", "#ffffff"),
                    ]
                ),
            ),
            (
                "dashboard",
                OrderedDict(
                    [
                        (
                            "cards",
                            ["today", "needs_attention", "completions", "projects"],
                        ),
                        (
                            "limits",
                            OrderedDict(
                                [
                                    ("today", 7),
                                    ("needs_attention", 7),
                                    ("projects", 7),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
        ]
    )
    data["views"] = OrderedDict(
        [
            (
                "today",
                OrderedDict(
                    [
                        ("around", "now"),
                        ("window", "1d"),
                        ("sort", "time"),
                        ("order", "asc"),
                    ]
                ),
            ),
            (
                "my_messages",
                OrderedDict(
                    [
                        ("view", "messages"),
                        ("recipient", "self"),
                        ("open_only", "true"),
                        ("sort", "time"),
                        ("order", "asc"),
                    ]
                ),
            ),
            (
                "team_status",
                OrderedDict(
                    [
                        ("view", "status"),
                        ("type", "S"),
                        ("active", "true"),
                        ("refresh", "30"),
                    ]
                ),
            ),
        ]
    )
    data["templates"] = OrderedDict(
        [
            (
                "weekly_review",
                OrderedDict(
                    [
                        (
                            "lines",
                            [
                                "[ ] T Weekly_Review due:{next_monday} project:reflection",
                                "[ ] T Plan_Next_Week due:{next_monday} project:reflection",
                            ],
                        ),
                    ]
                ),
            )
        ]
    )
    data["sync_ics"] = OrderedDict(
        [
            ("output", ".generated/google_calendar.life.txt"),
            ("cache_dir", ".cache/lifetxt"),
            ("generated_paths", [".generated/google_calendar.life.txt"]),
            (
                "sources",
                [
                    OrderedDict(
                        [
                            ("name", "google"),
                            ("url_env", "LIFETXT_GOOGLE_CAL_ICS"),
                            ("tags", ["google"]),
                        ]
                    )
                ],
            ),
        ]
    )
    return data


def config_template_text():
    return json.dumps(config_template(), ensure_ascii=False, indent=2) + "\n"


def load_config(path=None):
    resolved = find_config_path(path)
    if resolved is None:
        return {}
    with open(resolved, "r", encoding="utf-8-sig") as handle:
        text = handle.read()
    try:
        data = json.loads(text, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        raise ValueError(
            "Could not read config: %s\nReason: invalid JSON (%s)" % (resolved, exc)
        )
    if not isinstance(data, dict):
        raise ValueError(
            "Could not read config: %s\nReason: must contain a JSON object" % resolved
        )
    data["_path"] = resolved
    return data


def find_config_path(path=None):
    if path:
        if not os.path.exists(path):
            raise ValueError("Config file does not exist: %s" % path)
        return path

    env_path = os.environ.get("LIFETXT_CONFIG")
    if env_path:
        if not os.path.exists(env_path):
            raise ValueError(
                "Config file from LIFETXT_CONFIG does not exist: %s" % env_path
            )
        return env_path

    for candidate in DEFAULT_CONFIG_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def config_paths(config):
    paths = config.get("paths") if config else None
    if not paths:
        return None
    if isinstance(paths, str):
        return [paths]
    if isinstance(paths, (list, tuple)):
        return [str(path) for path in paths if str(path)]
    raise ValueError("Config paths must be a string or an array of strings.")


def config_write_file(config):
    value = config.get("write_file") if config else None
    return str(value) if value else None


def config_user_name(config):
    user = config_section(config, "user")
    if user.get("name"):
        return str(user.get("name"))
    defaults = config_section(config, "defaults")
    if defaults.get("person"):
        return str(defaults.get("person"))
    message = config_section(config, "message")
    if message.get("default_sender"):
        return str(message.get("default_sender"))
    return "self"


def config_notification_recipient(config):
    notifications = config_section(config, "notifications")
    if notifications.get("recipient"):
        return str(notifications.get("recipient"))
    return config_user_name(config)


def config_user_aliases(config):
    aliases = OrderedDict()
    user_name = config_user_name(config)
    aliases[user_name] = _unique_values([user_name])

    user = config_section(config, "user")
    user_values = [user_name]
    for value in _as_list(user.get("aliases")):
        user_values.append(value)
    aliases[user_name] = _unique_values(user_values)

    users = config_section(config, "users")
    for name, values in users.items():
        if not isinstance(values, dict):
            continue
        expanded = [str(name)]
        for alias in _as_list(values.get("aliases")):
            expanded.append(alias)
        aliases[str(name)] = _unique_values(expanded)
    return aliases


def config_team_members(config):
    teams = OrderedDict()
    for name, values in config_section(config, "teams").items():
        if not isinstance(values, dict):
            continue
        members = []
        for member in _as_list(values.get("members")):
            members.append(member)
        teams[str(name)] = _unique_values(members)

    user_name = config_user_name(config)
    user = config_section(config, "user")
    for team in _as_list(user.get("teams")):
        teams.setdefault(str(team), [])
        if user_name not in teams[str(team)]:
            teams[str(team)].append(user_name)

    for name, values in config_section(config, "users").items():
        if not isinstance(values, dict):
            continue
        for team in _as_list(values.get("teams")):
            teams.setdefault(str(team), [])
            if str(name) not in teams[str(team)]:
                teams[str(team)].append(str(name))
    return teams


def config_team_aliases(config):
    aliases = OrderedDict()
    for name, values in config_section(config, "teams").items():
        expanded = [str(name)]
        if isinstance(values, dict):
            for alias in _as_list(values.get("aliases")):
                expanded.append(alias)
        aliases[str(name)] = _unique_values(expanded)
    return aliases


def config_tag_aliases(config):
    tags = config_section(config, "tags")
    raw_aliases = tags.get("aliases")
    aliases = OrderedDict()
    if isinstance(raw_aliases, dict):
        for name, values in raw_aliases.items():
            expanded = [str(name)]
            for value in _as_list(values):
                expanded.append(value)
            aliases[str(name)] = _unique_values(expanded)
    raw_groups = tags.get("groups")
    if isinstance(raw_groups, dict):
        for name, values in raw_groups.items():
            expanded = aliases.setdefault(str(name), [str(name)])
            for value in _as_list(values):
                if value not in expanded:
                    expanded.append(value)
    return aliases


def config_templates(config):
    templates = OrderedDict()
    for name, value in config_section(config, "templates").items():
        if isinstance(value, dict):
            lines = value.get("lines")
        else:
            lines = value
        templates[str(name)] = [str(line) for line in _as_list(lines)]
    return templates


def config_section(config, name):
    value = config.get(name) if config else None
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(entry) for entry in value if str(entry)]
    return [str(value)]


def _unique_values(values):
    result = []
    for value in values:
        value = str(value)
        if value and value not in result:
            result.append(value)
    return result
