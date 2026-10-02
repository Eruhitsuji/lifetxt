"""#1021: one textual Quick contract and observable cross-surface behavior."""

import argparse
import datetime
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lifetxt import mcp, tui_app, webapp
from lifetxt.model import Item
from lifetxt.parser import parse_text
from lifetxt.quick_input import QuickInputError, resolve_quick_input
from lifetxt.tui_backend import RemoteTuiBackend

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    "Buy milk @home #errand !high ^2026-10-02",
    "Buy milk @home ^tomorrow",
    '[ ] T "Buy milk" project:home due:2026-10-02',
    '[N] N "Idea @literal" body:"text #literal" tag:a tag:b custom:"quoted value"',
    '[N] J "Journal" on:2026-10-01 body:"..."',
    "[/] H Exercise repeat:daily",
    "[N] N Explicit uid:my-note",
)
INVALID = (
    '[ ] T "unterminated',
    "[Z] T Bad",
    "[ ] X Bad",
    "[/] S Missing_state",
    "[ ] T Thing body:",
    "[ ]T Thing",
    "[",
    "[ ]",
    "[ ] T A\n[ ] T B",
    "text\nsecond",
    "[ ] T A\\",
    "[ ] T A\u2028[ ] T B",
    "[ ] T Duplicate uid:x uid:x",
)


def logical(item):
    return (
        item.status,
        item.kind,
        item.title,
        {k: v for k, v in item.details.items() if k != "uid"},
    )


class QuickResolverTests(unittest.TestCase):
    def test_full_records_retain_explicit_semantics(self):
        for text in INPUTS[2:]:
            with self.subTest(text=text):
                expected, _ = parse_text(text, id_key="uid", check_references=False)
                resolved = resolve_quick_input(text, id_key="uid")
                self.assertEqual("full_line", resolved.mode)
                self.assertEqual(logical(expected[0]), logical(resolved.item))
                self.assertEqual(expected[0].details, resolved.item.details)

    def test_shorthand_uses_existing_date_and_flag_precedence(self):
        item = Item("[ ]", "T", "", {"project": ["flag"], "tag": ["a"]})
        result = resolve_quick_input(
            "Call Alice @home #a #b !high ^tomorrow",
            shorthand_item=item,
            merge_tags=True,
            today=datetime.date(2026, 10, 1),
        )
        self.assertEqual("shorthand", result.mode)
        self.assertEqual("Call Alice", result.item.title)
        self.assertEqual(
            {
                "project": ["flag"],
                "tag": ["a", "b"],
                "priority": ["high"],
                "due": ["2026-10-02"],
            },
            result.item.details,
        )

    def test_invalid_format_attempt_never_falls_back(self):
        for text in INVALID:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    resolve_quick_input(text, id_key="uid")

    def test_ordinary_quotes_and_literal_bracket_inside_title_remain_shorthand(self):
        for text in ("Write about [N] notes", 'A "quote', "a@b.com", r"Write \@home"):
            self.assertEqual("shorthand", resolve_quick_input(text).mode)
        self.assertEqual(
            "Buy @home", resolve_quick_input("Buy @home", shorthand=False).item.title
        )

    def test_invalid_full_line_cannot_bypass_with_no_shorthand(self):
        with self.assertRaisesRegex(QuickInputError, "E018"):
            resolve_quick_input('[ ] T "unterminated', shorthand=False)

    def test_context_fills_only_absent_fields_and_is_validated(self):
        result = resolve_quick_input(
            "[N] N Idea project:mine",
            extra_details={"project": ["context"], "related": ["parent"]},
        )
        self.assertEqual(["mine"], result.item.details["project"])
        self.assertEqual(["parent"], result.item.details["related"])
        for details in ([], {"due": "bad"}, {"bad key": ["value"]}):
            with self.subTest(details=details), self.assertRaises(ValueError):
                resolve_quick_input("Task", extra_details=details)

    def test_repeated_shorthand_tags_and_literal_escapes(self):
        item = resolve_quick_input(r"Write \@home #a #a").item
        self.assertEqual("Write @home", item.title)
        self.assertEqual(["a", "a"], item.details["tag"])
        self.assertEqual("Write @home", resolve_quick_input(r"Write \@home").item.title)
        for text in ("", " ", "@home", "Thing ^notadate"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                resolve_quick_input(text)


class QuickSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "life.txt"
        self.path.write_text("", encoding="utf-8")
        self.config = {
            "paths": [str(self.path)],
            "write_file": str(self.path),
            "ids": {"auto": True, "key": "uid", "prefixes": {"N": "memo"}},
            "mcp": {"source_metadata": False},
            "tui": {"session": "off"},
        }
        self.config_path = Path(self.temp.name) / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def client(self, config=None, read_only=False):
        from fastapi.testclient import TestClient

        client = TestClient(
            webapp.create_app(
                [str(self.path)],
                writable_path=str(self.path),
                config=config or self.config,
                read_only=read_only,
            )
        )
        self.addCleanup(client.close)
        return client

    def post(self, client, endpoint, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("If-Match", mcp.file_hash(str(self.path)))
        return client.post(endpoint, headers=headers, **kwargs)

    def cli(self, text, command="quick", options=()):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "--config",
                str(self.config_path),
                command,
                text,
                *options,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def state(self, backend=None):
        state = tui_app.WorkspaceState(
            argparse.Namespace(
                paths=[str(self.path)],
                config_data=self.config,
            ),
            glyphs=tui_app.ASCII_GLYPHS,
            backend=backend,
        )
        state.reload()
        return state

    def only_item(self):
        items, diagnostics = parse_text(
            self.path.read_text(encoding="utf-8"), id_key="uid"
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        from lifetxt.native_history import is_item_event

        items = [item for item in items if not is_item_event(item)]
        self.assertEqual(1, len(items))
        return items[0]

    def test_cli_local_tui_web_and_mcp_create_the_same_logical_records(self):
        client = self.client()
        for text in INPUTS:
            expected = logical(resolve_quick_input(text, id_key="uid").item)
            for surface in ("cli", "tui", "web", "mcp", "remote-tui"):
                with self.subTest(text=text, surface=surface):
                    self.path.write_text("", encoding="utf-8")
                    if surface == "cli":
                        result = self.cli(text)
                        self.assertEqual(
                            0, result.returncode, result.stdout + result.stderr
                        )
                    elif surface == "tui":
                        tui_app.run_command(self.state(), "/add " + text)
                    elif surface == "web":
                        result = self.post(
                            client,
                            "/api/items/capture",
                            json={"text": text},
                            headers={
                                "If-Match": client.get("/api/revision").json()[
                                    "revision"
                                ]
                            },
                        )
                        self.assertEqual(201, result.status_code, result.text)
                        self.assertEqual(
                            resolve_quick_input(text, id_key="uid").mode,
                            result.json()["mode"],
                        )
                    elif surface == "mcp":
                        context = mcp.McpContext(
                            paths=[str(self.path)],
                            writable_path=str(self.path),
                            config=self.config,
                        )
                        result = mcp.call_tool("capture_item", {"text": text}, context)
                        self.assertTrue(result["applied"])
                    else:
                        connection = self.connection(client)
                        backend = RemoteTuiBackend(connection)
                        tui_app.run_command(self.state(backend), "/add " + text)
                        self.assertEqual({"text": text}, connection.posts[-1][1])
                    item = self.only_item()
                    self.assertEqual(expected, logical(item))
                    self.assertTrue(item.details["uid"])
                    if item.kind == "N" and "uid:" not in text:
                        self.assertTrue(item.details["uid"][0].startswith("memo_"))

    def connection(self, client):
        path = self.path

        class Connection:
            base_url = "https://example.invalid"
            host = "example.invalid"
            username = "tester"
            file_revision = client.get("/api/revision").json()["revision"]
            posts = []

            def describe(self):
                return self.base_url

            def request(self, method, endpoint, json_body=None, if_match=None):
                headers = {"If-Match": if_match} if if_match else {}
                response = client.request(
                    method, endpoint, json=json_body, headers=headers
                )
                if method == "POST":
                    self.posts.append((endpoint, json_body, if_match))
                if response.status_code >= 400:
                    raise ValueError(response.json().get("message", response.text))
                self.file_revision = client.get("/api/revision").json()["revision"]
                return response.json()

            def get_revision(self):
                self.file_revision = client.get("/api/revision").json()["revision"]
                return self.file_revision

        return Connection()

    def test_invalid_inputs_do_not_write_in_any_adapter(self):
        client = self.client()
        for text in INVALID:
            for surface in ("cli", "tui", "web", "mcp", "remote-tui"):
                with self.subTest(text=text, surface=surface):
                    before = self.path.read_bytes()
                    if surface == "cli":
                        result = self.cli(text)
                        self.assertNotEqual(0, result.returncode)
                    elif surface == "web":
                        result = self.post(
                            client,
                            "/api/items/capture",
                            json={"text": text},
                            headers={
                                "If-Match": client.get("/api/revision").json()[
                                    "revision"
                                ]
                            },
                        )
                        self.assertIn(result.status_code, (400, 422))
                    else:
                        with self.assertRaises(ValueError):
                            if surface == "tui":
                                tui_app.run_command(self.state(), "/add " + text)
                            elif surface == "remote-tui":
                                tui_app.run_command(
                                    self.state(
                                        RemoteTuiBackend(self.connection(client))
                                    ),
                                    "/add " + text,
                                )
                            else:
                                context = mcp.McpContext(
                                    paths=[str(self.path)],
                                    writable_path=str(self.path),
                                    config=self.config,
                                )
                                mcp.call_tool("capture_item", {"text": text}, context)
                    self.assertEqual(before, self.path.read_bytes())

    def test_duplicate_configured_id_refuses_without_write(self):
        self.path.write_text("[N] N Existing uid:duplicate\n", encoding="utf-8")
        text = "[N] N New uid:duplicate"
        before = self.path.read_bytes()
        result = self.cli(text)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(ValueError):
            tui_app.run_command(self.state(), "/add " + text)
        response = self.post(
            self.client(),
            "/api/items/capture",
            json={"text": text},
        )
        self.assertGreaterEqual(response.status_code, 400, response.text)
        context = mcp.McpContext(
            paths=[str(self.path)], writable_path=str(self.path), config=self.config
        )
        with self.assertRaises(ValueError):
            mcp.call_tool("capture_item", {"text": text}, context)
        self.assertEqual(before, self.path.read_bytes())

    def test_auth_read_only_and_revision_guards_remain_in_force(self):
        before = self.path.read_bytes()
        readonly = self.client(read_only=True)
        for text in INPUTS[:2]:
            self.assertEqual(
                403,
                self.post(
                    readonly,
                    "/api/items/capture",
                    json={"text": text},
                ).status_code,
            )
        self.assertEqual(
            200,
            self.post(
                readonly, "/api/quick/resolve", json={"text": INPUTS[3]}
            ).status_code,
        )
        config = dict(self.config, api={"token": "test-token"})
        secured = self.client(config)
        self.assertEqual(
            401,
            self.post(
                secured, "/api/items/capture", json={"text": INPUTS[3]}
            ).status_code,
        )
        self.assertEqual(
            401,
            self.post(
                secured, "/api/quick/resolve", json={"text": INPUTS[3]}
            ).status_code,
        )
        response = self.post(
            secured,
            "/api/items/capture",
            json={"text": INPUTS[3]},
            headers={"Authorization": "Bearer test-token", "If-Match": "0" * 64},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual(before, self.path.read_bytes())
        context = mcp.McpContext(
            paths=[str(self.path)],
            writable_path=str(self.path),
            config=self.config,
            read_only=True,
        )
        with self.assertRaises(ValueError):
            mcp.call_tool("capture_item", {"text": INPUTS[3]}, context)
        self.assertEqual(before, self.path.read_bytes())

    def test_preview_raw_and_mcp_proposal_do_not_regress(self):
        client = self.client()
        before = self.path.read_bytes()
        for text in INPUTS:
            result = self.post(
                client,
                "/api/quick/resolve",
                json={"text": text},
            )
            self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(before, self.path.read_bytes())
        context = mcp.McpContext(
            paths=[str(self.path)], writable_path=str(self.path), config=self.config
        )
        result = mcp.call_tool(
            "capture_item", {"text": INPUTS[3], "dry_run": True}, context
        )
        self.assertTrue(result["proposal"])
        self.assertEqual("full_line", result["mode"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(
            201,
            self.post(client, "/api/items/raw", json={"line": INPUTS[3]}).status_code,
        )
        self.assertEqual(
            logical(resolve_quick_input(INPUTS[3]).item), logical(self.only_item())
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_all_browser_quick_handlers_delegate_and_match_server_semantics(self):
        result = subprocess.run(
            ["node", str(ROOT / "tests/quick_input_clients.mjs"), json.dumps(INPUTS)],
            capture_output=True,
            text=True,
            check=True,
        )
        client = self.client()
        for action in json.loads(result.stdout):
            with self.subTest(surface=action["surface"], text=action["text"]):
                self.path.write_text("", encoding="utf-8")
                self.assertEqual(1, len(action["calls"]))
                call = action["calls"][0]
                self.assertEqual("/api/items/capture", call["path"])
                self.assertEqual(action["text"], call["body"]["text"])
                response = self.post(client, call["path"], json=call["body"])
                if action.get("failure"):
                    self.assertGreaterEqual(response.status_code, 400)
                    self.assertEqual(action["text"], action["value"])
                    self.assertEqual(b"", self.path.read_bytes())
                else:
                    self.assertEqual(201, response.status_code, response.text)
                    expected = resolve_quick_input(
                        action["text"],
                        id_key="uid",
                        extra_details=call["body"].get("details"),
                    ).item
                    self.assertEqual(logical(expected), logical(self.only_item()))

    def test_related_capture_keeps_record_semantics_and_context_precedence(self):
        for remote in (False, True):
            with self.subTest(remote=remote):
                self.path.write_text(
                    "[ ] T Parent uid:parent project:context\n", encoding="utf-8"
                )
                backend = (
                    RemoteTuiBackend(self.connection(self.client())) if remote else None
                )
                state = self.state(backend)
                text = '[N] N "Follow up" project:explicit body:"details"'
                tui_app.run_command(state, "/related " + text)
                items, _ = parse_text(
                    self.path.read_text(encoding="utf-8"), id_key="uid"
                )
                item = next(item for item in items if item.title == "Follow up")
                self.assertEqual(("[N]", "N"), (item.status, item.kind))
                self.assertEqual(["explicit"], item.details["project"])
                self.assertEqual(["parent"], item.details["related"])

    def test_auto_id_off_preserves_explicit_id_on_all_adapters(self):
        self.config["ids"]["auto"] = False
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        text = "[N] N Explicit uid:chosen"
        for surface in ("cli", "web", "mcp", "tui"):
            with self.subTest(surface=surface):
                self.path.write_text("", encoding="utf-8")
                if surface == "cli":
                    result = self.cli(text)
                    self.assertEqual(0, result.returncode, result.stderr)
                elif surface == "web":
                    result = self.post(
                        self.client(), "/api/items/capture", json={"text": text}
                    )
                    self.assertEqual(201, result.status_code, result.text)
                elif surface == "mcp":
                    context = mcp.McpContext(
                        paths=[str(self.path)],
                        writable_path=str(self.path),
                        config=self.config,
                    )
                    mcp.call_tool("capture_item", {"text": text}, context)
                else:
                    tui_app.run_command(self.state(), "/add " + text)
                self.assertEqual(["chosen"], self.only_item().details["uid"])

    def test_cli_aliases_stdin_and_full_record_authority(self):
        for alias in ("quick", "q", "add"):
            self.path.write_text("", encoding="utf-8")
            result = self.cli(
                INPUTS[3],
                command=alias,
                options=["--type", "T", "--project", "default"],
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                logical(resolve_quick_input(INPUTS[3]).item), logical(self.only_item())
            )
        self.path.write_text("", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "--config",
                str(self.config_path),
                "quick",
                "-",
            ],
            input=INPUTS[4] + "\n",
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("J", self.only_item().kind)
        before = self.path.read_bytes()
        result = self.cli(INVALID[0], options=["--no-check", "--no-shorthand"])
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
