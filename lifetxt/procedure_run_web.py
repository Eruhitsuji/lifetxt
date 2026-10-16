"""Authenticated single-operator procedure runs; paths and actor are server-owned."""

import hmac
import json
import os
import re
from dataclasses import replace

from .ids import id_key_from_config
from .multi_target import MultiTargetError
from .mutation import MutationError
from .procedure_cli import read_definition
from .procedure_definition import ProcedureError
from .procedure_run_model import control_plan, safe_id
from .procedure_run_store import inspect_run, read_log, source_handle, write_run
from .procedure_transition import advance
from .procedure_web import _bounded, _token, sources
from .transaction_journal import TransactionJournalError
from .web_transport import expected_origin, origin_parts

ACTOR = "web-shared"
MAX_REQUEST_BYTES = 8192
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_RUN = re.compile(r"[0-9a-f]{32}\Z")
_FIELDS = {
    "source",
    "root_id",
    "operation",
    "request_id",
    "template_revision",
    "log_revision",
    "step",
    "sequence",
}


def fail(status, code, message):
    from fastapi import HTTPException

    raise HTTPException(status, {"error": code, "message": message})


def authorize(app, request, write=False):
    config = app.state.config
    if (config.get("remote") or {}).get("enabled"):
        fail(
            403,
            "PROCEDURE_REMOTE_DISABLED",
            "Procedure runs require the local Web operator boundary.",
        )
    token = (config.get("api") or {}).get("token")
    if not isinstance(token, str) or not token:
        fail(
            403,
            "PROCEDURE_AUTH_REQUIRED",
            "Configure a Web API token before using runs.",
        )
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not hmac.compare_digest(
        values[0].encode(), ("Bearer " + token).encode()
    ):
        fail(401, "PROCEDURE_AUTH_REQUIRED", "A valid Bearer token is required.")
    if id_key_from_config(config) != "id":
        fail(403, "PROCEDURE_ID_POLICY", "Procedure v1 requires canonical IDs.")
    if write:
        if app.state.read_only:
            fail(403, "READ_ONLY", "This server is read-only.")
        origins = request.headers.getlist("origin")
        expected = expected_origin(request, config)
        if (
            len(origins) != 1
            or expected is None
            or origin_parts(origins[0]) != origin_parts(expected)
        ):
            fail(403, "PROCEDURE_ORIGIN", "A matching browser Origin is required.")
        sites = request.headers.getlist("sec-fetch-site")
        if sites and sites != ["same-origin"]:
            fail(403, "PROCEDURE_ORIGIN", "Cross-site run operations are refused.")
        types = request.headers.getlist("content-type")
        if (
            len(types) != 1
            or types[0].split(";", 1)[0].strip().lower() != "application/json"
        ):
            fail(415, "PROCEDURE_JSON_REQUIRED", "Use application/json.")


def select_source(app, source, root_id):
    if (
        not isinstance(source, str)
        or not isinstance(root_id, str)
        or not safe_id(root_id)
    ):
        fail(
            422, "PROCEDURE_INPUT", "Select a configured source and canonical root ID."
        )
    path = sources(app).get(source)
    writable = app.state.writable_path
    if path is None:
        fail(404, "PROCEDURE_NOT_FOUND", "Unknown configured source.")
    if not writable or _token(writable) != source:
        fail(
            403,
            "PROCEDURE_SOURCE_READ_ONLY",
            "Runs are available only for the configured writable source.",
        )
    return path, str(writable) + ".procedure-runs.txt"


def writable(app, source, log):
    from .cli import _ensure_writable_path

    try:
        for path in (source, os.path.realpath(source), log, os.path.realpath(log)):
            _ensure_writable_path(path, app.state.config, "procedure run Web")
    except ValueError:
        fail(403, "PROCEDURE_SOURCE_READ_ONLY", "Source/log is generated or read-only.")


def own(state, source, root):
    return (
        state.actor == ACTOR
        and state.source_handle == source_handle(source)
        and state.root_id == root
    )


def owned_snapshot(app, source, root, log, run_id=None, request_id=None):
    # Check ownership before the store's receipt lookup can return another actor.
    snapshot = read_log(log)
    if run_id is not None:
        if not isinstance(run_id, str) or not _RUN.fullmatch(run_id):
            fail(422, "PROCEDURE_INPUT", "Invalid run ID.")
        state = snapshot.states.get(run_id)
        if state is None or not own(state, source, root):
            fail(
                404,
                "PROCEDURE_RUN_NOT_FOUND",
                "Run unavailable for this operator/source/root.",
            )
    if request_id is not None:
        if not isinstance(request_id, str) or not _TOKEN.fullmatch(request_id):
            fail(422, "PROCEDURE_INPUT", "Invalid request ID.")
        event = next(
            (e for e in snapshot.events if e["request_id"] == request_id), None
        )
        if event is None:
            return None
        state = snapshot.states[event["run_id"]]
        if not own(state, source, root) or (
            run_id is not None and run_id != state.run_id
        ):
            fail(
                404,
                "PROCEDURE_RUN_NOT_FOUND",
                "Request unavailable for this operator/source/root.",
            )
    result = inspect_run(source, root, log, run_id, request_id)
    if result.state is not None and not own(result.state, source, root):
        fail(404, "PROCEDURE_RUN_NOT_FOUND", "Run ownership changed during inspection.")
    return replace(result, runs=tuple(s for s in result.runs if own(s, source, root)))


def project_snapshot(app, snapshot, source, root, log):
    state = snapshot.state
    graph = None
    blocked = snapshot.blocked
    try:
        graph = read_definition(source, root)
        if state and (
            graph.projection.template_revision != state.template_revision
            or control_plan(graph) != control_plan(state.graph)
        ):
            graph, blocked = None, True
    except (OSError, ProcedureError):
        blocked = True
    reason = "READ_ONLY" if app.state.read_only else None
    try:
        writable(app, source, log)
    except Exception as exc:
        from fastapi import HTTPException

        if not isinstance(exc, HTTPException):
            raise
        reason = "SOURCE_READ_ONLY"
    actions = []
    if not reason:
        if state is None and graph is not None:
            actions = [
                {"operation": "start", "requires_loop_confirmation": graph.cyclic}
            ]
        elif state is not None:
            candidates = [
                (op, None) for op in ("next", "pause", "resume", "finish", "abandon")
            ]
            candidates += [
                ("choose", e.label)
                for e in state.graph.edges
                if e.source == state.cursor.step
            ]
            for op, choice in candidates:
                try:
                    advance(
                        state.graph,
                        state.cursor,
                        op,
                        choice=choice,
                        template_revision="<unavailable>"
                        if blocked
                        else snapshot.template_revision,
                    )
                    actions.append(
                        {"operation": op, **({"choice": choice} if choice else {})}
                    )
                except ProcedureError:
                    pass
    instruction = None
    if graph is not None and state is not None:
        node = next(n for n in graph.projection.steps if n.id == state.cursor.step)
        instruction = {
            "title": node.title,
            "body": list(node.body),
            "kind": dict(graph.step_kinds)[node.id],
        }
    from .remote_contracts_v6 import remote_client_time_header

    return _bounded(
        {
            "client_time_header": remote_client_time_header(app.state.config),
            "schema": "procedure-run-web-v1",
            "source": _token(source),
            "root_id": root,
            "source_revision": snapshot.template_revision,
            "template_revision": state.template_revision
            if state
            else snapshot.template_revision,
            "log_revision": snapshot.log_revision,
            "step": state.cursor.step if state else snapshot.start_step,
            "sequence": state.sequence if state else 0,
            "run_id": state.run_id if state else None,
            "status": state.cursor.status if state else "not_started",
            "blocked": blocked,
            "read_only_reason": reason,
            "actions": actions,
            "instruction": instruction,
            "runs": [
                {
                    "run_id": s.run_id,
                    "status": s.cursor.status,
                    "step": s.cursor.step,
                    "sequence": s.sequence,
                }
                for s in snapshot.runs
            ],
            "receipt": None
            if snapshot.receipt is None
            else {
                "request_id": snapshot.receipt.request_id,
                "run_id": snapshot.receipt.run_id,
                "sequence": snapshot.receipt.sequence,
                "event": snapshot.receipt.event,
            },
        }
    )


def validate_payload(value):
    if not isinstance(value, dict):
        fail(422, "PROCEDURE_INPUT", "A closed JSON object is required.")
    op = value.get("operation")
    if not isinstance(op, str):
        fail(422, "PROCEDURE_INPUT", "Operation must be a string.")
    expected = _FIELDS | ({"run_id"} if op != "start" else set())
    if op == "choose":
        expected.add("choice")
    if op == "start" and "allow_loops" in value:
        expected.add("allow_loops")
    if set(value) != expected or op not in {
        "start",
        "next",
        "choose",
        "pause",
        "resume",
        "finish",
        "abandon",
    }:
        fail(422, "PROCEDURE_INPUT", "Unknown/missing operation fields.")
    if any(
        not isinstance(value[k], str) for k in expected - {"sequence", "allow_loops"}
    ):
        fail(422, "PROCEDURE_INPUT", "String tokens are required.")
    if (
        type(value["sequence"]) is not int
        or value["sequence"] < 0
        or not safe_id(value["step"])
        or not _TOKEN.fullmatch(value["request_id"])
    ):
        fail(422, "PROCEDURE_INPUT", "Invalid sequence, step or request token.")
    if "allow_loops" in value and type(value["allow_loops"]) is not bool:
        fail(422, "PROCEDURE_INPUT", "Loop acknowledgement must be boolean.")
    return value


def register_run_routes(app):
    from fastapi import Request, Response

    # A glob expanded at startup may contain this reserved event-only sidecar.
    # Keep it out of the ordinary Items/Notes read sources, including restarts.
    log = str(app.state.writable_path) + ".procedure-runs.txt"
    app.state.paths = [p for p in app.state.paths if _token(p) != _token(log)]

    def result_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    def guarded(call):
        try:
            return call()
        except ProcedureError:
            fail(
                409,
                "PROCEDURE_CONFLICT",
                "Run or template changed/invalid. Reload or inspect the request receipt; never retry automatically.",
            )
        except (MutationError, MultiTargetError, TransactionJournalError, OSError):
            fail(
                409,
                "PROCEDURE_OUTCOME_UNCERTAIN",
                "Inspect the original request receipt and operator journal recovery before any new operation.",
            )
        except ValueError:
            fail(
                422,
                "PROCEDURE_INPUT",
                "Invalid procedure precondition or configuration.",
            )

    @app.get("/api/procedure-runs")
    def get_run(
        request: Request,
        response: Response,
        source: str,
        root_id: str,
        run_id: str | None = None,
        request_id: str | None = None,
    ):
        authorize(app, request)
        result_headers(response)
        path, log = select_source(app, source, root_id)

        def read():
            snapshot = owned_snapshot(app, path, root_id, log, run_id, request_id)
            if snapshot is None:
                return {
                    "schema": "procedure-run-web-v1",
                    "receipt": None,
                    "outcome": "not_found",
                }
            return project_snapshot(app, snapshot, path, root_id, log)

        return guarded(read)

    @app.post("/api/procedure-runs")
    async def mutate_run(request: Request, response: Response):
        authorize(app, request, write=True)
        result_headers(response)
        chunks, count = [], 0
        async for chunk in request.stream():
            count += len(chunk)
            if count > MAX_REQUEST_BYTES:
                fail(
                    413, "PROCEDURE_INPUT_LIMIT", "Run request exceeds the byte limit."
                )
            chunks.append(chunk)

        def closed_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON field")
                result[key] = value
            return result

        try:
            value = json.loads(b"".join(chunks), object_pairs_hook=closed_pairs)
        except (ValueError, UnicodeError, RecursionError):
            fail(422, "PROCEDURE_INPUT", "Invalid closed JSON payload.")
        value = validate_payload(value)
        path, log = select_source(app, value["source"], value["root_id"])
        writable(app, path, log)

        def commit():
            snapshot = owned_snapshot(
                app, path, value["root_id"], log, value.get("run_id")
            )
            matches = request.headers.getlist("if-match")
            if not matches:
                fail(
                    428,
                    "PROCEDURE_SOURCE_REVISION_REQUIRED",
                    "Use the source revision from the displayed snapshot.",
                )
            if matches != ['"' + snapshot.template_revision + '"']:
                fail(
                    409,
                    "PROCEDURE_CONFLICT",
                    "Source revision changed. Reload explicitly.",
                )
            write_run(
                path,
                value["root_id"],
                log,
                value["operation"],
                actor=ACTOR,
                request_id=value["request_id"],
                expected_template_revision=value["template_revision"],
                expected_log_revision=value["log_revision"],
                expected_step=value["step"],
                expected_sequence=value["sequence"],
                run_id=value.get("run_id"),
                choice=value.get("choice"),
                allow_loops=value.get("allow_loops", False),
                config=app.state.config,
            )
            # Resolve by the committed receipt; no mutation is replayed on uncertainty.
            final = owned_snapshot(
                app, path, value["root_id"], log, request_id=value["request_id"]
            )
            return project_snapshot(app, final, path, value["root_id"], log)

        # File locks and journal I/O must not block the ASGI event loop.
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(lambda: guarded(commit))
