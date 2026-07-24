"""Configuration validation, version gating, and credential policy.

Validation is dependency-free by default: it performs the structural and policy
checks that matter for data safety (supported ``config_version``, no committed
plaintext secrets, well-formed workspaces) and, when ``jsonschema`` is
installed, additionally validates the whole document against the published
``config-v1.schema.json``. Every problem is returned as a stable diagnostic so
CLI/doctor/Web callers can decide how to present it.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .config_registry import CONFIG_REGISTRY


# Highest configuration version this build can safely write. Newer documents may
# still be inspected read-only, but writes are refused so a downgrade cannot
# silently drop fields it does not understand.
CONFIG_SCHEMA_VERSION = 1

_SECRET_HINTS = ("password", "token", "secret", "passwd")


def diagnostic(severity, code, message, hint="", path=None):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("hint", hint),
            ("path", path),
        )
    )


def config_version(config):
    """Return the declared config_version, defaulting to 1 when absent."""
    if not isinstance(config, dict):
        return 1
    raw = config.get("config_version")
    if raw is None:
        return 1
    return raw


def is_supported_version(config):
    version = config_version(config)
    return isinstance(version, int) and 1 <= version <= CONFIG_SCHEMA_VERSION


def _is_secret_key(key):
    lowered = str(key).lower()
    if lowered.endswith("_env"):
        return False
    return any(hint in lowered for hint in _SECRET_HINTS)


def _walk_secrets(node, prefix, rows):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "_path":
                continue
            dotted = "%s.%s" % (prefix, key) if prefix else str(key)
            if _is_secret_key(key) and isinstance(value, str) and value.strip():
                rows.append(
                    diagnostic(
                        "error", "C003",
                        "Plaintext secret in configuration key %r." % dotted,
                        "Store the secret in an environment variable and reference it "
                        "with a '%s_env' key holding the variable name." % key,
                        dotted,
                    )
                )
            _walk_secrets(value, dotted, rows)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_secrets(value, "%s[%d]" % (prefix, index), rows)


def _version_diagnostics(config):
    rows = []
    version = config_version(config)
    if not isinstance(version, int):
        rows.append(
            diagnostic(
                "error", "C002",
                "config_version must be an integer, got %r." % (version,),
                "Set config_version to a supported integer (1).",
                "config_version",
            )
        )
        return rows
    if version < 1:
        rows.append(
            diagnostic("error", "C002", "config_version must be >= 1.",
                       "Set config_version to 1.", "config_version")
        )
    elif version > CONFIG_SCHEMA_VERSION:
        rows.append(
            diagnostic(
                "error", "C001",
                "Unsupported config_version %d; this build supports up to %d."
                % (version, CONFIG_SCHEMA_VERSION),
                "Upgrade lifetxt or inspect the file read-only; writes are refused.",
                "config_version",
            )
        )
    return rows


def _deprecation_diagnostics(config):
    rows = []
    for key, entry in CONFIG_REGISTRY.items():
        if "*" in key:
            continue
        if not entry.get("deprecated"):
            continue
        if _has_dotted(config, key):
            replacement = entry.get("replacement")
            hint = ("Use %s instead." % replacement) if replacement else "Remove this key."
            rows.append(
                diagnostic("warning", "C007", "Deprecated config key %r." % key, hint, key)
            )
    return rows


def _has_dotted(config, dotted):
    node = config
    for part in str(dotted).split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _workspace_diagnostics(config):
    rows = []
    workspaces = config.get("workspaces") if isinstance(config, dict) else None
    if workspaces is None:
        return rows
    if not isinstance(workspaces, dict):
        rows.append(
            diagnostic("error", "C005", "'workspaces' must be an object.",
                       "Map each workspace name to a definition object.", "workspaces")
        )
        return rows
    for name, definition in workspaces.items():
        dotted = "workspaces.%s" % name
        sources = None
        if isinstance(definition, dict):
            sources = definition.get("sources", definition.get("paths"))
        elif isinstance(definition, (list, tuple)):
            sources = definition
        if sources is None:
            rows.append(
                diagnostic("error", "C006", "Workspace %r has no sources." % name,
                           "Add a 'sources' array of paths or source objects.", dotted)
            )
            continue
        if not isinstance(sources, (list, tuple)):
            rows.append(
                diagnostic("error", "C006", "Workspace %r sources must be an array." % name,
                           "Use a list of path strings or source objects.", dotted)
            )
            continue
        for index, entry in enumerate(sources):
            if isinstance(entry, str):
                continue
            if isinstance(entry, dict):
                if not entry.get("path"):
                    rows.append(
                        diagnostic("error", "C006",
                                   "Workspace %r source #%d is missing 'path'." % (name, index),
                                   "Every source object needs a 'path'.",
                                   "%s.sources[%d]" % (dotted, index))
                    )
            else:
                rows.append(
                    diagnostic("error", "C006",
                               "Workspace %r source #%d must be a string or object." % (name, index),
                               "Use a path string or a source object.",
                               "%s.sources[%d]" % (dotted, index))
                )
    return rows


def _jsonschema_diagnostics(config):
    try:
        import importlib

        importlib.import_module("jsonschema")
    except Exception:
        return []
    from jsonschema import Draft202012Validator

    from .safety_foundation import schema_bundle

    schema = schema_bundle().get("config-v1.schema.json")
    if not schema:
        return []
    data = OrderedDict((k, v) for k, v in config.items() if k not in ("_path", "_active_workspace"))
    rows = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(part) for part in error.path) or "(root)"
        rows.append(
            diagnostic("error", "C008", "Schema violation at %s: %s" % (path, error.message),
                       "Fix the value to match config-v1.schema.json.", path)
        )
    return rows


def validate_config(config, use_jsonschema=True):
    """Return a list of stable diagnostics for a configuration mapping."""
    config = config or {}
    rows = []
    rows.extend(_version_diagnostics(config))
    _walk_secrets(config, "", rows)
    rows.extend(_workspace_diagnostics(config))
    rows.extend(_deprecation_diagnostics(config))
    if use_jsonschema:
        rows.extend(_jsonschema_diagnostics(config))
    return _dedupe(rows)


def validation_report(config, use_jsonschema=True):
    rows = validate_config(config, use_jsonschema=use_jsonschema)
    return OrderedDict(
        (
            ("ok", not any(row["severity"] == "error" for row in rows)),
            ("writable", is_supported_version(config)
             and not any(row["severity"] == "error" for row in rows)),
            ("config_version", config_version(config)),
            ("diagnostic_count", len(rows)),
            ("diagnostics", rows),
        )
    )


def _dedupe(rows):
    seen = set()
    result = []
    for row in rows:
        key = (row["code"], row["path"], row["message"])
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result
