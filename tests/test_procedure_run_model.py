import copy
import unittest
from unittest.mock import patch

from lifetxt.procedure_definition import ProcedureError
from lifetxt.procedure_run_model import (
    start_event,
    operation_event,
    replay,
    replay_log,
    event_digest,
    event_to_line,
    events_from_text,
)
from tests.test_procedure_transition import graph, REVISION

NOW = "2026-10-16T10:00:00Z"
HANDLE = "src_" + "b" * 64


def start(run="1" * 32, request="req1", actor="alice"):
    return start_event(
        graph(),
        run_id=run,
        request_id=request,
        actor=actor,
        at=NOW,
        source_handle=HANDLE,
        allow_loops=True,
    )


def operation(events, verb, choice=None, request=None):
    state = replay(events)
    return operation_event(
        state,
        verb,
        request_id=request or "req%d" % (state.sequence + 1),
        at=NOW,
        choice=choice,
        observed_template_revision=REVISION,
    )


class RunModelTests(unittest.TestCase):
    def test_roundtrip_replay_and_only_explicit_finish_completes(self):
        events = [start()]
        for verb, choice in [
            ("next", None),
            ("choose", "yes"),
            ("pause", None),
            ("resume", None),
        ]:
            events.append(operation(events, verb, choice))
        self.assertEqual("active", replay(events).cursor.status)
        events.append(operation(events, "finish"))
        text = "\n".join(event_to_line(e) for e in events) + "\n"
        restored = events_from_text(text)
        self.assertEqual(events, list(restored))
        self.assertEqual(replay(events), replay(restored))
        self.assertEqual(
            ("completed", "e", 6),
            (
                replay(restored).cursor.status,
                replay(restored).cursor.step,
                replay(restored).sequence,
            ),
        )
        with self.assertRaises(ProcedureError):
            operation(events, "pause")

    def test_same_template_two_runs_interleave_independently(self):
        first = start()
        second = start("2" * 32, "second", "bob")
        next_event = operation([first], "next")
        states = replay_log([first, second, next_event])
        self.assertEqual("q", states[first["run_id"]].cursor.step)
        self.assertEqual("a", states[second["run_id"]].cursor.step)
        with self.assertRaises(ProcedureError):
            replay([first, second])

    def test_closed_fields_guard_schema_digest_and_binding_refusals(self):
        first = start()
        second = operation([first], "next")
        cases = []
        for field, value in [
            ("schema", "future"),
            ("sequence", True),
            ("run_id", "bad"),
            ("at", "2026-02-30T00:00:00Z"),
            ("actor", "private value"),
            ("source_handle", "/private/path"),
            ("template_revision", "bad"),
        ]:
            e = copy.deepcopy(first)
            e[field] = value
            e["digest"] = event_digest(e)
            cases.append([e])
        e = copy.deepcopy(first)
        e["payload"]["body"] = "secret"
        e["digest"] = event_digest(e)
        cases.append([e])
        e = copy.deepcopy(first)
        e["payload"]["max_hops"] = 0
        e["digest"] = event_digest(e)
        cases.append([e])
        e = copy.deepcopy(first)
        e["secret"] = "bad"
        e["digest"] = event_digest(e)
        cases.append([e])
        e = copy.deepcopy(first)
        e["payload"]["control"]["steps"][0][0] = "bad"
        e["digest"] = event_digest(e)
        cases.append([e])
        for field, value in [
            ("sequence", 4),
            ("previous_digest", "c" * 64),
            ("actor", "bob"),
            ("root_id", "different"),
            ("template_revision", "d" * 64),
        ]:
            e = copy.deepcopy(second)
            e[field] = value
            e["digest"] = event_digest(e)
            cases.append([first, e])
        e = copy.deepcopy(second)
        e["payload"]["to_step"] = "e"
        e["digest"] = event_digest(e)
        cases.append([first, e])
        e = copy.deepcopy(second)
        e["digest"] = "d" * 64
        cases.append([first, e])
        cases.extend(
            [
                [first, second, second],
                [second],
                [first, operation([first], "pause", request="req1")],
                [None],
            ]
        )
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ProcedureError):
                replay(events)

    def test_frozen_plan_does_not_copy_titles_body_or_private_path(self):
        from lifetxt.procedure_validation import validate_definition
        from tests.test_procedure_definition import SAMPLE, project

        g = validate_definition(
            project(
                SAMPLE.replace("Read this instruction.", "TOP_SECRET").replace(
                    '"Inspect"', '"PRIVATE_TITLE"'
                ),
                source="/private/path",
                template_revision=REVISION,
            )
        )
        event = start_event(
            g,
            run_id="1" * 32,
            request_id="r1",
            actor="alice",
            at=NOW,
            source_handle=HANDLE,
            allow_loops=True,
        )
        line = event_to_line(event)
        for private in ("TOP_SECRET", "PRIVATE_TITLE", "/private/path"):
            self.assertNotIn(private, line)
        self.assertEqual("a", replay([event]).cursor.step)

    def test_corrupt_unknown_extra_record_and_duplicate_json_fail(self):
        line = event_to_line(start()) + "\n"
        for text in (
            line + "[ ] T unrelated id:task\n",
            line.replace("id:pev_", "id:wrong_"),
            line + "| injected body\n",
            line.replace("procedure-event-v1", "procedure-event-v2"),
            line.replace("request_id", "extra_field", 1),
        ):
            with self.subTest(text=text), self.assertRaises(ProcedureError):
                replay_log(events_from_text(text))
        # A duplicate property must be rejected before a JSON parser overwrites it.
        from lifetxt.model import Item
        from lifetxt.serializer import item_to_line
        from lifetxt.procedure_run_model import canonical

        data = canonical(start()).replace('"schema":', '"schema":"other","schema":')
        text = item_to_line(
            Item(
                "[N]",
                "N",
                "procedure_event",
                {
                    "record": ["procedure_event"],
                    "id": [start()["id"]],
                    "event_data": [data],
                },
            )
        )
        with self.assertRaises(ProcedureError):
            events_from_text(text)

    def test_event_cap_duplicate_global_request_and_unknown_choice(self):
        first = start()
        other = start("2" * 32, "req1")
        with self.assertRaises(ProcedureError):
            replay_log([first, other])
        q = operation([first], "next")
        with self.assertRaises(ProcedureError):
            operation([first, q], "choose", "unknown")
        with patch("lifetxt.procedure_run_model.MAX_RUN_EVENTS", 2):
            with self.assertRaises(ProcedureError):
                operation([first, q], "pause")
