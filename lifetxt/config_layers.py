"""Configuration precedence, effective values, provenance, and dotted access.

The precedence model, from lowest to highest priority:

1. built-in defaults (from the config template)
2. the loaded configuration file (``.lifetxt.json`` / ``--config`` / ``LIFETXT_CONFIG``)
3. the selected named profile (``profiles.<name>``)
4. environment overrides (an explicit, documented allowlist)

CLI flags are applied by the caller after this layer resolves, and remain the
highest-priority source. ``effective_config`` returns both the merged mapping
and a provenance map keyed by dotted path so ``config effective`` /
``config sources`` can explain where every value came from without exposing
secret values.
"""

from __future__ import unicode_literals

import copy
import os
from collections import OrderedDict

from .config import config_template


# Environment overrides are intentionally explicit. Each entry maps an
# environment variable to the dotted config path it overrides. Only non-secret,
# behavior-affecting values live here; secrets stay as ``*_env`` references.
ENV_OVERRIDES = OrderedDict(
    (
        ("LIFETXT_TIMEZONE", "defaults.timezone"),
        ("LIFETXT_PERSON", "defaults.person"),
        ("LIFETXT_WEB_HOST", "web.host"),
        ("LIFETXT_WEB_PORT", "web.port"),
        ("LIFETXT_DEFAULT_WORKSPACE", "default_workspace"),
    )
)

# Keys whose values must never be printed in effective output, sources, or
# support bundles. Secret material is referenced by environment-variable name
# through ``*_env`` fields; those references are safe to display.
_SECRET_LEAF_HINTS = ("password", "token", "secret", "pass")


def _is_secret_leaf(key):
    lowered = str(key).lower()
    if lowered.endswith("_env"):
        return False
    return any(hint in lowered for hint in _SECRET_LEAF_HINTS)


def _strip_private(config):
    if isinstance(config, dict):
        return OrderedDict(
            (key, _strip_private(value))
            for key, value in config.items()
            if key != "_path"
        )
    if isinstance(config, list):
        return [_strip_private(value) for value in config]
    return config


def _deep_merge(base, overlay, provenance, source_label, prefix=""):
    for key, value in overlay.items():
        if key == "_path":
            continue
        dotted = "%s.%s" % (prefix, key) if prefix else str(key)
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value, provenance, source_label, dotted)
        else:
            base[key] = copy.deepcopy(value)
            provenance[dotted] = source_label
            if isinstance(value, dict):
                _record_nested_provenance(value, provenance, source_label, dotted)


def _record_nested_provenance(value, provenance, source_label, prefix):
    for key, child in value.items():
        dotted = "%s.%s" % (prefix, key)
        provenance[dotted] = source_label
        if isinstance(child, dict):
            _record_nested_provenance(child, provenance, source_label, dotted)


def effective_config(config, profile=None, env=None, include_defaults=True):
    """Return ``(merged, provenance)`` after applying the precedence model."""
    if env is None:
        env = os.environ
    merged = OrderedDict()
    provenance = OrderedDict()

    if include_defaults:
        defaults = _strip_private(config_template())
        _deep_merge(merged, defaults, provenance, "builtin-default")

    config = config or {}
    config_label = (
        "config:%s" % config.get("_path") if config.get("_path") else "config"
    )
    _deep_merge(merged, _strip_private(config), provenance, config_label)

    if profile:
        profiles = config.get("profiles") if isinstance(config, dict) else None
        if isinstance(profiles, dict) and str(profile) in profiles:
            profile_data = profiles[str(profile)]
            if isinstance(profile_data, dict):
                _deep_merge(
                    merged,
                    _strip_private(profile_data),
                    provenance,
                    "profile:%s" % profile,
                )

    for env_name, dotted in ENV_OVERRIDES.items():
        if env_name in env and env[env_name] != "":
            set_dotted(merged, dotted, env[env_name])
            provenance[dotted] = "env:%s" % env_name

    return merged, provenance


def get_dotted(config, dotted, default=None):
    """Read a value at ``a.b.c``; returns ``default`` when absent."""
    node = config
    for part in str(dotted).split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_dotted(config, dotted, value):
    """Set ``a.b.c`` to ``value``, creating intermediate objects."""
    parts = str(dotted).split(".")
    node = config
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = OrderedDict()
            node[part] = child
        node = child
    node[parts[-1]] = value
    return config


def unset_dotted(config, dotted):
    """Remove ``a.b.c`` if present. Returns True when something was removed."""
    parts = str(dotted).split(".")
    node = config
    for part in parts[:-1]:
        child = node.get(part) if isinstance(node, dict) else None
        if not isinstance(child, dict):
            return False
        node = child
    if isinstance(node, dict) and parts[-1] in node:
        del node[parts[-1]]
        return True
    return False


def redacted_effective(config, profile=None, env=None):
    """Effective config with secret leaves masked, for display/export."""
    merged, provenance = effective_config(config, profile=profile, env=env)
    return _redact(merged), provenance


def _redact(value, key=None):
    if isinstance(value, dict):
        return OrderedDict((k, _redact(v, k)) for k, v in value.items())
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if key is not None and _is_secret_leaf(key) and value:
        return "***redacted***"
    return value


def flatten_provenance(config, profile=None, env=None):
    """Return ``[(dotted, value, source)]`` rows for ``config sources``."""
    merged, provenance = redacted_effective(config, profile=profile, env=env)
    rows = []

    def walk(node, prefix):
        if isinstance(node, dict):
            for key, value in node.items():
                dotted = "%s.%s" % (prefix, key) if prefix else str(key)
                if isinstance(value, dict) and value:
                    walk(value, dotted)
                else:
                    rows.append(
                        (dotted, value, provenance.get(dotted, "builtin-default"))
                    )
        else:
            rows.append((prefix, node, provenance.get(prefix, "builtin-default")))

    walk(merged, "")
    rows.sort(key=lambda row: row[0])
    return rows
