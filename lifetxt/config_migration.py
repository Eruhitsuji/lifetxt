"""Non-destructive configuration migration to the versioned workspace model.

Migration is explicit and reviewable. It never runs automatically: the user
invokes ``config migrate`` (optionally ``--dry-run``) and sees the exact list of
changes before anything is written. The transformation is idempotent, so
running it twice produces no further changes.
"""

from __future__ import unicode_literals

import copy
from collections import OrderedDict

from .config_validation import CONFIG_SCHEMA_VERSION


def _config_generated_paths(config):
    values = []
    raw = config.get("generated_paths")
    if isinstance(raw, str):
        values.append(raw)
    elif isinstance(raw, (list, tuple)):
        values.extend(str(v) for v in raw if str(v))
    sync = config.get("sync_ics")
    if isinstance(sync, dict):
        sync_raw = sync.get("generated_paths")
        if isinstance(sync_raw, str):
            values.append(sync_raw)
        elif isinstance(sync_raw, (list, tuple)):
            values.extend(str(v) for v in sync_raw if str(v))
    return values


def migrate_config(config):
    """Return ``(migrated_copy, changes)`` for a configuration mapping.

    ``changes`` is a list of human-readable strings; an empty list means the
    configuration is already current and nothing needs to be written.
    """
    source = OrderedDict(
        (key, value) for key, value in (config or {}).items()
        if key not in ("_path", "_active_workspace")
    )
    migrated = copy.deepcopy(source)
    changes = []

    if migrated.get("config_version") != CONFIG_SCHEMA_VERSION:
        old = migrated.get("config_version")
        migrated["config_version"] = CONFIG_SCHEMA_VERSION
        changes.append(
            "Set config_version to %d (was %r)." % (CONFIG_SCHEMA_VERSION, old)
        )

    has_workspaces = isinstance(migrated.get("workspaces"), dict) and migrated["workspaces"]
    legacy_paths = migrated.get("paths")
    legacy_write = migrated.get("write_file")

    if not has_workspaces and (legacy_paths or legacy_write):
        generated = set(_config_generated_paths(source))
        paths = legacy_paths
        if isinstance(paths, str):
            paths = [paths]
        elif not isinstance(paths, (list, tuple)):
            paths = []
        sources = []
        for value in paths:
            text = str(value)
            if not text:
                continue
            if text in generated:
                sources.append(OrderedDict([("path", text), ("role", "generated")]))
            else:
                sources.append(text)
        if not sources:
            sources = ["life.txt"]
        definition = OrderedDict([("sources", sources)])
        if legacy_write:
            definition["write_file"] = str(legacy_write)
        # Insert workspaces after config_version for readable output.
        migrated["workspaces"] = OrderedDict([("default", definition)])
        migrated.setdefault("default_workspace", "default")
        changes.append(
            "Converted legacy paths/write_file into workspaces.default (%d source(s))."
            % len(sources)
        )
        # Keep legacy keys for one release as a compatibility shorthand, but note
        # they are now mirrored by the workspace. Removal is a separate, explicit
        # step so downgrades keep working.

    return migrated, changes
