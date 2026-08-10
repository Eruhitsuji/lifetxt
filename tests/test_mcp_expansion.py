"""Tests for the expanded MCP server: parity tools, write safety, and prompts."""

import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt.mcp import (
    DESTRUCTIVE_TOOLS,
    PROMPT_DEFINITIONS,
    READ_ONLY_TOOLS,
    TOOL_HANDLERS,
    McpContext,
    call_tool,
    file_hash,
    handle_request,
    prompt_get,
    prompt_list,
    tool_schemas,
)
from lifetxt.parser import parse_text


SAMPLE = (
    "[ ] T Write_Report id:t1 project:work priority:high due:2026-07-25\n"
    "[ ] T Blocked_Task id:t2 depends_on:t1\n"
    "[?] T Someday_Idea id:t3\n"
    "[ ] T Parked id:t4 tag:someday\n"
    "[ ] H Exercise id:h1 repeat:daily done:2026-07-18 done:2026-07-19\n"
)


class McpTestCase(unittest.TestCase):
    def _context(self, content=SAMPLE, config=None, read_only=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        settings = {"timer": {"state_file": os.path.join(tmp.name, "timer.json")}}
        settings.update(config or {})
        context = McpContext(
            paths=[path], writable_path=path, config=settings, read_only=read_only
        )
        return context, path

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


class ToolRegistryTests(McpTestCase):
    def test_every_handler_has_a_schema_and_vice_versa(self):
        names = [schema["name"] for schema in tool_schemas()]

        self.assertEqual(sorted(names), sorted(TOOL_HANDLERS))
        self.assertEqual(len(names), len(set(names)), "duplicate tool name")

    def test_annotations_match_the_central_classification(self):
        for schema in tool_schemas():
            name = schema["name"]
            annotations = schema["annotations"]
            self.assertEqual(name in READ_ONLY_TOOLS, annotations["readOnlyHint"], name)
            self.assertEqual(
                name in DESTRUCTIVE_TOOLS, annotations["destructiveHint"], name
            )

    def test_read_only_tools_are_classified_consistently(self):
        # A tool cannot be both read-only and destructive.
        self.assertEqual(set(), READ_ONLY_TOOLS & DESTRUCTIVE_TOOLS)

    def test_every_schema_has_a_description(self):
        for schema in tool_schemas():
            self.assertTrue(schema["description"].strip(), schema["name"])
            self.assertEqual("object", schema["inputSchema"]["type"])

    def test_read_only_context_blocks_every_write_tool(self):
        context, path = self._context(read_only=True)
        before = self._read(path)
        write_tools = [name for name in TOOL_HANDLERS if name not in READ_ONLY_TOOLS]

        for name in write_tools:
            with self.assertRaises(ValueError, msg=name) as caught:
                call_tool(name, {"id": "t1", "text": "x", "state": "busy"}, context)
            # Whatever the tool needs, a read-only server must refuse first.
            self.assertIn("read-only", str(caught.exception).lower(), name)

        self.assertEqual(before, self._read(path))

    def test_read_tools_work_in_read_only_mode(self):
        context, _path = self._context(read_only=True)

        self.assertTrue(call_tool("list_items", {}, context)["items"])
        self.assertTrue(call_tool("get_next_actions", {}, context)["items"])
        self.assertFalse(call_tool("get_file_state", {}, context)["read_only"] is False)


class WriteSafetyTests(McpTestCase):
    def test_file_hash_changes_after_a_write(self):
        context, path = self._context()
        before = file_hash(path)

        call_tool("capture_item", {"text": "New task"}, context)

        self.assertNotEqual(before, file_hash(path))

    def test_file_hash_of_a_missing_file_is_empty(self):
        self.assertEqual("", file_hash(os.path.join(tempfile.mkdtemp(), "nope.txt")))

    def test_stale_expected_hash_is_rejected(self):
        context, path = self._context()
        stale = file_hash(path)
        call_tool("capture_item", {"text": "Interleaved edit"}, context)
        before = self._read(path)

        with self.assertRaises(ValueError) as caught:
            call_tool(
                "capture_item", {"text": "Second", "expected_file_hash": stale}, context
            )

        self.assertIn("conflict", str(caught.exception).lower())
        self.assertEqual(before, self._read(path))

    def test_current_expected_hash_is_accepted(self):
        context, path = self._context()
        current = file_hash(path)

        result = call_tool(
            "capture_item", {"text": "Fresh", "expected_file_hash": current}, context
        )

        self.assertTrue(result["applied"])

    def test_write_result_reports_the_new_hash(self):
        context, path = self._context()

        result = call_tool("capture_item", {"text": "New"}, context)

        self.assertEqual(file_hash(path), result["file_hash"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["proposal"])

    def test_hash_check_applies_to_update_done_and_delete(self):
        for name, args in (
            ("update_item", {"id": "t1", "set_details": {"tag": ["x"]}}),
            ("mark_done", {"id": "t1"}),
            ("delete_item", {"id": "t1"}),
        ):
            context, path = self._context()
            stale = "0" * 64
            before = self._read(path)

            payload = dict(args)
            payload["expected_file_hash"] = stale
            with self.assertRaises(ValueError, msg=name):
                call_tool(name, payload, context)

            self.assertEqual(before, self._read(path), name)

    def test_created_records_carry_source_metadata(self):
        context, _path = self._context()

        created = call_tool("create_item", {"type": "T", "title": "Made"}, context)
        captured = call_tool("capture_item", {"text": "Captured"}, context)

        self.assertEqual(["mcp"], created["item"]["details"]["source"])
        self.assertEqual(["mcp"], captured["item"]["details"]["source"])

    def test_source_metadata_can_be_disabled(self):
        context, _path = self._context(config={"mcp": {"source_metadata": False}})

        created = call_tool("create_item", {"type": "T", "title": "Made"}, context)

        self.assertNotIn("source", created["item"]["details"])

    def test_server_generates_an_id_even_when_auto_ids_are_off(self):
        context, _path = self._context()

        created = call_tool("create_item", {"type": "T", "title": "Made"}, context)
        captured = call_tool("capture_item", {"text": "Captured"}, context)

        first = created["item"]["details"]["id"][0]
        second = captured["item"]["details"]["id"][0]
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertNotEqual(first, second)

    def test_client_supplied_id_is_refused(self):
        context, _path = self._context()

        with self.assertRaises(ValueError) as caught:
            call_tool(
                "create_item",
                {"type": "T", "title": "Made", "details": {"id": ["invented"]}},
                context,
            )

        self.assertIn("generates it", str(caught.exception))


class ProposalModeTests(McpTestCase):
    def test_capture_dry_run_returns_a_diff_and_writes_nothing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool(
            "capture_item", {"text": "Proposed @work", "dry_run": True}, context
        )

        self.assertFalse(result["applied"])
        self.assertTrue(result["proposal"])
        self.assertTrue(any(line.startswith("+[ ] T") for line in result["diff"]))
        self.assertEqual(before, self._read(path))

    def test_mark_done_dry_run_writes_nothing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool("mark_done", {"id": "t1", "dry_run": True}, context)

        self.assertFalse(result["applied"])
        self.assertTrue(any("[x] T Write_Report" in line for line in result["diff"]))
        self.assertEqual(before, self._read(path))

    def test_update_dry_run_writes_nothing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool(
            "update_item",
            {"id": "t1", "set_details": {"priority": ["low"]}, "dry_run": True},
            context,
        )

        self.assertFalse(result["applied"])
        self.assertEqual(before, self._read(path))

    def test_set_status_dry_run_writes_nothing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool("set_status", {"state": "busy", "dry_run": True}, context)

        self.assertFalse(result["applied"])
        self.assertTrue(result["opened"])
        self.assertEqual(before, self._read(path))

    def test_proposal_leaves_the_file_byte_identical(self):
        context, path = self._context()
        before = self._read(path)
        before_hash = file_hash(path)

        call_tool("mark_done", {"id": "t1", "dry_run": True}, context)
        call_tool("update_item", {"id": "t2", "title": "X", "dry_run": True}, context)

        self.assertEqual(before, self._read(path))
        self.assertEqual(before_hash, file_hash(path))


class PresenceToolTests(McpTestCase):
    def test_set_status_opens_then_switches(self):
        context, path = self._context()

        first = call_tool("set_status", {"state": "busy"}, context)
        second = call_tool(
            "set_status", {"state": "focus", "title": "Deep Work"}, context
        )

        self.assertEqual([], first["closed"])
        self.assertEqual(1, len(second["closed"]))
        content = self._read(path)
        self.assertEqual(1, content.count("[/] S"))
        self.assertIn("state:focus", content)

    def test_repeating_a_state_writes_nothing(self):
        context, path = self._context()
        call_tool("set_status", {"state": "busy"}, context)
        before = self._read(path)

        result = call_tool("set_status", {"state": "busy"}, context)

        self.assertEqual("busy", result["unchanged"])
        self.assertFalse(result["applied"])
        self.assertEqual(before, self._read(path))

    def test_force_records_a_repeated_state(self):
        context, _path = self._context()
        call_tool("set_status", {"state": "busy"}, context)

        result = call_tool("set_status", {"state": "busy", "force": True}, context)

        self.assertEqual(1, len(result["closed"]))
        self.assertTrue(result["applied"])

    def test_end_closes_without_opening(self):
        context, path = self._context()
        call_tool("set_status", {"state": "busy"}, context)

        result = call_tool("set_status", {"end": True}, context)

        self.assertEqual("", result["opened"])
        self.assertEqual(0, self._read(path).count("[/] S"))

    def test_set_status_without_state_is_rejected(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("set_status", {}, context)

    def test_get_status_reports_the_open_record(self):
        context, _path = self._context()
        call_tool("set_status", {"state": "focus"}, context)

        result = call_tool("get_status", {}, context)

        self.assertEqual(1, len(result["open"]))
        self.assertEqual("focus", result["open"][0]["state"])

    def test_status_writes_stay_valid_life_txt(self):
        context, path = self._context()
        call_tool("set_status", {"state": "busy"}, context)
        call_tool("set_status", {"state": "away"}, context)

        _items, diagnostics = parse_text(self._read(path))
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])


class CaptureToolTests(McpTestCase):
    def test_capture_expands_sigils(self):
        context, path = self._context()

        result = call_tool(
            "capture_item", {"text": "Buy milk @home #errand !high ^tomorrow"}, context
        )

        line = result["text"]
        self.assertIn("project:home", line)
        self.assertIn("tag:errand", line)
        self.assertIn("priority:high", line)
        self.assertIn("due:", line)
        _items, diagnostics = parse_text(self._read(path))
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])

    def test_capture_rejects_an_invalid_date_token(self):
        context, _path = self._context()

        with self.assertRaises(ValueError) as caught:
            call_tool("capture_item", {"text": "Thing ^notadate"}, context)

        self.assertIn("is not a date", str(caught.exception))

    def test_capture_rejects_a_title_made_only_of_sigils(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("capture_item", {"text": "@home"}, context)

    def test_parse_shorthand_previews_without_writing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool(
            "parse_shorthand", {"text": "Buy milk @home ^tomorrow"}, context
        )

        self.assertEqual("Buy milk", result["title"])
        self.assertEqual(["home"], result["details"]["project"])
        self.assertEqual(before, self._read(path))

    def test_parse_shorthand_documents_the_token_set(self):
        context, _path = self._context()

        result = call_tool("parse_shorthand", {}, context)

        self.assertTrue(result["sigils"])
        self.assertTrue(result["date_tokens"])

    def test_parse_shorthand_resolves_a_single_date(self):
        context, _path = self._context()

        result = call_tool("parse_shorthand", {"date": "+3d"}, context)

        self.assertRegex(result["date"], r"^\d{4}-\d{2}-\d{2}$")


class CompletionPrecisionTests(McpTestCase):
    def test_mark_done_writes_a_date_by_default(self):
        context, _path = self._context()

        result = call_tool("mark_done", {"id": "t1"}, context)

        self.assertRegex(result["item"]["details"]["done"][0], r"^\d{4}-\d{2}-\d{2}$")

    def test_now_flag_writes_a_timestamp(self):
        context, _path = self._context()

        result = call_tool("mark_done", {"id": "t1", "now": True}, context)

        self.assertRegex(
            result["item"]["details"]["done"][0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
        )

    def test_config_precision_is_honoured(self):
        context, _path = self._context(config={"done": {"precision": "datetime"}})

        result = call_tool("mark_done", {"id": "t1"}, context)

        self.assertRegex(
            result["item"]["details"]["done"][0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
        )

    def test_explicit_done_value_still_wins(self):
        context, _path = self._context(config={"done": {"precision": "datetime"}})

        result = call_tool("mark_done", {"id": "t1", "done": "2026-06-12"}, context)

        self.assertEqual(["2026-06-12"], result["item"]["details"]["done"])


class AnalysisToolTests(McpTestCase):
    def test_next_actions_excludes_blocked_someday_and_parked(self):
        context, _path = self._context()

        titles = [
            item["title"]
            for item in call_tool("get_next_actions", {}, context)["items"]
        ]

        self.assertIn("Write_Report", titles)
        self.assertNotIn("Blocked_Task", titles)
        self.assertNotIn("Someday_Idea", titles)
        self.assertNotIn("Parked", titles)

    def test_next_actions_filters_by_project(self):
        context, _path = self._context()

        titles = [
            item["title"]
            for item in call_tool("get_next_actions", {"project": "work"}, context)[
                "items"
            ]
        ]

        self.assertEqual(["Write_Report"], titles)

    def test_next_actions_respects_limit(self):
        context, _path = self._context()

        result = call_tool("get_next_actions", {"limit": 1}, context)

        self.assertEqual(1, len(result["items"]))

    def test_search_ranks_title_matches_first(self):
        context, _path = self._context()

        titles = [
            item["title"]
            for item in call_tool("search_items", {"query": "repo"}, context)["items"]
        ]

        self.assertEqual("Write_Report", titles[0])

    def test_search_requires_a_query(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("search_items", {}, context)

    def test_habit_streaks_only_counts_habit_records(self):
        context, _path = self._context()

        habits = call_tool("get_habit_streaks", {}, context)["habits"]

        self.assertEqual(["Exercise"], [row["title"] for row in habits])

    def test_workload_counts_open_and_actionable(self):
        context, _path = self._context()

        people = call_tool("get_workload", {}, context)["people"]

        self.assertEqual(1, len(people))
        self.assertGreaterEqual(people[0]["open"], people[0]["actionable"])

    def test_stats_returns_the_documented_shape(self):
        context, _path = self._context()

        stats = call_tool("get_stats", {"group": "day"}, context)

        for key in ("range", "tasks", "habits", "by_project"):
            self.assertIn(key, stats)

    def test_stats_rejects_an_unknown_group(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("get_stats", {"group": "fortnight"}, context)

    def test_file_state_exposes_hashes_and_settings(self):
        context, path = self._context()

        state = call_tool("get_file_state", {}, context)

        self.assertEqual(path, state["writable_path"])
        self.assertEqual(file_hash(path), state["file_hash"])
        self.assertIn(path, state["hashes"])
        self.assertEqual("date", state["done_precision"])


class TimerToolTests(McpTestCase):
    def test_timer_start_status_and_stop(self):
        context, path = self._context()

        self.assertFalse(call_tool("timer_status", {}, context)["running"])

        call_tool("timer_start", {"id": "t1"}, context)
        status = call_tool("timer_status", {}, context)
        self.assertTrue(status["running"])
        self.assertEqual("t1", status["id"])

        call_tool("timer_stop", {}, context)
        self.assertFalse(call_tool("timer_status", {}, context)["running"])
        self.assertIn("elapsed:", self._read(path))

    def test_timer_start_refuses_a_second_timer(self):
        context, _path = self._context()
        call_tool("timer_start", {"id": "t1"}, context)

        with self.assertRaises(ValueError) as caught:
            call_tool("timer_start", {"id": "t2"}, context)

        self.assertIn("already running", str(caught.exception))

    def test_timer_start_requires_a_known_id(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("timer_start", {"id": "nope"}, context)

    def test_timer_cancel_discards_without_writing_elapsed(self):
        context, path = self._context()
        call_tool("timer_start", {"id": "t1"}, context)

        call_tool("timer_cancel", {}, context)

        self.assertFalse(call_tool("timer_status", {}, context)["running"])
        self.assertNotIn("elapsed:", self._read(path))

    def test_timer_stop_without_a_timer_is_rejected(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("timer_stop", {}, context)


class WorkSessionTests(McpTestCase):
    def test_start_work_sets_progress_timer_and_presence(self):
        context, path = self._context()

        call_tool("start_work", {"id": "t1"}, context)

        content = self._read(path)
        self.assertIn("[/] T Write_Report", content)
        self.assertIn("state:busy", content)
        self.assertTrue(call_tool("timer_status", {}, context)["running"])

    def test_stop_work_closes_everything(self):
        context, path = self._context()
        call_tool("start_work", {"id": "t1"}, context)

        call_tool("stop_work", {"done": True}, context)

        content = self._read(path)
        self.assertIn("[x] T Write_Report", content)
        self.assertIn("elapsed:", content)
        self.assertIn("done:", content)
        self.assertEqual(0, content.count("[/] S"))
        self.assertFalse(call_tool("timer_status", {}, context)["running"])

    def test_start_work_dry_run_changes_nothing(self):
        context, path = self._context()
        before = self._read(path)

        result = call_tool("start_work", {"id": "t1", "dry_run": True}, context)

        self.assertFalse(result["applied"])
        self.assertEqual(before, self._read(path))
        self.assertFalse(call_tool("timer_status", {}, context)["running"])

    def test_start_work_can_skip_presence(self):
        context, path = self._context()

        call_tool("start_work", {"id": "t1", "no_presence": True}, context)

        self.assertNotIn(" S ", self._read(path))

    def test_stop_work_without_a_session_is_rejected(self):
        context, _path = self._context()

        with self.assertRaises(ValueError):
            call_tool("stop_work", {}, context)


class PromptTests(McpTestCase):
    def test_prompt_list_matches_the_definitions(self):
        names = [prompt["name"] for prompt in prompt_list()]

        self.assertEqual(sorted(names), sorted(PROMPT_DEFINITIONS))
        for prompt in prompt_list():
            self.assertTrue(prompt["description"].strip(), prompt["name"])

    def test_prompt_get_returns_a_user_message(self):
        result = prompt_get("daily_review")

        self.assertEqual(1, len(result["messages"]))
        self.assertEqual("user", result["messages"][0]["role"])
        self.assertIn("get_next_actions", result["messages"][0]["content"]["text"])

    def test_prompt_arguments_are_appended_as_context(self):
        result = prompt_get("standup", {"person": "alice"})

        self.assertIn("alice", result["messages"][0]["content"]["text"])

    def test_unknown_prompt_is_rejected(self):
        with self.assertRaises(ValueError):
            prompt_get("nope")

    def test_prompts_only_reference_tools_that_exist(self):
        for name, spec in PROMPT_DEFINITIONS.items():
            for word in spec["template"].split():
                candidate = word.strip("().,:").rstrip(".")
                if candidate.startswith(
                    ("get_", "list_", "start_", "stop_", "update_", "capture_")
                ):
                    self.assertIn(
                        candidate, TOOL_HANDLERS, "%s in prompt %s" % (candidate, name)
                    )


class JsonRpcTests(McpTestCase):
    def _rpc(self, context, method, **params):
        return handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, context
        )

    def test_initialize_advertises_prompts(self):
        context, _path = self._context()

        capabilities = self._rpc(context, "initialize")["result"]["capabilities"]

        self.assertIn("prompts", capabilities)
        self.assertIn("tools", capabilities)
        self.assertIn("resources", capabilities)

    def test_prompts_list_and_get_over_jsonrpc(self):
        context, _path = self._context()

        listed = self._rpc(context, "prompts/list")["result"]["prompts"]
        fetched = self._rpc(context, "prompts/get", name="standup")["result"]

        self.assertTrue(listed)
        self.assertIn("messages", fetched)

    def test_tools_call_returns_structured_content(self):
        context, _path = self._context()

        response = self._rpc(
            context, "tools/call", name="get_next_actions", arguments={"limit": 1}
        )

        result = response["result"]
        self.assertIn("structuredContent", result)
        self.assertEqual(1, len(result["structuredContent"]["items"]))
        json.loads(result["content"][0]["text"])

    def test_tool_error_becomes_a_jsonrpc_error(self):
        context, _path = self._context()

        response = self._rpc(context, "tools/call", name="search_items", arguments={})

        self.assertIn("error", response)
        self.assertEqual(-32000, response["error"]["code"])

    def test_unknown_method_is_reported(self):
        context, _path = self._context()

        response = self._rpc(context, "nonsense/method")

        self.assertEqual(-32601, response["error"]["code"])


class RemoteMcpToolsTests(McpTestCase):
    """MCP-side wrapper over the existing lifetxt.remote_client library.

    remote_list_profiles/remote_test_connection/remote_list_resources/
    remote_get_resource reuse the same profile store and request() helper
    the CLI's `lifetxt remote` commands already use -- these tests mock at
    that shared boundary (lifetxt.remote_client.request), matching the
    pattern tests/test_remote_client_v19.py already established, rather than
    reimplementing HTTP-level mocking.
    """

    def _profiles_file(self, name="myserver", url="https://example.test"):
        from lifetxt.remote_client import set_profile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "profiles.json")
        set_profile(name, url, token_env="LIFETXT_TEST_TOKEN", path=path)
        return path

    def test_remote_list_profiles_reports_url_and_no_secrets(self):
        context, _path = self._context()
        profiles_file = self._profiles_file()

        result = call_tool(
            "remote_list_profiles", {"profiles_file": profiles_file}, context
        )

        self.assertEqual(1, result["count"])
        self.assertEqual("myserver", result["profiles"][0]["name"])
        self.assertEqual("https://example.test", result["profiles"][0]["url"])
        self.assertNotIn("LIFETXT_TEST_TOKEN", json.dumps(result))

    def test_remote_get_resource_requires_a_known_profile(self):
        context, _path = self._context()
        profiles_file = self._profiles_file()

        with self.assertRaises(ValueError):
            call_tool(
                "remote_get_resource",
                {
                    "profile": "does-not-exist",
                    "resource": "next",
                    "profiles_file": profiles_file,
                },
                context,
            )

    def test_remote_get_resource_requires_a_resource_name(self):
        context, _path = self._context()
        profiles_file = self._profiles_file()

        with self.assertRaises(ValueError):
            call_tool(
                "remote_get_resource",
                {"profile": "myserver", "profiles_file": profiles_file},
                context,
            )

    def test_remote_get_resource_rejects_non_object_params(self):
        context, _path = self._context()
        profiles_file = self._profiles_file()

        with self.assertRaises(ValueError):
            call_tool(
                "remote_get_resource",
                {
                    "profile": "myserver",
                    "resource": "next",
                    "params": "project=web",
                    "profiles_file": profiles_file,
                },
                context,
            )

    @mock.patch("lifetxt.remote_client.request")
    def test_remote_test_connection_reports_negotiated_protocol(self, req):
        context, _path = self._context()
        profiles_file = self._profiles_file()
        req.side_effect = [
            ({"enabled": True}, {"lifetxt-remote-capability-revision": "rev1"}),
            (
                {"principal": {"id": "alice"}},
                {"lifetxt_negotiated_protocol": 2},
            ),
        ]

        result = call_tool(
            "remote_test_connection",
            {"profile": "myserver", "profiles_file": profiles_file},
            context,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("alice", result["session"]["principal"]["id"])

    @mock.patch("lifetxt.remote_client.request")
    def test_remote_list_resources_returns_the_catalog(self, req):
        context, _path = self._context()
        profiles_file = self._profiles_file()
        req.return_value = (
            {"resources": [{"name": "next", "parameters": ["project"]}]},
            {},
        )

        result = call_tool(
            "remote_list_resources",
            {"profile": "myserver", "profiles_file": profiles_file},
            context,
        )

        self.assertEqual("next", result["resources"][0]["name"])
        req.assert_called_once()
        self.assertEqual("/api/remote/v1/resources", req.call_args.args[2])

    @mock.patch("lifetxt.remote_client.request")
    def test_remote_get_resource_forwards_params_and_returns_data(self, req):
        context, _path = self._context()
        profiles_file = self._profiles_file()
        req.return_value = ({"data": {"count": 1, "items": []}}, {})

        result = call_tool(
            "remote_get_resource",
            {
                "profile": "myserver",
                "resource": "next",
                "params": {"project": "web"},
                "profiles_file": profiles_file,
            },
            context,
        )

        self.assertEqual(1, result["data"]["count"])
        req.assert_called_once()
        call_kwargs = req.call_args.kwargs
        self.assertEqual({"project": "web"}, call_kwargs["params"])
        self.assertEqual("/api/remote/v1/resources/next", req.call_args.args[2])

    def test_remote_tools_are_read_only_and_open_world_matches_network_usage(self):
        # remote_list_profiles reads only the local profile store (no network
        # call); the other three make a real request to another host.
        schemas = {schema["name"]: schema for schema in tool_schemas()}
        for name in (
            "remote_list_profiles",
            "remote_test_connection",
            "remote_list_resources",
            "remote_get_resource",
        ):
            self.assertTrue(schemas[name]["annotations"]["readOnlyHint"], name)
        self.assertFalse(
            schemas["remote_list_profiles"]["annotations"]["openWorldHint"]
        )
        for name in (
            "remote_test_connection",
            "remote_list_resources",
            "remote_get_resource",
        ):
            self.assertTrue(schemas[name]["annotations"]["openWorldHint"], name)


if __name__ == "__main__":
    unittest.main()
