"""Tests for the expanded MCP server: parity tools, write safety, and prompts."""

import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt.mcp import (
    ASSIST_EXTRA_TOOLS,
    DESTRUCTIVE_TOOLS,
    PROMPT_DEFINITIONS,
    READ_ONLY_TOOLS,
    TOOL_HANDLERS,
    McpContext,
    _profile_allowed_tools,
    _require_tool_allowed_for_profile,
    call_tool,
    file_hash,
    filter_tool_schemas_for_profile,
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
    def _context(self, content=SAMPLE, config=None, read_only=False, profile=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        settings = {
            "timer": {"state_file": os.path.join(tmp.name, "timer.json")},
            "inbox": {"proposals_file": os.path.join(tmp.name, "proposals.json")},
        }
        settings.update(config or {})
        context = McpContext(
            paths=[path],
            writable_path=path,
            config=settings,
            read_only=read_only,
            profile=profile,
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


class McpPermissionProfileTests(McpTestCase):
    """--profile read|assist|full: selection, --read-only alias, and the
    per-profile tool allowlist enforced at tools/list and tools/call."""

    # --- Requirement 1 / 4.2 / 5.1 / 7.1: profile selection and normalization ---

    def test_no_flags_defaults_to_full(self):
        context, _path = self._context()

        self.assertEqual("full", context.profile)
        self.assertFalse(context.read_only)

    def test_profile_full_is_explicit_and_unrestricted(self):
        context, _path = self._context(profile="full")

        self.assertEqual("full", context.profile)
        self.assertFalse(context.read_only)
        self.assertIsNone(_profile_allowed_tools(context.profile))

    def test_profile_assist_does_not_imply_read_only(self):
        context, _path = self._context(profile="assist")

        self.assertEqual("assist", context.profile)
        self.assertFalse(context.read_only)

    def test_read_only_flag_normalizes_to_profile_read(self):
        context, _path = self._context(read_only=True)

        self.assertEqual("read", context.profile)
        self.assertTrue(context.read_only)

    def test_profile_read_is_equivalent_to_read_only_flag(self):
        via_flag, _ = self._context(read_only=True)
        via_profile, _ = self._context(profile="read")

        self.assertEqual(via_flag.profile, via_profile.profile)
        self.assertEqual(via_flag.read_only, via_profile.read_only)

    def test_read_only_flag_combined_with_matching_profile_is_accepted(self):
        context, _path = self._context(read_only=True, profile="read")

        self.assertEqual("read", context.profile)
        self.assertTrue(context.read_only)

    def test_read_only_flag_combined_with_a_different_profile_conflicts(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)

        for other in ("assist", "full"):
            with self.assertRaises(ValueError) as caught:
                McpContext(
                    paths=[path], writable_path=path, read_only=True, profile=other
                )
            self.assertIn("--read-only", str(caught.exception))
            self.assertIn(other, str(caught.exception))

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self._context(profile="bogus")

        self.assertIn("bogus", str(caught.exception))

    # --- Requirement 6: fail-closed allowlist computation ---

    def test_read_allowlist_is_exactly_read_only_tools(self):
        self.assertEqual(READ_ONLY_TOOLS, _profile_allowed_tools("read"))

    def test_assist_allowlist_is_read_only_tools_plus_stage_proposal(self):
        self.assertEqual({"stage_proposal"}, set(ASSIST_EXTRA_TOOLS))
        self.assertEqual(
            READ_ONLY_TOOLS | ASSIST_EXTRA_TOOLS, _profile_allowed_tools("assist")
        )

    def test_full_and_unset_profile_have_no_restriction(self):
        self.assertIsNone(_profile_allowed_tools("full"))
        self.assertIsNone(_profile_allowed_tools(None))

    def test_read_allowlist_is_a_subset_of_assist_allowlist(self):
        self.assertTrue(
            _profile_allowed_tools("read") <= _profile_allowed_tools("assist")
        )

    def test_never_classified_tool_is_denied_under_read_and_assist_but_allowed_under_full(
        self,
    ):
        fake_name = "mcp_permission_profile_test_never_classified_tool"
        self.assertNotIn(fake_name, READ_ONLY_TOOLS)
        self.assertNotIn(fake_name, ASSIST_EXTRA_TOOLS)
        self.assertNotIn(fake_name, DESTRUCTIVE_TOOLS)
        TOOL_HANDLERS[fake_name] = lambda args, context: {"ok": True}
        self.addCleanup(TOOL_HANDLERS.pop, fake_name, None)

        read_context, _ = self._context(profile="read")
        assist_context, _ = self._context(profile="assist")
        full_context, _ = self._context(profile="full")

        for context in (read_context, assist_context):
            with self.assertRaises(ValueError) as caught:
                _require_tool_allowed_for_profile(fake_name, context)
            self.assertIn(fake_name, str(caught.exception))

        _require_tool_allowed_for_profile(fake_name, full_context)  # does not raise

    def test_annotations_are_never_consulted_for_the_decision(self):
        # get_file_state is annotated readOnlyHint=True (it is in READ_ONLY_TOOLS);
        # create_item is annotated readOnlyHint=False and is a normal write tool.
        # _profile_allowed_tools must decide purely from READ_ONLY_TOOLS /
        # ASSIST_EXTRA_TOOLS membership, never from the annotation dict built by
        # _annotate() -- these two disjoint sources agreeing is exactly what a
        # bug reading annotations instead would not reproduce for every tool.
        allowed_read = _profile_allowed_tools("read")
        self.assertIn("get_file_state", allowed_read)
        self.assertNotIn("create_item", allowed_read)

    # --- call_tool / tools/call enforcement (Requirements 2, 3, 4, 6) ---

    def test_call_tool_direct_dispatch_denies_stage_proposal_under_read(self):
        context, path = self._context(profile="read")
        before = self._read(path)

        # The live dispatch chain has more than one layer that can refuse a
        # write under read_only (see research.md); this only asserts the
        # externally observable outcome -- denied, no write -- not which
        # layer's message wins.
        with self.assertRaises(ValueError):
            call_tool("stage_proposal", {"title": "x"}, context)

        self.assertEqual(before, self._read(path))

    def test_call_tool_direct_dispatch_allows_stage_proposal_under_assist(self):
        context, path = self._context(profile="assist")
        before = self._read(path)

        result = call_tool("stage_proposal", {"title": "Try assist"}, context)

        self.assertTrue(result["staged"])
        self.assertEqual(before, self._read(path))  # never touches life.txt

    def test_call_tool_direct_dispatch_denies_stage_proposal_under_full_is_not_forced(
        self,
    ):
        # Sanity check: full has no restriction, so the same call that is
        # denied under read/assist for an unrelated tool succeeds under full.
        context, _path = self._context(profile="full")

        result = call_tool("stage_proposal", {"title": "Try full"}, context)

        self.assertTrue(result["staged"])

    # --- Full stdio round trip (Requirements 1, 2, 3, 4, 5, 6) ---

    def _tools_list(self, context):
        response = handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, context
        )
        return {schema["name"] for schema in response["result"]["tools"]}

    def _tools_call(self, context, name, arguments):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            context,
        )
        return response

    def test_tools_list_under_read_contains_only_read_only_tools(self):
        context, _path = self._context(profile="read")

        listed = self._tools_list(context)

        self.assertTrue(listed)
        self.assertTrue(listed <= READ_ONLY_TOOLS)
        self.assertNotIn("stage_proposal", listed)
        self.assertNotIn("create_item", listed)

    def test_tools_list_under_assist_adds_only_stage_proposal(self):
        context, _path = self._context(profile="assist")

        listed = self._tools_list(context)

        self.assertIn("stage_proposal", listed)
        self.assertNotIn("create_item", listed)
        self.assertTrue(listed <= (READ_ONLY_TOOLS | ASSIST_EXTRA_TOOLS))

    def test_tools_list_under_full_matches_unfiltered_tool_schemas(self):
        context, _path = self._context(profile="full")

        listed = self._tools_list(context)

        self.assertEqual({schema["name"] for schema in tool_schemas()}, listed)

    def test_tools_list_with_no_profile_matches_full(self):
        # Constructing with neither --read-only nor --profile (today's
        # default) must list exactly what --profile full lists.
        default_context, _path = self._context()
        full_context, _ = self._context(profile="full")

        self.assertEqual(
            self._tools_list(full_context), self._tools_list(default_context)
        )

    def test_tools_call_under_read_denies_a_write_tool_even_with_a_valid_precondition(
        self,
    ):
        context, path = self._context(profile="read")
        response = self._tools_call(
            context,
            "create_item",
            {"type": "T", "title": "x", "expected_file_hash": file_hash(path)},
        )

        self.assertIn("error", response)
        self.assertIn("create_item", response["error"]["message"])
        self.assertEqual(SAMPLE, self._read(path))

    def test_tools_call_under_assist_denies_create_item_but_allows_stage_proposal(self):
        context, path = self._context(profile="assist")
        before = self._read(path)

        denied = self._tools_call(
            context,
            "create_item",
            {"type": "T", "title": "x", "expected_file_hash": file_hash(path)},
        )
        self.assertIn("error", denied)
        self.assertEqual(before, self._read(path))

        allowed = self._tools_call(context, "stage_proposal", {"title": "Assist works"})
        self.assertIn("result", allowed)
        self.assertEqual(before, self._read(path))  # proposal store only

    def test_tools_call_under_full_allows_create_item_with_a_valid_precondition(self):
        context, path = self._context(profile="full")
        before = self._read(path)

        response = self._tools_call(
            context,
            "create_item",
            {"type": "T", "title": "x", "expected_file_hash": file_hash(path)},
        )

        self.assertIn("result", response)
        self.assertNotEqual(before, self._read(path))

    def test_a_client_cannot_call_a_tool_it_was_never_shown(self):
        # tools/list and tools/call must agree: nothing hidden under a
        # constrained profile becomes callable by asking for it directly.
        context, path = self._context(profile="read")
        listed = self._tools_list(context)

        self.assertNotIn("stage_proposal", listed)
        response = self._tools_call(context, "stage_proposal", {"title": "sneaky"})

        self.assertIn("error", response)
        self.assertEqual(SAMPLE, self._read(path))

    # --- Requirement 7: existing handler-level guard still runs independently ---

    def test_require_writable_still_blocks_write_tools_under_read_only(self):
        context, path = self._context(read_only=True)
        before = self._read(path)
        write_tools = [
            name
            for name in TOOL_HANDLERS
            if name not in READ_ONLY_TOOLS and name != "stage_proposal"
        ]

        for name in write_tools:
            with self.assertRaises(ValueError, msg=name):
                call_tool(name, {"id": "t1", "text": "x", "state": "busy"}, context)

        self.assertEqual(before, self._read(path))

    def test_filter_tool_schemas_for_profile_is_independent_of_tool_schemas_signature(
        self,
    ):
        # tool_schemas() itself must keep working with zero arguments
        # (several other modules wrap it with their own zero-arg wrappers).
        schemas = tool_schemas()

        self.assertEqual(schemas, filter_tool_schemas_for_profile(schemas, "full"))
        self.assertEqual(schemas, filter_tool_schemas_for_profile(schemas, None))
        filtered = filter_tool_schemas_for_profile(schemas, "read")
        self.assertTrue({s["name"] for s in filtered} <= READ_ONLY_TOOLS)


class GlobalSearchToolFuzzyTests(McpTestCase):
    def test_fuzzy_defaults_to_false(self):
        context, _path = self._context()
        result = call_tool("global_search", {"term": "Wrte_Report"}, context)
        self.assertEqual(0, result["total"])

    def test_fuzzy_true_matches_a_typo(self):
        context, _path = self._context()
        # "Wrte_Report" is a deleted-letter typo for T1's title "Write_Report".
        result = call_tool(
            "global_search", {"term": "Wrte_Report", "fuzzy": True}, context
        )
        names = [row["name"] for row in result["groups"].get("item", [])]
        self.assertIn("t1", names)

    def test_fuzzy_true_still_ranks_exact_matches_first(self):
        context, _path = self._context()
        exact = call_tool(
            "global_search", {"term": "Write_Report", "fuzzy": True}, context
        )
        without_fuzzy = call_tool("global_search", {"term": "Write_Report"}, context)
        self.assertEqual(exact, without_fuzzy)


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

    def test_explain_item_is_listed_with_a_required_id_argument(self):
        prompts = {prompt["name"]: prompt for prompt in prompt_list()}

        self.assertIn("explain_item", prompts)
        arguments = prompts["explain_item"]["arguments"]
        self.assertEqual(1, len(arguments))
        self.assertEqual("id", arguments[0]["name"])
        self.assertTrue(arguments[0]["required"])

    def test_explain_item_composes_only_existing_read_only_tools(self):
        text = PROMPT_DEFINITIONS["explain_item"]["template"]

        for tool_name in (
            "get_temporal_context",
            "get_backlinks",
            "get_command_center",
            "get_next_actions",
            "get_ticket",
            "get_project",
        ):
            self.assertIn(tool_name, text)
            self.assertIn(tool_name, READ_ONLY_TOOLS)

    def test_explain_item_frames_the_result_as_an_explanation_not_a_write(self):
        text = PROMPT_DEFINITIONS["explain_item"]["template"]

        self.assertIn("Do not write", text)

    def test_explain_item_substitutes_the_id_into_the_returned_prompt(self):
        result = prompt_get("explain_item", {"id": "t1"})

        self.assertIn("Context: id = t1", result["messages"][0]["content"]["text"])

    def test_explain_item_missing_id_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            prompt_get("explain_item", {})

        self.assertIn("id", str(caught.exception))

    def test_explain_item_missing_id_is_rejected_with_no_arguments_at_all(self):
        with self.assertRaises(ValueError):
            prompt_get("explain_item")

    def test_prompt_get_still_tolerates_prompts_with_no_required_arguments(self):
        # A prompt with only optional (or no) arguments must not regress now
        # that prompt_get() validates required ones.
        for name in ("daily_review", "weekly_review", "inbox_triage"):
            result = prompt_get(name)
            self.assertEqual(1, len(result["messages"]))
        # standup/start_focus each have one optional argument; omitting it
        # must still work exactly as before.
        for name in ("standup", "start_focus"):
            result = prompt_get(name)
            self.assertEqual(1, len(result["messages"]))


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

    def test_prompt_missing_required_argument_becomes_a_jsonrpc_error(self):
        context, _path = self._context()

        response = self._rpc(context, "prompts/get", name="explain_item", arguments={})

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


class GetTemporalContextToolTests(McpTestCase):
    """get_temporal_context (#489): a thin read-only bridge to temporal_context()."""

    TEMPORAL_SAMPLE = (
        "#! timezone: UTC\n"
        "[ ] T Ship_report due:2000-01-01 id:t1\n"
        "[ ] T Review_draft due:2000-01-02 id:t2\n"
    )

    def test_matches_a_direct_call_to_the_canonical_engine(self):
        from lifetxt.temporal_context import temporal_context
        from lifetxt.timezone_policy import today as timezone_today

        context, path = self._context(content=self.TEMPORAL_SAMPLE)
        items = parse_text(self._read(path))[0]
        target = next(item for item in items if item.details.get("id") == ["t1"])
        expected = temporal_context(items, target, timezone_today(), key="id")

        result = call_tool("get_temporal_context", {"id": "t1"}, context)

        result_without_revision = dict(result)
        revision = result_without_revision.pop("revision")
        self.assertEqual(expected, result_without_revision)
        self.assertTrue(revision)
        self.assertEqual("temporal-context-v1", result["schema"])
        self.assertEqual(["t2"], [edge["target_id"] for edge in result["related"]])

    def test_window_and_limit_are_honoured(self):
        context, _path = self._context(content=self.TEMPORAL_SAMPLE)

        narrowed = call_tool("get_temporal_context", {"id": "t1", "window": 0}, context)
        self.assertEqual([], narrowed["related"])

        limited = call_tool("get_temporal_context", {"id": "t1", "limit": 0}, context)
        self.assertEqual([], limited["related"])

    def test_stale_after_reaches_the_engine(self):
        context, _path = self._context(content=self.TEMPORAL_SAMPLE)

        # A stale_after of 0 days makes stale_since apply as soon as there is
        # any recorded activity at all; the fixture items have none, so this
        # only proves the parameter reaches temporal_context() rather than
        # being silently dropped -- both calls stay fact-for-fact identical.
        default = call_tool("get_temporal_context", {"id": "t1"}, context)
        overridden = call_tool(
            "get_temporal_context", {"id": "t1", "stale_after": 0}, context
        )
        self.assertEqual(default["facts"], overridden["facts"])

    def test_unknown_id_fails_deterministically(self):
        context, _path = self._context(content=self.TEMPORAL_SAMPLE)

        with self.assertRaises(ValueError) as caught:
            call_tool("get_temporal_context", {"id": "nope"}, context)

        self.assertIn("nope", str(caught.exception))

    def test_missing_id_fails_deterministically(self):
        context, _path = self._context(content=self.TEMPORAL_SAMPLE)

        with self.assertRaises(ValueError):
            call_tool("get_temporal_context", {}, context)

    def test_ambiguous_id_fails_deterministically(self):
        # A writable context refuses duplicate workspace IDs at startup
        # (assert_unique_workspace_ids), so the only path that reaches
        # find_item_by_id's own ambiguity check is a read-only context.
        context, _path = self._context(
            content=self.TEMPORAL_SAMPLE + "[ ] T Duplicate id:t1\n",
            read_only=True,
        )

        with self.assertRaises(ValueError) as caught:
            call_tool("get_temporal_context", {"id": "t1"}, context)

        self.assertIn("Multiple items", str(caught.exception))

    def test_invalid_bounds_fail_deterministically(self):
        context, _path = self._context(content=self.TEMPORAL_SAMPLE)

        for field in ("window", "limit", "stale_after"):
            with self.assertRaises(ValueError, msg=field) as caught:
                call_tool("get_temporal_context", {"id": "t1", field: "abc"}, context)
            self.assertIn(field, str(caught.exception))

    def test_is_read_only_and_usable_in_read_only_mode(self):
        schemas = {schema["name"]: schema for schema in tool_schemas()}
        self.assertIn("get_temporal_context", READ_ONLY_TOOLS)
        self.assertTrue(schemas["get_temporal_context"]["annotations"]["readOnlyHint"])

        context, _path = self._context(content=self.TEMPORAL_SAMPLE, read_only=True)
        result = call_tool("get_temporal_context", {"id": "t1"}, context)
        self.assertEqual("temporal-context-v1", result["schema"])


class ContextRevisionTests(McpTestCase):
    """revision on bounded MCP context-read tools (#511/#513).

    Each of these tools reuses lifetxt.remote_backend.source_revision()
    unmodified -- the same hash Remote Safe Mode already attaches to every
    resource read -- so a client composing several calls (e.g. the
    explain_item prompt) can detect a workspace change between them.
    """

    TICKET_SAMPLE = SAMPLE + (
        "[ ] T Login_race record:ticket id:BUG-1 tracker:bug "
        "ticket_status:new priority:high severity:major project:work\n"
    )

    def _expected_revision(self, context):
        from lifetxt.remote_backend import source_revision

        return source_revision(context.paths)

    def test_get_command_center_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_command_center", {}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_get_temporal_context_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_temporal_context", {"id": "t1"}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_get_next_actions_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_next_actions", {}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_get_backlinks_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_backlinks", {"id": "t1"}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_get_ticket_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_ticket", {"id": "BUG-1"}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_get_project_carries_a_revision(self):
        context, _path = self._context(content=self.TICKET_SAMPLE)
        result = call_tool("get_project", {"name": "work"}, context)
        self.assertEqual(self._expected_revision(context), result["revision"])

    def test_revision_changes_when_the_source_file_changes(self):
        context, path = self._context(content=self.TICKET_SAMPLE)
        before = call_tool("get_command_center", {}, context)["revision"]

        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T New_task id:t5\n")

        after = call_tool("get_command_center", {}, context)["revision"]
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
