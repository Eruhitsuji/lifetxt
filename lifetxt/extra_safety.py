"""Extended CLI commands for release safety and Format 1.0 foundations."""

from __future__ import unicode_literals

import json
import os
import sys

from .extra_common import _json_text, _load_config, _resolved_input_paths, _write_output
from .release_policy import release_gate
from .safety_foundation import (
    CANON_VERSION,
    FORMAT_VERSION,
    audit_python_writes,
    canonical_issues,
    canonicalize_text,
    capability_document,
    file_directives,
    format_version_report,
    inspect_locks,
    read_text_exact,
    resolve_timezone_policy,
    schema_bundle,
    serve_target_diagnostic,
    stable_diagnostics,
    write_schema_bundle,
)


def command_safety(args, config_data):
    action = args.safety_action
    if action == "locks":
        paths = _resolved_input_paths(args.paths, config_data)
        records = inspect_locks(paths, stale_after=args.stale_after)
        return _output({"count": len(records), "locks": records}, args)
    if action == "serve-target":
        paths = _resolved_input_paths(args.paths, config_data)
        write_path = args.write_file
        if not write_path:
            from .config import config_write_file
            write_path = config_write_file(config_data) or (paths[0] if paths else "")
        report = serve_target_diagnostic(paths, write_path)
        return _output(report, args)
    if action == "timezone":
        text = ""
        paths = _resolved_input_paths(args.paths, config_data)
        if paths and paths[0] != "-" and os.path.exists(paths[0]):
            text, _raw, _bom = read_text_exact(paths[0])
        report = resolve_timezone_policy(config_data, text=text, cli_timezone=args.timezone)
        return _output(report, args)
    if action == "write-routes":
        root = os.path.abspath(args.root or os.getcwd())
        findings = audit_python_writes(root)
        report = {"ok": not findings, "root": root, "count": len(findings), "findings": findings}
        return _output(report, args, failure=bool(findings and args.strict))
    if action == "release-gate":
        root = os.path.abspath(args.root or os.getcwd())
        paths = _resolved_input_paths(args.paths, config_data) if args.paths else []
        report = release_gate(root, paths=paths)
        return _output(report, args, failure=not report["ok"])
    raise ValueError("Unknown safety action: %s" % action)


def command_format(args, _config_data):
    action = args.format_action
    if action == "info":
        text, _raw, _bom = read_text_exact(args.path)
        directives, duplicates = file_directives(text)
        report = {
            "format": format_version_report(text),
            "canonical_version": CANON_VERSION,
            "directives": directives,
            "duplicate_directives": duplicates,
            "policies": {
                "encoding": "UTF-8 without BOM",
                "line_endings": "LF",
                "unicode": "NFC",
                "detail_keys": "case-sensitive; canonical lowercase",
                "tags_ids_contexts_users_teams_groups_areas_projects": "case-sensitive",
                "metadata_precedence": ["CLI", "file directives", "config", "built-in defaults"],
                "multi_file": "IDs are workspace-unique; input order is authoritative; writes require an explicit target",
            },
        }
        return _output(report, args)
    if action == "check":
        report = stable_diagnostics(args.path)
        return _output(report, args, failure=not report["ok"])
    if action == "canon":
        text, raw, bom = read_text_exact(args.path)
        replacement = canonicalize_text(text)
        issues = canonical_issues(text, raw_bytes=raw, bom=bom, source=args.path)
        changed = replacement != text or bom
        if args.write and changed:
            from .mutation import read_text_snapshot, write_text
            snapshot = read_text_snapshot(args.path)
            write_text(
                args.path,
                replacement,
                expected_hash=snapshot.content_hash,
                operation="format.canon",
                create=False,
            )
        report = {
            "path": args.path,
            "canonical_version": CANON_VERSION,
            "changed": changed,
            "written": bool(args.write and changed),
            "diagnostics": issues,
        }
        if args.output and not args.write:
            _write_output(replacement, args.output)
            report["output"] = args.output
        return _output(report, args, failure=bool(issues and args.strict and not args.write))
    if action == "schemas":
        names = write_schema_bundle(args.directory)
        return _output({"schema_version": "1", "directory": os.path.abspath(args.directory), "files": names}, args)
    raise ValueError("Unknown format action: %s" % action)


def command_capabilities(args, config_data):
    targets = []
    from .config import config_write_file
    write_target = config_write_file(config_data)
    if write_target:
        targets.append(os.path.abspath(write_target))
    report = capability_document(
        read_only=args.read_only,
        authentication=args.authentication,
        writable_targets=targets,
    )
    return _output(report, args)


def _output(report, args, failure=False):
    fmt = getattr(args, "format", "json")
    pretty = bool(getattr(args, "pretty", False))
    output = getattr(args, "output", None)
    if fmt == "json":
        text = _json_text(report, pretty=pretty)
    else:
        text = _text_report(report)
    _write_output(text, output)
    return 1 if failure else 0


def _text_report(value, prefix=""):
    lines = []
    if isinstance(value, dict):
        for key, child in value.items():
            label = "%s%s" % (prefix, key)
            if isinstance(child, (dict, list)):
                lines.append(label + ":")
                lines.append(_text_report(child, prefix + "  ").rstrip("\n"))
            else:
                lines.append("%s: %s" % (label, child))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(prefix + "-")
                lines.append(_text_report(child, prefix + "  ").rstrip("\n"))
            else:
                lines.append(prefix + "- " + str(child))
    else:
        lines.append(prefix + str(value))
    return "\n".join(lines) + "\n"
