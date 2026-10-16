import unittest
from unittest.mock import patch

from lifetxt.procedure_definition import ProcedureError
from lifetxt.procedure_graph import render_procedure
from lifetxt.procedure_validation import validate_definition
from tests.test_procedure_definition import SAMPLE, project


class GraphTests(unittest.TestCase):
    def test_text_mermaid_dot_share_choices_and_do_not_write(self):
        graph = validate_definition(project())
        text = render_procedure(graph)
        mermaid = render_procedure(graph, "mermaid")
        dot = render_procedure(graph, "dot")
        self.assertIn("yes -> e", text)
        self.assertIn("Read this instruction.", text)
        self.assertNotIn(
            "Read this instruction.", render_procedure(graph, include_body=False)
        )
        self.assertIn('p1 -->|"yes"| p3', mermaid)
        self.assertIn("p1 -> p3 [label=yes]", dot)
        self.assertIn("p1{", mermaid)
        self.assertIn("p3([", mermaid)
        self.assertIn("shape=diamond", dot)
        for fmt in ("text", "mermaid", "dot"):
            self.assertEqual(render_procedure(graph, fmt), render_procedure(graph, fmt))

    def test_unsafe_labels_controls_and_node_id_collisions(self):
        text = SAMPLE.replace(
            '"Inspect"', '"<script> %% \\" ] --> evil[ x \\\\ 日本語"'
        )
        text = text.replace("id:a ", "id:a-b ").replace(
            "proc_start:a", "proc_start:a-b"
        )
        text = text.replace("id:q ", "id:a_b ").replace("proc_next:q", "proc_next:a_b")
        graph = validate_definition(project(text))
        mermaid = render_procedure(graph, "mermaid")
        self.assertIn("p0[", mermaid)
        self.assertIn("p1{", mermaid)
        self.assertIn('p0 -->|"next"| p1', mermaid)
        self.assertNotIn("<script>", mermaid)
        self.assertNotIn("%%", mermaid)
        self.assertNotIn("evil[", mermaid)
        self.assertIn("日本語", mermaid)
        self.assertIn("#34;", mermaid)
        dot = render_procedure(graph, "dot")
        self.assertIn('\\"', dot)
        self.assertNotIn("\x1b", dot)

    def test_no_terminal_control_sequences(self):
        # The text parser permits control bytes in titles: display them as data.
        graph = validate_definition(
            project(SAMPLE.replace('"Inspect"', '"Inspect\x1b[31m"'))
        )
        for fmt in ("text", "mermaid", "dot"):
            output = render_procedure(graph, fmt)
            self.assertNotIn("\x1b", output)

    def test_output_limit_rejects_whole_result(self):
        graph = validate_definition(project())
        with patch("lifetxt.procedure_graph.MAX_OUTPUT_BYTES", 10):
            with self.assertRaises(ProcedureError) as caught:
                render_procedure(graph, "mermaid")
        self.assertEqual("PG301", caught.exception.diagnostics[0].code)

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            render_procedure(validate_definition(project()), "html")
