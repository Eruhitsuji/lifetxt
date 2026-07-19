"""Tests for the Web UI slash commands and the shared command catalog."""

import os
import re
import tempfile
import unittest

from lifetxt.tui_app import COMMANDS, COMMANDS_BY_NAME
from lifetxt.webapp import HTML_PAGE, WEB_COMMAND_NOTES, WEB_COMMANDS


SCRIPT = "\n".join(re.findall(r"<script>(.*?)</script>", HTML_PAGE, re.S))


def _handler_block():
    match = re.search(r"const WEB_COMMAND_HANDLERS = \{(.*?)\n    \};", SCRIPT, re.S)
    assert match, "WEB_COMMAND_HANDLERS block not found in the page"
    return match.group(1)


class CommandCatalogTests(unittest.TestCase):
    """The catalog is derived from the TUI registry, so the two cannot drift."""

    def _client(self, content="[ ] T A id:t1 project:work\n"):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            self.skipTest("FastAPI test client is unavailable: %s" % exc)
        from lifetxt.webapp import create_app

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        config = {"timer": {"state_file": os.path.join(tmp.name, "timer.json")}}
        try:
            return TestClient(create_app([path], writable_path=path, config=config)), path
        except Exception as exc:
            self.skipTest("FastAPI test client could not start: %s" % exc)

    def test_catalog_lists_every_tui_command(self):
        client, _path = self._client()

        payload = client.get("/api/commands").json()

        self.assertEqual(len(COMMANDS), payload["count"])
        self.assertEqual(
            sorted(c.name for c in COMMANDS),
            sorted(row["name"] for row in payload["commands"]),
        )

    def test_catalog_carries_alias_usage_and_summary(self):
        client, _path = self._client()

        rows = {row["name"]: row for row in client.get("/api/commands").json()["commands"]}

        done = rows["done"]
        self.assertEqual(COMMANDS_BY_NAME["done"].summary, done["summary"])
        self.assertEqual(COMMANDS_BY_NAME["done"].usage, done["usage"])
        self.assertEqual("d", done["alias"])

    def test_terminal_only_commands_are_marked_with_a_reason(self):
        client, _path = self._client()

        rows = {row["name"]: row for row in client.get("/api/commands").json()["commands"]}

        self.assertFalse(rows["edit"]["web"])
        self.assertTrue(rows["edit"]["note"], "an unsupported command must explain why")
        self.assertTrue(rows["done"]["web"])

    def test_web_commands_are_all_real_commands(self):
        unknown = WEB_COMMANDS - set(COMMANDS_BY_NAME)

        self.assertEqual(set(), unknown)

    def test_every_note_refers_to_a_real_command(self):
        unknown = set(WEB_COMMAND_NOTES) - set(COMMANDS_BY_NAME)

        self.assertEqual(set(), unknown)


class BrowserHandlerTests(unittest.TestCase):
    """The page must actually implement what the catalog advertises."""

    def test_every_supported_command_has_a_browser_handler(self):
        handlers = set(re.findall(r"^      ([a-z_]+): async", _handler_block(), re.M))

        self.assertEqual(set(), WEB_COMMANDS - handlers, "advertised but not implemented")
        self.assertEqual(set(), handlers - WEB_COMMANDS, "implemented but not advertised")

    def test_handlers_only_call_functions_that_exist(self):
        # A typo here is a ReferenceError the moment the command runs, which
        # brace-counting and syntax checks do not catch.
        block = _handler_block()
        called = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", block))
        builtins = {
            "String", "Array", "JSON", "Error", "Number", "Object", "Boolean",
            "Set", "Map", "if", "for", "while", "switch", "catch", "return",
            "async", "await", "function", "parseInt", "parseFloat", "isNaN",
            "encodeURIComponent", "decodeURIComponent", "setTimeout",
            "clearTimeout", "console", "fetch", "Date", "Math", "RegExp", "split",
        }
        missing = []
        for name in sorted(called - builtins):
            declared = (
                re.search(r"\bfunction\s+%s\b" % re.escape(name), SCRIPT)
                or re.search(r"\b(?:const|let|var)\s+%s\b" % re.escape(name), SCRIPT)
                or re.search(r"\.%s\s*\(" % re.escape(name), SCRIPT)
                or re.search(r"\b%s\s*[:=]\s*(?:async\s*)?\(" % re.escape(name), SCRIPT)
            )
            if not declared:
                missing.append(name)

        self.assertEqual([], missing, "handlers reference undefined functions")

    def test_command_state_variables_are_declared(self):
        for name in ("COMMAND_CATALOG", "bulkSelectedLines", "currentItems", "selectedItem"):
            self.assertTrue(
                re.search(r"\b(?:const|let|var)\s+%s\b" % name, SCRIPT), name
            )

    def test_palette_renders_commands_and_loads_the_catalog(self):
        for probe in (
            "runWebCommand",
            "renderCmdkCommands",
            "loadCommandCatalog",
            '"/api/commands"',
            "Type / for commands",
        ):
            self.assertIn(probe, HTML_PAGE, probe)

    def test_help_table_documents_the_slash_entry_point(self):
        self.assertIn("Ctrl+K then /", HTML_PAGE)

    def test_page_javascript_braces_and_parens_balance(self):
        self.assertEqual(SCRIPT.count("{"), SCRIPT.count("}"))
        self.assertEqual(SCRIPT.count("("), SCRIPT.count(")"))


class CommandBackingEndpointTests(unittest.TestCase):
    """Every endpoint a browser command calls must exist and behave."""

    def _client(self):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            self.skipTest("FastAPI test client is unavailable: %s" % exc)
        from lifetxt.webapp import create_app

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Write_Report id:t1 project:work\n[ ] T Second id:t2\n")
        config = {"timer": {"state_file": os.path.join(tmp.name, "timer.json")}}
        try:
            return TestClient(create_app([path], writable_path=path, config=config)), path
        except Exception as exc:
            self.skipTest("FastAPI test client could not start: %s" % exc)

    def test_due_command_can_resolve_a_date_token(self):
        # /due relies on this; without it the browser would write "undefined".
        client, _path = self._client()

        response = client.post("/api/shorthand/parse", json={"date": "+3d"})

        self.assertEqual(200, response.status_code)
        self.assertRegex(response.json()["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_due_command_rejects_an_invalid_date_token(self):
        client, _path = self._client()

        response = client.post("/api/shorthand/parse", json={"date": "notadate"})

        self.assertEqual(400, response.status_code)

    def test_parse_without_a_date_still_returns_the_token_reference(self):
        client, _path = self._client()

        payload = client.post("/api/shorthand/parse", json={"text": "Buy milk @home"}).json()

        self.assertNotIn("date", payload)
        self.assertTrue(payload["date_tokens"])
        self.assertEqual(["home"], payload["details"]["project"])

    def test_add_command_endpoint(self):
        client, _path = self._client()

        response = client.post("/api/items/capture", json={"text": "From command @web"})

        self.assertEqual(201, response.status_code)
        self.assertIn("project:web", response.json()["line"])

    def test_state_command_endpoint(self):
        client, _path = self._client()

        self.assertEqual(201, client.post("/api/status", json={"state": "busy"}).status_code)

    def test_done_and_delete_command_endpoints(self):
        client, path = self._client()

        updated = client.put(
            "/api/items/1",
            json={"status": "[x]", "type": "T", "title": "Write_Report", "details": {"id": ["t1"]}},
        )
        deleted = client.delete("/api/items/2")

        self.assertEqual(200, updated.status_code)
        self.assertEqual(200, deleted.status_code)
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("[x] T Write_Report", content)
        self.assertNotIn("Second", content)


class TimerEndpointTests(unittest.TestCase):
    """`/timer` in the browser needs Web API endpoints the CLI already had."""

    def _client(self):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            self.skipTest("FastAPI test client is unavailable: %s" % exc)
        from lifetxt.webapp import create_app

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T A id:t1\n[ ] T B id:t2\n")
        config = {"timer": {"state_file": os.path.join(tmp.name, "timer.json")}}
        try:
            return TestClient(create_app([path], writable_path=path, config=config)), path
        except Exception as exc:
            self.skipTest("FastAPI test client could not start: %s" % exc)

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_idle_then_start_then_stop(self):
        client, path = self._client()

        self.assertFalse(client.get("/api/timer").json()["running"])

        started = client.post("/api/timer", json={"action": "start", "id": "t1"})
        self.assertEqual(200, started.status_code)
        self.assertTrue(client.get("/api/timer").json()["running"])

        stopped = client.post("/api/timer", json={"action": "stop"})
        self.assertEqual(200, stopped.status_code)
        self.assertTrue(stopped.json()["elapsed_written"])
        self.assertIn("elapsed:", self._read(path))

    def test_second_start_conflicts(self):
        client, _path = self._client()
        client.post("/api/timer", json={"action": "start", "id": "t1"})

        response = client.post("/api/timer", json={"action": "start", "id": "t2"})

        self.assertEqual(409, response.status_code)

    def test_cancel_discards_without_writing_elapsed(self):
        client, path = self._client()
        client.post("/api/timer", json={"action": "start", "id": "t1"})

        response = client.post("/api/timer", json={"action": "cancel"})

        self.assertFalse(response.json()["elapsed_written"])
        self.assertNotIn("elapsed:", self._read(path))
        self.assertFalse(client.get("/api/timer").json()["running"])

    def test_stop_without_a_timer_conflicts(self):
        client, _path = self._client()

        self.assertEqual(409, client.post("/api/timer", json={"action": "stop"}).status_code)

    def test_start_requires_an_id(self):
        client, _path = self._client()

        self.assertEqual(400, client.post("/api/timer", json={"action": "start"}).status_code)

    def test_unknown_action_is_rejected(self):
        client, _path = self._client()

        self.assertEqual(400, client.post("/api/timer", json={"action": "explode"}).status_code)

    def test_timer_endpoints_do_not_write_to_stdout(self):
        # The timer helpers print for CLI use; a server must stay quiet.
        import io as _io
        from contextlib import redirect_stdout

        client, _path = self._client()
        buffer = _io.StringIO()
        with redirect_stdout(buffer):
            client.post("/api/timer", json={"action": "start", "id": "t1"})
            client.post("/api/timer", json={"action": "stop"})

        self.assertEqual("", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
