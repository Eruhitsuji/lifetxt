"""Versioned workspace source-manifest resolution and named workspaces.

This module turns the flexible, human-friendly configuration syntax into a
single deterministic resolution result. It preserves the existing top-level
``paths`` / ``write_file`` behavior by treating that pair as an implicit
``workspaces.default`` entry, and it extends it into a typed source-manifest
model without forcing users to migrate.

Resolution never rewrites configuration and never performs I/O beyond reading
the filesystem to expand globs and detect duplicate physical files. It fails
loudly for unknown workspace names and surfaces every other concern as a
structured diagnostic so callers (CLI, TUI, Web, doctor) can decide severity.
"""

from __future__ import unicode_literals

import fnmatch
import glob
import os
from collections import OrderedDict


WORKSPACE_MANIFEST_VERSION = 1

# Roles describe how a source participates in the workspace. ``primary`` and
# ``input`` are read/write candidates; the remaining roles are read-only or
# machine-generated and are excluded from the default writable set.
KNOWN_ROLES = ("primary", "input", "generated", "archive", "readonly", "reference")
_READONLY_ROLES = ("generated", "archive", "readonly", "reference")
_HIDDEN_BY_DEFAULT_ROLES = ("generated", "archive")
_NON_WRITE_TARGET_ROLES = ("generated", "archive")

# Soft ceiling on source count; large workspaces still resolve but warn so a
# runaway glob or accidental directory import is visible.
MAX_SOURCES = 200


def diagnostic(severity, code, message, hint="", source=None):
    """Build one workspace diagnostic in the shared stable shape."""
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("hint", hint),
            ("source", source),
        )
    )


def config_base_dir(config):
    """Directory that relative source paths resolve against.

    Relative paths are resolved against the configuration file's directory so a
    workspace behaves identically regardless of the caller's current directory.
    When no config file is loaded we fall back to the current directory, which
    matches the historical behavior of bare ``paths`` arrays.
    """
    config_path = config.get("_path") if isinstance(config, dict) else None
    if config_path:
        directory = os.path.dirname(os.path.abspath(config_path))
        if directory:
            return directory
    return os.getcwd()


def _config_generated_paths(config):
    values = []
    if isinstance(config, dict):
        raw = config.get("generated_paths")
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, (list, tuple)):
            values.extend(str(value) for value in raw if str(value))
        sync = config.get("sync_ics")
        if isinstance(sync, dict):
            sync_raw = sync.get("generated_paths")
            if isinstance(sync_raw, str):
                values.append(sync_raw)
            elif isinstance(sync_raw, (list, tuple)):
                values.extend(str(value) for value in sync_raw if str(value))
    return values


def iter_workspace_definitions(config):
    """Return an ordered ``name -> raw definition`` map.

    When the configuration has no explicit ``workspaces`` section we synthesize
    a single ``default`` workspace from the legacy top-level ``paths`` and
    ``write_file`` settings so existing configuration keeps working unchanged.
    """
    workspaces = config.get("workspaces") if isinstance(config, dict) else None
    if isinstance(workspaces, dict) and workspaces:
        result = OrderedDict()
        for name, definition in workspaces.items():
            result[str(name)] = definition
        return result
    return OrderedDict([("default", _legacy_workspace_definition(config))])


def _legacy_workspace_definition(config):
    paths = config.get("paths") if isinstance(config, dict) else None
    if isinstance(paths, str):
        paths = [paths]
    elif not isinstance(paths, (list, tuple)):
        paths = []
    generated = set(os.path.normcase(value) for value in _config_generated_paths(config))
    sources = []
    for value in paths:
        text = str(value)
        if not text:
            continue
        if os.path.normcase(text) in generated:
            sources.append(OrderedDict([("path", text), ("role", "generated")]))
        else:
            sources.append(text)
    if not sources:
        sources = ["life.txt"]
    definition = OrderedDict()
    definition["sources"] = sources
    write_file = config.get("write_file") if isinstance(config, dict) else None
    if write_file:
        definition["write_file"] = str(write_file)
    definition["_legacy"] = True
    return definition


def default_workspace_name(config):
    explicit = config.get("default_workspace") if isinstance(config, dict) else None
    definitions = iter_workspace_definitions(config)
    if explicit and str(explicit) in definitions:
        return str(explicit)
    if "default" in definitions:
        return "default"
    for name in definitions:
        return name
    return "default"


def normalize_source(entry, base_dir):
    """Normalize one raw source entry into a typed manifest record."""
    if isinstance(entry, str):
        raw = OrderedDict([("path", entry)])
    elif isinstance(entry, dict):
        raw = entry
    else:
        raise ValueError("Workspace source must be a string or object, not %r" % type(entry).__name__)

    path = raw.get("path")
    if not path:
        raise ValueError("Workspace source is missing a 'path'.")
    path = str(path)

    role = str(raw.get("role") or "primary")
    writable_default = role not in _READONLY_ROLES
    visible_default = role not in _HIDDEN_BY_DEFAULT_ROLES

    record = OrderedDict()
    record["path"] = path
    record["role"] = role
    record["required"] = bool(raw.get("required", False))
    record["writable"] = bool(raw.get("writable", writable_default))
    record["default_visible"] = bool(raw.get("default_visible", visible_default))
    record["format"] = str(raw.get("format") or "life")
    try:
        record["priority"] = int(raw.get("priority", 100))
    except (TypeError, ValueError):
        record["priority"] = 100
    record["watch"] = bool(raw.get("watch", True))
    record["privacy"] = str(raw.get("privacy") or "normal")
    record["generated_by"] = raw.get("generated_by") or None
    exclude = raw.get("exclude")
    if isinstance(exclude, str):
        record["exclude"] = [exclude]
    elif isinstance(exclude, (list, tuple)):
        record["exclude"] = [str(value) for value in exclude if str(value)]
    else:
        record["exclude"] = []
    record["resolved_path"] = _resolve_against(path, base_dir)
    return record


def _resolve_against(path, base_dir):
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(base_dir, expanded))


def _has_glob(path):
    return any(char in path for char in ("*", "?", "["))


def _directory_life_files(directory):
    patterns = ("life.txt", "*.life.txt", "*_life.txt", "*.txt")
    matches = []
    seen = set()
    for pattern in patterns:
        for candidate in sorted(glob.glob(os.path.join(directory, pattern))):
            if not os.path.isfile(candidate):
                continue
            key = os.path.normcase(os.path.abspath(candidate))
            if key in seen:
                continue
            seen.add(key)
            matches.append(os.path.abspath(candidate))
    return matches


def _expand_source_files(record):
    """Return the deterministic, absolute file list a source contributes."""
    resolved = record["resolved_path"]
    if _has_glob(record["path"]):
        matches = sorted(
            os.path.abspath(match)
            for match in glob.glob(resolved, recursive=True)
            if os.path.isfile(match)
        )
        files = matches
        matched_glob = True
    elif os.path.isdir(resolved):
        files = _directory_life_files(resolved)
        matched_glob = True
    else:
        files = [resolved]
        matched_glob = False
    if record["exclude"]:
        files = [
            path
            for path in files
            if not any(fnmatch.fnmatch(os.path.normcase(path), os.path.normcase(_resolve_against(pattern, os.path.dirname(resolved)))) or fnmatch.fnmatch(path, pattern) for pattern in record["exclude"])
        ]
    record["matched_glob"] = matched_glob
    record["files"] = files
    record["exists"] = all(os.path.exists(path) for path in files) if files else False
    return files


def resolve_workspace(config, name=None, base_dir=None):
    """Resolve a workspace into a deterministic, inspectable result.

    Raises ``ValueError`` only for an unknown workspace name; every other
    concern (missing required source, duplicate physical file, unusable write
    target, outside-root path) is reported through ``diagnostics``.
    """
    config = config or {}
    definitions = iter_workspace_definitions(config)
    if name is None:
        name = default_workspace_name(config)
    name = str(name)
    if name not in definitions:
        raise ValueError(
            "Unknown workspace %r. Available: %s"
            % (name, ", ".join(definitions.keys()) or "(none)")
        )
    if base_dir is None:
        base_dir = config_base_dir(config)
    definition = definitions[name]
    is_legacy = bool(isinstance(definition, dict) and definition.get("_legacy"))

    raw_sources, write_file = _definition_sources(definition)

    diagnostics = []
    sources = []
    for entry in raw_sources:
        try:
            record = normalize_source(entry, base_dir)
        except ValueError as exc:
            diagnostics.append(
                diagnostic("error", "WS010", "Invalid workspace source: %s" % exc,
                           "Use a path string or an object with a 'path' field.")
            )
            continue
        if record["role"] not in KNOWN_ROLES:
            diagnostics.append(
                diagnostic("warning", "WS005",
                           "Unknown source role %r for %s." % (record["role"], record["path"]),
                           "Use one of: %s." % ", ".join(KNOWN_ROLES), record["path"])
            )
        _expand_source_files(record)
        sources.append(record)

    if not sources:
        diagnostics.append(
            diagnostic("error", "WS009", "Workspace %r has no sources." % name,
                       "Add at least one source path to the workspace.")
        )

    diagnostics.extend(_duplicate_diagnostics(sources))
    diagnostics.extend(_alias_diagnostics(sources))
    diagnostics.extend(_required_diagnostics(sources))
    diagnostics.extend(_outside_root_diagnostics(sources, base_dir))
    if len(sources) > MAX_SOURCES:
        diagnostics.append(
            diagnostic("warning", "WS013",
                       "Workspace %r has %d sources (soft limit %d)." % (name, len(sources), MAX_SOURCES),
                       "Split the workspace or narrow globs to keep resolution fast.")
        )

    input_paths = _ordered_input_paths(sources)
    default_visible = _ordered_input_paths(sources, visible_only=True)
    generated_paths = _paths_for_roles(sources, ("generated",))
    archive_paths = _paths_for_roles(sources, ("archive",))
    writable_candidates = _writable_candidates(sources)

    resolved_write = _resolve_write_target(
        write_file, base_dir, writable_candidates, sources, diagnostics
    )

    return OrderedDict(
        (
            ("manifest_version", WORKSPACE_MANIFEST_VERSION),
            ("name", name),
            ("legacy", is_legacy),
            ("base_dir", base_dir),
            ("sources", sources),
            ("input_paths", input_paths),
            ("default_visible_paths", default_visible),
            ("write_file", resolved_write),
            ("generated_paths", generated_paths),
            ("archive_paths", archive_paths),
            ("diagnostics", diagnostics),
            ("ok", not any(row["severity"] == "error" for row in diagnostics)),
        )
    )


def _definition_sources(definition):
    if isinstance(definition, (list, tuple)):
        return list(definition), None
    if isinstance(definition, str):
        return [definition], None
    if isinstance(definition, dict):
        raw = definition.get("sources")
        if raw is None:
            raw = definition.get("paths")
        if isinstance(raw, str):
            raw = [raw]
        elif not isinstance(raw, (list, tuple)):
            raw = []
        write_file = definition.get("write_file")
        return list(raw), (str(write_file) if write_file else None)
    return [], None


def _ordered_input_paths(sources, visible_only=False):
    ordered = sorted(
        sources,
        key=lambda record: (record["priority"], record["path"]),
    )
    result = []
    seen = set()
    for record in ordered:
        if record["role"] in ("generated", "archive", "reference") and visible_only and not record["default_visible"]:
            continue
        if visible_only and not record["default_visible"]:
            continue
        for path in record["files"]:
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
    return result


def _paths_for_roles(sources, roles):
    result = []
    seen = set()
    for record in sources:
        if record["role"] not in roles:
            continue
        for path in record["files"]:
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
    return result


def _writable_candidates(sources):
    result = []
    for record in sources:
        if not record["writable"]:
            continue
        for path in record["files"]:
            result.append(path)
    return result


def _duplicate_diagnostics(sources):
    rows = []
    owners = OrderedDict()
    for record in sources:
        for path in record["files"]:
            owners.setdefault(os.path.normcase(path), []).append((record["path"], path))
    for _key, entries in owners.items():
        if len(entries) > 1:
            origins = ", ".join(sorted(set(origin for origin, _ in entries)))
            rows.append(
                diagnostic("warning", "WS002",
                           "Duplicate physical file resolved from multiple sources: %s (from %s)."
                           % (entries[0][1], origins),
                           "Remove the duplicate source or use distinct files.", entries[0][1])
            )
    return rows


def _alias_diagnostics(sources):
    """Detect distinct source paths that resolve to one physical file via links.

    ``_duplicate_diagnostics`` already reports identical resolved paths. This
    check catches symlink/junction aliases where the literal paths differ but
    ``realpath`` collapses them to the same file, which is easy to miss.
    """
    rows = []
    owners = OrderedDict()
    for record in sources:
        for path in record["files"]:
            try:
                real = os.path.normcase(os.path.realpath(path))
            except OSError:
                continue
            owners.setdefault(real, [])
            key = os.path.normcase(path)
            if key not in [os.path.normcase(p) for p in owners[real]]:
                owners[real].append(path)
    for real, paths in owners.items():
        if len(paths) > 1:
            rows.append(
                diagnostic("warning", "WS011",
                           "Multiple sources resolve to the same physical file through links: %s."
                           % ", ".join(sorted(paths)),
                           "Point sources at one canonical path or remove the alias.", real)
            )
    return rows


def source_reason(record):
    """Human-readable reason a source contributes files, for --resolved output."""
    parts = ["role=%s" % record["role"]]
    if record["required"]:
        parts.append("required")
    if record.get("matched_glob"):
        parts.append("glob/dir match")
    else:
        parts.append("literal path")
    if record["exclude"]:
        parts.append("exclude=%s" % ",".join(record["exclude"]))
    if not record["default_visible"]:
        parts.append("hidden by default")
    return "; ".join(parts)


def _required_diagnostics(sources):
    rows = []
    for record in sources:
        if record["required"] and not record["exists"]:
            rows.append(
                diagnostic("error", "WS001",
                           "Required source is missing: %s." % record["path"],
                           "Create the file or mark the source as not required.",
                           record["resolved_path"])
            )
    return rows


def _outside_root_diagnostics(sources, base_dir):
    rows = []
    root = os.path.normcase(os.path.abspath(base_dir))
    for record in sources:
        resolved = os.path.normcase(record["resolved_path"])
        try:
            common = os.path.commonpath([root, resolved])
        except ValueError:
            common = None
        if common != root:
            rows.append(
                diagnostic("info", "WS003",
                           "Source resolves outside the configuration directory: %s." % record["path"],
                           "This is allowed but review it for portability.", record["resolved_path"])
            )
    return rows


def _resolve_write_target(write_file, base_dir, writable_candidates, sources, diagnostics):
    candidate_keys = set(os.path.normcase(path) for path in writable_candidates)
    if write_file:
        resolved = _resolve_against(write_file, base_dir)
        role = _role_owning_path(sources, resolved)
        if role in _NON_WRITE_TARGET_ROLES:
            diagnostics.append(
                diagnostic("error", "WS012",
                           "Write target points at a %s source: %s." % (role, write_file),
                           "Never write to generated or archive files; choose a primary source.",
                           resolved)
            )
        if os.path.normcase(resolved) not in candidate_keys and not _is_writable_declared(sources, resolved):
            # A configured write target should be an input the workspace also
            # reads; warn but honor it so single-file setups keep working.
            diagnostics.append(
                diagnostic("warning", "WS006",
                           "Write target is not one of the workspace's writable sources: %s." % write_file,
                           "Add the write target as a writable source or point write_file at one.",
                           resolved)
            )
        return resolved
    if writable_candidates:
        return writable_candidates[0]
    diagnostics.append(
        diagnostic("error", "WS007", "Workspace has no writable source.",
                   "Add a writable primary source or set write_file explicitly.")
    )
    return None


def _role_owning_path(sources, resolved):
    key = os.path.normcase(resolved)
    for record in sources:
        if os.path.normcase(record["resolved_path"]) == key:
            return record["role"]
        for path in record["files"]:
            if os.path.normcase(path) == key:
                return record["role"]
    return None


def _is_writable_declared(sources, resolved):
    key = os.path.normcase(resolved)
    for record in sources:
        if not record["writable"]:
            continue
        if os.path.normcase(record["resolved_path"]) == key:
            return True
    return False


def workspace_summaries(config):
    """Lightweight per-workspace summary used by ``workspace list``."""
    definitions = iter_workspace_definitions(config)
    default = default_workspace_name(config)
    summaries = []
    for name in definitions:
        try:
            resolution = resolve_workspace(config, name)
        except ValueError:
            continue
        summaries.append(
            OrderedDict(
                (
                    ("name", name),
                    ("default", name == default),
                    ("legacy", resolution["legacy"]),
                    ("source_count", len(resolution["sources"])),
                    ("input_count", len(resolution["input_paths"])),
                    ("write_file", resolution["write_file"]),
                    ("ok", resolution["ok"]),
                )
            )
        )
    return summaries


def workspace_doctor(config):
    """Aggregate every workspace's resolution and diagnostics for reporting."""
    definitions = iter_workspace_definitions(config)
    default = default_workspace_name(config)
    reports = []
    all_rows = []
    physical_owners = OrderedDict()
    for name in definitions:
        try:
            resolution = resolve_workspace(config, name)
        except ValueError as exc:
            all_rows.append(
                diagnostic("error", "WS008", "Cannot resolve workspace %r: %s" % (name, exc))
            )
            continue
        reports.append(
            OrderedDict(
                (
                    ("name", name),
                    ("default", name == default),
                    ("ok", resolution["ok"]),
                    ("write_file", resolution["write_file"]),
                    ("input_count", len(resolution["input_paths"])),
                    ("diagnostics", resolution["diagnostics"]),
                )
            )
        )
        all_rows.extend(resolution["diagnostics"])
        for path in resolution["input_paths"]:
            physical_owners.setdefault(os.path.normcase(path), []).append(name)
    # Cross-workspace duplicate physical files are informational, not an error:
    # sharing a file between workspaces is legitimate, but worth surfacing.
    shared = OrderedDict(
        (key, names) for key, names in physical_owners.items() if len(set(names)) > 1
    )
    return OrderedDict(
        (
            ("ok", not any(row["severity"] == "error" for row in all_rows)),
            ("workspace_count", len(reports)),
            ("default_workspace", default),
            ("workspaces", reports),
            ("shared_files", [
                OrderedDict((("path", key), ("workspaces", sorted(set(names)))))
                for key, names in shared.items()
            ]),
            ("diagnostic_count", len(all_rows)),
        )
    )
