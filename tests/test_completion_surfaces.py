"""Completion beyond the shell: the shared layer, the Web API, and the TUI.

The point of these is that one source feeds every surface, so a value the
shell offers is a value the Web UI and the TUI offer too.
"""
import argparse
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifetxt import completion, tui_app
from lifetxt.parser import parse_text
from lifetxt.presence import COMMON_STATES

SAMPLE = (
    "[ ] T Write_Report id:t1 project:work tag:urgent assignee:alice context:office priority:high\n"
    "[ ] T Read_Paper id:t2 project:research tag:reading\n"
    "[/] S Deep_Dive person:bob state:hyperfocus from:2026-07-20T09:00\n"
)


def _items():
    return parse_text(SAMPLE)[0]


class SharedCandidateTests(unittest.TestCase):
    def test_items_and_paths_agree(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)

        for kind in ("project", "tag", "id", "person", "state", "context"):
            from_items = completion.candidates(kind, items=_items())
            from_file = completion.candidates(kind, paths=[path])

            self.assertEqual(from_file, from_items, kind)

    def test_prefix_matches_rank_above_substring_matches(self):
        pool = completion.candidates("project", "r", items=_items())

        # "research" starts with r and "work" merely contains it, so the
        # prefix match has to come first.
        self.assertEqual(["research", "work"], pool)

    def test_non_matching_values_are_dropped(self):
        self.assertEqual(["research"], completion.candidates("project", "res", items=_items()))
        self.assertEqual([], completion.candidates("project", "zzz", items=_items()))

    def test_prefix_ranking_puts_starts_with_first(self):
        ranked = completion._rank(["deep_focus", "focus", "unfocused"], "focus")

        self.assertEqual("focus", ranked[0])

    def test_limit_truncates(self):
        self.assertEqual(2, len(completion.candidates("type", limit=2)))

    def test_builtins_precede_file_values(self):
        values = completion.candidates("state", items=_items())

        self.assertEqual(list(COMMON_STATES), values[:len(COMMON_STATES)])
        self.assertIn("hyperfocus", values)

    def test_person_spans_every_people_key(self):
        people = completion.candidates("person", items=_items())

        self.assertIn("alice", people)
        self.assertIn("bob", people)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            completion.candidates("password", items=_items())


class TuiArgumentCompletionTests(unittest.TestCase):
    def _state(self, text=SAMPLE):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        args = argparse.Namespace(paths=[path], config_data={})
        state = tui_app.WorkspaceState(args, glyphs=tui_app.UNICODE_GLYPHS)
        state.reload()
        return state

    def test_fixed_choice_arguments_complete(self):
        state = self._state()

        prefix, values = tui_app.argument_suggestions(state, "/timer st")

        self.assertEqual("st", prefix)
        self.assertEqual(["start", "stop", "status"], values)

    def test_file_derived_arguments_complete(self):
        state = self._state()

        self.assertEqual(["research"], tui_app.argument_suggestions(state, "/project re")[1])
        self.assertEqual(["urgent"], tui_app.argument_suggestions(state, "/tag ur")[1])
        self.assertEqual(["alice"], tui_app.argument_suggestions(state, "/assign al")[1])
        self.assertEqual(["office"], tui_app.argument_suggestions(state, "/context of")[1])

    def test_state_command_offers_the_files_own_state(self):
        state = self._state()

        self.assertIn("hyperfocus", tui_app.argument_suggestions(state, "/state hyper")[1])

    def test_date_tokens_complete_for_due(self):
        state = self._state()

        self.assertEqual(["tomorrow"], tui_app.argument_suggestions(state, "/due tomo")[1])

    def test_commands_without_value_arguments_offer_nothing(self):
        state = self._state()

        # `/search` takes free text; offering record values would be noise.
        self.assertEqual([], tui_app.argument_suggestions(state, "/search anything")[1])
        self.assertEqual([], tui_app.argument_suggestions(state, "/add A new task")[1])

    def test_completion_needs_a_command_and_a_space(self):
        state = self._state()

        self.assertEqual([], tui_app.argument_suggestions(state, "/sta")[1])
        self.assertEqual([], tui_app.argument_suggestions(state, "/")[1])

    def test_aliases_complete_like_their_command(self):
        state = self._state()

        self.assertIn("busy", tui_app.argument_suggestions(state, "/s bu")[1])

    def test_accepting_replaces_only_the_word_being_typed(self):
        state = self._state()
        state.input = "/state bu"
        state.palette_index = 0

        self.assertTrue(tui_app.apply_argument_completion(state))
        self.assertEqual("/state busy", state.input)
        self.assertEqual(len(state.input), state.cursor)

    def test_accepting_takes_the_highlighted_candidate(self):
        state = self._state()
        state.input = "/timer st"
        state.palette_index = 1

        tui_app.apply_argument_completion(state)

        self.assertEqual("/timer stop", state.input)

    def test_accepting_keeps_earlier_words(self):
        state = self._state()
        state.input = "/state busy"
        state.palette_index = 0
        # "busy" is itself a candidate, so the word is replaced, not appended.
        tui_app.apply_argument_completion(state)

        self.assertEqual("/state busy", state.input)

    def test_palette_lists_argument_values(self):
        state = self._state()
        state.input = "/timer "
        state.palette_index = 0

        lines = tui_app._build_palette(state, 80)
        rendered = ["".join(text for text, _style in line) for line in lines]

        self.assertTrue(any("start" in line for line in rendered), rendered)
        self.assertTrue(any("cancel" in line for line in rendered), rendered)

    def test_palette_still_lists_commands_before_the_space(self):
        state = self._state()
        state.input = "/tim"
        state.palette_index = 0

        rendered = ["".join(t for t, _ in line) for line in tui_app._build_palette(state, 80)]

        self.assertTrue(any("/timer" in line for line in rendered), rendered)

    def test_every_declared_value_source_is_usable(self):
        state = self._state()

        for command in tui_app.COMMANDS:
            if not command.values:
                continue
            if isinstance(command.values, tuple):
                self.assertTrue(all(isinstance(v, str) for v in command.values), command.name)
                continue
            self.assertIn(
                command.values,
                tuple(completion.VALUE_KINDS) + ("date",),
                "%s declares an unknown value kind" % command.name,
            )


class WebApiCompletionTests(unittest.TestCase):
    def setUp(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi is not installed")

        from lifetxt.webapp import create_app

        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        path = os.path.join(self.directory, "life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)
        self.client = TestClient(create_app(paths=[path]))

    def test_returns_candidates_for_each_kind(self):
        for kind in ("state", "project", "tag", "id", "person", "context", "key", "type", "status"):
            response = self.client.get("/api/complete", params={"kind": kind})

            self.assertEqual(200, response.status_code, kind)
            body = response.json()
            self.assertEqual(kind, body["kind"])
            self.assertTrue(body["candidates"], kind)

    def test_prefix_narrows_the_result(self):
        body = self.client.get("/api/complete", params={"kind": "project", "prefix": "res"}).json()

        self.assertEqual(["research"], body["candidates"])

    def test_limit_is_clamped_not_trusted(self):
        # A hostile or mistyped limit must not turn completion into a dump.
        body = self.client.get("/api/complete", params={"kind": "id", "limit": 99999}).json()
        self.assertLessEqual(len(body["candidates"]), 200)

        body = self.client.get("/api/complete", params={"kind": "id", "limit": "abc"}).json()
        self.assertLessEqual(len(body["candidates"]), 20)

    def test_unknown_kind_is_rejected_with_the_supported_list(self):
        response = self.client.get("/api/complete", params={"kind": "password"})

        self.assertEqual(400, response.status_code)
        self.assertIn("state", response.json()["detail"]["supported"])

    def test_matches_the_shared_layer(self):
        # The browser must not drift from the shell and the TUI.
        body = self.client.get("/api/complete", params={"kind": "person"}).json()

        self.assertEqual(completion.candidates("person", items=_items()), body["candidates"])


class McpCompletionTests(unittest.TestCase):
    def setUp(self):
        from lifetxt import mcp

        self.mcp = mcp
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.path = os.path.join(self.directory, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)

    def _call(self, arguments):
        context = self.mcp.McpContext(paths=[self.path], writable_path=self.path, config={})
        return self.mcp.call_tool("complete", arguments, context)

    def test_tool_is_registered_and_read_only(self):
        schema = [s for s in self.mcp.tool_schemas() if s["name"] == "complete"]

        self.assertEqual(1, len(schema))
        self.assertTrue(schema[0]["annotations"]["readOnlyHint"])
        self.assertFalse(schema[0]["annotations"]["destructiveHint"])

    def test_no_kind_lists_the_supported_kinds(self):
        self.assertEqual(list(completion.VALUE_KINDS), self._call({})["kinds"])

    def test_returns_values_from_the_file(self):
        result = self._call({"kind": "project"})

        self.assertEqual(["research", "work"], sorted(result["values"]))
        self.assertEqual(len(result["values"]), result["count"])

    def test_prefix_and_limit_apply(self):
        self.assertEqual(["busy"], self._call({"kind": "state", "prefix": "bu"})["values"])
        self.assertEqual(1, len(self._call({"kind": "id", "limit": 1})["values"]))

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            self._call({"kind": "password"})


if __name__ == "__main__":
    unittest.main()
