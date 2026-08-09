import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings

import lifetxt
from lifetxt import mcp, mutation, webapp
from lifetxt.mcp import McpContext
from lifetxt.mutation import MutationConflict, MutationOperation, read_text_snapshot
from lifetxt.review import resolve_named_review_range
from lifetxt.surface_runtime import (
    UnsupportedFormatVersion,
    capability_document_for,
    operation_matrix,
    operation_names,
    transaction_scope,
)


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIFT_EXCEPTION_PATH = os.path.join(
    REPO_ROOT,
    ".ai",
    "project",
    "CAPABILITY_DRIFT_EXCEPTIONS.json",
)
CAPABILITY_GATE_FIELDS = (
    "surface",
    "server",
    "capability_version",
    "format_versions",
    "canonical_versions",
    "schema_versions",
    "read_only",
    "authentication",
    "writable_targets",
    "operations",
    "operation_matrix",
    "optional_feature_state",
)


def _load_capability_drift_exceptions(testcase):
    with open(DRIFT_EXCEPTION_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    testcase.assertEqual(1, data.get("schema_version"))
    exceptions = data.get("exceptions")
    testcase.assertIsInstance(exceptions, list)
    for entry in exceptions:
        testcase.assertIsInstance(entry, dict)
        for field in (
            "id",
            "surface",
            "field",
            "operation",
            "reason",
            "owner",
            "removal_condition",
            "tracked_by",
        ):
            testcase.assertTrue(
                entry.get(field),
                "capability drift exception must set %s: %r" % (field, entry),
            )
        testcase.assertRegex(
            entry["tracked_by"],
            r"^https://github\.com/Eruhitsuji/lifetxt/issues/[0-9]+$",
        )
    return exceptions


def _exception_matches(entry, mismatch):
    return (
        entry.get("surface") in ("*", mismatch["surface"])
        and entry.get("field") in ("*", mismatch["field"])
        and entry.get("operation") in ("*", mismatch["operation"])
    )


def _format_mismatch(mismatch):
    surfaces = ",".join(mismatch.get("surfaces") or [mismatch["surface"]])
    return "surface=%s operation=%s field=%s surfaces=%s detail=%s" % (
        mismatch["surface"],
        mismatch["operation"],
        mismatch["field"],
        surfaces,
        mismatch["detail"],
    )


def _assert_no_capability_drift(testcase, mismatches):
    exceptions = _load_capability_drift_exceptions(testcase)
    undocumented = [
        mismatch
        for mismatch in mismatches
        if not any(_exception_matches(entry, mismatch) for entry in exceptions)
    ]
    testcase.assertEqual(
        [],
        undocumented,
        "undocumented capability drift:\n%s"
        % "\n".join(_format_mismatch(row) for row in undocumented),
    )


def _operation_mismatches(surface, actual, expected):
    mismatches = []
    actual_ops = list(actual.get("operations") or [])
    expected_ops = list(expected.get("operations") or operation_names(surface))
    for operation in sorted(set(expected_ops) - set(actual_ops)):
        mismatches.append(
            {
                "surface": surface,
                "operation": operation,
                "field": "operations",
                "surfaces": [surface],
                "detail": "missing from live capability document",
            }
        )
    for operation in sorted(set(actual_ops) - set(expected_ops)):
        mismatches.append(
            {
                "surface": surface,
                "operation": operation,
                "field": "operations",
                "surfaces": [surface],
                "detail": "not listed for this surface in the operation registry",
            }
        )
    if actual_ops == expected_ops:
        return mismatches
    if not mismatches:
        mismatches.append(
            {
                "surface": surface,
                "operation": "*",
                "field": "operations",
                "surfaces": [surface],
                "detail": "operation order differs from the registry",
            }
        )
    return mismatches


def _matrix_mismatches(surface, actual, expected):
    mismatches = []
    actual_rows = {
        row.get("operation"): row
        for row in (actual.get("operation_matrix") or [])
        if isinstance(row, dict)
    }
    expected_rows = {
        row.get("operation"): row
        for row in (expected.get("operation_matrix") or operation_matrix())
        if isinstance(row, dict)
    }
    for operation in sorted(set(expected_rows) - set(actual_rows)):
        mismatches.append(
            {
                "surface": surface,
                "operation": operation,
                "field": "operation_matrix",
                "surfaces": list(expected_rows[operation].get("surfaces") or []),
                "detail": "missing operation_matrix row",
            }
        )
    for operation in sorted(set(actual_rows) - set(expected_rows)):
        mismatches.append(
            {
                "surface": surface,
                "operation": operation,
                "field": "operation_matrix",
                "surfaces": list(actual_rows[operation].get("surfaces") or []),
                "detail": "extra operation_matrix row",
            }
        )
    for operation in sorted(set(expected_rows) & set(actual_rows)):
        if actual_rows[operation] != expected_rows[operation]:
            mismatches.append(
                {
                    "surface": surface,
                    "operation": operation,
                    "field": "operation_matrix",
                    "surfaces": list(expected_rows[operation].get("surfaces") or []),
                    "detail": "row differs from registry: %r != %r"
                    % (actual_rows[operation], expected_rows[operation]),
                }
            )
    return mismatches


def _capability_mismatches(surface, actual, expected):
    mismatches = []
    mismatches.extend(_operation_mismatches(surface, actual, expected))
    mismatches.extend(_matrix_mismatches(surface, actual, expected))
    for field in CAPABILITY_GATE_FIELDS:
        if field in ("operations", "operation_matrix"):
            continue
        if actual.get(field) != expected.get(field):
            mismatches.append(
                {
                    "surface": surface,
                    "operation": "*",
                    "field": field,
                    "surfaces": [surface],
                    "detail": "%r != %r" % (actual.get(field), expected.get(field)),
                }
            )
    return mismatches


def _command_catalog_mismatches(payload):
    from lifetxt.tui_app import COMMANDS, COMMANDS_BY_NAME
    from lifetxt.webapp import WEB_COMMAND_NOTES, WEB_COMMANDS

    mismatches = []
    actual_rows = {
        row.get("name"): row
        for row in payload.get("commands") or []
        if isinstance(row, dict)
    }
    expected_names = [command.name for command in COMMANDS]
    actual_names = list(actual_rows)
    for command in sorted(set(expected_names) - set(actual_names)):
        mismatches.append(
            {
                "surface": "tui",
                "operation": command,
                "field": "command_catalog",
                "surfaces": ["tui", "web"],
                "detail": "TUI command missing from live Web command catalog",
            }
        )
    for command in sorted(set(actual_names) - set(expected_names)):
        mismatches.append(
            {
                "surface": "web",
                "operation": command,
                "field": "command_catalog",
                "surfaces": ["tui", "web"],
                "detail": "Web command catalog row is not in the TUI registry",
            }
        )
    if payload.get("count") != len(COMMANDS):
        mismatches.append(
            {
                "surface": "web",
                "operation": "*",
                "field": "command_catalog",
                "surfaces": ["tui", "web"],
                "detail": "count %r != TUI registry count %r"
                % (payload.get("count"), len(COMMANDS)),
            }
        )
    for command in COMMANDS:
        row = actual_rows.get(command.name)
        if row is None:
            continue
        expected_web = command.name in WEB_COMMANDS
        expected_note = WEB_COMMAND_NOTES.get(command.name, "")
        expected = {
            "name": command.name,
            "alias": command.alias or "",
            "usage": command.usage,
            "summary": command.summary,
            "web": expected_web,
            "note": expected_note,
        }
        if row != expected:
            mismatches.append(
                {
                    "surface": "web",
                    "operation": command.name,
                    "field": "command_catalog",
                    "surfaces": ["tui", "web"],
                    "detail": "%r != %r" % (row, expected),
                }
            )
    for command in sorted(WEB_COMMANDS - set(COMMANDS_BY_NAME)):
        mismatches.append(
            {
                "surface": "web",
                "operation": command,
                "field": "command_catalog",
                "surfaces": ["tui", "web"],
                "detail": "WEB_COMMANDS advertises a command absent from TUI registry",
            }
        )
    for command in sorted(set(WEB_COMMAND_NOTES) - set(COMMANDS_BY_NAME)):
        mismatches.append(
            {
                "surface": "web",
                "operation": command,
                "field": "command_catalog",
                "surfaces": ["tui", "web"],
                "detail": "WEB_COMMAND_NOTES documents a command absent from TUI registry",
            }
        )
    return mismatches


class SurfaceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name="life.txt"):
        return os.path.join(self.temp_dir.name, name)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read(self, path):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            return handle.read()

    def initial_text(self):
        return "#! format_version: 1\n[ ] T Existing id:T-1\n"

    def write_json(self, path, data):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def cli_capabilities(self, config_path):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "--config",
                config_path,
                "capabilities",
                "--pretty",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def public_tool(self, name, arguments, context):
        response = mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            context,
        )
        self.assertNotIn("error", response)
        return response["result"]["structuredContent"]

    def test_transaction_stages_one_commit_and_rejects_stale_revision(self):
        path = self.path()
        self.write(path, self.initial_text())
        snapshot = read_text_snapshot(path)

        with transaction_scope(
            path, snapshot.content_hash, "test.update"
        ) as transaction:
            webapp.write_text(path, transaction.text + "[ ] T Added id:T-2\n")
            self.assertEqual(self.read(path), self.initial_text())
            revision = transaction.commit()

        self.assertIn("Added", self.read(path))
        self.assertEqual(revision, read_text_snapshot(path).content_hash)
        with self.assertRaises(MutationConflict):
            with transaction_scope(path, snapshot.content_hash, "test.stale"):
                pass

    def test_mutation_guard_rejects_unsupported_declared_version(self):
        path = self.path()
        self.write(path, "#! format_version: 2\n[ ] T Future id:T-1\n")
        snapshot = read_text_snapshot(path)
        with self.assertRaises(UnsupportedFormatVersion):
            mutation.write_text(
                path,
                snapshot.text + "[ ] T Unsafe id:T-2\n",
                expected_hash=snapshot.content_hash,
                operation="test.unsupported",
            )
        self.assertNotIn("Unsafe", self.read(path))

    def test_apply_text_mutation_keeps_positional_expected_hash_signature(self):
        path = self.path()
        self.write(path, self.initial_text())
        snapshot = read_text_snapshot(path)
        operation = MutationOperation(
            "test.positional", lambda current: current + "# ok\n"
        )
        result = mutation.apply_text_mutation(path, operation, snapshot.content_hash)
        self.assertTrue(result.changed)
        self.assertTrue(self.read(path).endswith("# ok\n"))

    def test_registry_capability_matrix_is_honest_about_partial_operations(self):
        matrix = {row["operation"]: row for row in operation_matrix()}
        self.assertTrue(matrix["create"]["revision_required"])
        self.assertTrue(matrix["acknowledge"]["revision_required"])
        self.assertFalse(matrix["timer"]["revision_required"])
        self.assertFalse(matrix["attachments"]["revision_required"])
        document = capability_document_for("mcp", writable_targets=["life.txt"])
        self.assertEqual(document["surface"], "mcp")
        self.assertIn("capabilities", document["operations"])
        self.assertEqual(document["operation_matrix"], operation_matrix())

    def test_cli_mcp_and_resource_capabilities_match_registry_gate(self):
        from lifetxt.config import load_config

        path = self.path()
        self.write(path, self.initial_text())
        config_path = self.path("config.json")
        self.write_json(
            config_path,
            {
                "config_version": 1,
                "git": {"enable_api": True},
                "timer": {"state_file": self.path("timer.json")},
            },
        )
        config = load_config(config_path)
        context = McpContext(paths=[path], writable_path=path, config=config)

        cli_capabilities = self.cli_capabilities(config_path)
        self.assertEqual("lifetxt", cli_capabilities["server"]["package"])
        self.assertEqual(lifetxt.__version__, cli_capabilities["server"]["version"])
        for feature in ("web", "tui", "mcp", "git", "smtp"):
            state = cli_capabilities["optional_feature_state"][feature]
            self.assertIn("installed", state)
            self.assertIn("configured", state)
        mcp_capabilities = mcp.call_tool("get_capabilities", {}, context)
        resource = mcp.resource_read(context, "lifetxt://capabilities")
        mcp_resource = json.loads(resource["contents"][0]["text"])
        self.assertEqual(mcp_capabilities, mcp_resource)

        mismatches = []
        mismatches.extend(
            _capability_mismatches(
                "cli",
                cli_capabilities,
                capability_document_for(
                    "cli",
                    authentication="token",
                    writable_targets=[],
                    config=config,
                ),
            )
        )
        mismatches.extend(
            _capability_mismatches(
                "mcp",
                mcp_capabilities,
                capability_document_for(
                    "mcp",
                    authentication="stdio",
                    writable_targets=[path],
                    config=config,
                ),
            )
        )
        _assert_no_capability_drift(self, mismatches)

    def test_named_review_ranges_share_one_deterministic_resolver(self):
        today = datetime.date(2026, 7, 23)
        self.assertEqual(
            resolve_named_review_range("last-week", today=today),
            (datetime.date(2026, 7, 13), datetime.date(2026, 7, 19)),
        )
        self.assertEqual(
            resolve_named_review_range("last-month", today=today),
            (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30)),
        )
        self.assertEqual(
            resolve_named_review_range("year", year=2025, today=today),
            (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)),
        )
        with self.assertRaises(ValueError):
            resolve_named_review_range("quarter", today=today)

    def test_mcp_write_schemas_require_exact_file_revision(self):
        schemas = {schema["name"]: schema for schema in mcp.tool_schemas()}
        for name in (
            "create_item",
            "update_item",
            "mark_done",
            "complete_item",
            "delete_item",
            "ack_message",
            "snooze_message",
            "set_status",
            "capture_item",
        ):
            self.assertIn(
                "expected_file_hash", schemas[name]["inputSchema"]["properties"]
            )
            self.assertIn(
                "expected_file_hash", schemas[name]["inputSchema"]["required"]
            )
        self.assertTrue(schemas["get_capabilities"]["annotations"]["readOnlyHint"])
        self.assertIn("range", schemas["get_review"]["inputSchema"]["properties"])

    def test_mcp_jsonrpc_create_requires_revision_and_rejects_stale(self):
        path = self.path()
        self.write(path, self.initial_text())
        context = McpContext(paths=[path], writable_path=path)

        missing = self.public_tool(
            "create_item",
            {"type": "T", "title": "No revision", "details": {}},
            context,
        )
        self.assertEqual(missing["error"], "PRECONDITION_REQUIRED")
        self.assertNotIn("No revision", self.read(path))

        revision = read_text_snapshot(path).content_hash
        created = self.public_tool(
            "create_item",
            {
                "type": "T",
                "title": "Created safely",
                "details": {},
                "expected_file_hash": revision,
            },
            context,
        )
        self.assertNotIn("error", created)
        self.assertEqual(created["revision"], read_text_snapshot(path).content_hash)
        self.assertIn("Created safely", self.read(path))

        stale = self.public_tool(
            "create_item",
            {
                "type": "T",
                "title": "Stale",
                "details": {},
                "expected_file_hash": revision,
            },
            context,
        )
        self.assertEqual(stale["error"], "CONFLICT")
        self.assertEqual(stale["expected_revision"], revision)
        self.assertNotIn("Stale", self.read(path))

    def test_direct_mcp_helper_remains_backward_compatible(self):
        path = self.path()
        self.write(path, self.initial_text())
        context = McpContext(paths=[path], writable_path=path)
        result = mcp.call_tool(
            "create_item",
            {"type": "T", "title": "Embedded helper", "details": {}},
            context,
        )
        self.assertIn("item", result)
        self.assertIn("Embedded helper", self.read(path))

    def test_mcp_repeat_completion_is_one_public_transaction(self):
        path = self.path()
        self.write(
            path,
            "#! format_version: 1\n"
            "[ ] T Weekly due:2026-07-23 repeat:weekly id:T-weekly\n",
        )
        context = McpContext(paths=[path], writable_path=path)
        revision = read_text_snapshot(path).content_hash
        result = self.public_tool(
            "complete_item",
            {
                "id": "T-weekly",
                "date": "2026-07-23",
                "expected_file_hash": revision,
            },
            context,
        )
        self.assertNotIn("error", result)
        items, diagnostics = lifetxt.parse_text(self.read(path))
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].status, "[x]")
        self.assertEqual(items[1].status, "[ ]")
        self.assertEqual(result["revision"], read_text_snapshot(path).content_hash)

    def test_mcp_capability_tool_resource_and_named_review(self):
        path = self.path()
        self.write(path, self.initial_text())
        context = McpContext(paths=[path], writable_path=path)
        capabilities = mcp.call_tool("get_capabilities", {}, context)
        self.assertEqual(capabilities["surface"], "mcp")
        self.assertEqual(
            capabilities["revision"], read_text_snapshot(path).content_hash
        )

        resources = {row["uri"]: row for row in mcp.resource_list(context)}
        self.assertIn("lifetxt://capabilities", resources)
        content = mcp.resource_read(context, "lifetxt://capabilities")
        parsed = json.loads(content["contents"][0]["text"])
        self.assertEqual(
            parsed["capability_version"], capabilities["capability_version"]
        )

        review = mcp.call_tool("get_review", {"range": "year", "year": 2026}, context)
        self.assertEqual(review["from"], "2026-01-01")
        self.assertEqual(review["to"], "2026-12-31")


@unittest.skipUnless(
    __import__("importlib").util.find_spec("fastapi") is not None
    and __import__("importlib").util.find_spec("httpx") is not None,
    "Web test dependencies are not installed.",
)
class WebSurfaceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write("#! format_version: 1\n[ ] T Existing id:T-1\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def client(self):
        from fastapi.testclient import TestClient

        return TestClient(webapp.create_app(paths=self.path, writable_path=self.path))

    def test_web_strict_session_precondition_conflict_and_browser_bridge(self):
        client = self.client()
        listing = client.get("/api/items")
        self.assertEqual(listing.status_code, 200)
        revision = listing.headers.get("etag")
        self.assertTrue(revision)

        discovered = client.get("/api/revision")
        self.assertEqual(discovered.status_code, 200)
        self.assertEqual(discovered.json()["revision"], revision.strip('"'))

        missing = client.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Missing", "details": {}},
        )
        self.assertEqual(missing.status_code, 428)
        self.assertEqual(missing.json()["error"], "PRECONDITION_REQUIRED")

        created = client.post(
            "/api/items",
            headers={"If-Match": revision},
            json={"status": "[ ]", "type": "T", "title": "Web safe", "details": {}},
        )
        self.assertEqual(created.status_code, 201)
        next_revision = created.headers.get("etag")
        self.assertNotEqual(next_revision, revision)

        stale = client.post(
            "/api/items",
            headers={"If-Match": revision},
            json={"status": "[ ]", "type": "T", "title": "Web stale", "details": {}},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["error"], "CONFLICT")

        page = client.get("/")
        self.assertIn("lifetxt-revision-contract-v1", page.text)
        capabilities = client.get("/api/capabilities")
        self.assertEqual(capabilities.json()["surface"], "web")
        self.assertEqual(capabilities.headers.get("etag"), next_revision)

    def test_web_capabilities_match_registry_gate(self):
        client = self.client()
        capabilities = client.get("/api/capabilities").json()
        expected = capability_document_for(
            "web",
            read_only=False,
            authentication="none",
            writable_targets=[self.path],
            config={},
        )
        _assert_no_capability_drift(
            self,
            _capability_mismatches("web", capabilities, expected),
        )

    def test_live_web_command_catalog_matches_tui_registry_gate(self):
        client = self.client()
        payload = client.get("/api/commands").json()

        _assert_no_capability_drift(self, _command_catalog_mismatches(payload))

    def test_legacy_web_write_is_allowed_with_visible_warning(self):
        client = self.client()
        response = client.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Legacy", "details": {}},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("Legacy write", response.headers.get("warning", ""))

    def test_web_repeat_completion_commits_update_and_next_item_together(self):
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(
                "#! format_version: 1\n"
                "[ ] T Weekly due:2026-07-23 repeat:weekly id:T-weekly\n"
            )
        client = self.client()
        revision = client.get("/api/items").headers["etag"]
        response = client.post(
            "/api/items/id/T-weekly/complete",
            headers={"If-Match": revision},
            json={"date": "2026-07-23"},
        )
        self.assertEqual(response.status_code, 200)
        with open(self.path, "r", encoding="utf-8") as handle:
            items, diagnostics = lifetxt.parse_text(handle.read())
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].status, "[x]")
        self.assertEqual(items[1].status, "[ ]")

    def test_web_named_review_range_is_rewritten_before_route_binding(self):
        client = self.client()
        response = client.get("/api/review?range=year&year=2025")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["from"], "2025-01-01")
        self.assertEqual(response.json()["to"], "2025-12-31")

    def test_serve_target_rejects_windows_drive_relative_write_path(self):
        with self.assertRaises(ValueError):
            webapp.create_app(paths=[self.path], writable_path="C:relative\\life.txt")

    def test_serve_target_warns_when_read_and_write_targets_differ(self):
        other = os.path.join(self.temp_dir.name, "other.txt")
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            app = webapp.create_app(paths=[self.path], writable_path=other)
        self.assertTrue(captured)
        self.assertTrue(app.state.serve_target_diagnostic["mismatch"])


_TUI_DOC_ROW = re.compile(r"^\|\s*`/(?P<name>[a-z_]+)(?:\s+(?P<usage>[^`]*))?`\s*\|")


def _tui_doc_commands():
    """Parse the '#### Commands' section of docs/en/cli.md into name->usage.

    Mirrors lifetxt.tui_app.help_entries()'s own "/name usage" string shape so
    the two can be compared directly without a second parsing convention.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "docs", "en", "cli.md")
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("#### Commands")
    end = text.index("#### Choosing an editor", start)
    section = text[start:end]

    commands = {}
    for line in section.splitlines():
        match = _TUI_DOC_ROW.match(line.strip())
        if not match:
            continue
        name = match.group("name")
        usage = (match.group("usage") or "").strip().replace("\\|", "|")
        commands[name] = usage
    return commands


class TuiDocumentationDriftTests(unittest.TestCase):
    """Covers #G: docs/en/cli.md's TUI command tables must track tui_app.COMMANDS.

    No automated check enforced this before -- the two were kept in sync by
    hand, which drifts silently on the next command addition/change.
    """

    def test_docs_command_tables_match_the_tui_command_registry(self):
        from lifetxt.tui_app import COMMANDS

        documented = _tui_doc_commands()
        registered = {command.name: command.usage for command in COMMANDS}

        missing_from_docs = sorted(set(registered) - set(documented))
        stale_in_docs = sorted(set(documented) - set(registered))
        self.assertEqual(
            [], missing_from_docs, "TUI commands missing from docs/en/cli.md"
        )
        self.assertEqual(
            [],
            stale_in_docs,
            "docs/en/cli.md documents commands no longer in tui_app.COMMANDS",
        )

        usage_mismatches = [
            "/%s: docs usage %r != registry usage %r"
            % (name, documented[name], registered[name])
            for name in sorted(set(documented) & set(registered))
            if documented[name] != registered[name]
        ]
        self.assertEqual([], usage_mismatches)


if __name__ == "__main__":
    unittest.main()
