from dataclasses import replace
import unittest

from lifetxt.procedure_definition import ProcedureError
from lifetxt.procedure_transition import advance, initial_cursor
from lifetxt.procedure_validation import validate_definition
from tests.test_procedure_definition import project

REVISION = "a" * 64


def graph():
    return validate_definition(project(template_revision=REVISION))


class TransitionTests(unittest.TestCase):
    def test_explicit_next_choice_finish_and_no_mutation(self):
        g = graph()
        start = initial_cursor(g, True)
        q = advance(g, start, "next", template_revision=REVISION).cursor
        end = advance(g, q, "choose", choice="yes", template_revision=REVISION).cursor
        self.assertEqual(("e", "active"), (end.step, end.status))
        self.assertEqual(
            "completed",
            advance(g, end, "finish", template_revision=REVISION).cursor.status,
        )
        self.assertEqual(("a", 0), (start.step, start.hops))
        self.assertEqual(
            q, advance(g, start, "next", template_revision=REVISION).cursor
        )

    def test_wrong_kind_choice_missing_stale_and_unvalidated_refuse(self):
        g = graph()
        start = initial_cursor(g, True)
        q = advance(g, start, "next", template_revision=REVISION).cursor
        for cursor, op, choice, rev in [
            (start, "choose", "yes", REVISION),
            (start, "finish", None, REVISION),
            (start, "next", "x", REVISION),
            (start, "next", None, "b" * 64),
            (q, "choose", None, REVISION),
            (q, "choose", "YES", REVISION),
            (q, "next", None, REVISION),
            (q, "choose", "no;cmd", REVISION),
        ]:
            with self.subTest(op=op, choice=choice), self.assertRaises(ProcedureError):
                advance(g, cursor, op, choice=choice, template_revision=rev)
        with self.assertRaises(ProcedureError):
            initial_cursor(g)
        with self.assertRaises(ProcedureError):
            advance(object(), start, "next", template_revision=REVISION)
        with self.assertRaises(ProcedureError):
            advance(replace(g, start="bad"), start, "next", template_revision=REVISION)
        with self.assertRaises(ProcedureError):
            advance(g, replace(start, hops=True), "next", template_revision=REVISION)

    def test_pause_resume_and_abandon_have_no_edge_traversal(self):
        g = graph()
        start = initial_cursor(g, True)
        paused = advance(g, start, "pause", template_revision="stale").cursor
        self.assertEqual(("paused", "a", 0), (paused.status, paused.step, paused.hops))
        with self.assertRaises(ProcedureError):
            advance(g, paused, "resume", template_revision="stale")
        active = advance(g, paused, "resume", template_revision=REVISION).cursor
        self.assertEqual(start, active)
        terminal = advance(g, paused, "abandon", template_revision="stale").cursor
        with self.assertRaises(ProcedureError):
            advance(g, terminal, "pause", template_revision=REVISION)

    def test_visit_and_hop_limits_are_hard_guards(self):
        g = graph()
        cursor = initial_cursor(g, True)
        cursor = advance(g, cursor, "next", template_revision=REVISION).cursor
        for _ in range(19):
            cursor = advance(
                g, cursor, "choose", choice="no", template_revision=REVISION
            ).cursor
            cursor = advance(g, cursor, "next", template_revision=REVISION).cursor
        self.assertEqual(20, dict(cursor.visits)["q"])
        retry = advance(
            g, cursor, "choose", choice="no", template_revision=REVISION
        ).cursor
        with self.assertRaises(ProcedureError):
            advance(g, retry, "next", template_revision=REVISION)
        self.assertEqual(
            "abandoned",
            advance(g, retry, "abandon", template_revision=REVISION).cursor.status,
        )
        # At the hop cap use a valid 51-node visit distribution, not forged sums.
        text = (
            "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
            + "".join(
                "[N] N Step id:s%d parent:r proc_role:step proc_kind:action proc_next:s%d\n"
                % (i, i + 1)
                for i in range(51)
            )
            + "[N] N End id:s51 parent:r proc_role:step proc_kind:end\n"
        )
        from lifetxt.procedure_transition import Cursor

        g2 = validate_definition(project(text, template_revision=REVISION))
        at_limit = Cursor(
            "s50",
            "active",
            1000,
            tuple([("s%d" % i, 20) for i in range(50)] + [("s50", 1)]),
        )
        with self.assertRaises(ProcedureError):
            advance(g2, at_limit, "next", template_revision=REVISION)
