from __future__ import unicode_literals

import argparse
import unittest
import unittest.mock

from lifetxt import tui_app
from lifetxt.tui_backend import RemoteTuiBackend, remote_source_label


class _StubConnection(object):
    """A fake RemoteTuiConnection recording calls without any real HTTP."""

    def __init__(self, items_payload=None):
        self.host = "example.internal"
        self.base_url = "https://example.internal"
        self.username = "alice"
        # `file_revision` mirrors the real RemoteTuiConnection field: the
        # last revision *this connection* has observed. `server_revision`
        # is the fake "true" remote state a test mutates to simulate a
        # concurrent change; the two only stay equal after an explicit
        # get_revision()/request() call, exactly like the real client.
        self.file_revision = "rev0"
        self.server_revision = "rev0"
        self.calls = []
        self._items_payload = items_payload or {"items": []}
        self._raise_on_next = None

    def describe(self):
        return "https://example.internal as alice"

    def raise_next(self, exc):
        self._raise_on_next = exc

    def request(self, method, path, json_body=None, if_match=None):
        self.calls.append((method, path, json_body, if_match))
        if self._raise_on_next is not None:
            exc = self._raise_on_next
            self._raise_on_next = None
            raise exc
        if method == "GET" and path == "/api/items":
            return self._items_payload
        self.server_revision = "rev-%d" % (len(self.calls) + 1)
        self.file_revision = self.server_revision
        return {"ok": True}

    def get_revision(self):
        self.calls.append(("GET", "/api/revision", None, None))
        if self._raise_on_next is not None:
            exc = self._raise_on_next
            self._raise_on_next = None
            raise exc
        self.file_revision = self.server_revision
        return self.file_revision


def _item_payload(item_id, line, status="[ ]", text=None):
    return {
        "id": item_id,
        "line": line,
        "status": status,
        "type": "T",
        "title": "Buy_milk",
        "text": text or ("%s T Buy_milk id:%s" % (status, item_id)),
        "generated": False,
    }


class RemoteTuiBackendLoadItemsTests(unittest.TestCase):
    def test_load_items_reconstructs_items_with_stable_source_and_line(self):
        connection = _StubConnection(
            {"items": [_item_payload("t1", 3), _item_payload("t2", 7)]}
        )
        backend = RemoteTuiBackend(connection)

        items, diagnostics = backend.load_items()

        self.assertIsNone(diagnostics)
        self.assertEqual(len(items), 2)
        expected_source = remote_source_label(connection)
        self.assertTrue(all(item.source == expected_source for item in items))
        self.assertEqual(sorted(item.line for item in items), [3, 7])

    def test_load_items_returns_none_and_message_on_connection_failure(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection()
        connection.raise_next(RemoteConnectionError("could not reach server"))
        backend = RemoteTuiBackend(connection)

        items, diagnostics = backend.load_items()

        self.assertIsNone(items)
        self.assertIn("could not reach server", diagnostics)


class RemoteTuiBackendMutationTests(unittest.TestCase):
    def setUp(self):
        self.connection = _StubConnection(
            {"items": [_item_payload("t1", 1, status="[ ]")]}
        )
        self.backend = RemoteTuiBackend(self.connection)
        self.backend.load_items()

    def test_status_change_sends_a_merged_put_payload(self):
        source = remote_source_label(self.connection)
        grouped = {source: [{"id": "t1", "status": "[x]"}]}
        self.backend.apply_semantic_changes(grouped, {}, id_key="id")

        method, path, body, if_match = self.connection.calls[-1]
        self.assertEqual(method, "PUT")
        self.assertEqual(path, "/api/items/id/t1")
        self.assertEqual(body["status"], "[x]")
        self.assertEqual(body["details"].get("id"), ["t1"])
        self.assertEqual(if_match, "rev0")

    def test_set_details_merges_onto_the_cached_item(self):
        source = remote_source_label(self.connection)
        grouped = {source: [{"id": "t1", "set_details": {"due": ["2026-09-10"]}}]}
        self.backend.apply_semantic_changes(grouped, {}, id_key="id")

        _method, _path, body, _if_match = self.connection.calls[-1]
        self.assertEqual(body["details"].get("due"), ["2026-09-10"])
        # Existing details survive the merge.
        self.assertEqual(body["details"].get("id"), ["t1"])

    def test_delete_change_calls_the_delete_route(self):
        source = remote_source_label(self.connection)
        grouped = {source: [{"id": "t1", "delete": True}]}
        self.backend.apply_semantic_changes(grouped, {}, id_key="id")

        method, path, _body, _if_match = self.connection.calls[-1]
        self.assertEqual(method, "DELETE")
        self.assertEqual(path, "/api/items/id/t1")

    def test_conflict_propagates_without_retry(self):
        from lifetxt.tui_remote_client import RemoteMutationConflict

        self.connection.raise_next(RemoteMutationConflict("stale"))
        source = remote_source_label(self.connection)
        grouped = {source: [{"id": "t1", "status": "[x]"}]}

        with self.assertRaises(RemoteMutationConflict):
            self.backend.apply_semantic_changes(grouped, {}, id_key="id")

        # Exactly one PUT attempt: no automatic retry.
        put_calls = [c for c in self.connection.calls if c[0] == "PUT"]
        self.assertEqual(len(put_calls), 1)

    def test_multi_file_grouping_is_rejected(self):
        grouped = {"a": [{"id": "t1", "status": "[x]"}], "b": [{"id": "t2"}]}
        with self.assertRaises(NotImplementedError):
            self.backend.apply_semantic_changes(grouped, {}, id_key="id")

    def test_change_with_no_id_is_rejected(self):
        source = remote_source_label(self.connection)
        grouped = {source: [{"status": "[x]"}]}
        with self.assertRaises(ValueError):
            self.backend.apply_semantic_changes(grouped, {}, id_key="id")


class WorkspaceStateRemoteWiringTests(unittest.TestCase):
    def _state(self, connection):
        backend = RemoteTuiBackend(connection)
        args = argparse.Namespace(paths=[], config_data={}, remote_url="http://x")
        return tui_app.WorkspaceState(
            args, glyphs=tui_app.ASCII_GLYPHS, backend=backend
        )

    def test_load_uses_the_remote_backend(self):
        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        state.load()
        state.refresh()
        self.assertEqual(state.error, "")
        self.assertTrue(any(row.get("id") == "t1" for row in state.rows))

    def test_load_failure_is_surfaced_as_an_error_not_a_crash(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection()
        connection.raise_next(RemoteConnectionError("refused"))
        state = self._state(connection)
        state.load()
        self.assertIn("refused", state.error)

    def test_write_target_refuses_for_remote_backend(self):
        connection = _StubConnection({"items": []})
        state = self._state(connection)
        state.load()
        with self.assertRaises(ValueError):
            tui_app._write_target(state)

    def test_mutate_rows_skips_local_snapshot_for_remote(self):
        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        state.load()
        state.refresh()
        rows = state.rows

        def change_for_row(row):
            return {"id": row["id"], "status": "[x]"}

        count = tui_app._mutate_rows(state, rows, "test", change_for_row)
        self.assertEqual(count, 1)
        self.assertEqual(state.undo_stack, [])
        put_calls = [c for c in connection.calls if c[0] == "PUT"]
        self.assertEqual(len(put_calls), 1)

    def test_cmd_add_creates_a_remote_item(self):
        connection = _StubConnection({"items": []})
        state = self._state(connection)
        state.load()
        tui_app._cmd_add(state, "Buy milk")
        post_calls = [c for c in connection.calls if c[0] == "POST"]
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(post_calls[0][1], "/api/items")
        self.assertEqual(post_calls[0][2]["title"], "Buy milk")

    def test_header_shows_remote_connection_label_without_credentials(self):
        connection = _StubConnection({"items": []})
        state = self._state(connection)
        state.load()
        header = tui_app._build_header(state, 60)
        rendered = "".join(text for text, _style in header[1])
        self.assertIn("remote:https://example.internal as alice", rendered)

    def test_header_shows_disconnected_when_remote_status_is_disconnected(self):
        connection = _StubConnection({"items": []})
        state = self._state(connection)
        state.load()
        state.remote_status = "disconnected"
        header = tui_app._build_header(state, 60)
        rendered = "".join(text for text, _style in header[1])
        self.assertIn("(disconnected)", rendered)


class RemoteTuiBackendPollChangedTests(unittest.TestCase):
    def setUp(self):
        self.connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        self.backend = RemoteTuiBackend(self.connection)
        self.backend.load_items()

    def test_poll_reports_no_change_when_revision_is_unchanged(self):
        self.assertFalse(self.backend.poll_changed())

    def test_poll_reports_a_change_when_revision_advances(self):
        self.connection.server_revision = "rev-new"
        self.assertTrue(self.backend.poll_changed())

    def test_poll_propagates_connection_failures(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        self.connection.raise_next(RemoteConnectionError("refused"))
        with self.assertRaises(RemoteConnectionError):
            self.backend.poll_changed()

    def test_poll_uses_the_cheap_revision_endpoint_only(self):
        self.backend.poll_changed()
        self.assertEqual(self.connection.calls[-1][:2], ("GET", "/api/revision"))


class RemotePollingLoopTests(unittest.TestCase):
    """#680: the bounded background-poll tick used inside run_workspace's
    main loop, exercised directly (no real curses session needed)."""

    def _state(self, connection):
        backend = RemoteTuiBackend(connection)
        args = argparse.Namespace(paths=[], config_data={}, remote_url="http://x")
        state = tui_app.WorkspaceState(
            args, glyphs=tui_app.ASCII_GLYPHS, backend=backend
        )
        state.load()
        state.refresh()
        return state

    def test_poll_before_the_interval_elapses_is_a_no_op(self):
        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        calls_before = len(connection.calls)
        state._last_remote_poll = 1000.0
        dirty = tui_app._poll_remote(state, now=1000.1)
        self.assertFalse(dirty)
        self.assertEqual(len(connection.calls), calls_before)

    def test_poll_with_no_change_does_not_reload(self):
        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        calls_before = len(connection.calls)
        state._last_remote_poll = 0.0
        dirty = tui_app._poll_remote(state, now=1000.0)
        self.assertFalse(dirty)
        self.assertEqual(state.remote_status, "connected")
        new_get_item_calls = [
            c for c in connection.calls[calls_before:] if c[1] == "/api/items"
        ]
        self.assertEqual(len(new_get_item_calls), 0)

    def test_poll_with_a_real_change_reloads_and_preserves_selection(self):
        connection = _StubConnection(
            {"items": [_item_payload("t1", 1), _item_payload("t2", 2)]}
        )
        state = self._state(connection)
        # Select the second row (t2), then simulate a server-side change
        # that reorders the payload -- t2 now comes first.
        state.selected = 1
        self.assertEqual(state.selected_row()["id"], "t2")
        connection._items_payload = {
            "items": [_item_payload("t2", 2), _item_payload("t1", 1)]
        }
        connection.server_revision = "rev-changed"
        state._last_remote_poll = 0.0

        dirty = tui_app._poll_remote(state, now=1000.0)

        self.assertTrue(dirty)
        self.assertEqual(state.selected_row()["id"], "t2")

    def test_poll_failure_marks_disconnected_without_losing_existing_rows(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        original_rows = list(state.rows)
        connection.raise_next(RemoteConnectionError("refused"))
        state._last_remote_poll = 0.0

        dirty = tui_app._poll_remote(state, now=1000.0)

        self.assertTrue(dirty)
        self.assertEqual(state.remote_status, "disconnected")
        self.assertIn("refused", state.remote_status_detail)
        self.assertEqual(state.rows, original_rows)

    def test_reconnection_after_failure_clears_disconnected_status(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        state = self._state(connection)
        connection.raise_next(RemoteConnectionError("refused"))
        tui_app._poll_remote(state, now=1000.0)
        self.assertEqual(state.remote_status, "disconnected")

        dirty = tui_app._poll_remote(state, now=1002.0)

        self.assertTrue(dirty)
        self.assertEqual(state.remote_status, "connected")
        self.assertEqual(state.remote_status_detail, "")


class RemoteTuiBackendOfflineCacheTests(unittest.TestCase):
    """#681: opt-in read-only offline cache."""

    def setUp(self):
        import tempfile

        self.cache_dir = tempfile.mkdtemp()
        self._patch = unittest.mock.patch(
            "lifetxt.tui_remote_cache.cache_dir", return_value=self.cache_dir
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_cache_disabled_by_default_never_persists_anything(self):
        import os

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection)
        backend.load_items()
        self.assertEqual(
            os.listdir(self.cache_dir) if os.path.isdir(self.cache_dir) else [], []
        )

    def test_enabled_cache_persists_after_a_successful_read(self):
        import os

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        backend.load_items()
        self.assertTrue(os.listdir(self.cache_dir))

    def test_falls_back_to_cache_on_connection_failure(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        backend.load_items()  # populate the cache while connected

        connection.raise_next(RemoteConnectionError("refused"))
        items, diagnostic = backend.load_items()

        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)
        self.assertTrue(backend.serving_cache)
        self.assertIn("cached", diagnostic.lower())

    def test_no_cache_available_still_reports_the_original_error(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": []})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        connection.raise_next(RemoteConnectionError("refused"))

        items, diagnostic = backend.load_items()

        self.assertIsNone(items)
        self.assertIn("refused", diagnostic)
        self.assertFalse(backend.serving_cache)

    def test_serving_cache_refuses_every_mutation(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        backend.load_items()
        connection.raise_next(RemoteConnectionError("refused"))
        backend.load_items()
        self.assertTrue(backend.serving_cache)

        source = remote_source_label(connection)
        with self.assertRaises(ValueError):
            backend.apply_semantic_changes(
                {source: [{"id": "t1", "status": "[x]"}]}, {}, id_key="id"
            )
        with self.assertRaises(ValueError):
            backend.create_item(
                {"status": "[ ]", "type": "T", "title": "x", "details": {}}
            )
        with self.assertRaises(ValueError):
            backend.delete_item("t1")

    def test_a_real_successful_read_clears_cached_mode(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        backend.load_items()
        connection.raise_next(RemoteConnectionError("refused"))
        backend.load_items()
        self.assertTrue(backend.serving_cache)

        backend.load_items()  # server reachable again
        self.assertFalse(backend.serving_cache)

        # Writes now succeed once cached mode is cleared.
        source = remote_source_label(connection)
        backend.apply_semantic_changes(
            {source: [{"id": "t1", "status": "[x]"}]}, {}, id_key="id"
        )

    def test_cache_never_contains_the_password(self):
        import os

        from lifetxt.tui_remote_client import RemoteTuiConnection

        real_connection = RemoteTuiConnection(
            "http://127.0.0.1:9", username="alice", password="hunter2"
        )
        backend = RemoteTuiBackend(real_connection, cache_enabled=True)
        backend._save_cache_snapshot([{"id": "t1", "text": "x", "line": 1}])
        found_any = False
        for name in os.listdir(self.cache_dir):
            found_any = True
            with open(
                os.path.join(self.cache_dir, name), "r", encoding="utf-8"
            ) as handle:
                text = handle.read()
            self.assertNotIn("hunter2", text)
        self.assertTrue(found_any)


class WorkspaceStatePollReconnectAfterCacheTests(unittest.TestCase):
    """#681/#680 integration: reconnecting after cached mode forces a real
    reload and clears write-refusal, even when the revision happens to be
    unchanged from what the cache already showed."""

    def test_reconnect_forces_a_reload_and_clears_cache_mode(self):
        from lifetxt.tui_remote_client import RemoteConnectionError

        connection = _StubConnection({"items": [_item_payload("t1", 1)]})
        backend = RemoteTuiBackend(connection, cache_enabled=True)
        args = argparse.Namespace(paths=[], config_data={}, remote_url="http://x")
        state = tui_app.WorkspaceState(
            args, glyphs=tui_app.ASCII_GLYPHS, backend=backend
        )
        state.load()
        state.refresh()

        connection.raise_next(RemoteConnectionError("refused"))
        state._last_remote_poll = 0.0
        tui_app._poll_remote(state, now=1000.0)
        self.assertEqual(state.remote_status, "disconnected")

        # Reconnect: the server is reachable again with the identical
        # revision the cache already had.
        state._last_remote_poll = 1000.0
        dirty = tui_app._poll_remote(state, now=1002.0)

        self.assertTrue(dirty)
        self.assertEqual(state.remote_status, "connected")
        self.assertFalse(backend.serving_cache)


if __name__ == "__main__":
    unittest.main()
