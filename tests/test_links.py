import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.parser import parse_text
from lifetxt.links import (
    backlink_records,
    dependency_blocker_records,
    dependency_blockers_by_item,
    dependency_chain_records,
    dependency_chains_to_dot,
    dependency_chains_to_mermaid,
    format_dependency_chain,
    format_link_table,
    link_records,
    links_to_dot,
    links_to_json,
    links_to_jsonl,
    links_to_mermaid,
    reference_diagnostics,
)


class ReferenceKeysCoverageTests(unittest.TestCase):
    """duplicate_of/replaced_by must get the same reference-graph treatment
    as the other REFERENCE_KEYS relations (#161)."""

    def test_duplicate_of_missing_target_warns(self):
        _items, diagnostics = parse_text(
            "[ ] T Original id:orig duplicate_of:nonexistent\n"
        )
        self.assertTrue(any(d.code == "W215" for d in diagnostics))

    def test_replaced_by_missing_target_warns(self):
        _items, diagnostics = parse_text("[ ] T Old id:old replaced_by:nonexistent\n")
        self.assertTrue(any(d.code == "W215" for d in diagnostics))

    def test_duplicate_of_self_reference_warns(self):
        _items, diagnostics = parse_text("[ ] T Self id:s duplicate_of:s\n")
        self.assertTrue(any(d.code == "W216" for d in diagnostics))

    def test_replaced_by_self_reference_warns(self):
        _items, diagnostics = parse_text("[ ] T Self id:s replaced_by:s\n")
        self.assertTrue(any(d.code == "W216" for d in diagnostics))

    def test_duplicate_of_ambiguous_target_warns(self):
        text = (
            "[ ] T First id:dup\n"
            "[ ] T Second id:dup\n"
            "[ ] T Reporter id:r duplicate_of:dup\n"
        )
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W218" for d in diagnostics))

    def test_duplicate_of_and_replaced_by_appear_in_link_records(self):
        text = (
            "[ ] T Original id:orig\n"
            "[x] T Copy id:copy duplicate_of:orig\n"
            "[ ] T Old id:old\n"
            "[ ] T New id:new replaced_by:old\n"
        )
        items, _diagnostics = parse_text(text)
        records = link_records(items)
        compact = [
            (r["relation"], r["source_id"], r["target_id"], r["status"])
            for r in records
        ]
        self.assertIn(("duplicate_of", "copy", "orig", "ok"), compact)
        self.assertIn(("replaced_by", "new", "old", "ok"), compact)

    def test_backlink_records_surfaces_duplicate_of_and_replaced_by(self):
        text = (
            "[ ] T Original id:orig\n"
            "[x] T Copy id:copy duplicate_of:orig\n"
            "[ ] T New id:new replaced_by:orig\n"
        )
        items, _diagnostics = parse_text(text)
        records = backlink_records(items, "orig")
        relations = {r["relation"] for r in records}
        self.assertIn("duplicate_of", relations)
        self.assertIn("replaced_by", relations)

    def test_reference_diagnostics_directly_covers_duplicate_of(self):
        text = "[ ] T Reporter id:r duplicate_of:nope\n"
        items, _diagnostics = parse_text(text)
        diagnostics = reference_diagnostics(items)
        self.assertTrue(any(d.code == "W215" for d in diagnostics))


class ExtendedCycleDetectionTests(unittest.TestCase):
    """Cycle detection beyond parent: (#162)."""

    def test_parent_cycle_message_is_unchanged(self):
        _items, diagnostics = parse_text(
            "[ ] T First id:a parent:b\n[ ] T Second id:b parent:a\n"
        )
        matches = [d for d in diagnostics if d.code == "W217"]
        self.assertEqual(1, len(matches))
        self.assertEqual(
            "Parent reference cycle detected: a -> b -> a.", matches[0].message
        )

    def test_depends_on_cycle_is_detected(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W227" for d in diagnostics))

    def test_mixed_depends_on_and_blocks_cycle_is_detected(self):
        # a depends_on b (a waits on b); b blocks a (a waits on b, same edge) --
        # add a second hop so the cycle is genuinely mixed: a depends_on b,
        # c blocks a (a waits on c), and c depends_on a closes the loop.
        text = (
            "[ ] T A id:a depends_on:b\n"
            "[ ] T B id:b\n"
            "[ ] T C id:c depends_on:a blocks:b\n"
        )
        _items, diagnostics = parse_text(text)
        # a -> b (depends_on), b -> c (c blocks b means b waits on c), c -> a (depends_on)
        self.assertTrue(any(d.code == "W227" for d in diagnostics))

    def test_non_cyclic_dependency_chain_has_no_cycle_warning(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:c\n[ ] T C id:c\n"
        _items, diagnostics = parse_text(text)
        self.assertFalse(any(d.code == "W227" for d in diagnostics))

    def test_duplicate_of_cycle_is_detected(self):
        text = "[ ] T A id:a duplicate_of:b\n[ ] T B id:b duplicate_of:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W228" for d in diagnostics))

    def test_replaced_by_cycle_is_detected(self):
        text = "[ ] T A id:a replaced_by:b\n[ ] T B id:b replaced_by:a\n"
        _items, diagnostics = parse_text(text)
        self.assertTrue(any(d.code == "W229" for d in diagnostics))

    def test_duplicate_of_and_replaced_by_cycles_are_independent(self):
        # A duplicate_of B, B replaced_by A -- not a cycle in either single
        # relation, so neither W228 nor W229 should fire.
        text = "[ ] T A id:a duplicate_of:b\n[ ] T B id:b replaced_by:a\n"
        _items, diagnostics = parse_text(text)
        self.assertFalse(any(d.code == "W228" for d in diagnostics))
        self.assertFalse(any(d.code == "W229" for d in diagnostics))

    def test_new_cycle_codes_are_categorized_as_reference(self):
        from lifetxt.diagnostic_contract import diagnostic_category
        from lifetxt.model import Diagnostic

        for code in ("W227", "W228", "W229"):
            diagnostic = Diagnostic("warning", code, "x")
            self.assertEqual("reference", diagnostic_category(diagnostic))


class DependencyBlockerRecordsTests(unittest.TestCase):
    """dependency_blocker_records / dependency_blockers_by_item (#163)."""

    def test_open_depends_on_open_produces_a_blocker_record(self):
        text = "[ ] T Setup id:setup\n[ ] T Work id:work depends_on:setup\n"
        items, _diagnostics = parse_text(text)
        records = dependency_blocker_records(items)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("depends_on", record["relation"])
        self.assertEqual("work", record["blocked_id"])
        self.assertEqual("setup", record["blocker_id"])

    def test_depends_on_a_done_item_produces_no_blocker_record(self):
        text = "[x] T Setup id:setup\n[ ] T Work id:work depends_on:setup\n"
        items, _diagnostics = parse_text(text)
        self.assertEqual([], dependency_blocker_records(items))

    def test_done_item_depends_on_open_item_produces_no_blocker_record(self):
        # dependency_blocker_records only reports open+open pairs; the done-
        # but-still-blocked case is a separate diagnostic (W224), not this API.
        text = "[ ] T Setup id:setup\n[x] T Work id:work depends_on:setup\n"
        items, _diagnostics = parse_text(text)
        self.assertEqual([], dependency_blocker_records(items))

    def test_open_blocks_open_produces_a_blocker_record_with_reversed_roles(self):
        text = "[ ] T Gate id:gate blocks:work\n[ ] T Work id:work\n"
        items, _diagnostics = parse_text(text)
        records = dependency_blocker_records(items)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("blocks", record["relation"])
        self.assertEqual("work", record["blocked_id"])
        self.assertEqual("gate", record["blocker_id"])

    def test_missing_and_ambiguous_targets_are_skipped_without_raising(self):
        text = (
            "[ ] T Work id:work depends_on:nope\n"
            "[ ] T Dup id:dup\n"
            "[ ] T Dup2 id:dup\n"
            "[ ] T Other id:other depends_on:dup\n"
        )
        items, _diagnostics = parse_text(text)
        # Must not raise; both references are unresolvable (missing / ambiguous).
        self.assertEqual([], dependency_blocker_records(items))

    def test_dependency_blockers_by_item_groups_by_blocked_item(self):
        text = (
            "[ ] T Setup id:setup\n"
            "[ ] T Gate id:gate\n"
            "[ ] T Work id:work depends_on:setup depends_on:gate\n"
        )
        items, _diagnostics = parse_text(text)
        grouped = dependency_blockers_by_item(items)
        self.assertEqual(1, len(grouped))
        (blockers,) = grouped.values()
        self.assertEqual({"setup", "gate"}, {b["id"] for b in blockers})


class DependencyChainRecordsTests(unittest.TestCase):
    """dependency_chain_records (#163)."""

    def test_root_id_resolves_to_a_single_node_tree(self):
        text = "[ ] T Setup id:setup\n[ ] T Work id:work depends_on:setup\n"
        items, _diagnostics = parse_text(text)
        chains = dependency_chain_records(items, root_id="work")
        self.assertEqual(1, len(chains))
        root = chains[0]
        self.assertEqual("work", root["id"])
        self.assertEqual(1, len(root["deps"]))
        self.assertEqual("setup", root["deps"][0]["id"])

    def test_missing_root_id_returns_a_missing_placeholder(self):
        items, _diagnostics = parse_text("[ ] T Work id:work\n")
        chains = dependency_chain_records(items, root_id="nope")
        self.assertEqual(1, len(chains))
        self.assertEqual("missing", chains[0]["reference_status"])

    def test_ambiguous_root_id_returns_an_ambiguous_placeholder(self):
        text = "[ ] T A id:dup\n[ ] T B id:dup\n"
        items, _diagnostics = parse_text(text)
        chains = dependency_chain_records(items, root_id="dup")
        self.assertEqual(1, len(chains))
        self.assertEqual("ambiguous", chains[0]["reference_status"])

    def test_blocked_only_excludes_items_without_an_open_direct_blocker(self):
        text = (
            "[ ] T Setup id:setup\n"
            "[x] T Done_Setup id:done_setup\n"
            "[ ] T Blocked id:blocked depends_on:setup\n"
            "[ ] T Unblocked id:unblocked depends_on:done_setup\n"
        )
        items, _diagnostics = parse_text(text)
        chains = dependency_chain_records(items, blocked_only=True)
        ids = {chain["id"] for chain in chains}
        self.assertIn("blocked", ids)
        self.assertNotIn("unblocked", ids)

    def test_max_depth_truncates_and_marks_truncated(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:c\n[ ] T C id:c\n"
        items, _diagnostics = parse_text(text)
        chains = dependency_chain_records(items, root_id="a", max_depth=1)
        root = chains[0]
        self.assertEqual(1, len(root["deps"]))
        b_node = root["deps"][0]
        self.assertEqual([], b_node["deps"])
        self.assertTrue(b_node.get("truncated"))

    def test_cycle_is_flagged_without_infinite_recursion(self):
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:a\n"
        items, _diagnostics = parse_text(text)
        chains = dependency_chain_records(items, root_id="a")
        root = chains[0]
        b_node = root["deps"][0]
        a_again = b_node["deps"][0]
        self.assertTrue(a_again.get("cycle"))
        self.assertEqual([], a_again["deps"])

    def test_missing_dependency_target_is_a_placeholder_node(self):
        items, _diagnostics = parse_text("[ ] T Work id:work depends_on:nope\n")
        chains = dependency_chain_records(items, root_id="work")
        dep = chains[0]["deps"][0]
        self.assertEqual("missing", dep["reference_status"])
        self.assertEqual("nope", dep["id"])


class DependencyChainFormattingTests(unittest.TestCase):
    """format_dependency_chain / dependency_chains_to_mermaid/dot (#163)."""

    def _chain(self):
        text = "[ ] T Setup id:setup\n[x] T Work id:work depends_on:setup\n"
        items, _diagnostics = parse_text(text)
        return dependency_chain_records(items, root_id="work")

    def test_format_dependency_chain_indents_and_shows_relation(self):
        text = format_dependency_chain(self._chain())
        lines = text.splitlines()
        self.assertEqual(2, len(lines))
        self.assertTrue(lines[0].startswith("work "))
        self.assertTrue(lines[1].startswith("  setup"))
        self.assertIn("(depends_on)", lines[1])

    def test_format_dependency_chain_empty_input(self):
        self.assertEqual("No dependency chains found.\n", format_dependency_chain([]))

    def test_dependency_chains_to_mermaid_includes_nodes_and_edge(self):
        text = dependency_chains_to_mermaid(self._chain())
        self.assertTrue(text.startswith("graph LR"))
        self.assertIn("work", text)
        self.assertIn("setup", text)
        self.assertIn("-- depends_on -->", text)

    def test_dependency_chains_to_mermaid_empty_input(self):
        text = dependency_chains_to_mermaid([])
        self.assertEqual("graph LR\n", text)

    def test_dependency_chains_to_dot_includes_nodes_and_edge(self):
        text = dependency_chains_to_dot(self._chain())
        self.assertTrue(text.startswith("digraph deps {"))
        self.assertIn("->", text)
        self.assertIn("[label=depends_on]", text)

    def test_dependency_chains_to_dot_empty_input(self):
        text = dependency_chains_to_dot([])
        self.assertEqual("digraph deps {\n}\n", text)


class LinkGraphExportTests(unittest.TestCase):
    """links_to_mermaid/dot/json/jsonl, format_link_table (#163)."""

    def _records(self):
        text = "[ ] T Root id:root\n[x] T Child id:child parent:root\n"
        items, _diagnostics = parse_text(text)
        return link_records(items, relations=["parent"])

    def test_format_link_table_has_header_and_row(self):
        text = format_link_table(self._records())
        lines = text.splitlines()
        self.assertIn("relation", lines[0])
        self.assertTrue(any("parent" in line for line in lines[1:]))

    def test_format_link_table_empty_input(self):
        self.assertEqual("No links found.\n", format_link_table([]))

    def test_links_to_mermaid_includes_nodes_and_done_class(self):
        text = links_to_mermaid(self._records())
        self.assertTrue(text.startswith("graph LR"))
        self.assertIn("root", text)
        self.assertIn("child", text)
        self.assertIn(":::done", text)
        self.assertIn("classDef done", text)

    def test_links_to_mermaid_empty_input(self):
        self.assertEqual("graph LR\n", links_to_mermaid([]))

    def test_links_to_dot_includes_nodes_and_style(self):
        text = links_to_dot(self._records())
        self.assertTrue(text.startswith("digraph links {"))
        self.assertIn("style=dashed", text)

    def test_links_to_dot_empty_input(self):
        self.assertEqual("digraph links {\n}\n", links_to_dot([]))

    def test_links_to_json_round_trips(self):
        records = self._records()
        parsed = json.loads(links_to_json(records))
        self.assertEqual(records, parsed)

    def test_links_to_json_pretty_is_indented(self):
        pretty = links_to_json(self._records(), pretty=True)
        self.assertIn("\n", pretty)
        self.assertEqual(json.loads(pretty), json.loads(links_to_json(self._records())))

    def test_links_to_jsonl_one_record_per_line(self):
        records = self._records()
        lines = links_to_jsonl(records).splitlines()
        self.assertEqual(len(records), len(lines))
        for line, record in zip(lines, records):
            self.assertEqual(record, json.loads(line))


class CrossFileLinkIntegrityTests(unittest.TestCase):
    """Cross-file parent/link resolution, cycle detection, and source-metadata
    preservation (#421, the remaining scope from #322 after #415/#416/#417
    shipped).

    `link_records`/`reference_diagnostics` operate on the merged item list
    the CLI already builds from every loaded file (`cli.py::_parse_life_inputs`
    calls `_set_source` per file, then extends one combined `items` list), so
    they have no per-file boundary to begin with -- verified live against two
    real files via `lifetxt links` before writing these tests. These tests
    exercise the same mechanism directly against two independently-parsed
    item lists carrying distinct `.source` values, matching how the CLI
    actually tags multi-file input.
    """

    def _two_files(self, text_a, text_b, source_a="a.life.txt", source_b="b.life.txt"):
        items_a, _diagnostics_a = parse_text(text_a)
        items_b, _diagnostics_b = parse_text(text_b)
        for item in items_a:
            item.source = source_a
        for item in items_b:
            item.source = source_b
        return items_a + items_b

    def test_cross_file_parent_reference_resolves_and_preserves_source(self):
        items = self._two_files(
            "[ ] T Parent id:parent\n",
            "[ ] T Child id:child parent:parent\n",
        )
        records = link_records(items, relations=["parent"])
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("ok", record["status"])
        self.assertEqual("child", record["source_id"])
        self.assertEqual("parent", record["target_id"])
        # The explicit source-metadata-preservation assertion #421 asks for:
        # each side of the cross-file link carries its own originating file,
        # not the other side's or a shared/blank value.
        self.assertEqual("b.life.txt:1", record["source_location"])
        self.assertEqual("a.life.txt:1", record["target_location"])

    def test_cross_file_parent_cycle_is_detected(self):
        items = self._two_files(
            "[ ] T A id:a parent:b\n",
            "[ ] T B id:b parent:a\n",
        )
        diagnostics = reference_diagnostics(items)
        matches = [d for d in diagnostics if d.code == "W217"]
        self.assertEqual(1, len(matches))
        self.assertIn("a -> b -> a", matches[0].message)

    def test_cross_file_depends_on_cycle_is_detected(self):
        items = self._two_files(
            "[ ] T A id:a depends_on:b\n",
            "[ ] T B id:b depends_on:a\n",
        )
        diagnostics = reference_diagnostics(items)
        self.assertTrue(any(d.code == "W227" for d in diagnostics))

    def test_cross_file_missing_reference_names_the_referencing_source(self):
        items = self._two_files(
            "[ ] T A id:a\n",
            "[ ] T B id:b depends_on:nope\n",
        )
        diagnostics = reference_diagnostics(items)
        matches = [d for d in diagnostics if d.code == "W215"]
        self.assertEqual(1, len(matches))
        self.assertEqual("b.life.txt", matches[0].source)


class TicketEventCrossFileResolutionTests(unittest.TestCase):
    """Direct (non-archive) ticket/event cross-file `parent:` resolution
    (#421's last remaining criterion). `tests/test_project_archive.py`
    already covers this relationship, but only inside the `project archive`
    workflow; this drives an ordinary multi-file `lifetxt links` invocation
    over two real files with no archiving involved, matching the live CLI
    verification done before writing this test.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lifetxt-links-")
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_ticket_event_parent_resolves_across_files_without_archive(self):
        tickets = self.write(
            "tickets.life.txt",
            "[ ] T Fix_the_bug id:TK-1 tracker:bug project:Web\n",
        )
        history = self.write(
            "history.life.txt",
            "[N] N Investigated_root_cause record:ticket_event id:EV-1 "
            "parent:TK-1 event:comment author:local at:2026-01-01T00:00:00Z "
            "sequence:1 transaction:tx1 ticket_revision:1\n",
        )

        code, stdout, stderr = self.run_command(
            ["links", tickets, history, "--relation", "parent", "--format", "json"]
        )

        self.assertEqual(0, code, stderr)
        records = json.loads(stdout)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("parent", record["relation"])
        self.assertEqual("ok", record["status"])
        self.assertEqual("EV-1", record["source_id"])
        self.assertEqual("TK-1", record["target_id"])
        self.assertTrue(record["source_location"].endswith("history.life.txt:1"))
        self.assertTrue(record["target_location"].endswith("tickets.life.txt:1"))


if __name__ == "__main__":
    unittest.main()
