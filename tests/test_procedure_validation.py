import unittest

from lifetxt.procedure_definition import ProcedureError
from lifetxt.procedure_validation import validate_definition
from tests.test_procedure_definition import SAMPLE, project


class ValidationTests(unittest.TestCase):
    def test_choice_order_merge_and_exit_cycle(self):
        graph = validate_definition(project())
        self.assertEqual("a", graph.start)
        self.assertEqual(
            [
                ("a", "q", "next"),
                ("q", "e", "yes"),
                ("q", "retry", "no"),
                ("retry", "q", "next"),
            ],
            [(e.source, e.target, e.label) for e in graph.edges],
        )
        self.assertTrue(graph.cyclic)
        self.assertEqual("PG201", graph.diagnostics[0].code)

    def test_three_choices_and_shared_target_are_not_a_cycle(self):
        text = SAMPLE.replace(
            "proc_case:no=retry", "proc_case:no=retry proc_case:skip=e"
        ).replace('proc_next:q\n[N] N "End"', 'proc_next:e\n[N] N "End"')
        graph = validate_definition(project(text))
        self.assertFalse(graph.cyclic)
        self.assertEqual(
            ["yes", "no", "skip"], [e.label for e in graph.edges if e.source == "q"]
        )

    def test_semantic_rejections_are_explicit_and_stably_ordered(self):
        cases = [
            ("proc_version:1", "proc_version:2", "PG101"),
            ("proc_version:1", "proc_version:1 proc_version:1", "PG101"),
            ("proc_start:a", "proc_start:a proc_start:q", "PG101"),
            ("proc_start:a", "proc_start:missing", "PG109"),
            ("proc_kind:action proc_next:q", "proc_kind:unknown proc_next:q", "PG101"),
            ("proc_next:q", "proc_next:q proc_next:q", "PG101"),
            ("proc_next:q", "", "PG101"),
            ("proc_next:q", "proc_next:missing", "PG110"),
            ("proc_next:q", "proc_next:r", "PG110"),
            ("proc_next:q", "proc_next:q proc_typo:1", "PG102"),
            ("proc_kind:end", "proc_kind:end proc_next:a", "PG104"),
            ("proc_kind:end", "proc_kind:end proc_version:1", "PG103"),
            ("proc_case:no=retry", "proc_case:yes=retry", "PG107"),
            ("proc_case:no=retry", "", "PG105"),
            ("proc_case:no=retry", 'proc_case:"disk>10=retry"', "PG106"),
            ("proc_case:no=retry", "proc_case:NO=retry", "PG106"),
            ("proc_case:no=retry", "proc_case:no=missing", "PG110"),
            ("proc_case:no=retry", "proc_case:no=e", "PG111"),
        ]
        for old, new, expected in cases:
            with self.subTest(expected=expected, replacement=new):
                with self.assertRaises(ProcedureError) as caught:
                    validate_definition(project(SAMPLE.replace(old, new, 1)))
                diagnostics = caught.exception.diagnostics
                self.assertIn(expected, [d.code for d in diagnostics])
                self.assertEqual(
                    list(diagnostics),
                    sorted(diagnostics, key=lambda d: (d.line, d.code, d.message)),
                )

    def test_closed_cycle_cannot_render_as_valid(self):
        text = SAMPLE.replace("proc_case:yes=e", "proc_case:yes=q")
        with self.assertRaises(ProcedureError) as caught:
            validate_definition(project(text))
        self.assertIn("PG112", [d.code for d in caught.exception.diagnostics])

    def test_self_loop_with_exit_is_warning(self):
        text = SAMPLE.replace(
            'proc_next:q\n[N] N "End"', 'proc_next:e\n[N] N "End"'
        ).replace("proc_case:no=retry", "proc_case:no=q proc_case:retry=retry")
        self.assertTrue(validate_definition(project(text)).cyclic)

    def test_choice_limit_and_cross_root_refusal(self):
        text = SAMPLE.replace(
            "proc_case:no=retry", " ".join("proc_case:c%d=retry" % i for i in range(16))
        )
        with self.assertRaises(ProcedureError) as caught:
            validate_definition(project(text))
        self.assertIn("PG105", [d.code for d in caught.exception.diagnostics])
        text = (
            SAMPLE.replace("proc_next:q", "proc_next:other", 1)
            + "[N] N Other id:other proc_role:root proc_version:1 proc_start:z\n[N] N End id:z parent:other proc_role:step proc_kind:end\n"
        )
        with self.assertRaises(ProcedureError) as caught:
            validate_definition(project(text))
        self.assertIn("PG110", [d.code for d in caught.exception.diagnostics])

    def test_ordinary_relation_keys_never_become_transition_edges(self):
        text = SAMPLE.replace(
            "id:a parent:r", "id:a parent:r depends_on:e follows:e next:e"
        )
        graph = validate_definition(project(text))
        self.assertEqual(["q"], [e.target for e in graph.edges if e.source == "a"])

    def test_500_step_limit_uses_iterative_graph_walks(self):
        text = (
            "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
            + "".join(
                "[N] N Step id:s%d parent:r proc_role:step %s\n"
                % (
                    i,
                    "proc_kind:end"
                    if i == 499
                    else "proc_kind:action proc_next:s%d" % (i + 1),
                )
                for i in range(500)
            )
        )
        graph = validate_definition(project(text))
        self.assertEqual(499, len(graph.edges))
        self.assertFalse(graph.cyclic)

    def test_edge_limit_is_enforced(self):
        # All 500 nodes are reachable; repeated labels merge onto the next node.
        text = "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
        for i in range(499):
            text += (
                "[N] N Step id:s%d parent:r proc_role:step proc_kind:decision %s\n"
                % (i, " ".join("proc_case:c%d=s%d" % (j, i + 1) for j in range(5)))
            )
        text += "[N] N End id:s499 parent:r proc_role:step proc_kind:end\n"
        with self.assertRaises(ProcedureError) as caught:
            validate_definition(project(text))
        self.assertIn("PG108", [row.code for row in caught.exception.diagnostics])
