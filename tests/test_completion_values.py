"""Tests for per-command completion scoping and file-derived candidates.

The generated scripts are what users actually load, so these assert on the
generated text and on `dynamic_values` rather than on internal helpers alone.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifetxt import completion
from lifetxt.presence import COMMON_STATES


class DynamicValueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Write_report id:rep project:work tag:urgent assignee:alice\n"
                "[ ] T Read_paper id:paper project:research tag:reading\n"
                "[/] S Deep_dive person:bob state:hyperfocus from:2026-07-20T09:00\n"
            )
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_states_combine_the_documented_set_with_the_users_own(self):
        values = completion.dynamic_values("state", [self.path]).split()

        for state in COMMON_STATES:
            self.assertIn(state, values)
        self.assertIn("hyperfocus", values)
        # The documented ones come first so a brand-new file still completes.
        self.assertEqual(list(COMMON_STATES), values[:len(COMMON_STATES)])

    def test_projects_tags_ids_and_people_come_from_the_file(self):
        self.assertEqual(["work", "research"], completion.dynamic_values("project", [self.path]).split())
        self.assertEqual(["urgent", "reading"], completion.dynamic_values("tag", [self.path]).split())
        self.assertEqual(["rep", "paper"], completion.dynamic_values("id", [self.path]).split())

        people = completion.dynamic_values("person", [self.path]).split()
        self.assertIn("alice", people)
        self.assertIn("bob", people)

    def test_type_and_status_do_not_need_a_file(self):
        self.assertIn("task", completion.dynamic_values("type", None).split())
        self.assertIn("[x]", completion.dynamic_values("status", None).split())

    def test_unreadable_file_falls_back_instead_of_failing(self):
        # A shell calls this while the user types; an exception would corrupt
        # the completion display, so a missing file yields the built-ins.
        values = completion.dynamic_values("state", [os.path.join(self.directory, "gone.txt")])

        self.assertEqual(list(COMMON_STATES), values.split())
        self.assertEqual("", completion.dynamic_values("project", [os.path.join(self.directory, "gone.txt")]))

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            completion.dynamic_values("password", [self.path])


class PerCommandScopingTests(unittest.TestCase):
    def test_command_options_are_scoped_to_that_command(self):
        check_options = completion._command_options("check")
        assist_options = completion._command_options("assist")

        self.assertIn("--format", check_options)
        self.assertIn("--rrule", assist_options)
        # The whole point: a flag from another command must not be offered.
        self.assertNotIn("--rrule", check_options)

    def test_every_command_option_set_includes_the_common_options(self):
        for name in completion._command_names():
            options = completion._command_options(name)
            if options:
                self.assertIn("--help", options, name)

    def test_generated_scripts_scope_options_per_command(self):
        bash = completion.bash_completion()

        # The per-command case statement must exist, not one global list.
        self.assertIn('case "$cmd" in', bash)
        self.assertIn("--verify-files", bash)


class StateCompletionTests(unittest.TestCase):
    def test_state_values_are_derived_from_presence(self):
        # A duplicated literal here silently drifts from the real state list.
        self.assertEqual(" ".join(COMMON_STATES), completion.OPTION_VALUES["--state"])

    def test_positional_state_is_completed_for_the_state_commands(self):
        for command in ("state", "s", "start"):
            self.assertEqual("--state", completion.COMMAND_POSITIONAL_VALUES[command])

    def test_every_shell_offers_state_values(self):
        for name in ("bash", "zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()

            self.assertIn("busy", script, name)
            self.assertIn("sleeping", script, name)

    def test_every_shell_completes_the_positional_state(self):
        # `lifetxt state busy` is the form people type, so completing only
        # `--state` would miss the common case entirely.
        bash = completion.bash_completion()
        self.assertIn("state) COMPREPLY=( $(compgen -W \"$(_lifetxt_values state)\"", bash)

        for name in ("zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()
            self.assertIn("--kind state", script, name)


class GeneratedScriptTests(unittest.TestCase):
    def test_scripts_generate_without_unsubstituted_placeholders(self):
        for name in ("bash", "zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()

            self.assertTrue(script.strip(), name)
            self.assertNotIn("%(", script, name)

    def test_scripts_reference_the_dynamic_value_command(self):
        for name in ("bash", "zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()

            self.assertIn("completion values", script, name)

    def test_dynamic_lookups_are_silenced(self):
        # Completion runs while the user types: an error message printed into
        # the terminal would corrupt the prompt.
        for name in ("bash", "zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()

            self.assertIn("2>/dev/null", script, name)


class PowerShellCompletionTests(unittest.TestCase):
    def setUp(self):
        from lifetxt import extra_shell

        self.script = extra_shell._powershell_completion_script()

    def test_commands_are_derived_not_hand_maintained(self):
        # The previous hardcoded list had lost rrule/tag/plot/lint and still
        # named commands that no longer existed.
        for command in ("rrule", "tag", "plot", "lint", "init", "standup"):
            self.assertIn("'%s'" % command, self.script)

    def test_every_real_command_is_present(self):
        for command in completion._command_names():
            self.assertIn("'%s'" % command, self.script, command)

    def test_offers_per_command_options_and_values(self):
        self.assertIn("LifetxtCommandOptions", self.script)
        self.assertIn("LifetxtOptionValues", self.script)
        self.assertIn("--verify-files", self.script)

    def test_command_scan_does_not_use_a_reverse_range(self):
        # `$tokens[1..0]` counts backwards in PowerShell, which handed back the
        # executable name and suppressed the command list on a bare `lifetxt `.
        self.assertNotIn("$tokens[1..(", self.script)
        self.assertIn("for ($i = 1; $i -lt $tokens.Count; $i++)", self.script)


if __name__ == "__main__":
    unittest.main()
