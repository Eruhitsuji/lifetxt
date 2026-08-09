"""Project-archive preflight hardening after the production zero-byte incident (#183).

The incident root cause is intentionally not claimed here. This compatibility
layer addresses concrete safety gaps found during investigation while keeping
generic ``archive`` behavior backward compatible.
"""

from __future__ import unicode_literals

import argparse
import os


_INSTALLED = False


def install_archive_safety_v3():
    """Install stricter checks only around ``project archive`` execution."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import cli as cli_module

    original_project_archive = cli_module.command_project_archive
    if getattr(original_project_archive, "_lifetxt_archive_safety_v3", False):
        _INSTALLED = True
        return

    def command_project_archive(args):
        # The legacy project command delegates to module-global command_archive.
        # Patch that dependency only for this call, then always restore it. This
        # keeps generic archive and direct cli callers on their historical contract.
        original_archive = cli_module.command_archive

        def guarded_archive(archive_args):
            _archive_preflight(cli_module, archive_args)
            return original_archive(archive_args)

        cli_module.command_archive = guarded_archive
        try:
            return original_project_archive(args)
        finally:
            cli_module.command_archive = original_archive

    command_project_archive._lifetxt_archive_safety_v3 = True
    cli_module.command_project_archive = command_project_archive
    _patch_archive_help(cli_module)
    _INSTALLED = True


def _config_relative_path(path, config):
    expanded = os.path.expanduser(str(path))
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    config_path = config.get("_path") if isinstance(config, dict) else None
    base = os.path.dirname(os.path.abspath(config_path)) if config_path else os.getcwd()
    return os.path.abspath(os.path.join(base, expanded))


def _error_diagnostics(diagnostics):
    return [
        diagnostic
        for diagnostic in diagnostics
        if str(getattr(diagnostic, "severity", "")).lower() == "error"
    ]


def _diagnostic_summary(errors):
    rows = []
    for diagnostic in errors[:3]:
        code = str(getattr(diagnostic, "code", "ERROR") or "ERROR")
        line = getattr(diagnostic, "line", None)
        message = str(getattr(diagnostic, "message", "invalid archive source"))
        location = " line %s" % line if line not in (None, "") else ""
        rows.append("%s%s: %s" % (code, location, message))
    if len(errors) > 3:
        rows.append("... and %d more error(s)" % (len(errors) - 3))
    return "; ".join(rows)


def _snapshot_and_validate(cli_module, path, config, allow_missing=False):
    from .mutation import read_text_snapshot

    snapshot = read_text_snapshot(path, allow_missing=allow_missing)
    if not snapshot.exists:
        return snapshot
    _items, diagnostics = cli_module.parse_text(
        snapshot.text,
        id_key=cli_module.id_key_from_config(config),
        check_ids=False,
        check_references=False,
    )
    errors = _error_diagnostics(diagnostics)
    if errors:
        raise ValueError(
            "Refusing archive because %s has parser error(s): %s"
            % (snapshot.path, _diagnostic_summary(errors))
        )
    return snapshot


def _revision_mismatch(path, expected, actual):
    return ValueError(
        "Archive revision mismatch for %s: expected %s, found %s. "
        "Run project archive --dry-run again and use the reported revision set."
        % (path, expected, actual)
    )


def _archive_preflight(cli_module, args):
    config = cli_module._config(args)
    paths = cli_module._normalize_paths(
        getattr(args, "paths", None) or [],
        config,
        stdin_when_empty=False,
    )
    if not paths:
        return

    dry_run = bool(getattr(args, "dry_run", False))

    # Parse revision tokens before command_archive's historical dry-run return.
    # An empty or malformed PATH= token must fail instead of looking like a
    # successful safety preview.
    revisions = cli_module._path_revision_map(getattr(args, "revision", None))

    source_snapshots = {}
    for path in paths:
        if path == "-":
            continue
        absolute = os.path.abspath(path)
        source_snapshots[absolute] = _snapshot_and_validate(
            cli_module, absolute, config, allow_missing=False
        )

    dest = getattr(args, "dest", None)
    destination = os.path.abspath(dest) if dest else None
    destination_snapshot = None
    if destination:
        destination_snapshot = _snapshot_and_validate(
            cli_module, destination, config, allow_missing=True
        )

    known_snapshots = dict(source_snapshots)
    if destination_snapshot is not None:
        known_snapshots[destination] = destination_snapshot

    # A supplied revision is a claim about the preview/write precondition. Do
    # not silently ignore an unrelated path or stale value, even on dry-run.
    for path, expected in revisions.items():
        snapshot = known_snapshots.get(path)
        if snapshot is None:
            raise ValueError(
                "Archive revision path is not a scanned source or destination: %s"
                % path
            )
        if str(expected) != str(snapshot.content_hash):
            raise _revision_mismatch(path, expected, snapshot.content_hash)

    # The active write target is the authoritative workspace source. An empty
    # value here is an incident signal, not a safe no-match result.
    write_file = cli_module.config_write_file(config)
    if write_file:
        write_path = _config_relative_path(write_file, config)
        write_snapshot = source_snapshots.get(write_path)
        if write_snapshot is not None and write_snapshot.size == 0:
            raise ValueError(
                "Refusing project archive because the active writable source is "
                "0 bytes: %s. Restore or verify the source before archiving."
                % write_path
            )

    required_paths = sorted(source_snapshots)
    if destination:
        required_paths.append(destination)

    if not dry_run:
        missing = [path for path in required_paths if path not in revisions]
        if missing:
            raise ValueError(
                "Live project archive requires an explicit --revision PATH=SHA256 "
                "for every scanned source and the destination. Missing: %s. "
                "Run the same command with --dry-run to print the exact revision "
                "set. Use <missing> only when the destination does not exist."
                % ", ".join(missing)
            )

    if dry_run:
        _print_project_revision_set(source_snapshots, destination, destination_snapshot)


def _print_project_revision_set(source_snapshots, destination, destination_snapshot):
    import sys

    sys.stdout.write("Revision set for a live project archive:\n")
    for path in sorted(source_snapshots):
        sys.stdout.write(
            "  --revision %s=%s\n" % (path, source_snapshots[path].content_hash)
        )
    if destination and destination_snapshot is not None:
        sys.stdout.write(
            "  --revision %s=%s\n" % (destination, destination_snapshot.content_hash)
        )


def _patch_archive_help(cli_module):
    """Explain the stricter project-archive revision contract in ``--help``."""
    original = cli_module.build_parser
    if getattr(original, "_lifetxt_archive_help_v3", False):
        return

    def build_parser():
        parser = original()
        project = _subparser(parser, "project")
        archive = _subparser(project, "archive") if project is not None else None
        if archive is not None:
            for action in archive._actions:
                if "--revision" in getattr(action, "option_strings", ()):
                    action.help = (
                        "Expected revision for a scanned source or destination as "
                        "PATH=SHA256. Required for every scanned source and the "
                        "destination on live project archive; dry-run prints the "
                        "exact set. Use <missing> for an absent destination."
                    )
                    break
        return parser

    build_parser._lifetxt_archive_help_v3 = True
    cli_module.build_parser = build_parser


def _subparser(parser, name):
    if parser is None:
        return None
    for action in getattr(parser, "_actions", ()):
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(name)
    return None
