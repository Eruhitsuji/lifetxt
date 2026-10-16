"""Closed native procedure events and pure replay; no I/O or effect execution."""

import datetime
import hashlib
import json
import re
from dataclasses import dataclass

from .ids import id_value_is_safe
from .model import Item
from .parser import parse_text
from .serializer import item_to_line
from .procedure_definition import MAX_STEPS, ProcedureNode, ProcedureProjection
from .procedure_transition import (
    Cursor,
    advance,
    _advance,
    checked_graph,
    initial_cursor,
    refuse,
)
from .procedure_validation import (
    MAX_EDGES,
    MAX_HOPS,
    MAX_VISITS,
    ValidatedProcedure,
    validate_definition,
)

SCHEMA = "procedure-event-v1"
MAX_RUN_EVENTS = 5_000
MAX_LOG_EVENTS = 50_000
MAX_LOG_BYTES = 32 * 1024 * 1024
MAX_EVENT_BYTES = 2 * 1024 * 1024
_FIELDS = {
    "schema",
    "id",
    "run_id",
    "sequence",
    "request_id",
    "at",
    "actor",
    "source_handle",
    "root_id",
    "template_revision",
    "event",
    "previous_digest",
    "payload",
    "digest",
}
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"[0-9a-f]{32}\Z")


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def event_digest(event):
    return hashlib.sha256(
        canonical({k: v for k, v in event.items() if k != "digest"}).encode("utf-8")
    ).hexdigest()


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        refuse("PR201", "Unknown or missing event/schema/payload fields.")


def safe_id(value):
    return (
        isinstance(value, str)
        and len(value) <= 256
        and id_value_is_safe(value)
        and "\n" not in value
    )


def control_plan(graph):
    checked_graph(graph)
    return {
        "start": graph.start,
        "steps": [list(row) for row in graph.step_kinds],
        "edges": [[e.source, e.target, e.label] for e in graph.edges],
    }


def graph_from_plan(plan, root_id, revision):
    _keys(plan, {"start", "steps", "edges"})
    steps, edges = plan["steps"], plan["edges"]
    if (
        not isinstance(steps, list)
        or not 1 <= len(steps) <= MAX_STEPS
        or not isinstance(edges, list)
        or len(edges) > MAX_EDGES
    ):
        refuse("PR202", "Invalid or oversized frozen control plan.")
    if not safe_id(root_id) or not safe_id(plan["start"]):
        refuse("PR202", "Invalid frozen control identity.")
    ids = set()
    outgoing = {}
    for row in edges:
        if (
            not isinstance(row, list)
            or len(row) != 3
            or not all(isinstance(v, str) for v in row)
            or not safe_id(row[0])
            or not safe_id(row[1])
        ):
            refuse("PR202", "Invalid frozen control edge.")
        outgoing.setdefault(row[0], []).append((row[1], row[2]))
    nodes = []
    for row in steps:
        if (
            not isinstance(row, list)
            or len(row) != 2
            or not safe_id(row[0])
            or row[0] == root_id
            or row[0] in ids
            or row[1] not in ("action", "decision", "end")
        ):
            refuse("PR202", "Invalid or duplicate frozen step.")
        ident, kind = row
        ids.add(ident)
        details = [("proc_role", ("step",)), ("proc_kind", (kind,))]
        values = outgoing.get(ident, ())
        if kind == "action":
            if any(label != "next" for _, label in values):
                refuse("PR202", "Invalid frozen action label.")
            details.append(("proc_next", tuple(target for target, _ in values)))
        elif kind == "decision":
            details.append(
                ("proc_case", tuple(label + "=" + target for target, label in values))
            )
        elif values:
            refuse("PR202", "Frozen end must have no outgoing edge.")
        nodes.append(
            ProcedureNode(ident, "", "[N]", "N", (), root_id, 1, 0, "", tuple(details))
        )
    if set(outgoing) - ids:
        refuse("PR202", "Frozen edge has no source step.")
    root = ProcedureNode(
        root_id,
        "",
        "[N]",
        "N",
        (),
        None,
        0,
        0,
        "",
        (
            ("proc_role", ("root",)),
            ("proc_version", ("1",)),
            ("proc_start", (plan["start"],)),
        ),
    )
    graph = validate_definition(ProcedureProjection(root, tuple(nodes), "", revision))
    # Serialization order is canonical: reject hidden/reordered edge metadata.
    if control_plan(graph) != plan:
        refuse("PR202", "Frozen control plan is not canonical.")
    return graph


@dataclass(frozen=True)
class RunState:
    run_id: str
    actor: str
    source_handle: str
    root_id: str
    template_revision: str
    started_at: str
    sequence: int
    last_digest: str
    cursor: Cursor
    graph: ValidatedProcedure
    allow_loops: bool


def validate_event(event):
    _keys(event, _FIELDS)
    if (
        event["schema"] != SCHEMA
        or not isinstance(event["run_id"], str)
        or not _RUN.fullmatch(event["run_id"])
    ):
        refuse("PR203", "Unsupported event schema or invalid run ID.")
    seq = event["sequence"]
    if (
        type(seq) is not int
        or not 1 <= seq <= MAX_RUN_EVENTS
        or event["id"] != "pev_%s_%d" % (event["run_id"], seq)
    ):
        refuse("PR204", "Invalid event ID/sequence or run event limit exceeded.")
    if any(
        not isinstance(event[key], str) or not _TOKEN.fullmatch(event[key])
        for key in ("actor", "request_id")
    ):
        refuse("PR205", "Actor/request ID must be a bounded ASCII token.")
    if (
        not isinstance(event["source_handle"], str)
        or not re.fullmatch(r"src_[0-9a-f]{64}", event["source_handle"])
        or not safe_id(event["root_id"])
    ):
        refuse("PR205", "Invalid source/root binding.")
    if not isinstance(event["template_revision"], str) or not _HEX.fullmatch(
        event["template_revision"]
    ):
        refuse("PR205", "Invalid template revision.")
    at = event["at"]
    try:
        if not isinstance(at, str) or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at
        ):
            raise ValueError()
        datetime.datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        refuse("PR206", "Event time must be a valid canonical UTC timestamp.")
    if seq == 1:
        if event["event"] != "start" or event["previous_digest"] is not None:
            refuse("PR207", "A run must start at sequence 1 with no previous digest.")
        _keys(event["payload"], {"control", "allow_loops", "max_hops", "max_visits"})
        payload = event["payload"]
        if (
            type(payload["allow_loops"]) is not bool
            or type(payload["max_hops"]) is not int
            or payload["max_hops"] != MAX_HOPS
            or type(payload["max_visits"]) is not int
            or payload["max_visits"] != MAX_VISITS
        ):
            refuse("PR208", "Unsupported or changed run guard contract.")
    else:
        if (
            event["event"]
            not in ("next", "choose", "pause", "resume", "finish", "abandon")
            or not isinstance(event["previous_digest"], str)
            or not _HEX.fullmatch(event["previous_digest"])
        ):
            refuse("PR207", "Unknown event operation or missing previous digest.")
        _keys(event["payload"], {"from_step", "to_step", "choice"})
        payload = event["payload"]
        if (
            not safe_id(payload["from_step"])
            or not safe_id(payload["to_step"])
            or (
                payload["choice"] is not None and not isinstance(payload["choice"], str)
            )
        ):
            refuse("PR208", "Invalid transition payload.")
    try:
        encoded = canonical(event).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        refuse("PR209", "Event must contain canonical JSON data only.")
    if len(encoded) > MAX_EVENT_BYTES or event["digest"] != event_digest(event):
        refuse("PR209", "Event digest mismatch or event size limit exceeded.")
    return event


def _consume(state, event):
    validate_event(event)
    if state is None:
        if event["sequence"] != 1:
            refuse("PR210", "Missing start event.")
        p = event["payload"]
        graph = graph_from_plan(
            p["control"], event["root_id"], event["template_revision"]
        )
        cursor = initial_cursor(graph, p["allow_loops"])
        started_at = event["at"]
        allow_loops = p["allow_loops"]
    else:
        if (
            event["sequence"] != state.sequence + 1
            or event["previous_digest"] != state.last_digest
        ):
            refuse("PR210", "Duplicate, missing or out-of-order event sequence/digest.")
        if any(
            event[k] != getattr(state, k)
            for k in (
                "run_id",
                "actor",
                "source_handle",
                "root_id",
                "template_revision",
            )
        ):
            refuse("PR211", "Event belongs to a different run/actor/source/revision.")
        graph = state.graph
        p = event["payload"]
        transition = _advance(
            graph,
            state.cursor,
            event["event"],
            choice=p["choice"],
            template_revision=state.template_revision,
        )
        if (p["from_step"], p["to_step"]) != (transition.from_step, transition.to_step):
            refuse("PR212", "Event transition does not match the frozen procedure.")
        cursor, started_at, allow_loops = (
            transition.cursor,
            state.started_at,
            state.allow_loops,
        )
    return RunState(
        event["run_id"],
        event["actor"],
        event["source_handle"],
        event["root_id"],
        event["template_revision"],
        started_at,
        event["sequence"],
        event["digest"],
        cursor,
        graph,
        allow_loops,
    )


def replay(events):
    """Replay exactly one run in supplied order, without sorting or side effects."""
    state, requests = None, set()
    for event in events:
        validate_event(event)
        if event["request_id"] in requests:
            refuse("PR213", "Duplicate request ID.")
        state = _consume(state, event)
        requests.add(event["request_id"])
    if state is None:
        refuse("PR210", "Run has no start event.")
    return state


def replay_log(events):
    states, requests, ids = {}, set(), set()
    for index, event in enumerate(events):
        if index >= MAX_LOG_EVENTS:
            refuse("PR214", "Run log event limit exceeded.")
        validate_event(event)
        if event["request_id"] in requests or event["id"] in ids:
            refuse("PR213", "Duplicate event/request ID in run log.")
        states[event["run_id"]] = _consume(states.get(event["run_id"]), event)
        requests.add(event["request_id"])
        ids.add(event["id"])
    return states


def _event(
    run_id,
    sequence,
    request_id,
    at,
    actor,
    source_handle,
    root_id,
    revision,
    operation,
    previous_digest,
    payload,
):
    result = dict(
        schema=SCHEMA,
        id="pev_%s_%d" % (run_id, sequence),
        run_id=run_id,
        sequence=sequence,
        request_id=request_id,
        at=at,
        actor=actor,
        source_handle=source_handle,
        root_id=root_id,
        template_revision=revision,
        event=operation,
        previous_digest=previous_digest,
        payload=payload,
    )
    result["digest"] = event_digest(result)
    validate_event(result)
    return result


def start_event(
    graph, *, run_id, request_id, at, actor, source_handle, allow_loops=False
):
    initial_cursor(graph, allow_loops)
    result = _event(
        run_id,
        1,
        request_id,
        at,
        actor,
        source_handle,
        graph.projection.root.id,
        graph.projection.template_revision,
        "start",
        None,
        dict(
            control=control_plan(graph),
            allow_loops=allow_loops,
            max_hops=MAX_HOPS,
            max_visits=MAX_VISITS,
        ),
    )
    replay([result])
    return result


def operation_event(
    state, operation, *, request_id, at, choice=None, observed_template_revision=None
):
    transition = advance(
        state.graph,
        state.cursor,
        operation,
        choice=choice,
        template_revision=observed_template_revision,
    )
    return _event(
        state.run_id,
        state.sequence + 1,
        request_id,
        at,
        state.actor,
        state.source_handle,
        state.root_id,
        state.template_revision,
        operation,
        state.last_digest,
        dict(from_step=transition.from_step, to_step=transition.to_step, choice=choice),
    )


def event_to_line(event):
    validate_event(event)
    return item_to_line(
        Item(
            "[N]",
            "N",
            "procedure_event",
            {
                "record": ["procedure_event"],
                "id": [event["id"]],
                "event_data": [canonical(event)],
            },
        )
    )


def _json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            refuse("PR215", "Duplicate JSON object key in event.")
        value[key] = item
    return value


def events_from_text(text):
    if (
        len(text.encode("utf-8")) > MAX_LOG_BYTES
        or sum(
            1
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        > MAX_LOG_EVENTS
    ):
        refuse("PR214", "Run log byte/record limit exceeded.")
    # Each event is one physical line; bodies/joins can hide data or order.
    if any(
        line.lstrip().startswith("|") or line.rstrip().endswith("\\")
        for line in text.splitlines()
    ):
        refuse("PR215", "Run log events must be single-line records.")
    items, diagnostics = parse_text(text, check_ids=False, check_references=False)
    if any(row.severity == "error" for row in diagnostics):
        refuse("PR215", "Run log has invalid life.txt syntax.")
    events = []
    for item in items:
        if (
            item.status != "[N]"
            or item.kind != "N"
            or item.title != "procedure_event"
            or set(item.details) != {"record", "id", "event_data"}
            or item.details["record"] != ["procedure_event"]
            or any(len(values) != 1 for values in item.details.values())
        ):
            refuse("PR215", "Expected a closed procedure_event-only run log.")
        data = item.details["event_data"][0]
        if len(data.encode("utf-8")) > MAX_EVENT_BYTES:
            refuse("PR214", "Event byte limit exceeded.")
        try:
            event = json.loads(data, object_pairs_hook=_json_object)
        except (ValueError, RecursionError):
            refuse("PR215", "Invalid event JSON.")
        validate_event(event)
        if item.details["id"] != [event["id"]]:
            refuse("PR215", "Record and event ID disagree.")
        events.append(event)
    return tuple(events)
