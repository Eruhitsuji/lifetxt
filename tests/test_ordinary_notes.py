"""#1020: one ordinary Note set across core, CLI, Web, TUI and MCP."""

import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from lifetxt import cli, mcp, tui_app, webapp
from lifetxt.agenda import filter_items
from lifetxt.ordinary_notes import (
    is_ordinary_note,
    ordinary_notes_page,
    select_ordinary_notes,
)
from lifetxt.parser import parse_text
from lifetxt.tui_backend import LocalTuiBackend, RemoteTuiBackend
from lifetxt.web_assets import HTML_PAGE, PLANNER_HTML_PAGE

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


def mixed_text(count=12, excluded=50):
    # >20 semantic rows precede every ordinary Note in file order.
    semantic = "".join(
        "[N] N History id:h%s record:item_event\n" % i for i in range(excluded)
    )
    semantic += "".join("[N] N Context id:p%s person:self\n" % i for i in range(8))
    semantic += "[N] N Other_person id:person-alice person:alice\n"
    semantic += "[N] N Ticket_audit id:ticket-event record:ticket_event\n"
    semantic += "[N] N Work_time id:time-entry record:time_entry\n"
    semantic += "[N] N Progress_audit id:progress-event record:progress_event\n"
    notes = "".join("[N] N Note_%02d id:n%02d\n" % (i, i) for i in range(count))
    return semantic + notes


def ids(items):
    return [item.details["id"][0] for item in items]


class OrdinaryNotesTests(unittest.TestCase):
    def test_filter_before_limit_and_all_existing_classifiers(self):
        items, _ = parse_text(mixed_text())
        rows = select_ordinary_notes(items)
        self.assertEqual(["n%02d" % i for i in range(12)], ids(rows))
        self.assertEqual(rows, filter_items(items, ordinary_notes=True))
        self.assertEqual(ordinary_notes_page(items)["total"], 12)
        self.assertEqual(ordinary_notes_page(items)["count"], 5)
        self.assertTrue(all(is_ordinary_note(item) for item in rows))

    def test_freeform_marker_title_person_and_no_migration(self):
        items, _ = parse_text(
            "[N] N Context id:a\n[N] N History id:b record:my_custom_note\n"
            "[N] N Plain id:c assignee:self\n[ ] T Task id:t\n"
        )
        self.assertEqual(["a", "b", "c"], ids(select_ordinary_notes(items)))

    def test_selected_date_updated_created_and_stable_fallback(self):
        items, _ = parse_text(
            "[N] N Z id:z\n[N] N A id:a\n"
            "[N] N Created id:c created:2031-02-05\n"
            "[N] N Updated id:u updated:2031-02-04T12:00Z\n"
            "[N] N Updated_tie id:v updated:2031-02-04T12:00Z created:2031-02-05\n"
            "[N] N Day id:d on:2031-02-03\n"
            "[N] N Interval id:i from:2031-02-02T10:00 to:2031-02-04T10:00\n"
        )
        expected = ["d", "i", "v", "u", "c", "a", "z"]
        self.assertEqual(expected, ids(select_ordinary_notes(items, date="2031-02-03")))
        self.assertEqual(
            expected,
            ids(select_ordinary_notes(list(reversed(items)), date="2031-02-03")),
        )
        self.assertEqual(
            ["v", "u", "c", "a", "d", "i", "z"], ids(select_ordinary_notes(items))
        )
        self.assertEqual(
            "A", select_ordinary_notes(items, sort="title", order="asc")[0].title
        )

    def test_page_boundaries_empty_and_revision_changes(self):
        for count in (0, 1, 5, 12):
            with self.subTest(count=count):
                items, _ = parse_text(mixed_text(count))
                seen, offset, revisions = [], 0, set()
                while True:
                    page = ordinary_notes_page(items, offset=offset)
                    seen.extend(ids(page["items"]))
                    revisions.add(page["revision"])
                    self.assertEqual(count, page["total"])
                    self.assertLessEqual(page["count"], 5)
                    if not page["has_more"]:
                        self.assertIsNone(page["next_offset"])
                        break
                    offset = page["next_offset"]
                self.assertEqual(count, len(seen))
                self.assertEqual(count, len(set(seen)))
                self.assertEqual(1, len(revisions))
                self.assertEqual(
                    [], ordinary_notes_page(items, offset=count + 10)["items"]
                )
        items, _ = parse_text("[N] N A id:a\n")
        before = ordinary_notes_page(items)["revision"]
        items[0].status = "[x]"
        self.assertNotEqual(before, ordinary_notes_page(items)["revision"])
        items[0].details["body"] = ["Edited"]
        self.assertNotEqual(before, ordinary_notes_page(items)["revision"])

    def test_invalid_page_date_and_sort(self):
        for kwargs in (
            {"offset": -1},
            {"offset": 1.2},
            {"limit": True},
            {"limit": 0},
            {"limit": 101},
            {"limit": "five"},
            {"date": "2031-02-30"},
            {"date": "2031-02-03T10:00"},
            {"sort": "score"},
            {"order": "sideways"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ordinary_notes_page([], **kwargs)


class OrdinaryNotesSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "life.txt"
        self.path.write_text(mixed_text(), encoding="utf-8")
        self.items, _ = parse_text(self.path.read_text())
        self.expected = ids(select_ordinary_notes(self.items))
        self.args = argparse.Namespace(
            paths=[str(self.path)], config_data={}, limit=100
        )

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = cli.main(list(args))
        self.assertEqual(0, result, err.getvalue())
        return out.getvalue()

    def test_cli_json_jsonl_shared_export_and_fzf(self):
        data = json.loads(
            self.run_cli("notes", str(self.path), "--limit", "100", "--format", "json")
        )
        self.assertEqual(12, data["total"])
        self.assertEqual(
            self.expected, [item["details"]["id"][0] for item in data["items"]]
        )
        rows = [
            json.loads(line)
            for line in self.run_cli(
                "notes", str(self.path), "--format", "jsonl"
            ).splitlines()
        ]
        self.assertEqual(self.expected[:5], [row["details"]["id"][0] for row in rows])
        data = json.loads(self.run_cli("to-json", str(self.path), "--ordinary-notes"))
        self.assertEqual(self.expected, [item["details"]["id"][0] for item in data])
        from lifetxt.fzf_helper import load_filtered_items

        parser = cli.build_parser()
        args = parser.parse_args(["fzf", str(self.path), "--ordinary-notes"])
        args.config_data = {}
        self.assertEqual(self.expected, ids(load_filtered_items(args)))
        raw = json.loads(self.run_cli("to-json", str(self.path), "--type", "N"))
        self.assertGreater(len(raw), 20)

    def test_mcp_shared_projection_read_profile_and_raw(self):
        context = mcp.McpContext(paths=[str(self.path)], read_only=True)
        result = mcp.call_tool("list_notes", {"limit": 100}, context)
        self.assertEqual(self.expected, [row["id"] for row in result["items"]])
        self.assertEqual(12, result["total"])
        self.assertEqual(
            self.expected,
            [
                row["id"]
                for row in mcp.call_tool(
                    "list_items", {"ordinary_notes": True}, context
                )["items"]
            ],
        )
        self.assertGreater(
            mcp.call_tool("list_items", {"type": "N"}, context)["count"], 20
        )
        schemas = mcp.filter_tool_schemas_for_profile(mcp.tool_schemas(), "read")
        self.assertTrue(
            next(row for row in schemas if row["name"] == "list_notes")["annotations"][
                "readOnlyHint"
            ]
        )

    def test_local_tui_browsing_raw_search_and_detail(self):
        backend = LocalTuiBackend(self.args)
        self.assertEqual(self.expected, ids(backend.load_notes()[0]))
        state = tui_app.WorkspaceState(self.args, backend=backend)
        state.reload()
        tui_app._cmd_view(state, "notes")
        state.refresh()
        self.assertEqual(self.expected, [row["id"] for row in state.rows])
        self.assertEqual("Note_00", state.selected_row()["title"])
        state.query = "Note_11"
        state.refresh()
        self.assertEqual("n11", state.rows[0]["id"])
        self.assertTrue(all(row["id"] in self.expected for row in state.rows))
        state.query = ""
        tui_app._cmd_view(state, "raw-notes")
        state.refresh()
        self.assertGreater(len(state.rows), 20)

    @unittest.skipIf(TestClient is None, "Web extras unavailable")
    def test_web_mcp_cli_local_remote_tui_parity(self):
        with TestClient(
            webapp.create_app(paths=[str(self.path)], read_only=True)
        ) as client:
            api = client.get("/api/notes?limit=100").json()
            self.assertEqual(self.expected, [row["id"] for row in api["items"]])
            self.assertEqual(12, api["total"])
            self.assertEqual(
                self.expected,
                [
                    row["id"]
                    for row in client.get("/api/items?ordinary_notes=true").json()[
                        "items"
                    ]
                ],
            )
            self.assertGreater(client.get("/api/items?type=N").json()["count"], 20)
            calls = []

            class Connection:
                host = "example.test"
                base_url = "https://example.test"
                username = "reader"

                def request(self, method, path):
                    calls.append(path)
                    response = client.get(path)
                    response.raise_for_status()
                    return response.json()

            backend = RemoteTuiBackend(Connection())
            notes, error = backend.load_notes(items=self.items)
            self.assertIsNone(error)
            self.assertEqual(self.expected, ids(notes))
            self.assertTrue(all(path.startswith("/api/notes?") for path in calls))
            state = tui_app.WorkspaceState(self.args, backend=backend)
            tui_app._cmd_view(state, "notes")
            state.refresh()
            self.assertEqual(self.expected, [row["id"] for row in state.rows])
            # Browser clients never contain private classification rules.
            self.assertIn("/api/notes?date=", PLANNER_HTML_PAGE)
            self.assertIn("ordinary_notes", HTML_PAGE)
            self.assertIn("Ordinary Notes", HTML_PAGE)
            self.assertIn("Raw Notes (N)", HTML_PAGE)
            self.assertNotIn("/api/items?type=N&limit=20", PLANNER_HTML_PAGE)
            for invalid in (
                "limit=0",
                "offset=-1",
                "limit=101",
                "date=2031-02-30",
                "sort=score",
            ):
                self.assertEqual(400, client.get("/api/notes?" + invalid).status_code)
            response = client.get("/api/notes?text=Note_11&limit=5").json()
            self.assertEqual(1, response["total"])
            self.assertEqual("n11", response["items"][0]["id"])

    @unittest.skipIf(TestClient is None, "Web extras unavailable")
    def test_web_bounded_pages_empty_and_normal_note_creation(self):
        with TestClient(
            webapp.create_app(paths=[str(self.path)], writable_path=str(self.path))
        ) as client:
            pages = [client.get("/api/notes?offset=%s" % i).json() for i in (0, 5, 10)]
            self.assertEqual([5, 5, 2], [p["count"] for p in pages])
            self.assertEqual([True, True, False], [p["has_more"] for p in pages])
            self.assertEqual(
                self.expected, [row["id"] for p in pages for row in p["items"]]
            )
            payload = {"status": "[N]", "type": "N", "title": "New Note", "details": {}}
            self.assertEqual(201, client.post("/api/items", json=payload).status_code)
            result = client.get("/api/notes?limit=100").json()
            self.assertEqual(13, result["total"])
            self.assertIn("New Note", [row["title"] for row in result["items"]])
            self.path.write_text(mixed_text(0), encoding="utf-8")
            empty = client.get("/api/notes").json()
            self.assertEqual([], empty["items"])
            self.assertEqual(0, empty["total"])
            self.assertFalse(empty["has_more"])

    @unittest.skipIf(TestClient is None, "Web extras unavailable")
    def test_selected_date_order_search_and_page_parity(self):
        self.path.write_text(
            mixed_text() + "[N] N Selected id:day on:2031-02-03\n"
            "[N] N Recent id:recent updated:2031-02-04T11:00Z\n",
            encoding="utf-8",
        )
        items, _ = parse_text(self.path.read_text())
        expected = ids(
            ordinary_notes_page(items, date="2031-02-03", offset=1, limit=5)["items"]
        )
        cli_result = json.loads(
            self.run_cli(
                "notes",
                str(self.path),
                "--date",
                "2031-02-03",
                "--offset",
                "1",
                "--format",
                "json",
            )
        )
        context = mcp.McpContext(paths=[str(self.path)], read_only=True)
        mcp_result = mcp.call_tool(
            "list_notes", {"date": "2031-02-03", "offset": 1}, context
        )
        with TestClient(
            webapp.create_app(paths=[str(self.path)], read_only=True)
        ) as client:
            web_result = client.get("/api/notes?date=2031-02-03&offset=1").json()
            self.assertEqual(expected, [row["id"] for row in web_result["items"]])
        self.assertEqual(expected, [row["id"] for row in mcp_result["items"]])
        self.assertEqual(
            expected, [row["details"]["id"][0] for row in cli_result["items"]]
        )
        self.assertEqual(14, cli_result["total"])
        self.assertEqual("recent", expected[0])

    def test_remote_safe_resource_parity_visibility_paging_and_redaction(self):
        from lifetxt.remote_access import RemoteAccessError, principal_registry
        from lifetxt.remote_backend import read_resource

        config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {"id": "reader", "role": "reader", "visibilities": ["shared"]}
                ],
            }
        }
        principal = principal_registry(config)["reader"]
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                "[N] N Secret id:secret visibility:private owner:other updated:2099-01-01\n"
            )
            handle.write("[N] N Public id:public attachment:/tmp/private-file.txt\n")
        result = read_resource(
            "notes", [str(self.path)], config, principal, {"limit": 100}
        )
        self.assertEqual(13, result["data"]["total"])
        self.assertEqual(
            set(self.expected + ["public"]),
            {row["id"] for row in result["data"]["items"]},
        )
        self.assertNotIn("Secret", json.dumps(result))
        self.assertNotIn("/tmp/private-file.txt", json.dumps(result))
        self.assertTrue(
            all(
                not row["editable"] and "source" not in row and "text" not in row
                for row in result["data"]["items"]
            )
        )
        page = read_resource(
            "notes", [str(self.path)], config, principal, {"limit": 5, "offset": 5}
        )["data"]
        self.assertEqual(5, page["count"])
        self.assertEqual(13, page["total"])
        self.assertEqual(10, page["next_offset"])
        with self.assertRaises(RemoteAccessError):
            read_resource("notes", [str(self.path)], config, principal, {"limit": 101})

    @unittest.skipIf(TestClient is None, "Web extras unavailable")
    def test_authenticated_remote_notes_resource_and_browser_entry(self):
        config = {
            "api": {"token": "legacy-test-token"},
            "remote": {
                "enabled": True,
                "browser_ui": True,
                "allow_loopback_http": True,
                "principals": [
                    {
                        "id": "reader",
                        "role": "reader",
                        "token_env": "NOTES_TEST_TOKEN",
                        "visibilities": ["shared"],
                    }
                ],
            },
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("[N] N Secret id:secret visibility:private owner:other\n")
        with (
            patch.dict(os.environ, {"NOTES_TEST_TOKEN": "notes-test-token"}),
            TestClient(
                webapp.create_app(paths=[str(self.path)], config=config, read_only=True)
            ) as client,
        ):
            headers = {
                "X-Lifetxt-Remote-Version": "2",
                "Authorization": "Bearer notes-test-token",
            }
            response = client.get(
                "/api/remote/v1/resources/notes?limit=100", headers=headers
            )
            self.assertEqual(200, response.status_code, response.text)
            data = response.json()["data"]
            self.assertEqual(self.expected, [row["id"] for row in data["items"]])
            self.assertEqual(12, data["total"])
            self.assertNotIn("Secret", response.text)
            self.assertEqual(
                401, client.get("/api/remote/v1/resources/notes").status_code
            )
            page = client.get("/remote").text
            self.assertIn('id="notes-refresh"', page)
            self.assertIn("/api/remote/v1/resources/notes?limit=20", page)
            self.assertIn("通常のメモ", page)
            self.assertIn("Next Notes page", page)

    def test_remote_paging_authority_no_client_classification_and_errors(self):
        rows = [
            {"id": "n%s" % i, "line": i + 1, "text": "[N] N Note id:n%s" % i}
            for i in range(112)
        ]
        calls = []

        class Connection:
            host = "example.test"
            base_url = "https://example.test"
            username = "reader"

            def request(self, method, path):
                calls.append(path)
                offset = int(parse_qs(urlsplit(path).query)["offset"][0])
                return {
                    "items": rows[offset : offset + 100],
                    "total": 112,
                    "has_more": offset == 0,
                    "next_offset": 100 if offset == 0 else None,
                    "revision": "r",
                }

        backend = RemoteTuiBackend(Connection())
        notes, error = backend.load_notes()
        self.assertIsNone(error)
        self.assertEqual(112, len(notes))
        self.assertEqual(2, len(calls))
        # Trust the server even when a record looks specialized locally.
        rows[0]["text"] = "[N] N Server_choice id:n0 person:self"
        self.assertEqual("n0", ids(backend.load_notes()[0])[0])
        with patch.object(
            backend.connection, "request", side_effect=ValueError("offline")
        ):
            notes, error = backend.load_notes(items=self.items)
            self.assertIsNone(notes)
            self.assertIn("offline", error)
        with patch.object(backend.connection, "request", return_value={"items": []}):
            self.assertIn("does not provide", backend.load_notes()[1])
        with patch.object(
            backend.connection,
            "request",
            side_effect=[
                {
                    "items": rows[:100],
                    "total": 112,
                    "has_more": True,
                    "next_offset": 100,
                    "revision": "r",
                },
                {
                    "items": rows[100:],
                    "total": 112,
                    "has_more": False,
                    "revision": "changed",
                },
            ],
        ):
            self.assertIn("changed during paging", backend.load_notes()[1])
