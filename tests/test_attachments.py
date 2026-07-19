"""Tests for file: and dir: attachments."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

from lifetxt import attachments as A
from lifetxt.model import KNOWN_KEYS
from lifetxt.parser import parse_text


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKSLASH = chr(92)


class ValueSyntaxTests(unittest.TestCase):
    def test_path_without_hash(self):
        self.assertEqual(("./docs/spec.md", ""), A.split_value("./docs/spec.md"))

    def test_path_with_hash(self):
        self.assertEqual(("./docs/spec.md", "1a2b3c"), A.split_value("./docs/spec.md#sha256=1a2b3c"))

    def test_last_marker_wins_so_paths_may_contain_hash_signs(self):
        # A "#" is legal in a filename on every platform.
        self.assertEqual(("./a#b/c.md", "ff00"), A.split_value("./a#b/c.md#sha256=ff00"))

    def test_empty_hash_is_treated_as_absent(self):
        self.assertEqual(("./a.md", ""), A.split_value("./a.md#sha256="))

    def test_value_without_a_path_is_rejected(self):
        with self.assertRaises(A.AttachmentError):
            A.split_value("#sha256=abc")

    def test_non_hex_hash_is_rejected(self):
        with self.assertRaises(A.AttachmentError):
            A.split_value("./a.md#sha256=ZZZZ")

    def test_join_round_trips(self):
        value = A.join_value("./docs/spec.md", "1a2b3c")

        self.assertEqual("./docs/spec.md#sha256=1a2b3c", value)
        self.assertEqual(("./docs/spec.md", "1a2b3c"), A.split_value(value))

    def test_join_without_hash_omits_the_marker(self):
        self.assertEqual("./docs/spec.md", A.join_value("./docs/spec.md"))

    def test_attachment_values_parse_as_life_txt(self):
        line = '[ ] T Review id:t1 file:./docs/spec.md#sha256=1a2b3c dir:./assets\n'
        items, diagnostics = parse_text(line)

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(["./docs/spec.md#sha256=1a2b3c"], items[0].details["file"])
        self.assertEqual(["./assets"], items[0].details["dir"])

    def test_quoted_value_supports_spaces(self):
        items, diagnostics = parse_text('[ ] T Review file:"./my docs/spec.md"\n')

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(["./my docs/spec.md"], items[0].details["file"])

    def test_keys_are_registered_so_no_custom_key_warning(self):
        self.assertIn("file", KNOWN_KEYS)
        self.assertIn("dir", KNOWN_KEYS)

        _items, diagnostics = parse_text("[ ] T Review id:t1 file:./a.md dir:./b\n")
        self.assertEqual([], [d for d in diagnostics if d.code == "W106"])


class PathNormalizationTests(unittest.TestCase):
    def test_backslashes_become_forward_slashes(self):
        windows = "." + BACKSLASH + "docs" + BACKSLASH + "spec.md"

        self.assertEqual("./docs/spec.md", A.normalize_stored_path(windows))

    def test_redundant_segments_collapse(self):
        self.assertEqual("./docs/spec.md", A.normalize_stored_path("./docs/./spec.md"))
        self.assertEqual("docs/spec.md", A.normalize_stored_path("docs//spec.md"))

    def test_leading_dot_slash_is_preserved(self):
        # "./x" reads as "next to this file"; keeping it makes intent obvious.
        self.assertEqual("./docs/spec.md", A.normalize_stored_path("./docs/spec.md"))

    def test_parent_segments_are_kept(self):
        self.assertEqual("../sibling/x.md", A.normalize_stored_path("../sibling/x.md"))

    def test_drive_letters_are_kept_but_slashed(self):
        windows = "C:" + BACKSLASH + "Users" + BACKSLASH + "me" + BACKSLASH + "a.md"

        self.assertEqual("C:/Users/me/a.md", A.normalize_stored_path(windows))

    def test_home_shortcut_is_preserved_in_storage(self):
        self.assertEqual("~/notes/plan.md", A.normalize_stored_path("~/notes/plan.md"))

    def test_resolution_is_relative_to_the_life_txt_directory(self):
        base = os.path.join(tempfile.mkdtemp(), "notes")
        os.makedirs(base)

        resolved = A.resolve_raw_path("./spec.md", base)

        self.assertEqual(os.path.normpath(os.path.join(base, "spec.md")), resolved)
        # Explicitly not the process working directory.
        self.assertNotEqual(os.path.normpath(os.path.join(os.getcwd(), "spec.md")), resolved)

    def test_home_shortcut_expands_on_resolution(self):
        resolved = A.resolve_raw_path("~/notes/plan.md", "/somewhere/else")

        self.assertTrue(resolved.startswith(os.path.expanduser("~")))

    def test_absolute_paths_ignore_the_base(self):
        absolute = os.path.abspath(os.path.join(tempfile.mkdtemp(), "a.md"))

        self.assertEqual(
            os.path.normpath(absolute),
            A.resolve_raw_path(absolute.replace(os.sep, "/"), "/unrelated"),
        )

    def test_empty_path_is_rejected(self):
        with self.assertRaises(A.AttachmentError):
            A.resolve_raw_path("", ".")


class PortabilityNoteTests(unittest.TestCase):
    def test_backslash_is_reported(self):
        notes = A.portability_notes("." + BACKSLASH + "a" + BACKSLASH + "b.md")

        self.assertTrue(any("Backslash" in note for note in notes))

    def test_drive_letter_is_reported(self):
        self.assertTrue(any("Drive letters" in n for n in A.portability_notes("C:/Users/me/a.md")))

    def test_unc_path_is_reported(self):
        self.assertTrue(any("UNC" in n for n in A.portability_notes("//server/share/a.md")))

    def test_posix_absolute_path_is_reported(self):
        self.assertTrue(any("Absolute" in n for n in A.portability_notes("/etc/passwd")))

    def test_relative_path_is_clean(self):
        self.assertEqual([], A.portability_notes("./docs/spec.md"))

    def test_home_relative_path_is_clean(self):
        self.assertEqual([], A.portability_notes("~/notes/plan.md"))

    def test_trailing_dot_is_reported_for_windows(self):
        self.assertTrue(any("Trailing" in n for n in A.portability_notes("./docs/spec.")))


class HashingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _write(self, relative, content):
        full = os.path.join(self.tmp, relative.replace("/", os.sep))
        directory = os.path.dirname(full)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(full, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        return full

    def test_file_hash_is_stable_and_short(self):
        target = self._write("a.txt", "hello\n")

        digest = A.hash_file(target)

        self.assertEqual(A.HASH_LENGTH, len(digest))
        self.assertEqual(digest, A.hash_file(target))

    def test_file_hash_changes_with_content(self):
        target = self._write("a.txt", "hello\n")
        before = A.hash_file(target)
        self._write("a.txt", "goodbye\n")

        self.assertNotEqual(before, A.hash_file(target))

    def test_directory_hash_covers_nested_content(self):
        self._write("tree/a.txt", "a")
        self._write("tree/sub/b.txt", "b")
        tree = os.path.join(self.tmp, "tree")
        before = A.hash_directory(tree)

        self._write("tree/sub/b.txt", "edited")

        self.assertNotEqual(before, A.hash_directory(tree))

    def test_directory_hash_notices_added_and_removed_files(self):
        self._write("tree/a.txt", "a")
        tree = os.path.join(self.tmp, "tree")
        before = A.hash_directory(tree)

        added = self._write("tree/b.txt", "b")
        self.assertNotEqual(before, A.hash_directory(tree))

        os.unlink(added)
        self.assertEqual(before, A.hash_directory(tree))

    def test_directory_hash_notices_a_rename(self):
        first = self._write("tree/a.txt", "same")
        tree = os.path.join(self.tmp, "tree")
        before = A.hash_directory(tree)

        os.rename(first, os.path.join(tree, "b.txt"))

        self.assertNotEqual(before, A.hash_directory(tree))

    def test_ignored_directories_do_not_affect_the_hash(self):
        self._write("tree/a.txt", "a")
        tree = os.path.join(self.tmp, "tree")
        before = A.hash_directory(tree)

        self._write("tree/.git/objects/x", "noise")
        self._write("tree/node_modules/pkg/index.js", "noise")

        self.assertEqual(before, A.hash_directory(tree))

    def test_file_count_guard_fails_loudly(self):
        for index in range(4):
            self._write("tree/f%d.txt" % index, "x")

        with self.assertRaises(A.AttachmentError) as caught:
            A.hash_directory(os.path.join(self.tmp, "tree"), max_files=2)

        self.assertIn("max_files", str(caught.exception))

    def test_byte_size_guard_fails_loudly(self):
        self._write("tree/big.txt", "x" * 1000)

        with self.assertRaises(A.AttachmentError) as caught:
            A.hash_directory(os.path.join(self.tmp, "tree"), max_bytes=100)

        self.assertIn("max_bytes", str(caught.exception))

    def test_hash_target_picks_by_what_is_on_disk(self):
        target = self._write("a.txt", "a")
        self._write("tree/b.txt", "b")
        tree = os.path.join(self.tmp, "tree")

        self.assertEqual(A.hash_file(target), A.hash_target(target))
        self.assertEqual(A.hash_directory(tree), A.hash_target(tree))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "docs"))
        os.makedirs(os.path.join(self.tmp, "assets"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v1\n")
        with open(os.path.join(self.tmp, "assets", "a.txt"), "w") as handle:
            handle.write("asset\n")

    def _item(self, line):
        items, _diagnostics = parse_text(line + "\n")
        return items[0]

    def _records(self, line, verify=True):
        return A.attachment_records(self._item(line), base_dir=self.tmp, verify=verify)

    def test_existing_file_without_a_hash_is_unhashed(self):
        record = self._records("[ ] T A file:./docs/spec.md")[0]

        self.assertEqual(A.STATUS_UNHASHED, record["status"])
        self.assertTrue(record["exists"])

    def test_matching_hash_is_ok(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))

        record = self._records("[ ] T A file:./docs/spec.md#sha256=%s" % digest)[0]

        self.assertEqual(A.STATUS_OK, record["status"])

    def test_changed_content_is_detected(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2\n")

        record = self._records("[ ] T A file:./docs/spec.md#sha256=%s" % digest)[0]

        self.assertEqual(A.STATUS_CHANGED, record["status"])
        self.assertNotEqual(record["hash"], record["actual_hash"])

    def test_missing_target_is_detected(self):
        record = self._records("[ ] T A file:./docs/nope.md")[0]

        self.assertEqual(A.STATUS_MISSING, record["status"])
        self.assertFalse(record["exists"])

    def test_file_key_pointing_at_a_directory_is_reported(self):
        record = self._records("[ ] T A file:./assets")[0]

        self.assertEqual(A.STATUS_WRONG_TYPE, record["status"])
        self.assertTrue(any("dir:" in note for note in record["notes"]))

    def test_dir_key_pointing_at_a_file_is_reported(self):
        record = self._records("[ ] T A dir:./docs/spec.md")[0]

        self.assertEqual(A.STATUS_WRONG_TYPE, record["status"])
        self.assertTrue(any("file:" in note for note in record["notes"]))

    def test_malformed_value_is_reported_not_crashed(self):
        record = self._records("[ ] T A file:./x.md#sha256=ZZZ")[0]

        self.assertEqual(A.STATUS_ERROR, record["status"])

    def test_no_verify_skips_hashing(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("changed\n")

        record = self._records("[ ] T A file:./docs/spec.md#sha256=%s" % digest, verify=False)[0]

        self.assertEqual(A.STATUS_OK, record["status"])
        self.assertEqual("", record["actual_hash"])

    def test_multiple_attachments_keep_their_own_hashes(self):
        spec = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))
        line = "[ ] T A file:./docs/spec.md#sha256=%s file:./docs/nope.md#sha256=%s" % (
            spec,
            "0" * 16,
        )

        records = self._records(line)

        self.assertEqual(A.STATUS_OK, records[0]["status"])
        self.assertEqual(A.STATUS_MISSING, records[1]["status"])

    def test_update_writes_hashes_and_normalizes_paths(self):
        item = self._item("[ ] T A file:." + BACKSLASH + "docs" + BACKSLASH + "spec.md")

        changes = A.update_item_hashes(item, base_dir=self.tmp)

        self.assertEqual(1, len(changes))
        value = item.details["file"][0]
        self.assertTrue(value.startswith("./docs/spec.md#sha256="))

    def test_update_leaves_missing_targets_alone(self):
        item = self._item("[ ] T A file:./docs/nope.md")

        changes = A.update_item_hashes(item, base_dir=self.tmp)

        self.assertEqual([], changes)
        self.assertEqual(["./docs/nope.md"], item.details["file"])

    def test_update_is_idempotent(self):
        item = self._item("[ ] T A file:./docs/spec.md")
        A.update_item_hashes(item, base_dir=self.tmp)
        first = item.details["file"][0]

        changes = A.update_item_hashes(item, base_dir=self.tmp)

        self.assertEqual([], changes)
        self.assertEqual(first, item.details["file"][0])

    def test_item_base_dir_prefers_source_then_default(self):
        item = self._item("[ ] T A file:./x.md")
        self.assertEqual(".", A.item_base_dir(item))

        item.source = os.path.join(self.tmp, "life.txt")
        self.assertEqual(os.path.abspath(self.tmp), A.item_base_dir(item))

        other = self._item("[ ] T B file:./x.md")
        self.assertEqual(
            os.path.abspath(self.tmp),
            A.item_base_dir(other, os.path.join(self.tmp, "life.txt")),
        )


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "docs"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v1\n")
        self.life = os.path.join(self.tmp, "life.txt")

    def _diagnostics(self, line, verify=True):
        items, _diagnostics = parse_text(line + "\n")
        for item in items:
            item.source = self.life
        return A.attachment_diagnostics(items, verify=verify)

    def test_missing_file_warns_w401(self):
        codes = [d.code for d in self._diagnostics("[ ] T A file:./docs/nope.md")]

        self.assertIn("W401", codes)

    def test_changed_file_warns_w402(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2\n")

        codes = [d.code for d in self._diagnostics("[ ] T A file:./docs/spec.md#sha256=%s" % digest)]

        self.assertIn("W402", codes)

    def test_wrong_type_warns_w403(self):
        codes = [d.code for d in self._diagnostics("[ ] T A dir:./docs/spec.md")]

        self.assertIn("W403", codes)

    def test_non_portable_path_warns_w404(self):
        line = "[ ] T A file:." + BACKSLASH + "docs" + BACKSLASH + "spec.md"

        codes = [d.code for d in self._diagnostics(line)]

        self.assertIn("W404", codes)

    def test_clean_attachment_produces_no_diagnostics(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))

        diagnostics = self._diagnostics("[ ] T A file:./docs/spec.md#sha256=%s" % digest)

        self.assertEqual([], diagnostics)

    def test_no_verify_skips_hash_diagnostics(self):
        digest = A.hash_file(os.path.join(self.tmp, "docs", "spec.md"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2\n")

        codes = [
            d.code
            for d in self._diagnostics("[ ] T A file:./docs/spec.md#sha256=%s" % digest, verify=False)
        ]

        self.assertNotIn("W402", codes)


def _run_cli(cwd, *args):
    env = dict(os.environ, PYTHONPATH=ROOT_DIR, PYTHONIOENCODING="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "lifetxt"] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env,
    )
    out, _err = process.communicate()
    return out.decode("utf-8", "replace").strip(), process.returncode


class FilesCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "docs"))
        os.makedirs(os.path.join(self.tmp, "assets"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v1\n")
        with open(os.path.join(self.tmp, "assets", "a.txt"), "w") as handle:
            handle.write("asset\n")
        self.life = os.path.join(self.tmp, "life.txt")
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Review id:t1 file:./docs/spec.md\n"
                "[ ] T Assets id:t2 dir:./assets\n"
                "[ ] T Broken id:t3 file:./docs/nope.md\n"
            )

    def _read(self):
        with open(self.life, encoding="utf-8") as handle:
            return handle.read()

    def test_list_reports_each_attachment(self):
        out, code = _run_cli(self.tmp, "files", "life.txt")

        self.assertEqual(0, code, out)
        self.assertIn("unhashed", out)
        self.assertIn("missing", out)

    def test_update_writes_hashes(self):
        out, code = _run_cli(self.tmp, "files", "life.txt", "--update")

        self.assertEqual(0, code, out)
        content = self._read()
        self.assertIn("file:./docs/spec.md#sha256=", content)
        self.assertIn("dir:./assets#sha256=", content)
        # A missing target keeps its bare path.
        self.assertIn("file:./docs/nope.md\n", content)

    def test_update_dry_run_writes_nothing(self):
        before = self._read()

        out, code = _run_cli(self.tmp, "files", "life.txt", "--update", "--dry-run")

        self.assertEqual(0, code)
        self.assertIn("[dry-run]", out)
        self.assertEqual(before, self._read())

    def test_check_exits_non_zero_on_problems(self):
        _out, code = _run_cli(self.tmp, "files", "life.txt", "--check")

        self.assertEqual(1, code)

    def test_check_passes_once_problems_are_resolved(self):
        os.unlink(os.path.join(self.tmp, "life.txt"))
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Review id:t1 file:./docs/spec.md\n")
        _run_cli(self.tmp, "files", "life.txt", "--update")

        _out, code = _run_cli(self.tmp, "files", "life.txt", "--check")

        self.assertEqual(0, code)

    def test_check_detects_an_edit_after_hashing(self):
        _run_cli(self.tmp, "files", "life.txt", "--update")
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2 edited\n")

        out, code = _run_cli(self.tmp, "files", "life.txt", "--check", "--problems")

        self.assertEqual(1, code)
        self.assertIn("changed", out)

    def test_paths_resolve_against_the_life_txt_not_the_shell(self):
        # The whole point of storing relative paths: the answer must not depend
        # on which directory the command was run from.
        from_here, _code = _run_cli(self.tmp, "files", "life.txt", "--format", "json")
        from_elsewhere, _code = _run_cli(ROOT_DIR, "files", self.life, "--format", "json")

        here = json.loads(from_here)
        elsewhere = json.loads(from_elsewhere)
        self.assertEqual(
            [row["status"] for row in here["attachments"]],
            [row["status"] for row in elsewhere["attachments"]],
        )

    def test_json_output_shape(self):
        out, _code = _run_cli(self.tmp, "files", "life.txt", "--format", "json")

        payload = json.loads(out)
        self.assertIn("attachments", payload)
        self.assertEqual(3, payload["count"])
        self.assertEqual(1, payload["problems"])

    def test_id_filter(self):
        out, _code = _run_cli(self.tmp, "files", "life.txt", "--id", "t2", "--format", "json")

        payload = json.loads(out)
        self.assertEqual(1, payload["count"])
        self.assertEqual("dir", payload["attachments"][0]["key"])

    def test_no_attachments_message(self):
        empty = os.path.join(self.tmp, "empty.life.txt")
        with open(empty, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Nothing id:x1\n")

        out, code = _run_cli(self.tmp, "files", "empty.life.txt")

        self.assertEqual(0, code)
        self.assertIn("No file: or dir: attachments", out)

    def test_update_preserves_other_lines_and_comments(self):
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "# a comment\n"
                "[ ] T Review id:t1 file:./docs/spec.md\n"
                "\n"
                "[ ] T Other id:t9\n"
            )

        _run_cli(self.tmp, "files", "life.txt", "--update")

        content = self._read()
        self.assertIn("# a comment", content)
        self.assertIn("[ ] T Other id:t9", content)
        self.assertIn("#sha256=", content)


class CheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "docs"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v1\n")
        self.life = os.path.join(self.tmp, "life.txt")

    def _write(self, content):
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def test_check_reports_a_missing_attachment(self):
        self._write("[ ] T A id:t1 file:./docs/nope.md\n")

        out, _code = _run_cli(self.tmp, "check", "life.txt")

        self.assertIn("W401", out)

    def test_check_does_not_hash_unless_asked(self):
        # A deliberately wrong hash: only --verify-files should notice.
        self._write("[ ] T A id:t1 file:./docs/spec.md#sha256=%s\n" % ("0" * 16))

        without, _code = _run_cli(self.tmp, "check", "life.txt")
        with_verify, _code = _run_cli(self.tmp, "check", "life.txt", "--verify-files")

        self.assertNotIn("W402", without)
        self.assertIn("W402", with_verify)

    def test_no_files_flag_skips_attachment_checks(self):
        self._write("[ ] T A id:t1 file:./docs/nope.md\n")

        out, _code = _run_cli(self.tmp, "check", "life.txt", "--no-files")

        self.assertNotIn("W401", out)

    def test_attachment_keys_do_not_trigger_custom_key_warnings(self):
        self._write("[ ] T A id:t1 file:./docs/spec.md dir:./docs\n")

        out, _code = _run_cli(self.tmp, "check", "life.txt")

        self.assertNotIn("W106", out)

    def test_diagnostics_carry_the_files_category(self):
        self._write("[ ] T A id:t1 file:./docs/nope.md\n")

        out, _code = _run_cli(self.tmp, "check", "life.txt", "--format", "json")

        payload = json.loads(out)
        self.assertEqual("files", payload[0]["category"])

    def test_category_filter_accepts_files(self):
        self._write("[ ] T A id:t1 file:./docs/nope.md\n")

        out, code = _run_cli(self.tmp, "check", "life.txt", "--category", "files")

        self.assertEqual(0, code)
        self.assertIn("W401", out)


class McpAttachmentTests(unittest.TestCase):
    def setUp(self):
        from lifetxt.mcp import McpContext

        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "docs"))
        os.makedirs(os.path.join(self.tmp, "assets"))
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v1\n")
        with open(os.path.join(self.tmp, "assets", "a.txt"), "w") as handle:
            handle.write("asset\n")
        self.life = os.path.join(self.tmp, "life.txt")
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Review id:t1\n[ ] T Assets id:t2\n")
        self.context = McpContext(paths=[self.life], writable_path=self.life, config={})

    def _call(self, name, **args):
        from lifetxt.mcp import call_tool

        return call_tool(name, args, self.context)

    def _read(self):
        with open(self.life, encoding="utf-8") as handle:
            return handle.read()

    def test_attach_file_records_a_hash(self):
        result = self._call("attach_file", id="t1", path="./docs/spec.md")

        self.assertEqual("file", result["key"])
        self.assertIn("#sha256=", result["value"])
        self.assertIn("file:./docs/spec.md#sha256=", self._read())

    def test_attach_directory_uses_the_dir_key(self):
        result = self._call("attach_file", id="t2", path="./assets")

        self.assertEqual("dir", result["key"])
        self.assertIn("dir:./assets#sha256=", self._read())

    def test_attach_normalizes_a_windows_style_path(self):
        windows = "." + BACKSLASH + "docs" + BACKSLASH + "spec.md"

        result = self._call("attach_file", id="t1", path=windows)

        self.assertTrue(result["value"].startswith("./docs/spec.md#sha256="))

    def test_attach_rejects_a_missing_target(self):
        with self.assertRaises(ValueError) as caught:
            self._call("attach_file", id="t1", path="./docs/nope.md")

        self.assertIn("does not exist", str(caught.exception))

    def test_attach_rejects_a_mismatched_key(self):
        with self.assertRaises(ValueError):
            self._call("attach_file", id="t1", path="./assets", key="file")

    def test_reattaching_refreshes_rather_than_duplicates(self):
        self._call("attach_file", id="t1", path="./docs/spec.md")
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2\n")

        self._call("attach_file", id="t1", path="./docs/spec.md")

        self.assertEqual(1, self._read().count("file:./docs/spec.md"))
        self.assertEqual(0, self._call("check_files")["problems"])

    def test_check_files_reports_problems(self):
        self._call("attach_file", id="t1", path="./docs/spec.md")
        with open(os.path.join(self.tmp, "docs", "spec.md"), "w") as handle:
            handle.write("v2 edited\n")

        result = self._call("check_files", problems_only=True)

        self.assertEqual(1, result["problems"])
        self.assertEqual("changed", result["attachments"][0]["status"])

    def test_attach_dry_run_writes_nothing(self):
        before = self._read()

        result = self._call("attach_file", id="t1", path="./docs/spec.md", dry_run=True)

        self.assertFalse(result["applied"])
        self.assertEqual(before, self._read())

    def test_attach_is_blocked_in_read_only_mode(self):
        from lifetxt.mcp import McpContext, call_tool

        context = McpContext(
            paths=[self.life], writable_path=self.life, config={}, read_only=True
        )

        with self.assertRaises(ValueError) as caught:
            call_tool("attach_file", {"id": "t1", "path": "./docs/spec.md"}, context)

        self.assertIn("read-only", str(caught.exception).lower())

    def test_check_files_works_in_read_only_mode(self):
        from lifetxt.mcp import McpContext, call_tool

        self._call("attach_file", id="t1", path="./docs/spec.md")
        context = McpContext(
            paths=[self.life], writable_path=self.life, config={}, read_only=True
        )

        result = call_tool("check_files", {}, context)

        self.assertEqual(0, result["problems"])


class ServeBindDiagnosticTests(unittest.TestCase):
    """`serve` should explain why a port cannot be bound.

    uvicorn reports the OS error only after printing "Application startup
    complete", which reads like success, so the failure is easy to miss.
    """

    def test_free_port_passes_preflight(self):
        import socket

        from lifetxt.cli import _preflight_bind

        # A just-released port can still be unbindable for a moment, and the
        # probe deliberately does not set SO_REUSEADDR on Windows, so try a few
        # candidates rather than asserting on one and racing the OS.
        last_error = None
        for _ in range(5):
            probe = socket.socket()
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.close()
            try:
                _preflight_bind("127.0.0.1", port)
                return
            except ValueError as exc:
                last_error = exc

        self.fail("no free port accepted the preflight check: %s" % last_error)

    def test_port_in_use_is_reported_with_a_suggestion(self):
        import socket

        from lifetxt.cli import _preflight_bind

        holder = socket.socket()
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        self.addCleanup(holder.close)

        with self.assertRaises(ValueError) as caught:
            _preflight_bind("127.0.0.1", port)

        message = str(caught.exception)
        self.assertIn("Cannot bind", message)
        self.assertIn("--port", message)

    def test_windows_reserved_port_message_names_the_real_cause(self):
        from lifetxt.cli import _bind_error_message

        error = OSError(13, "forbidden")
        error.winerror = 10013

        with unittest.mock.patch.object(os, "name", "nt"):
            message = _bind_error_message("127.0.0.1", 8000, error)

        self.assertIn("reserving that port", message)
        self.assertIn("excludedportrange", message)
        # "port in use" advice would send the user down a dead end here.
        self.assertNotIn("Another process", message)

    def test_port_in_use_message_is_distinct(self):
        from lifetxt.cli import _bind_error_message

        error = OSError(98, "in use")
        error.winerror = 10048

        message = _bind_error_message("127.0.0.1", 8000, error)

        self.assertIn("Another process", message)
        self.assertNotIn("reserving that port", message)

    def test_suggestion_is_never_the_port_that_failed(self):
        from lifetxt.cli import _bind_error_message

        for port in (8000, 8080, 8090):
            error = OSError(98, "in use")
            error.winerror = 10048

            message = _bind_error_message("127.0.0.1", port, error)

            hint = [line for line in message.splitlines() if "--port" in line][0]
            self.assertNotIn(str(port), hint, "suggested the port that just failed")

    def test_probe_does_not_reuse_addresses_on_windows(self):
        """Windows SO_REUSEADDR lets a probe bind a port a server already holds.

        Setting it there would make the whole preflight check silently useless
        for the most common failure, a second server on the same port.
        """
        import socket

        from lifetxt.cli import _preflight_bind

        recorded = []

        class RecordingSocket(socket.socket):
            def setsockopt(self, level, option, value):
                recorded.append((level, option, value))
                return super(RecordingSocket, self).setsockopt(level, option, value)

        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
        probe.close()

        with unittest.mock.patch.object(socket, "socket", RecordingSocket):
            with unittest.mock.patch.object(os, "name", "nt"):
                _preflight_bind("127.0.0.1", free_port)

        reuse = [entry for entry in recorded if entry[1] == socket.SO_REUSEADDR]
        self.assertEqual([], reuse, "SO_REUSEADDR must not be set on Windows")

    def test_privileged_port_message_on_posix(self):
        from lifetxt.cli import _bind_error_message

        error = OSError(13, "permission denied")

        with unittest.mock.patch.object(os, "name", "posix"):
            message = _bind_error_message("127.0.0.1", 80, error)

        self.assertIn("elevated privileges", message)


if __name__ == "__main__":
    unittest.main()
