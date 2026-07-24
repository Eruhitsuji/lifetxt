"""Authoritative metadata registry for configuration keys.

``config explain PATH`` and generated documentation both read from this single
registry so descriptions, defaults, and security notes never drift between the
CLI and the docs. Every entry is intentionally curated; unknown keys resolve to
a generic "no registered metadata" answer rather than silently succeeding.
"""

from __future__ import unicode_literals

from collections import OrderedDict


def _entry(type_, default, description, required=False, secret=False,
           env=None, restart_required=False, allowed=None, since="0.1.0"):
    return OrderedDict(
        (
            ("type", type_),
            ("default", default),
            ("description", description),
            ("required", required),
            ("secret", secret),
            ("env_override", env),
            ("restart_required", restart_required),
            ("allowed_values", allowed),
            ("since", since),
        )
    )


CONFIG_REGISTRY = OrderedDict(
    (
        ("config_version", _entry(
            "integer", 1,
            "Configuration schema version. Reserved for migration; unset means version 1.")),
        ("default_workspace", _entry(
            "string", "default",
            "Name of the workspace used when --workspace is not given.",
            env="LIFETXT_DEFAULT_WORKSPACE")),
        ("paths", _entry(
            "array<string>", ["life.txt"],
            "Legacy input files. Treated as the implicit 'default' workspace sources.")),
        ("write_file", _entry(
            "string", "life.txt",
            "Legacy default write target. Treated as the default workspace write_file.")),
        ("workspaces", _entry(
            "object", None,
            "Named workspaces. Each value is a source-manifest (see workspace-source-manifest-v1).")),
        ("workspaces.*.sources", _entry(
            "array<string|object>", None,
            "Ordered source manifest entries: a path string or a typed source object.")),
        ("workspaces.*.write_file", _entry(
            "string", None,
            "Default write target for the workspace. Must be a writable source.")),
        ("profiles", _entry(
            "object", None,
            "Named configuration overlays applied above the base config via --profile.")),
        ("defaults.timezone", _entry(
            "string", "Asia/Tokyo",
            "IANA timezone used when a file or item does not declare one.",
            env="LIFETXT_TIMEZONE")),
        ("defaults.person", _entry(
            "string", "self",
            "Default person/owner identity for authored items.",
            env="LIFETXT_PERSON")),
        ("web.host", _entry(
            "string", "127.0.0.1",
            "Bind address for the web server.",
            env="LIFETXT_WEB_HOST", restart_required=True)),
        ("web.port", _entry(
            "integer", 8000,
            "TCP port for the web server.",
            env="LIFETXT_WEB_PORT", restart_required=True)),
        ("notifications.email.smtp_pass_env", _entry(
            "string", "LIFETXT_SMTP_PASS",
            "Name of the environment variable holding the SMTP password. Never store the "
            "password itself in configuration.",
            secret=False)),
        ("ids.auto", _entry(
            "boolean", True,
            "Automatically assign stable IDs to new items.")),
    )
)


def explain_key(dotted):
    """Return registry metadata for ``dotted``, matching wildcard entries."""
    dotted = str(dotted)
    if dotted in CONFIG_REGISTRY:
        return CONFIG_REGISTRY[dotted]
    for pattern, entry in CONFIG_REGISTRY.items():
        if "*" in pattern and _wildcard_match(pattern, dotted):
            return entry
    return None


def _wildcard_match(pattern, dotted):
    pparts = pattern.split(".")
    dparts = dotted.split(".")
    if len(pparts) != len(dparts):
        return False
    for pat, actual in zip(pparts, dparts):
        if pat != "*" and pat != actual:
            return False
    return True


def registry_keys():
    return list(CONFIG_REGISTRY.keys())
