from __future__ import unicode_literals

import os
import tempfile
import unittest
import unittest.mock

from lifetxt import tui_remote_cache as cache


class CacheKeyTests(unittest.TestCase):
    def test_same_url_and_user_produce_the_same_key(self):
        a = cache.connection_cache_key("https://example.internal", "alice")
        b = cache.connection_cache_key("https://example.internal/", "alice")
        self.assertEqual(a, b)

    def test_different_users_on_the_same_server_produce_different_keys(self):
        a = cache.connection_cache_key("https://example.internal", "alice")
        b = cache.connection_cache_key("https://example.internal", "bob")
        self.assertNotEqual(a, b)

    def test_different_servers_produce_different_keys(self):
        a = cache.connection_cache_key("https://one.internal", "alice")
        b = cache.connection_cache_key("https://two.internal", "alice")
        self.assertNotEqual(a, b)


class SaveLoadClearTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_round_trip_preserves_items_and_revision(self):
        items = [{"id": "t1", "text": "[ ] T Buy_milk id:t1", "line": 1}]
        cache.save_snapshot(
            "https://example.internal",
            items,
            "rev1",
            username="alice",
            directory=self.tmp,
            now=1000.0,
        )
        snapshot = cache.load_snapshot(
            "https://example.internal", username="alice", directory=self.tmp
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["revision"], "rev1")
        self.assertEqual(snapshot["items"], items)
        self.assertEqual(snapshot["saved_at"], 1000.0)

    def test_missing_cache_returns_none(self):
        self.assertIsNone(
            cache.load_snapshot(
                "https://nobody-cached-this.internal", directory=self.tmp
            )
        )

    def test_corrupt_cache_file_returns_none_rather_than_raising(self):
        path = cache.cache_file_path("https://example.internal", directory=self.tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("not json{{{")
        self.assertIsNone(
            cache.load_snapshot("https://example.internal", directory=self.tmp)
        )

    def test_wrong_cache_version_is_treated_as_no_cache(self):
        cache.save_snapshot("https://example.internal", [], "rev1", directory=self.tmp)
        path = cache.cache_file_path("https://example.internal", directory=self.tmp)
        import json

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data["cache_version"] = 999
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        self.assertIsNone(
            cache.load_snapshot("https://example.internal", directory=self.tmp)
        )

    def test_credentials_are_never_part_of_the_persisted_payload(self):
        items = [{"id": "t1", "text": "[ ] T Buy_milk id:t1", "line": 1}]
        cache.save_snapshot(
            "https://example.internal",
            items,
            "rev1",
            username="alice",
            directory=self.tmp,
        )
        path = cache.cache_file_path(
            "https://example.internal", username="alice", directory=self.tmp
        )
        with open(path, "r", encoding="utf-8") as handle:
            raw_text = handle.read()
        self.assertNotIn("password", raw_text.lower())
        self.assertNotIn("authorization", raw_text.lower())
        self.assertNotIn("basic ", raw_text.lower())

    def test_cache_is_bounded_to_the_max_item_count(self):
        items = [{"id": "t%d" % i, "text": "x", "line": i} for i in range(5)]
        with unittest.mock.patch.object(cache, "MAX_CACHED_ITEMS", 3):
            cache.save_snapshot(
                "https://example.internal", items, "rev1", directory=self.tmp
            )
            snapshot = cache.load_snapshot(
                "https://example.internal", directory=self.tmp
            )
        self.assertEqual(len(snapshot["items"]), 3)

    def test_clear_snapshot_removes_the_file_and_reports_success(self):
        cache.save_snapshot("https://example.internal", [], "rev1", directory=self.tmp)
        self.assertTrue(
            cache.clear_snapshot("https://example.internal", directory=self.tmp)
        )
        self.assertIsNone(
            cache.load_snapshot("https://example.internal", directory=self.tmp)
        )

    def test_clear_snapshot_on_a_nonexistent_cache_reports_false(self):
        self.assertFalse(
            cache.clear_snapshot("https://never-cached.internal", directory=self.tmp)
        )


if __name__ == "__main__":
    unittest.main()
