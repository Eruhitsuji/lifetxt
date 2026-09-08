import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.parser import parse_text
from lifetxt.progress_history import (
    apply_progress_mutation,
    authoritative_progress_events,
    build_progress_event,
    progress_history_diagnostics,
)
from lifetxt.serializer import item_to_line


REVISION = "a" * 64


class ProgressEventBuilderTests(unittest.TestCase):
    def test_preserves_fraction_values_and_normalizes_offset_timestamp(self):
        event = build_progress_event(
            "task-1",
            "3/10",
            "6/20",
            "set",
            "2026-09-08T18:00:00+09:00",
            1,
            "PTX-task-1-000001",
            REVISION,
        )
        self.assertEqual(["3/10"], event.details["before_progress"])
        self.assertEqual(["6/20"], event.details["after_progress"])
        self.assertEqual(["2026-09-08T09:00:00Z"], event.details["at"])
        self.assertEqual(["PE-task-1-000001"], event.details["id"])

    def test_missing_before_is_explicit_and_not_zero(self):
        event = build_progress_event(
            "task-1",
            None,
            "25%",
            "set",
            "2026-09-08T09:00:00Z",
            1,
            "PTX-task-1-000001",
            REVISION,
        )
        self.assertEqual(["true"], event.details["before_missing"])
        self.assertNotIn("before_progress", event.details)


class ProgressMutationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "life.txt")

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return mutation.read_text_snapshot(self.path)

    def _items(self):
        with open(self.path, encoding="utf-8") as handle:
            items, diagnostics = parse_text(handle.read())
        self.assertFalse(
            [row for row in diagnostics if row.severity == "error"], diagnostics
        )
        return items

    def _bytes(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_set_updates_item_and_appends_event_in_one_revision(self):
        snapshot = self._write("[ ] T Task id:task-1 progress:25%\n")
        result = apply_progress_mutation(
            self.path,
            "task-1",
            "40%",
            "set",
            snapshot.content_hash,
            expected_before="25%",
            at="2026-09-08T09:00:00Z",
        )
        self.assertNotEqual(snapshot.content_hash, result.mutation.after_hash)
        items = self._items()
        events = authoritative_progress_events(items, "task-1")
        self.assertEqual(1, len(events))
        self.assertEqual(["25%"], events[0].details["before_progress"])
        self.assertEqual(["40%"], events[0].details["after_progress"])
        self.assertEqual(
            [snapshot.content_hash], events[0].details["source_revision"]
        )

    def test_sequential_events_have_contiguous_values_and_sequences(self):
        first = self._write("[ ] T Task id:task-1 progress:3/10\n")
        result1 = apply_progress_mutation(
            self.path,
            "task-1",
            "4/10",
            "delta",
            first.content_hash,
            expected_before="3/10",
            at="2026-09-08T09:00:00Z",
        )
        apply_progress_mutation(
            self.path,
            "task-1",
            "6/20",
            "set",
            result1.mutation.after_hash,
            expected_before="4/10",
            at="2026-09-08T09:00:00Z",
        )
        events = authoritative_progress_events(self._items(), "task-1")
        self.assertEqual(["1", "2"], [e.details["sequence"][0] for e in events])
        self.assertEqual(["4/10"], events[0].details["after_progress"])
        self.assertEqual(["4/10"], events[1].details["before_progress"])
        self.assertEqual(["6/20"], events[1].details["after_progress"])
        self.assertEqual(
            [result1.mutation.after_hash], events[1].details["source_revision"]
        )

    def test_manual_gap_is_recorded_but_not_silently_repaired(self):
        first = self._write("[ ] T Task id:task-1 progress:25%\n")
        apply_progress_mutation(
            self.path,
            "task-1",
            "40%",
            "set",
            first.content_hash,
            expected_before="25%",
            at="2026-09-08T09:00:00Z",
        )
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read().replace("progress:40%", "progress:50%", 1)
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        manual = mutation.read_text_snapshot(self.path)
        apply_progress_mutation(
            self.path,
            "task-1",
            "60%",
            "set",
            manual.content_hash,
            expected_before="50%",
            at="2026-09-08T10:00:00Z",
        )
        items = self._items()
        self.assertIn(
            "W241", [row.code for row in progress_history_diagnostics(items)]
        )
        self.assertEqual([], authoritative_progress_events(items, "task-1"))

    def test_stale_revision_leaves_bytes_unchanged(self):
        self._write("[ ] T Task id:task-1 progress:25%\n")
        before = self._bytes()
        with self.assertRaises(mutation.MutationConflict):
            apply_progress_mutation(
                self.path,
                "task-1",
                "40%",
                "set",
                REVISION,
                expected_before="25%",
                at="2026-09-08T09:00:00Z",
            )
        self.assertEqual(before, self._bytes())

    def test_missing_id_is_rejected_without_writing(self):
        snapshot = self._write("[ ] T Task progress:25%\n")
        before = self._bytes()
        with self.assertRaises(Exception):
            apply_progress_mutation(
                self.path,
                "task-1",
                "40%",
                "set",
                snapshot.content_hash,
                expected_before="25%",
                at="2026-09-08T09:00:00Z",
            )
        self.assertEqual(before, self._bytes())


class ProgressHistoryValidationTests(unittest.TestCase):
    def _parse(self, *lines):
        items, diagnostics = parse_text("\n".join(lines) + "\n")
        self.assertFalse([row for row in diagnostics if row.severity == "error"])
        return items

    def _event(self, before, after, sequence=1, at="2026-09-08T09:00:00Z"):
        return item_to_line(
            build_progress_event(
                "task-1",
                before,
                after,
                "set" if before is None else "delta",
                at,
                sequence,
                "PTX-task-1-%06d" % sequence,
                REVISION,
            )
        )

    def test_no_history_is_valid_and_authoritative_result_is_empty(self):
        items = self._parse("[ ] T Task id:task-1 progress:25%")
        self.assertEqual([], progress_history_diagnostics(items))
        self.assertEqual([], authoritative_progress_events(items, "task-1"))

    def test_manual_current_change_marks_history_incomplete(self):
        items = self._parse(
            "[ ] T Task id:task-1 progress:50%", self._event("25%", "40%")
        )
        codes = [row.code for row in progress_history_diagnostics(items)]
        self.assertIn("W243", codes)
        self.assertEqual([], authoritative_progress_events(items, "task-1"))

    def test_duplicate_sequence_and_id_are_rejected(self):
        first = self._event("25%", "40%")
        items = self._parse("[ ] T Task id:task-1 progress:40%", first, first)
        codes = [row.code for row in progress_history_diagnostics(items)]
        self.assertIn("W239", codes)

    def test_discontinuity_and_backwards_timestamp_are_rejected(self):
        items = self._parse(
            "[ ] T Task id:task-1 progress:60%",
            self._event("25%", "40%", 1, "2026-09-08T10:00:00Z"),
            self._event("50%", "60%", 2, "2026-09-08T09:00:00Z"),
        )
        codes = [row.code for row in progress_history_diagnostics(items)]
        self.assertIn("W241", codes)
        self.assertIn("W242", codes)

    def test_non_normalized_timestamp_is_not_authoritative(self):
        event = self._event("25%", "40%").replace(
            "at:2026-09-08T09:00:00Z", "at:2026-09-08T18:00:00+09:00"
        )
        items = self._parse("[ ] T Task id:task-1 progress:40%", event)
        self.assertIn("W233", [row.code for row in progress_history_diagnostics(items)])
        self.assertEqual([], authoritative_progress_events(items, "task-1"))

    def test_repeated_required_field_is_not_authoritative(self):
        event = self._event("25%", "40%").replace(
            " operation:delta", " operation:delta operation:set"
        )
        items = self._parse("[ ] T Task id:task-1 progress:40%", event)
        self.assertIn("W231", [row.code for row in progress_history_diagnostics(items)])
        self.assertEqual([], authoritative_progress_events(items, "task-1"))
