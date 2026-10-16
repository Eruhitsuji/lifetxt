"""Explicit non-TTY run navigation; instructions themselves are never executed."""

import sys
from dataclasses import replace

from .atomic import write_console_text
from .ids import id_key_from_config
from .mutation import MutationError
from .multi_target import MultiTargetError
from .transaction_journal import TransactionJournalError
from .procedure_definition import ProcedureError
from .procedure_graph import console_text
from .procedure_run_store import inspect_run, write_run


def register_run(commands):
    parser = commands.add_parser(
        "run", help="Explicit local human-run events (no external action execution)."
    )
    verbs = parser.add_subparsers(dest="run_command", required=True)
    for verb in (
        "start",
        "show",
        "next",
        "choose",
        "pause",
        "resume",
        "finish",
        "abandon",
    ):
        command = verbs.add_parser(verb)
        command.add_argument("file", help="Explicit definition file.")
        command.add_argument("--id", required=True, help="Procedure root ID.")
        command.add_argument(
            "--log", required=True, help="Explicit separate run log file."
        )
        command.add_argument("--run-id", required=verb not in {"start", "show"})
        if verb == "show":
            command.add_argument(
                "--request-id", help="Read a committed request receipt; never retry it."
            )
        if verb != "show":
            for option in (
                "actor",
                "request-id",
                "template-revision",
                "log-revision",
                "step",
            ):
                command.add_argument("--" + option, required=True)
            command.add_argument("--sequence", required=True, type=int)
        if verb == "start":
            command.add_argument("--allow-loops", action="store_true")
        if verb == "choose":
            command.add_argument("--choice", required=True)
        command.set_defaults(func=command_run)


def format_snapshot(snapshot, definition=None):
    lines = [
        "Source handle: " + snapshot.source_handle,
        "Root: " + console_text(snapshot.root_id),
        "Template revision: " + snapshot.template_revision,
        "Log revision: " + snapshot.log_revision,
    ]
    state = snapshot.state
    if state is None:
        lines.append("Start step: " + console_text(snapshot.start_step))
        for run in snapshot.runs:
            lines.append(
                "Run: %s  Status: %s  Step: %s  Sequence: %d"
                % (
                    run.run_id,
                    run.cursor.status,
                    console_text(run.cursor.step),
                    run.sequence,
                )
            )
    else:
        lines.extend(
            [
                "Run: " + state.run_id,
                "Actor: " + state.actor,
                "Bound template revision: " + state.template_revision,
                "Status: " + state.cursor.status,
                "Step: " + console_text(state.cursor.step),
                "Sequence: %d" % state.sequence,
                "Hops: %d" % state.cursor.hops,
                "Blocked: "
                + ("template changed/unavailable" if snapshot.blocked else "no"),
            ]
        )
        for edge in state.graph.edges:
            if edge.source == state.cursor.step:
                lines.append(
                    "Choice: %s -> %s" % (edge.label, console_text(edge.target))
                )
    if state is not None and definition is not None and not snapshot.blocked:
        node = next(
            node for node in definition.projection.steps if node.id == state.cursor.step
        )
        lines.append("Instruction: " + console_text(node.title))
        for body in node.body:
            lines.extend("  | " + console_text(line) for line in body.splitlines())
    if snapshot.receipt is not None:
        receipt = snapshot.receipt
        lines.append(
            "Committed request: %s  Event: %s  Sequence: %d"
            % (receipt.request_id, receipt.event, receipt.sequence)
        )
    if snapshot.transaction_id:
        lines.append("Transaction: " + snapshot.transaction_id)
    return "\n".join(lines) + "\n"


def command_run(args):
    try:
        config = getattr(args, "config_data", {}) or {}
        if id_key_from_config(config) != "id":
            raise ValueError("Procedure v1 requires canonical id.")
        if args.run_command == "show":
            snapshot = inspect_run(
                args.file, args.id, args.log, args.run_id, args.request_id
            )
        else:
            snapshot = write_run(
                args.file,
                args.id,
                args.log,
                args.run_command,
                actor=args.actor,
                request_id=args.request_id,
                expected_template_revision=args.template_revision,
                expected_log_revision=args.log_revision,
                expected_step=args.step,
                expected_sequence=args.sequence,
                run_id=args.run_id,
                choice=getattr(args, "choice", None),
                allow_loops=getattr(args, "allow_loops", False),
                config=config,
            )
        definition = None
        if snapshot.state is not None and not snapshot.blocked:
            from .procedure_cli import read_definition

            try:
                definition = read_definition(args.file, args.id)
                if (
                    definition.projection.template_revision
                    != snapshot.state.template_revision
                ):
                    snapshot = replace(
                        snapshot,
                        blocked=True,
                        template_revision=definition.projection.template_revision,
                    )
                    definition = None
            except (ProcedureError, OSError):
                snapshot = replace(
                    snapshot, blocked=True, template_revision="<unavailable>"
                )
        write_console_text(sys.stdout, format_snapshot(snapshot, definition))
        return 0
    except ProcedureError as exc:
        write_console_text(sys.stderr, str(exc) + "\n")
    except (MutationError, MultiTargetError, TransactionJournalError):
        # Journal/lock exceptions can contain absolute/private paths or errors.
        write_console_text(
            sys.stderr,
            "ERROR PR399: Write conflict or uncertain transaction. Inspect run and existing transaction recovery tools; do not automatically retry.\n",
        )
    except OSError:
        write_console_text(
            sys.stderr,
            "ERROR PR398: Cannot access the explicit source/log or transaction storage.\n",
        )
    except ValueError:
        write_console_text(
            sys.stderr, "ERROR PR397: Invalid run configuration/precondition.\n"
        )
    return 1
