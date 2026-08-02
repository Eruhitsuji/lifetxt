"""Authoritative metadata registry for configuration keys.

``config explain PATH`` and generated documentation both read from this single
registry so descriptions, defaults, and security notes never drift between the
CLI and the docs. Every entry is intentionally curated; unknown keys resolve to
a generic "no registered metadata" answer rather than silently succeeding.
"""

from __future__ import unicode_literals

from collections import OrderedDict


def _entry(
    type_,
    default,
    description,
    required=False,
    secret=False,
    env=None,
    restart_required=False,
    allowed=None,
    since="0.1.0",
    deprecated=False,
    replacement=None,
):
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
            ("deprecated", deprecated),
            ("replacement", replacement),
        )
    )


CONFIG_REGISTRY = OrderedDict(
    (
        (
            "config_version",
            _entry(
                "integer",
                1,
                "Configuration schema version. Reserved for migration; unset means version 1.",
            ),
        ),
        (
            "default_workspace",
            _entry(
                "string",
                "default",
                "Name of the workspace used when --workspace is not given.",
                env="LIFETXT_DEFAULT_WORKSPACE",
            ),
        ),
        (
            "paths",
            _entry(
                "array<string>",
                ["life.txt"],
                "Legacy input files. Treated as the implicit 'default' workspace sources.",
            ),
        ),
        (
            "write_file",
            _entry(
                "string",
                "life.txt",
                "Legacy default write target. Treated as the default workspace write_file.",
            ),
        ),
        (
            "workspaces",
            _entry(
                "object",
                None,
                "Named workspaces. Each value is a source-manifest (see workspace-source-manifest-v1).",
            ),
        ),
        (
            "workspaces.*.sources",
            _entry(
                "array<string|object>",
                None,
                "Ordered source manifest entries: a path string or a typed source object.",
            ),
        ),
        (
            "workspaces.*.write_file",
            _entry(
                "string",
                None,
                "Default write target for the workspace. Must be a writable source.",
            ),
        ),
        (
            "workspace.max_total_source_bytes",
            _entry(
                "integer",
                67108864,
                "Maximum aggregate bytes accepted across unique resolved workspace source files.",
            ),
        ),
        (
            "profiles",
            _entry(
                "object",
                None,
                "Named configuration overlays applied above the base config via --profile.",
            ),
        ),
        (
            "defaults.timezone",
            _entry(
                "string",
                "Asia/Tokyo",
                "IANA timezone used when a file or item does not declare one.",
                env="LIFETXT_TIMEZONE",
            ),
        ),
        (
            "defaults.person",
            _entry(
                "string",
                "self",
                "Default person/owner identity for authored items.",
                env="LIFETXT_PERSON",
            ),
        ),
        (
            "web.host",
            _entry(
                "string",
                "127.0.0.1",
                "Bind address for the web server.",
                env="LIFETXT_WEB_HOST",
                restart_required=True,
            ),
        ),
        (
            "web.port",
            _entry(
                "integer",
                8000,
                "TCP port for the web server.",
                env="LIFETXT_WEB_PORT",
                restart_required=True,
            ),
        ),
        (
            "notifications.email.smtp_pass_env",
            _entry(
                "string",
                "LIFETXT_SMTP_PASS",
                "Name of the environment variable holding the SMTP password. Never store the "
                "password itself in configuration.",
                secret=False,
            ),
        ),
        (
            "ids.auto",
            _entry("boolean", True, "Automatically assign stable IDs to new items."),
        ),
        (
            "editor",
            _entry(
                "string",
                None,
                "External editor command. lifetxt edits a temporary copy and revision-checks the apply.",
            ),
        ),
        (
            "attachments.root",
            _entry(
                "string",
                "attachments",
                "Root directory that confines file, directory, package, and open-reference attachments.",
            ),
        ),
        (
            "attachments.max_files",
            _entry(
                "integer",
                1000,
                "Maximum regular files accepted while packaging or hashing a directory attachment.",
            ),
        ),
        (
            "attachments.max_bytes",
            _entry(
                "integer",
                268435456,
                "Maximum aggregate bytes accepted for an attachment directory or bounded file read.",
            ),
        ),
        (
            "attachments.max_file_bytes",
            _entry(
                "integer", 67108864, "Maximum bytes accepted for one attachment file."
            ),
        ),
        (
            "attachments.ignores",
            _entry(
                "array<string>",
                [".git", ".lifetxt-transactions", "__pycache__"],
                "Directory names omitted from deterministic attachment packages.",
            ),
        ),
        (
            "attachments.allowed_mime",
            _entry(
                "array<string>",
                None,
                "Optional MIME allow-list. Supports exact values and type/* patterns.",
            ),
        ),
        (
            "attachments.blocked_mime",
            _entry(
                "array<string>",
                [],
                "MIME deny-list checked before attachment content is journaled.",
            ),
        ),
        (
            "attachments.open_state_file",
            _entry(
                "string",
                ".lifetxt-attachment-open.json",
                "Revision-checked metadata file recording validated attachment open operations.",
            ),
        ),
        (
            "attachments.remote_source_root",
            _entry(
                "string",
                None,
                "Server-side root confining directories that Web/MCP may package. Defaults to attachments.root.",
            ),
        ),
        (
            "attachments.remote_chunk_bytes",
            _entry(
                "integer",
                65536,
                "Default bounded chunk size for Web/MCP attachment reads; hard-capped at 1 MiB.",
            ),
        ),
        (
            "transactions.policy_file",
            _entry(
                "string",
                None,
                "Versioned transaction policy document loaded in addition to configuration.",
            ),
        ),
        (
            "transactions.admin_audit_file",
            _entry(
                "string",
                None,
                "Bounded JSON audit log for policy, archive, and recovery administration.",
            ),
        ),
        (
            "transactions.preflight_on_startup",
            _entry(
                "boolean",
                False,
                "Run transaction policy and permission preflight when a server starts.",
                restart_required=True,
            ),
        ),
        (
            "transactions.terminal_retention_days",
            _entry(
                "number",
                30.0,
                "Minimum age before terminal transaction journals may be archived or cleaned.",
            ),
        ),
        (
            "transactions.max_transactions",
            _entry(
                "integer",
                500,
                "Maximum transaction journals permitted before new transactions are refused.",
            ),
        ),
        (
            "transactions.max_total_bytes",
            _entry(
                "integer",
                268435456,
                "Maximum total bytes permitted under the transaction journal root.",
            ),
        ),
        (
            "transactions.max_transaction_bytes",
            _entry(
                "integer",
                67108864,
                "Maximum estimated evidence bytes permitted for one transaction.",
            ),
        ),
        (
            "transactions.require_private_permissions",
            _entry(
                "boolean",
                True,
                "Require current-user ownership and no group/other permissions where supported.",
            ),
        ),
        (
            "transactions.allow_newer_read_only",
            _entry(
                "boolean",
                True,
                "Allow inspection, but never mutation, of newer journal versions.",
            ),
        ),
        (
            "transactions.evidence_include_paths",
            _entry(
                "boolean",
                False,
                "Include local paths in recovery evidence. Keep disabled for portable support bundles.",
            ),
        ),
        (
            "clock.skew_warning_seconds",
            _entry(
                "number",
                30.0,
                "Absolute client/server clock skew that produces a warning.",
            ),
        ),
        (
            "clock.skew_reject_seconds",
            _entry(
                "number",
                300.0,
                "Absolute client/server clock skew above which remote writes are refused.",
            ),
        ),
        (
            "clock.require_remote_write_time",
            _entry(
                "boolean",
                False,
                "Require an offset-aware client timestamp on every writable Web/MCP request.",
                restart_required=True,
            ),
        ),
        (
            "clock.client_time_header",
            _entry(
                "string",
                "X-Lifetxt-Client-Time",
                "HTTP header carrying the offset-aware client timestamp for remote write skew checks.",
                restart_required=True,
            ),
        ),
        (
            "remote",
            _entry(
                "object",
                None,
                "Authenticated deny-by-default Remote Safe Mode configuration.",
            ),
        ),
        (
            "remote.enabled",
            _entry(
                "boolean",
                False,
                "Enable authenticated Remote Safe Mode routes.",
                restart_required=True,
            ),
        ),
        (
            "remote.browser_ui",
            _entry(
                "boolean", False, "Expose a remote browser UI. Disabled by default."
            ),
        ),
        (
            "remote.principals",
            _entry(
                "array<object>",
                [],
                "Remote principal registry with roles, scopes, projects, groups, visibility grants, and token_env references.",
            ),
        ),
        (
            "remote.trusted_proxies",
            _entry(
                "array<string>",
                [],
                "Direct-peer IP/CIDR ranges allowed to assert configured principal IDs.",
            ),
        ),
        (
            "remote.proxy_principal_header",
            _entry(
                "string",
                "X-Lifetxt-Principal",
                "Header accepted only from a trusted direct proxy.",
            ),
        ),
        (
            "remote.allow_loopback_http",
            _entry(
                "boolean",
                True,
                "Allow plain HTTP only for loopback development clients.",
            ),
        ),
        (
            "remote.rate_limit_per_minute",
            _entry("integer", 120, "Per-principal Remote Safe Mode request limit."),
        ),
        (
            "remote.audit_log",
            _entry(
                "string",
                None,
                "Bounded JSONL audit log path for authenticated remote requests.",
            ),
        ),
        (
            "remote.audit_max_bytes",
            _entry(
                "integer",
                5242880,
                "Maximum bytes retained in the bounded Remote JSONL audit log.",
            ),
        ),
        (
            "remote.allowed_origins",
            _entry(
                "array<string>",
                [],
                "Additional exact browser origins allowed for Remote session CSRF checks.",
            ),
        ),
        (
            "remote.browser_session_ttl_seconds",
            _entry(
                "integer",
                28800,
                "Absolute lifetime of an opaque Remote browser session.",
            ),
        ),
        (
            "remote.browser_session_idle_seconds",
            _entry(
                "integer", 1800, "Idle lifetime of an opaque Remote browser session."
            ),
        ),
        (
            "remote.browser_session_max",
            _entry(
                "integer",
                256,
                "Maximum process-local Remote browser sessions before oldest-session eviction.",
            ),
        ),
        (
            "remote.browser_login_rate_limit_per_minute",
            _entry(
                "integer",
                10,
                "Per-client login-attempt limit for the Remote browser session endpoint.",
            ),
        ),
        (
            "remote.session_cookie_name",
            _entry(
                "string",
                "lifetxt_remote_session",
                "Opaque HttpOnly Remote browser session cookie name.",
            ),
        ),
        (
            "remote.csrf_header",
            _entry(
                "string",
                "X-CSRF-Token",
                "Header carrying the Remote browser-session CSRF token.",
            ),
        ),
        (
            "transactions.require_operator_authorization",
            _entry(
                "boolean",
                False,
                "Require transaction administration operators to appear in transactions.authorized_operators.",
            ),
        ),
        (
            "transactions.authorized_operators",
            _entry(
                "array<string>",
                [],
                "Operators allowed to perform policy, archive, restore, and audit administration when authorization is required.",
            ),
        ),
        (
            "projects",
            _entry(
                "object",
                None,
                "Static project registry: display name, aliases, default source/assignee/area, "
                "templates, and visibility. Changing progress/risks/decisions stay in life.txt records.",
            ),
        ),
        (
            "projects.*.aliases",
            _entry(
                "array<string>",
                None,
                "Alternate names that resolve to this project in project/portfolio commands.",
            ),
        ),
        (
            "ticketing",
            _entry(
                "object",
                None,
                "Development ticket configuration: trackers, statuses, priorities, severities, "
                "components, defaults, id_prefix, required_fields, and typed custom fields "
                "(ticket-v1.schema.json).",
            ),
        ),
        (
            "ticketing.id_prefix",
            _entry(
                "string",
                "TK",
                "Prefix for generated ticket ids, e.g. TK-1. Keep distinct from task id prefixes.",
            ),
        ),
        (
            "ticketing.required_fields",
            _entry(
                "array<string>",
                [],
                "Ticket fields that must be present; missing ones are reported as TK005 errors.",
            ),
        ),
        (
            "inbox.proposals_file",
            _entry(
                "string",
                ".cache/lifetxt/proposals.json",
                "Operational store for Unified Inbox proposals staged before acceptance. "
                "Not authoritative life.txt content.",
            ),
        ),
        (
            "groups",
            _entry(
                "object",
                None,
                "Messaging groups: name -> {members, disabled_members, visibility, aliases}. "
                "Members may be people, teams (team:name), or other groups; expansion is "
                "deterministic with cycle detection (group-v1.schema.json).",
            ),
        ),
        (
            "saved_views",
            _entry(
                "object",
                None,
                "Named saved views (queries). Each value has a query string plus optional "
                "sort, order, and limit. Executed via the shared query language.",
            ),
        ),
        (
            "generated_paths",
            _entry(
                "array<string>",
                None,
                "Top-level list of generated files. Superseded by per-source 'generated' "
                "roles and sync_ics.generated_paths.",
                deprecated=True,
                replacement="workspaces.*.sources[].role=generated",
            ),
        ),
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
