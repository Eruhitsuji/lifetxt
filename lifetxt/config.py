import json
import os
from collections import OrderedDict


DEFAULT_CONFIG_CANDIDATES = (".lifetxt.json", "lifetxt.config.json")


def config_template():
    data = OrderedDict()
    data["paths"] = ["life.txt", ".generated/google_calendar.life.txt"]
    data["write_file"] = "life.txt"
    data["defaults"] = OrderedDict(
        [
            ("person", "self"),
            ("timezone", "Asia/Tokyo"),
        ]
    )
    data["message"] = OrderedDict(
        [
            ("default_sender", "self"),
            ("default_channel", "lifetxt"),
        ]
    )
    data["web"] = OrderedDict(
        [
            ("host", "127.0.0.1"),
            ("port", 8000),
            ("display_refresh", 60),
        ]
    )
    data["sync_ics"] = OrderedDict(
        [
            ("output", ".generated/google_calendar.life.txt"),
            ("cache_dir", ".cache/lifetxt"),
            ("sources", [OrderedDict([("name", "google"), ("url_env", "LIFETXT_GOOGLE_CAL_ICS"), ("tags", ["google"])])]),
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
        data = json.load(handle, object_pairs_hook=OrderedDict)
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
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
            raise ValueError("Config file from LIFETXT_CONFIG does not exist: %s" % env_path)
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


def config_section(config, name):
    value = config.get(name) if config else None
    if isinstance(value, dict):
        return value
    return {}
