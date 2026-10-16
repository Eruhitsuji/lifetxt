"""Explicit local procedure run logs, committed by the shared CAS/journal writer."""

import datetime
import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass

from . import mutation
from .multi_target import apply_multi_target, text_plan
from .transaction_journal import journal_directory, list_journals
from .procedure_definition import MAX_SOURCE_BYTES, ProcedureError
from .procedure_run_model import (
    RunState,
    MAX_LOG_BYTES,
    MAX_LOG_EVENTS,
    events_from_text,
    event_to_line,
    operation_event,
    replay_log,
    start_event,
    control_plan,
    safe_id,
)
from .procedure_transition import refuse


@dataclass(frozen=True)
class LogSnapshot:
    text: str
    revision: str
    events: tuple[dict, ...]
    states: dict[str, RunState]
    bom: bool = False


@dataclass(frozen=True)
class RequestReceipt:
    request_id: str
    run_id: str
    sequence: int
    event: str


@dataclass(frozen=True)
class RunSnapshot:
    template_revision: str
    log_revision: str
    source_handle: str
    root_id: str
    state: RunState | None
    runs: tuple[RunState, ...]
    start_step: str | None
    blocked: bool
    transaction_id: str | None = None
    receipt: RequestReceipt | None = None


def source_handle(path):
    identity = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    return "src_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _read(path, limit, missing=False):
    if str(path) == "-":
        refuse("PR301", "Run source/log must be explicit regular files, not stdin.")
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0),
        )
    except FileNotFoundError:
        if missing:
            return None
        raise
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            refuse("PR301", "Run source/log must be regular files.")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        refuse("PR302", "Run source/log byte limit exceeded.")
    return raw


def _paths(source, log):
    if os.path.islink(log):
        refuse("PR303", "Run log symlinks are not supported.")
    if os.path.normcase(os.path.realpath(source)) == os.path.normcase(
        os.path.realpath(log)
    ):
        refuse("PR303", "Run log must be separate from the definition.")
    if os.path.exists(source) and os.path.exists(log) and os.path.samefile(source, log):
        refuse("PR303", "Run log and definition must not be hardlink aliases.")


def read_log(path):
    if os.path.islink(path):
        refuse("PR303", "Run log symlinks are not supported.")
    raw = _read(path, MAX_LOG_BYTES, missing=True)
    if raw is None:
        return LogSnapshot("", mutation.MISSING_HASH, (), {})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        refuse("PR304", "Run log must be UTF-8.")
    events = events_from_text(text)
    states = replay_log(events)
    return LogSnapshot(
        text, mutation.hash_bytes(raw), events, states, raw.startswith(b"\xef\xbb\xbf")
    )


def _observed_revision(source):
    try:
        raw = _read(source, MAX_SOURCE_BYTES, missing=True)
        return mutation.MISSING_HASH if raw is None else mutation.hash_bytes(raw)
    except (OSError, ProcedureError):
        return "<unavailable>"


def inspect_run(source, root_id, log, run_id=None, request_id=None):
    _paths(source, log)
    snapshot = read_log(log)
    handle = source_handle(source)
    receipt = None
    if request_id is not None:
        matches = [
            event for event in snapshot.events if event["request_id"] == request_id
        ]
        if len(matches) != 1 or (run_id is not None and run_id != matches[0]["run_id"]):
            refuse(
                "PR314", "Request ID not found for this run. No operation was replayed."
            )
        event = matches[0]
        run_id = event["run_id"]
        receipt = RequestReceipt(
            event["request_id"], run_id, event["sequence"], event["event"]
        )
    state = snapshot.states.get(run_id) if run_id is not None else None
    if run_id is not None and state is None:
        refuse("PR305", "Run ID does not exist in this log.")
    if state is not None and (
        state.source_handle != handle or state.root_id != root_id
    ):
        refuse("PR306", "Run is bound to a different source/root.")
    observed = _observed_revision(source)
    start = None
    if state is None:
        from .procedure_cli import read_definition

        graph = read_definition(source, root_id)
        observed, start = graph.projection.template_revision, graph.start
    runs = tuple(
        s
        for s in snapshot.states.values()
        if s.source_handle == handle and s.root_id == root_id
    )
    return RunSnapshot(
        observed,
        snapshot.revision,
        handle,
        root_id,
        state,
        runs,
        start,
        state is not None and observed != state.template_revision,
        receipt=receipt,
    )


def _writable(log, config):
    from .cli import _ensure_writable_path

    try:
        _ensure_writable_path(log, config, "procedure run")
        _ensure_writable_path(os.path.realpath(log), config, "procedure run")
    except ValueError:
        refuse("PR307", "Run log is generated, read-only or not writable.")
    parent = os.path.dirname(os.path.abspath(log))
    if (
        not os.path.isdir(parent)
        or not os.stat(parent).st_mode & 0o222
        or not os.access(parent, os.W_OK)
    ):
        refuse("PR307", "Run log parent must exist and be writable.")


def _no_pending(journal_dir):
    if os.path.isdir(journal_dir) and len(os.listdir(journal_dir)) > 20_000:
        refuse(
            "PR308", "Journal inspection limit reached; use operator archival tools."
        )
    if list_journals(journal_dir, include_terminal=False):
        refuse(
            "PR308",
            "Unresolved/corrupt transaction journal: inspect and recover with existing safety tools before writing.",
        )


def _revision(value, missing=False):
    return isinstance(value, str) and (
        bool(re.fullmatch(r"[0-9a-f]{64}", value))
        or (missing and value == mutation.MISSING_HASH)
    )


def write_run(
    source,
    root_id,
    log,
    operation,
    *,
    actor,
    request_id,
    expected_template_revision,
    expected_log_revision,
    expected_step,
    expected_sequence,
    run_id=None,
    choice=None,
    allow_loops=False,
    config=None,
    journal_dir=None,
    failure_hook=None,
):
    """One explicit request -> one recoverable log event, never a template write."""
    config = config or {}
    if (
        not _revision(expected_template_revision)
        or not _revision(expected_log_revision, missing=True)
        or type(expected_sequence) is not int
        or expected_sequence < 0
    ):
        refuse(
            "PR309", "Exact template/log revisions and expected sequence are required."
        )
    if operation not in {
        "start",
        "next",
        "choose",
        "pause",
        "resume",
        "finish",
        "abandon",
    } or (operation != "start" and allow_loops):
        refuse("PR309", "Unsupported operation/options.")
    _paths(source, log)
    _writable(log, config)
    canonical_log = os.path.realpath(log)
    log_snapshot = read_log(log)
    if log_snapshot.revision != expected_log_revision:
        refuse(
            "PR310",
            "Stale log revision. Reread explicitly; do not retry automatically.",
        )
    if any(event["request_id"] == request_id for event in log_snapshot.events):
        refuse(
            "PR311",
            "Request ID already committed. Inspect the log; no event was appended.",
        )
    if len(log_snapshot.events) >= MAX_LOG_EVENTS:
        refuse("PR302", "Run log event limit reached.")
    handle = source_handle(source)
    observed = _observed_revision(source)
    now = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    if operation == "start":
        from .procedure_cli import read_definition

        if run_id is not None or choice is not None or expected_sequence != 0:
            refuse("PR309", "Start requires a new run, sequence 0 and no choice.")
        graph = read_definition(source, root_id)
        if (
            graph.projection.template_revision != expected_template_revision
            or graph.start != expected_step
        ):
            refuse("PR312", "Stale template/start step precondition.")
        run_id = uuid.uuid4().hex
        event = start_event(
            graph,
            run_id=run_id,
            request_id=request_id,
            at=now,
            actor=actor,
            source_handle=handle,
            allow_loops=allow_loops,
        )
    else:
        state = log_snapshot.states.get(run_id)
        if state is None:
            refuse("PR305", "Run ID does not exist in this log.")
        if (
            state.actor,
            state.source_handle,
            state.root_id,
            state.template_revision,
        ) != (actor, handle, root_id, expected_template_revision):
            refuse("PR306", "Run actor/source/root/template binding mismatch.")
        if (state.cursor.step, state.sequence) != (expected_step, expected_sequence):
            refuse("PR313", "Stale run step/sequence precondition.")
        if operation not in {"pause", "abandon"}:
            from .procedure_cli import read_definition

            graph = read_definition(source, root_id)
            if (
                graph.projection.template_revision != state.template_revision
                or control_plan(graph) != control_plan(state.graph)
            ):
                refuse(
                    "PR312",
                    "Template changed or event control plan mismatches its definition.",
                )
        event = operation_event(
            state,
            operation,
            request_id=request_id,
            at=now,
            choice=choice,
            observed_template_revision=observed,
        )
    newline = "\r\n" if "\r\n" in log_snapshot.text else "\n"
    prefix = log_snapshot.text
    replacement = (
        prefix
        + ("" if not prefix or prefix.endswith(("\n", "\r")) else newline)
        + event_to_line(event)
        + newline
    )
    if (
        len(replacement.encode("utf-8")) + (3 if log_snapshot.bom else 0)
        > MAX_LOG_BYTES
    ):
        refuse("PR302", "Run log byte limit reached.")
    # Validate the entire replacement, including all independent interleaved runs.
    replay_log(events_from_text(replacement))
    journal_dir = journal_dir or journal_directory(config, writable_path=log)
    _no_pending(journal_dir)

    def transform(current):
        if current != log_snapshot.text:
            refuse("PR310", "Run log changed during admission.")
        _paths(source, log)
        _writable(log, config)
        _no_pending(journal_dir)
        return replacement

    def hook(phase, plan, index):
        if failure_hook is not None:
            failure_hook(phase, plan, index)
        if phase == "before_commit":
            _paths(source, log)
            _writable(log, config)
            if (
                os.path.realpath(log) != canonical_log
                or source_handle(source) != handle
            ):
                refuse("PR306", "Source/log path binding changed during commit.")
            # pause/abandon can dispose of the original run after source edits.
            if (
                operation not in {"pause", "abandon"}
                and _observed_revision(source) != expected_template_revision
            ):
                refuse("PR312", "Template changed before log commit.")
            read_log(log)  # bounded regular-file admission immediately before write

    result = apply_multi_target(
        [
            text_plan(
                log,
                transform,
                expected_log_revision,
                create=expected_log_revision == mutation.MISSING_HASH,
                default="",
                validate=lambda text: replay_log(events_from_text(text)),
            )
        ],
        operation="procedure.run." + operation,
        journal_dir=journal_dir,
        config=config,
        failure_hook=hook,
    )
    final = read_log(log)
    if final.revision != result.targets[0].after_hash:
        refuse(
            "PR310",
            "Log changed after commit; outcome uncertain. Inspect before any new operation.",
        )
    observed = _observed_revision(source)
    state = final.states[run_id]
    return RunSnapshot(
        observed,
        final.revision,
        handle,
        root_id,
        state,
        (),
        None,
        observed != state.template_revision,
        result.transaction_id,
    )
