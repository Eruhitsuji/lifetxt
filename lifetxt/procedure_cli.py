"""Explicit single-file procedure CLI. Read-only; no log or run creation."""

import os
import stat
import sys

from .atomic import write_console_text
from .ids import id_key_from_config
from .mutation import hash_bytes
from .parser import parse_text
from .procedure_definition import (
    MAX_RECORDS,
    MAX_SOURCE_BYTES,
    ProcedureDiagnostic,
    ProcedureError,
    project_definition,
)
from .procedure_graph import render_procedure
from .procedure_validation import validate_definition


def main(argv):
    """Use the shared parser/config without speculative source-file pre-reads."""
    from . import cli
    from .cli_error_guidance import render_value_error_text

    try:
        cleaned, config_path, workspace = cli._extract_config_arg(argv)
        args = cli.build_parser().parse_args(cleaned)
        args.config = config_path
        args.workspace = workspace
        args.config_data = cli.load_config(config_path)
        cli._maybe_apply_workspace(args)
        return command_procedure(args)
    except ValueError as exc:
        write_console_text(sys.stderr, render_value_error_text(exc))
        return 1


def register_procedure(subparsers):
    command = subparsers.add_parser(
        "procedure", help="Read-only human procedure definitions and flowcharts."
    )
    commands = command.add_subparsers(dest="procedure_command", required=True)
    for name in ("show", "graph"):
        parser = commands.add_parser(
            name, help="Read a validated procedure; never execute its instructions."
        )
        parser.add_argument(
            "file",
            help="One explicit UTF-8 life.txt file (no workspace glob or stdin).",
        )
        parser.add_argument("--id", required=True, help="Explicit procedure root ID.")
        if name == "graph":
            parser.add_argument(
                "--format", choices=("text", "mermaid", "dot"), default="text"
            )
        parser.set_defaults(func=command_procedure)


def read_definition(path, root_id, *, id_key="id"):
    """Bound the read before parsing, keeping the exact source-byte hash.

    hash_bytes is the same SHA-256 primitive as read_text_snapshot; a bounded
    read avoids that unbounded snapshot reader's allocation on malicious files.
    Opening once avoids separate stat/read source identity races.
    """
    if path == "-":
        raise ProcedureError(
            [
                ProcedureDiagnostic(
                    "PG401",
                    "Procedure v1 requires an explicit regular file, not stdin.",
                )
            ]
        )
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ProcedureError(
                [
                    ProcedureDiagnostic(
                        "PG401", "Procedure source must be a regular file."
                    )
                ]
            )
        raw = handle.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ProcedureError(
            [
                ProcedureDiagnostic(
                    "PG402", "Procedure source exceeds %d bytes." % MAX_SOURCE_BYTES
                )
            ]
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProcedureError(
            [ProcedureDiagnostic("PG403", "Procedure source must be UTF-8.")]
        ) from exc
    # Count logical item candidates before constructing Item/Diagnostic objects.
    # Body lines/comments are data; backslash joins follow the existing parser.
    count, joined = 0, False
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if not joined and stripped and not stripped.startswith(("#", "|")):
            count += 1
            if count > MAX_RECORDS:
                raise ProcedureError(
                    [
                        ProcedureDiagnostic(
                            "PG002", "Input exceeds %d records." % MAX_RECORDS
                        )
                    ]
                )
        joined = line.rstrip(" ").endswith("\\")
    items, diagnostics = parse_text(text, check_ids=False, check_references=False)
    errors = [
        ProcedureDiagnostic(
            "PG404", "Invalid life.txt syntax (%s)." % row.code, row.line or 0
        )
        for row in diagnostics
        if row.severity == "error"
    ]
    if errors:
        raise ProcedureError(errors)
    projection = project_definition(
        items,
        root_id,
        source=os.path.basename(path),
        template_revision=hash_bytes(raw),
        id_key=id_key,
    )
    return validate_definition(projection)


def command_procedure(args):
    try:
        graph = read_definition(
            args.file,
            args.id,
            id_key=id_key_from_config(getattr(args, "config_data", None) or {}),
        )
        output = render_procedure(
            graph,
            getattr(args, "format", "text"),
            include_body=args.procedure_command == "show",
        )
    except ProcedureError as exc:
        write_console_text(sys.stderr, str(exc) + "\n")
        return 1
    except OSError:
        write_console_text(
            sys.stderr, "ERROR PG405: Cannot read the explicit procedure file.\n"
        )
        return 1
    for diagnostic in graph.diagnostics:
        write_console_text(sys.stderr, diagnostic.format() + "\n")
    write_console_text(sys.stdout, output)
    return 0
