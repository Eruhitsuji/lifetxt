"""Contract-level projection tests; generic parser behavior remains unchanged."""

from dataclasses import FrozenInstanceError
import unittest

from lifetxt.parser import parse_text
from lifetxt.procedure_definition import ProcedureError, project_definition
from lifetxt.serializer import item_to_line

SAMPLE = """[N] N "Maintenance" id:r proc_role:root proc_version:1 proc_start:a
[N] N "Inspect" id:a parent:r proc_role:step proc_kind:action proc_next:q
| Read this instruction.
[N] N "Result" id:q parent:r proc_role:step proc_kind:decision proc_case:yes=e proc_case:no=retry
[N] N "Retry manually" id:retry parent:r proc_role:step proc_kind:action proc_next:q
[N] N "End" id:e parent:r proc_role:step proc_kind:end
"""


def project(text=SAMPLE, root="r", **kwargs):
    items, diagnostics = parse_text(text)
    if any(row.severity == "error" for row in diagnostics):
        raise AssertionError("Invalid test fixture: %r" % diagnostics)
    return project_definition(items, root, **kwargs)


class ProjectionTests(unittest.TestCase):
    def assert_error(self, code, text=SAMPLE, **kwargs):
        with self.assertRaises(ProcedureError) as caught:
            project(text, **kwargs)
        self.assertIn(code, [row.code for row in caught.exception.diagnostics])

    def test_preserves_body_order_location_details_and_does_not_mutate(self):
        items, _ = parse_text(SAMPLE)
        before = [item_to_line(item) for item in items]
        result = project_definition(
            items, "r", source="template", template_revision="abc"
        )
        self.assertEqual(["a", "q", "retry", "e"], [n.id for n in result.steps])
        self.assertEqual(("Read this instruction.",), result.steps[0].body)
        self.assertEqual(("yes=e", "no=retry"), result.steps[1].values("proc_case"))
        self.assertEqual(
            (2, "template", 1),
            (result.steps[0].line, result.steps[0].source, result.steps[0].depth),
        )
        self.assertEqual("abc", result.template_revision)
        self.assertEqual(before, [item_to_line(item) for item in items])
        items[1].details["body"][0] = "changed"
        self.assertEqual(("Read this instruction.",), result.steps[0].body)
        with self.assertRaises(FrozenInstanceError):
            result.steps[0].title = "changed"

    def test_other_root_and_ordinary_records_not_included(self):
        extra = SAMPLE.replace("id:r ", "id:r2 ").replace("parent:r ", "parent:r2 ")
        # Give all IDs unique names, preserving parent references.
        for old, new in (("a", "a2"), ("q", "q2"), ("retry", "retry2"), ("e", "e2")):
            extra = extra.replace("id:" + old + " ", "id:" + new + " ").replace(
                "id:" + old + "\n", "id:" + new + "\n"
            )
            extra = extra.replace(
                "proc_start:" + old + "\n", "proc_start:" + new + "\n"
            ).replace("proc_next:" + old + "\n", "proc_next:" + new + "\n")
            extra = extra.replace("=" + old + " ", "=" + new + " ").replace(
                "=" + old + "\n", "=" + new + "\n"
            )
        text = (
            SAMPLE
            + extra
            + "[ ] T Work id:task next:a\n[N] N Plain id:note proc_hint:description\n"
        )
        self.assertEqual(4, len(project(text).steps))
        self.assertEqual("r2", project(text, root="r2").root.id)

    def test_empty_missing_and_nonoptin_root(self):
        for text in ("", "[N] N Plain id:r\n", "[ ] T Work id:r\n"):
            with self.subTest(text=text):
                self.assert_error("PG005", text)

    def test_duplicate_ids_including_same_record_repeated_id(self):
        self.assert_error("PG004", SAMPLE + "[N] N Other id:a\n")
        self.assert_error("PG004", SAMPLE.replace("id:a parent", "id:a id:a parent"))

    def test_duplicate_unsafe_missing_id_or_wrong_record(self):
        for text, code in (
            (SAMPLE.replace("id:a ", ""), "PG013"),
            (SAMPLE.replace("id:a ", 'id:"a b" '), "PG013"),
            (SAMPLE.replace('[N] N "Inspect"', '[ ] T "Inspect"'), "PG014"),
            (SAMPLE.replace("parent:r", "parent:r parent:r", 1), "PG009"),
            (SAMPLE.replace("parent:r", "parent:missing", 1), "PG009"),
            (SAMPLE.replace("id:r ", "id:r parent:a "), "PG006"),
        ):
            with self.subTest(code=code, text=text):
                self.assert_error(code, text)

    def test_hierarchy_cycle_and_nonprofile_parent(self):
        self.assert_error(
            "PG007",
            SAMPLE.replace("id:a parent:r", "id:a parent:q").replace(
                "id:q parent:r", "id:q parent:a"
            ),
        )
        self.assert_error(
            "PG008",
            SAMPLE.replace("id:a parent:r", "id:a parent:plain")
            + "[N] N Plain id:plain\n",
        )

    def test_nested_steps_input_order_not_execution_order(self):
        result = project(SAMPLE.replace("id:q parent:r", "id:q parent:a"))
        self.assertEqual([1, 2, 1, 1], [n.depth for n in result.steps])

    def test_multiple_sources_or_alternate_id_key_refused(self):
        items, _ = parse_text(SAMPLE)
        items[0].details["_source_file"] = ["a.txt"]
        items[1].details["_source_file"] = ["b.txt"]
        with self.assertRaises(ProcedureError) as caught:
            project_definition(items, "r")
        self.assertEqual("PG003", caught.exception.diagnostics[0].code)
        self.assert_error("PG001", id_key="uid")

    def test_record_step_body_and_depth_limits(self):
        self.assert_error("PG002", SAMPLE + "[N] N filler\n" * 10_000)
        many = (
            "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
            + "".join(
                "[N] N Step id:s%d parent:r proc_role:step proc_kind:end\n" % i
                for i in range(501)
            )
        )
        self.assert_error("PG012", many)
        self.assertEqual(500, len(project(many.rsplit("\n", 2)[0] + "\n").steps))
        self.assert_error(
            "PG015", SAMPLE.replace("Read this instruction.", "界" * 22_000)
        )
        deep = (
            "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
            + "".join(
                "[N] N Step id:s%d parent:%s proc_role:step proc_kind:end\n"
                % (i, "r" if i == 0 else "s%d" % (i - 1))
                for i in range(33)
            )
        )
        self.assert_error("PG010", deep)
        self.assertEqual(32, len(project(deep.rsplit("\n", 2)[0] + "\n").steps))

    def test_generic_parser_and_serializer_preserve_profile_with_w106(self):
        items, diagnostics = parse_text(SAMPLE)
        self.assertEqual({"W106"}, {row.code for row in diagnostics})
        again, _ = parse_text("\n".join(item_to_line(item) for item in items) + "\n")
        self.assertEqual(
            [(i.status, i.kind, i.title, i.details) for i in items],
            [(i.status, i.kind, i.title, i.details) for i in again],
        )
