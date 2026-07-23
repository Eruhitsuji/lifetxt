"""Compatibility fixes for the P0 safety layer discovered by the full matrix."""

from __future__ import unicode_literals

import os


_INSTALLED = False


def install_safety_compat_v2():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_cli_timezone_installer()
    _patch_doctor_dispatch()
    _patch_revision_conflict_output()
    _patch_stable_diagnostic_shape()
    _INSTALLED = True


def _patch_cli_timezone_installer():
    from . import runtime_safety_v2

    def install_cli_timezone_context(cli_module):
        from .config import config_paths, load_config
        from .safety_foundation import read_text_exact
        from .timezone_policy import resolve_timezone_name, timezone_context

        current = cli_module.main
        if getattr(current, "_lifetxt_timezone_context_v2", False):
            return

        def main(argv=None):
            raw = list(argv or [])
            config_path = None
            for index, value in enumerate(raw):
                if value == "--config" and index + 1 < len(raw):
                    config_path = raw[index + 1]
                elif value.startswith("--config="):
                    config_path = value.split("=", 1)[1]
            config = load_config(config_path) or {}
            candidates = []
            for value in raw:
                if value and not value.startswith("-") and os.path.exists(value):
                    candidates.append(value)
            candidates.extend(config_paths(config) or [])
            text = ""
            for path in candidates:
                if path and path != "-" and os.path.exists(path):
                    try:
                        text, _raw, _bom = read_text_exact(path)
                        break
                    except OSError:
                        continue
            name = resolve_timezone_name(config, text=text)
            with timezone_context(name):
                return current(argv)

        main._lifetxt_timezone_context_v2 = True
        cli_module.main = main

    runtime_safety_v2.install_cli_timezone_context = install_cli_timezone_context


def _patch_doctor_dispatch():
    from . import extra_cli

    original = extra_cli.main
    if getattr(original, "_lifetxt_doctor_dispatch_v2", False):
        return

    def main(argv=None, config_path=None):
        raw = list(argv or [])
        if raw and raw[0] == "doctor" and "--workspace-safety" not in raw:
            raw.insert(1, "--workspace-safety")
        return original(raw, config_path=config_path)

    main._lifetxt_doctor_dispatch_v2 = True
    extra_cli.main = main


def _patch_revision_conflict_output():
    from . import extra_cli, extra_safety
    from .mutation import MutationConflict

    original = extra_safety.command_safety
    if getattr(original, "_lifetxt_revision_conflict_output_v2", False):
        return

    def command_safety(args, config_data):
        try:
            return original(args, config_data)
        except MutationConflict as exc:
            if getattr(args, "safety_action", None) != "revisions":
                raise
            report = {
                "ok": False,
                "error": "CONFLICT",
                "operation": exc.operation,
                "path": exc.path,
                "expected_revision": exc.expected_hash,
                "current_revision": exc.actual_hash,
                "message": str(exc),
            }
            return extra_safety._output(report, args, failure=True)

    command_safety._lifetxt_revision_conflict_output_v2 = True
    extra_safety.command_safety = command_safety
    extra_cli.command_safety = command_safety


def _patch_stable_diagnostic_shape():
    from . import release_policy, safety_foundation, workspace_diagnostics

    original = workspace_diagnostics.stable_file_diagnostics
    if getattr(original, "_lifetxt_complete_shape_v2", False):
        return

    def stable_file_diagnostics(path):
        report = original(path)
        rows = []
        for raw in report.get("diagnostics") or []:
            row = dict(raw)
            row.setdefault("severity", "error")
            row.setdefault("code", "P000")
            row.setdefault("message", "")
            row.setdefault("source", path)
            row.setdefault("line", None)
            row.setdefault("column", None)
            row.setdefault(
                "span",
                {
                    "start": {"line": row.get("line"), "column": row.get("column")},
                    "end": {"line": row.get("line"), "column": row.get("column")},
                },
            )
            row.setdefault("hint", "")
            rows.append(row)
        rows = workspace_diagnostics._sort_diagnostics(rows)
        return {
            "ok": not any(row.get("severity") == "error" for row in rows),
            "item_count": report.get("item_count", 0),
            "diagnostics": rows,
        }

    stable_file_diagnostics._lifetxt_complete_shape_v2 = True
    workspace_diagnostics.stable_file_diagnostics = stable_file_diagnostics
    safety_foundation.stable_diagnostics = stable_file_diagnostics
    release_policy.stable_diagnostics = stable_file_diagnostics
