"""Guard against escape artifacts in text a user actually reads.

A patch that writes ``\\n`` into a Python string produces a newline; writing the
same thing into HTML, help text, or a description produces the two characters
backslash-n, which then render literally. That happened once in the Web UI
keyboard-shortcut table, so these tests cover every surface that displays text.
"""

import argparse
import io
import os
import re
import tempfile
import unittest

from lifetxt import cli, completion, mcp, tui_app


BACKSLASH = chr(92)
#: Escapes that are never legitimate in rendered prose.
SUSPECT = tuple(BACKSLASH + suffix for suffix in ("n", "t", "r"))


def _offenders(text):
    found = []
    for token in SUSPECT:
        index = str(text).find(token)
        if index >= 0:
            snippet = " ".join(str(text).split())
            position = snippet.find(token)
            found.append(
                "%r near %r" % (token, snippet[max(0, position - 40) : position + 40])
            )
    return found


class WebPageTextTests(unittest.TestCase):
    def _visible_text(self):
        from lifetxt.webapp import HTML_PAGE

        body = re.sub(r"<script>.*?</script>", "", HTML_PAGE, flags=re.S)
        body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
        return body

    def test_no_literal_escapes_in_page_text(self):
        text = re.sub(r"<[^>]+>", " ", self._visible_text())

        self.assertEqual([], _offenders(text))

    def test_no_literal_escapes_in_user_facing_attributes(self):
        body = self._visible_text()
        bad = []
        for match in re.finditer(r'(title|aria-label|placeholder)="([^"]*)"', body):
            if _offenders(match.group(2)):
                bad.append(match.group(0)[:80])

        self.assertEqual([], bad)

    def test_keyboard_shortcut_rows_are_well_formed(self):
        from lifetxt.webapp import HTML_PAGE

        rows = re.findall(r"<tr><td>([^<]*)</td><td>([^<]*)</td></tr>", HTML_PAGE)

        self.assertTrue(rows, "no shortcut rows found")
        for key, description in rows:
            self.assertEqual([], _offenders(key), key)
            self.assertEqual([], _offenders(description), description)


class CliTextTests(unittest.TestCase):
    def test_no_literal_escapes_in_command_help(self):
        parser = cli.build_parser()
        bad = []
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    if _offenders(sub.format_help()):
                        bad.append(name)
        if _offenders(parser.format_help()):
            bad.append("(root)")

        self.assertEqual([], bad)

    def test_every_shell_completion_generates_cleanly(self):
        for name in ("bash", "zsh", "fish"):
            script = getattr(completion, "%s_completion" % name)()

            self.assertNotIn(
                "%(", script, "%s left an unsubstituted placeholder" % name
            )


class TuiTextTests(unittest.TestCase):
    def test_no_literal_escapes_in_command_summaries(self):
        for command in tui_app.COMMANDS:
            self.assertEqual([], _offenders(command.summary), command.name)
            self.assertEqual([], _offenders(command.usage), command.name)

    def test_no_literal_escapes_in_rendered_frames(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Sample id:t1 project:work\n")
        state = tui_app.WorkspaceState(
            argparse.Namespace(paths=[path], config_data={"tui": {"session": "off"}}),
            glyphs=tui_app.ASCII_GLYPHS,
        )
        state.reload()

        for label, frame in (
            ("workspace", tui_app.build_frame(state, 100, 30)),
            ("palette", None),
        ):
            if frame is None:
                state.input = "/"
                frame = tui_app.build_frame(state, 100, 30)
            # frame_to_text joins spans; real newlines only appear between rows.
            for line in frame:
                for span, _style in line:
                    self.assertEqual([], _offenders(span), "%s: %r" % (label, span))

    def test_help_reference_is_clean(self):
        for usage, summary in tui_app.help_entries():
            self.assertEqual([], _offenders(usage), usage)
            self.assertEqual([], _offenders(summary), summary)


class McpTextTests(unittest.TestCase):
    def test_no_literal_escapes_in_tool_descriptions(self):
        for schema in mcp.tool_schemas():
            self.assertEqual([], _offenders(schema["description"]), schema["name"])

    def test_no_literal_escapes_in_prompts(self):
        for name, spec in mcp.PROMPT_DEFINITIONS.items():
            self.assertEqual([], _offenders(spec["description"]), name)
            self.assertEqual([], _offenders(spec["template"]), name)


if __name__ == "__main__":
    unittest.main()
