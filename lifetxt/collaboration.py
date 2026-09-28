"""Shared per-workspace collaboration membership and permission resolver.

Workspace roles are an additional gate over existing Remote principal scopes.
They never replace item/source visibility and never grant server administration.
"""

from __future__ import unicode_literals

from collections import OrderedDict
import copy
import re

from .remote_access import RemoteAccessError, principal_registry
from .workspace import (
    active_workspace_name,
    default_workspace_name,
    iter_workspace_definitions,
)


WORKSPACE_ROLES = frozenset(("owner", "editor", "viewer"))
ROLE_OPERATIONS = {
    "owner": frozenset(("read", "write", "member_admin")),
    "editor": frozenset(("read", "write")),
    "viewer": frozenset(("read",)),
}


def selected_workspace_name(config, workspace_name=None):
    if workspace_name is not None:
        return str(workspace_name)
    return active_workspace_name(config) or default_workspace_name(config)


def collaboration_enabled(config, workspace_name=None):
    name = selected_workspace_name(config, workspace_name)
    definition = iter_workspace_definitions(config).get(name)
    return isinstance(definition, dict) and "collaboration" in definition


def _fail_closed():
    raise RemoteAccessError(
        "WORKSPACE_COLLABORATION_INVALID",
        "Workspace collaboration configuration is invalid.",
        403,
    )


def resolve_membership(config, principal, workspace_name=None):
    """Return bounded effective workspace authority for one authenticated user.

    A workspace without a collaboration section preserves legacy Remote
    behavior. For enabled collaboration, malformed configuration, unknown or
    disabled principals, and non-members all fail closed.
    """
    name = selected_workspace_name(config, workspace_name)
    definitions = iter_workspace_definitions(config)
    definition = definitions.get(name)
    if definition is None:
        raise RemoteAccessError(
            "WORKSPACE_NOT_AVAILABLE", "The selected workspace is unavailable.", 404
        )
    scopes = set((principal or {}).get("scopes") or [])
    enabled = isinstance(definition, dict) and "collaboration" in definition
    if not enabled:
        return OrderedDict(
            (
                ("workspace_name", name),
                ("workspace_id", None),
                ("principal_id", (principal or {}).get("id")),
                ("member", True),
                ("collaboration_enabled", False),
                ("role", None),
                (
                    "permissions",
                    OrderedDict(
                        (
                            ("read", "read" in scopes),
                            ("write", "write" in scopes),
                            ("member_admin", False),
                        )
                    ),
                ),
            )
        )

    collaboration = definition.get("collaboration")
    members = collaboration.get("members") if isinstance(collaboration, dict) else None
    principal_id = str((principal or {}).get("id") or "")
    registry = principal_registry(config)
    registered = registry.get(principal_id)
    if (
        not isinstance(members, dict)
        or not principal_id
        or not registered
        or registered.get("disabled")
    ):
        _fail_closed()
    member = members.get(principal_id)
    role = member.get("role") if isinstance(member, dict) else None
    if role not in WORKSPACE_ROLES:
        raise RemoteAccessError(
            "WORKSPACE_ACCESS_DENIED",
            "The principal is not an active member of this workspace.",
            403,
        )
    role_operations = ROLE_OPERATIONS[role]
    permissions = OrderedDict(
        (
            ("read", "read" in role_operations and "read" in scopes),
            ("write", "write" in role_operations and "write" in scopes),
            (
                "member_admin",
                "member_admin" in role_operations and "admin" in scopes,
            ),
        )
    )
    import hashlib

    workspace_id = hashlib.sha256(
        ("lifetxt-collaboration-workspace-v1\0" + name).encode("utf-8")
    ).hexdigest()
    return OrderedDict(
        (
            ("workspace_name", name),
            ("workspace_id", workspace_id),
            ("principal_id", principal_id),
            ("member", True),
            ("collaboration_enabled", True),
            ("role", role),
            ("permissions", permissions),
        )
    )


def require_workspace_permission(config, principal, operation, workspace_name=None):
    result = resolve_membership(config, principal, workspace_name)
    if not result["permissions"].get(operation, False):
        # Preserve the established Remote scope error contract when workspace
        # collaboration is not configured. In that mode the only applicable
        # authorization gate is the principal's existing global scope.
        if not result["collaboration_enabled"] and operation in ("read", "write"):
            from .remote_access import require_scope

            require_scope(principal, operation)
        raise RemoteAccessError(
            "WORKSPACE_PERMISSION_DENIED",
            "The principal lacks the required workspace permission.",
            403,
        )
    return result


def config_membership_diagnostics(config):
    """Validate membership references and last-owner safety without secrets."""
    from .config_validation import diagnostic

    rows = []
    definitions = config.get("workspaces") if isinstance(config, dict) else None
    if not isinstance(definitions, dict):
        return rows
    remote = config.get("remote") if isinstance(config.get("remote"), dict) else {}
    raw_principals = remote.get("principals") or []
    if isinstance(raw_principals, dict):
        principals = {str(key): value for key, value in raw_principals.items()}
    elif isinstance(raw_principals, list):
        principals = {
            str(row.get("id")): row for row in raw_principals if isinstance(row, dict)
        }
    else:
        principals = {}
    for workspace_name, definition in definitions.items():
        if not isinstance(definition, dict) or "collaboration" not in definition:
            continue
        base = "workspaces.%s.collaboration" % workspace_name
        collab = definition.get("collaboration")
        if not isinstance(collab, dict) or set(collab) - {"members"}:
            rows.append(
                diagnostic(
                    "error",
                    "C020",
                    "Workspace collaboration must be an object containing only 'members'.",
                    "Use collaboration: {members: {principal_id: {role: owner|editor|viewer}}}.",
                    base,
                )
            )
            continue
        members = collab.get("members")
        if not isinstance(members, dict) or not members:
            rows.append(
                diagnostic(
                    "error",
                    "C020",
                    "Workspace collaboration members must be a non-empty object.",
                    "Configure at least one active owner.",
                    base + ".members",
                )
            )
            continue
        active_owners = 0
        for principal_id, entry in members.items():
            path = "%s.members.%s" % (base, principal_id)
            registered = principals.get(str(principal_id))
            if registered is None:
                rows.append(
                    diagnostic(
                        "error",
                        "C021",
                        "Workspace membership references an unknown Remote principal.",
                        "Add the principal to remote.principals before assigning a workspace role.",
                        path,
                    )
                )
                continue
            if (
                not isinstance(entry, dict)
                or set(entry) != {"role"}
                or entry.get("role") not in WORKSPACE_ROLES
            ):
                rows.append(
                    diagnostic(
                        "error",
                        "C022",
                        "Workspace member role must be owner, editor, or viewer.",
                        "Use exactly one supported role for each member.",
                        path,
                    )
                )
                continue
            disabled = (
                bool(registered.get("disabled"))
                if isinstance(registered, dict)
                else False
            )
            if entry["role"] == "owner" and not disabled:
                active_owners += 1
        if active_owners == 0:
            rows.append(
                diagnostic(
                    "error",
                    "C023",
                    "Collaboration-enabled workspace must have at least one active owner.",
                    "Enable or add an active owner before removing or disabling the last owner.",
                    base + ".members",
                )
            )
    return rows


def member_listing(config, principal, workspace_name):
    """Return the authorized member roster and exact configuration revision."""
    require_workspace_permission(config, principal, "member_admin", workspace_name)
    name = selected_workspace_name(config, workspace_name)
    definition = iter_workspace_definitions(config).get(name)
    if not isinstance(definition, dict) or not isinstance(
        definition.get("collaboration"), dict
    ):
        _fail_closed()
    members = definition["collaboration"].get("members")
    if not isinstance(members, dict):
        _fail_closed()
    registry = principal_registry(config)
    rows = []
    for principal_id, value in sorted(members.items()):
        configured = registry.get(str(principal_id))
        if not configured:
            _fail_closed()
        rows.append(
            OrderedDict(
                (
                    ("principal_id", str(principal_id)),
                    ("display_name", configured["display_name"]),
                    ("role", value.get("role")),
                    ("disabled", bool(configured.get("disabled"))),
                )
            )
        )
    from .config_writer import config_revision

    revision = config_revision((config or {}).get("_path"))
    if not (config or {}).get("_path"):
        revision = None
    return OrderedDict(
        (
            ("workspace", name),
            ("members", rows),
            ("config_revision", revision),
        )
    )


def fresh_config_snapshot(config):
    """Reload a persistent config and reject a file that changed mid-read."""
    path = (config or {}).get("_path")
    if not path:
        return config, None
    from .config import load_config
    from .config_writer import config_revision

    before = config_revision(path)
    fresh = load_config(path)
    after = config_revision(path)
    if before != after:
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_REVISION_CONFLICT",
            "Workspace configuration changed; refresh and retry.",
            409,
            {"current_revision": after},
        )
    if "_active_workspace" in config:
        fresh["_active_workspace"] = config["_active_workspace"]
    return fresh, after


def change_membership(
    config,
    actor,
    workspace_name,
    operation,
    principal_id,
    role=None,
    expected_revision=None,
):
    """Apply one owner-guarded member change using configuration CAS."""
    require_workspace_permission(config, actor, "member_admin", workspace_name)
    operation = str(operation or "").strip().lower()
    principal_id = str(principal_id or "").strip()
    if operation not in ("add", "role", "remove"):
        raise RemoteAccessError(
            "WORKSPACE_MEMBER_OPERATION_INVALID",
            "operation must be add, role, or remove.",
            400,
        )
    if not principal_id:
        raise RemoteAccessError(
            "WORKSPACE_MEMBER_REQUIRED", "principal_id is required.", 400
        )
    if operation in ("add", "role") and role not in WORKSPACE_ROLES:
        raise RemoteAccessError(
            "WORKSPACE_MEMBER_ROLE_INVALID",
            "role must be owner, editor, or viewer.",
            400,
        )
    registry = principal_registry(config)
    if principal_id not in registry:
        raise RemoteAccessError(
            "WORKSPACE_PRINCIPAL_UNKNOWN",
            "The configured Remote principal does not exist.",
            404,
        )
    path = (config or {}).get("_path")
    if not path:
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_WRITE_UNAVAILABLE",
            "Workspace membership cannot be changed through this server configuration.",
            503,
        )
    from .config_writer import (
        ConfigWriteError,
        StaleConfigRevision,
        config_revision,
        write_config,
    )

    if expected_revision is None:
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_REVISION_REQUIRED",
            "expected_config_revision is required.",
            428,
        )
    if not isinstance(expected_revision, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_revision
    ):
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_REVISION_INVALID",
            "expected_config_revision must be a SHA-256 revision.",
            400,
        )
    current_revision = config_revision(path)
    if current_revision != expected_revision:
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_REVISION_CONFLICT",
            "Workspace membership changed; refresh the member list and retry.",
            409,
            {"current_revision": current_revision},
        )
    name = selected_workspace_name(config, workspace_name)
    candidate = copy.deepcopy(config)
    definitions = candidate.get("workspaces")
    definition = definitions.get(name) if isinstance(definitions, dict) else None
    if not isinstance(definition, dict) or not isinstance(
        definition.get("collaboration"), dict
    ):
        _fail_closed()
    members = definition["collaboration"].get("members")
    if not isinstance(members, dict):
        _fail_closed()
    current = members.get(principal_id)
    if operation == "add":
        if current is not None:
            raise RemoteAccessError(
                "WORKSPACE_MEMBER_EXISTS", "The principal is already a member.", 409
            )
        members[principal_id] = {"role": role}
    elif operation == "role":
        if current is None:
            raise RemoteAccessError(
                "WORKSPACE_MEMBER_NOT_FOUND", "The workspace member was not found.", 404
            )
        members[principal_id] = {"role": role}
    else:
        if current is None:
            raise RemoteAccessError(
                "WORKSPACE_MEMBER_NOT_FOUND", "The workspace member was not found.", 404
            )
        del members[principal_id]

    active_owners = sum(
        1
        for member_id, entry in members.items()
        if isinstance(entry, dict)
        and entry.get("role") == "owner"
        and member_id in registry
        and not registry[member_id].get("disabled")
    )
    if active_owners == 0:
        raise RemoteAccessError(
            "WORKSPACE_LAST_OWNER_REQUIRED",
            "The last active workspace owner cannot be removed or demoted.",
            409,
        )
    try:
        report = write_config(
            path,
            candidate,
            expected_revision=expected_revision,
            require_revision=True,
        )
    except StaleConfigRevision as exc:
        raise RemoteAccessError(
            "WORKSPACE_CONFIG_REVISION_CONFLICT",
            "Workspace membership changed; refresh the member list and retry.",
            409,
            {"current_revision": exc.current},
        )
    except ConfigWriteError:
        raise RemoteAccessError(
            "WORKSPACE_MEMBERSHIP_INVALID",
            "The requested membership change failed configuration validation.",
            400,
        )
    candidate["_path"] = path
    if "_active_workspace" in config:
        candidate["_active_workspace"] = config["_active_workspace"]
    from .config_writer import config_revision as current_config_revision

    revision = current_config_revision(path)
    return OrderedDict(
        (
            ("ok", True),
            ("operation", "member.%s" % operation),
            ("workspace", name),
            ("principal_id", principal_id),
            ("role", role if operation != "remove" else None),
            ("revision_before", report["before_revision"]),
            ("revision_after", revision),
        )
    ), candidate
