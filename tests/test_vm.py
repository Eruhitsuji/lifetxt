"""Tests for the opt-in lifetxt VM (#560): program building and execution."""

import unittest

from lifetxt.parser import parse_text
from lifetxt.vm import (
    Counter,
    DecJzInstruction,
    HaltInstruction,
    IncInstruction,
    VMProgramError,
    VMStepLimitExceeded,
    build_program,
    program_to_dot,
    program_to_mermaid,
    run_program,
)


MOVE_X_TO_Y = """[N] N Counter_X id:x value:3
[N] N Counter_Y id:y value:0

[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
[N] N Increment_Y id:s2 op:inc var:y next:s1

[N] N Halt id:halt op:halt
"""


def _items(text):
    items, diagnostics = parse_text(text)
    return items


class BuildProgramTests(unittest.TestCase):
    def test_counters_and_instructions_are_recognized_by_kind(self):
        program = build_program(_items(MOVE_X_TO_Y))
        self.assertEqual({"x", "y"}, set(program.counters))
        self.assertEqual({"s1", "s2", "halt"}, set(program.instructions))
        self.assertIsInstance(program.counters["x"], Counter)
        self.assertEqual(3, program.counters["x"].initial_value)
        self.assertEqual(0, program.counters["y"].initial_value)
        self.assertIsInstance(program.instructions["s1"], DecJzInstruction)
        self.assertIsInstance(program.instructions["s2"], IncInstruction)
        self.assertIsInstance(program.instructions["halt"], HaltInstruction)

    def test_items_without_value_or_op_are_ignored(self):
        text = (
            "[ ] T Buy_Milk due:2026-09-01\n"
            "[N] N Counter_X id:x value:1\n"
            "[N] N Halt id:halt op:halt\n"
        )
        program = build_program(_items(text))
        self.assertEqual({"x"}, set(program.counters))
        self.assertEqual({"halt"}, set(program.instructions))

    def test_custom_id_key_is_honored(self):
        text = "[N] N X uid:x value:1\n[N] N Halt uid:halt op:halt\n"
        program = build_program(_items(text), id_key="uid")
        self.assertEqual({"x"}, set(program.counters))
        self.assertEqual({"halt"}, set(program.instructions))

    def test_missing_id_is_rejected(self):
        text = "[N] N NoId value:1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("missing required detail 'id'", str(ctx.exception))

    def test_duplicate_id_across_counter_and_instruction_is_rejected(self):
        text = "[N] N A id:dup value:1\n[N] N B id:dup op:halt\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("Duplicate VM id 'dup'", str(ctx.exception))

    def test_duplicate_id_across_two_counters_is_rejected(self):
        text = "[N] N A id:dup value:1\n[N] N B id:dup value:2\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("Duplicate VM id 'dup'", str(ctx.exception))

    def test_record_with_both_value_and_op_is_rejected(self):
        text = "[N] N Weird id:w value:1 op:halt\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("has both value: and op:", str(ctx.exception))

    def test_multiple_id_values_are_rejected(self):
        text = "[N] N X id:x id:x2 value:1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("exactly one is required", str(ctx.exception))

    def test_multiple_value_details_are_rejected(self):
        text = "[N] N X id:x value:1 value:2\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("exactly one is required", str(ctx.exception))

    def test_non_integer_counter_value_is_rejected(self):
        text = "[N] N X id:x value:abc\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("non-integer value", str(ctx.exception))

    def test_negative_counter_value_is_rejected(self):
        text = "[N] N X id:x value:-5\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("negative value", str(ctx.exception))

    def test_zero_counter_value_is_accepted(self):
        text = "[N] N X id:x value:0\n[N] N Halt id:halt op:halt\n"
        program = build_program(_items(text))
        self.assertEqual(0, program.counters["x"].initial_value)

    def test_arbitrary_precision_counter_value_is_accepted(self):
        big = str(10**40)
        text = "[N] N X id:x value:%s\n[N] N Halt id:halt op:halt\n" % big
        program = build_program(_items(text))
        self.assertEqual(10**40, program.counters["x"].initial_value)

    def test_unknown_op_is_rejected(self):
        text = "[N] N S1 id:s1 op:frobnicate\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("unknown op 'frobnicate'", str(ctx.exception))

    def test_inc_without_var_is_rejected(self):
        text = "[N] N S1 id:s1 op:inc next:s1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("missing required detail 'var'", str(ctx.exception))

    def test_inc_without_next_is_rejected(self):
        text = "[N] N X id:x value:0\n[N] N S1 id:s1 op:inc var:x\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("missing required detail 'next'", str(ctx.exception))

    def test_dec_jz_without_nonzero_is_rejected(self):
        text = "[N] N X id:x value:0\n[N] N S1 id:s1 op:dec_jz var:x zero:s1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("missing required detail 'nonzero'", str(ctx.exception))

    def test_dec_jz_without_zero_is_rejected(self):
        text = "[N] N X id:x value:0\n[N] N S1 id:s1 op:dec_jz var:x nonzero:s1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("missing required detail 'zero'", str(ctx.exception))

    def test_dec_jz_referencing_unknown_counter_is_rejected(self):
        text = (
            "[N] N S1 id:s1 op:dec_jz var:missing nonzero:s1 zero:halt\n"
            "[N] N Halt id:halt op:halt\n"
        )
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("unknown counter 'missing'", str(ctx.exception))

    def test_inc_referencing_unknown_counter_is_rejected(self):
        text = "[N] N S1 id:s1 op:inc var:missing next:s1\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("unknown counter 'missing'", str(ctx.exception))

    def test_dangling_next_transition_is_rejected(self):
        text = "[N] N X id:x value:0\n[N] N S1 id:s1 op:inc var:x next:nope\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("next: 'nope', which does not exist", str(ctx.exception))

    def test_dangling_zero_transition_is_rejected(self):
        text = (
            "[N] N X id:x value:0\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:s1 zero:nope\n"
        )
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("zero: 'nope', which does not exist", str(ctx.exception))

    def test_dangling_nonzero_transition_is_rejected(self):
        text = (
            "[N] N X id:x value:0\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:nope zero:s1\n"
        )
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("nonzero: 'nope', which does not exist", str(ctx.exception))

    def test_transition_pointing_at_a_counter_is_rejected(self):
        text = "[N] N X id:x value:0\n[N] N S1 id:s1 op:inc var:x next:x\n"
        with self.assertRaises(VMProgramError) as ctx:
            build_program(_items(text))
        self.assertIn("which is a counter, not an instruction", str(ctx.exception))


class RunProgramTests(unittest.TestCase):
    def test_move_x_to_y_example_halts_after_seven_steps(self):
        program = build_program(_items(MOVE_X_TO_Y))
        result = run_program(program, "s1")
        self.assertEqual(7, result.steps)
        self.assertEqual({"x": 0, "y": 3}, dict(result.state))
        self.assertEqual("halt", result.pc)

    def test_dec_jz_zero_branch_halts_immediately_without_a_step(self):
        text = (
            "[N] N X id:x value:0\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:s1 zero:halt\n"
            "[N] N Halt id:halt op:halt\n"
        )
        program = build_program(_items(text))
        result = run_program(program, "s1")
        self.assertEqual(1, result.steps)
        self.assertEqual({"x": 0}, dict(result.state))

    def test_dec_jz_nonzero_branch_decrements_and_loops(self):
        text = (
            "[N] N X id:x value:2\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:s1 zero:halt\n"
            "[N] N Halt id:halt op:halt\n"
        )
        program = build_program(_items(text))
        result = run_program(program, "s1")
        # x=2 -> decrement to 1 (step1) -> decrement to 0 (step2) -> the
        # check that finds it already zero is itself a third executed step,
        # matching the issue's own worked example (7 steps for x=3/y=0).
        self.assertEqual(3, result.steps)
        self.assertEqual({"x": 0}, dict(result.state))

    def test_entry_id_that_does_not_exist_is_rejected(self):
        program = build_program(_items(MOVE_X_TO_Y))
        with self.assertRaises(VMProgramError) as ctx:
            run_program(program, "nope")
        self.assertIn("does not exist", str(ctx.exception))

    def test_entry_id_that_is_a_counter_is_rejected(self):
        program = build_program(_items(MOVE_X_TO_Y))
        with self.assertRaises(VMProgramError) as ctx:
            run_program(program, "x")
        self.assertIn("refers to a counter, not an instruction", str(ctx.exception))

    def test_negative_max_steps_is_rejected(self):
        program = build_program(_items(MOVE_X_TO_Y))
        with self.assertRaises(VMProgramError) as ctx:
            run_program(program, "s1", max_steps=-1)
        self.assertIn("max_steps must be >= 0", str(ctx.exception))

    def test_step_limit_below_completion_raises_before_halting(self):
        program = build_program(_items(MOVE_X_TO_Y))
        with self.assertRaises(VMStepLimitExceeded) as ctx:
            run_program(program, "s1", max_steps=6)
        exc = ctx.exception
        self.assertEqual(6, exc.max_steps)
        self.assertNotEqual("halt", exc.pc)

    def test_step_limit_exactly_matching_completion_succeeds(self):
        program = build_program(_items(MOVE_X_TO_Y))
        result = run_program(program, "s1", max_steps=7)
        self.assertEqual(7, result.steps)

    def test_zero_max_steps_means_unlimited(self):
        # A long-running but terminating program: count a large counter down
        # to zero one decrement at a time.
        text = (
            "[N] N X id:x value:500\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:s1 zero:halt\n"
            "[N] N Halt id:halt op:halt\n"
        )
        program = build_program(_items(text))
        result = run_program(program, "s1", max_steps=0)
        # 500 decrementing checks plus the final check that finds it zero.
        self.assertEqual(501, result.steps)
        self.assertEqual({"x": 0}, dict(result.state))

    def test_default_max_steps_is_generous_but_finite(self):
        program = build_program(_items(MOVE_X_TO_Y))
        result = run_program(program, "s1")
        self.assertLess(result.steps, 100000)

    def test_runtime_state_never_mutates_the_source_items(self):
        items = _items(MOVE_X_TO_Y)
        program = build_program(items)
        run_program(program, "s1")
        # The parsed item details are untouched; only in-memory VM state
        # changed.
        x_item = next(i for i in items if "x" in i.details.get("id", []))
        self.assertEqual(["3"], x_item.details["value"])


class ProgramToMermaidTests(unittest.TestCase):
    def test_every_counter_and_instruction_becomes_a_node(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_mermaid(program)
        for node_id in ("x", "y", "s1", "s2", "halt"):
            self.assertIn(node_id, text)

    def test_counters_use_a_stadium_shape_and_instructions_a_rectangle(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_mermaid(program)
        self.assertIn('x(["x=3"])', text)
        self.assertIn('s1["s1: dec_jz x"]', text)

    def test_control_flow_and_var_edges_are_distinct(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_mermaid(program)
        self.assertIn("s1 -. var .-> x", text)
        self.assertIn("s1 -- nonzero --> s2", text)
        self.assertIn("s1 -- zero --> halt", text)
        self.assertIn("s2 -- next --> s1", text)

    def test_entry_is_marked_and_validated(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_mermaid(program, entry="s1")
        self.assertIn(":::entry", text)
        self.assertIn("classDef entry", text)
        with self.assertRaises(VMProgramError):
            program_to_mermaid(program, entry="nope")

    def test_omitting_entry_renders_the_whole_program_unmarked(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_mermaid(program)
        self.assertNotIn(":::entry", text)


class ProgramToDotTests(unittest.TestCase):
    def test_counters_are_ellipses_and_instructions_are_boxes(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_dot(program)
        self.assertIn('x [shape=ellipse, label="x=3"];', text)
        self.assertIn('s1 [shape=box, label="s1: dec_jz x"];', text)

    def test_control_flow_and_var_edges_are_distinct(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_dot(program)
        self.assertIn("s1 -> x [style=dashed, label=var];", text)
        self.assertIn("s1 -> s2 [label=nonzero];", text)
        self.assertIn("s1 -> halt [label=zero];", text)
        self.assertIn("s2 -> s1 [label=next];", text)

    def test_entry_gets_double_border_and_is_validated(self):
        program = build_program(_items(MOVE_X_TO_Y))
        text = program_to_dot(program, entry="s1")
        self.assertIn("peripheries=2", text)
        with self.assertRaises(VMProgramError):
            program_to_dot(program, entry="nope")

    def test_entry_that_is_a_counter_is_rejected(self):
        program = build_program(_items(MOVE_X_TO_Y))
        with self.assertRaises(VMProgramError) as ctx:
            program_to_dot(program, entry="x")
        self.assertIn("refers to a counter, not an instruction", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
