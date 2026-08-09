import os
import tempfile
import threading
import unittest

from lifetxt import mutation
from lifetxt.mcp import McpContext, call_tool
from lifetxt.timer import start_timer_transaction, timer_status_data


class TimerTransactionRevisionV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.state = os.path.join(self.temp.name, "timer.json")
        self.config = {
            "timer": {"state_file": self.state},
            "transactions": {
                "journal_dir": os.path.join(self.temp.name, "transactions")
            },
        }
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")

    def test_start_requires_both_revisions_in_strict_call(self):
        with self.assertRaises(ValueError):
            start_timer_transaction(
                self.life, "t1", config=self.config, require_revisions=True
            )
        result = start_timer_transaction(
            self.life,
            "t1",
            config=self.config,
            expected_item_revision=mutation.read_text_snapshot(self.life).content_hash,
            expected_timer_revision=mutation.MISSING_HASH,
            require_revisions=True,
        )
        self.assertTrue(result["transaction_id"])
        self.assertNotEqual(mutation.MISSING_HASH, result["timer_revision"])
        self.assertNotEqual(mutation.MISSING_HASH, result["item_revision"])

    def test_same_revisions_have_one_winner_and_one_conflict(self):
        item_revision = mutation.read_text_snapshot(self.life).content_hash
        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            try:
                barrier.wait()
                start_timer_transaction(
                    self.life,
                    "t1",
                    config=self.config,
                    expected_item_revision=item_revision,
                    expected_timer_revision=mutation.MISSING_HASH,
                    require_revisions=True,
                )
                outcomes.append("winner")
            except Exception as exc:
                outcomes.append(type(exc).__name__)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(1, outcomes.count("winner"), outcomes)
        self.assertEqual(2, len(outcomes))


class TimerMcpRevisionV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.state = os.path.join(self.temp.name, "timer.json")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")
        self.context = McpContext(
            [self.life],
            writable_path=self.life,
            config={
                "web": {"revision_mode": "required"},
                "timer": {"state_file": self.state},
                "transactions": {
                    "journal_dir": os.path.join(self.temp.name, "transactions")
                },
            },
        )

    def test_required_mcp_timer_discovers_and_chains_two_revisions(self):
        with self.assertRaises(ValueError):
            call_tool("timer_start", {"id": "t1"}, self.context)
        started = call_tool(
            "timer_start",
            {
                "id": "t1",
                "item_revision": mutation.read_text_snapshot(self.life).content_hash,
                "timer_revision": mutation.MISSING_HASH,
            },
            self.context,
        )
        self.assertTrue(started["transaction_id"])
        stopped = call_tool(
            "timer_stop",
            {
                "item_revision": started["item_revision"],
                "timer_revision": started["timer_revision"],
            },
            self.context,
        )
        self.assertFalse(stopped["running"])
        self.assertEqual(mutation.MISSING_HASH, stopped["timer_revision"])


@unittest.skipUnless(
    __import__("importlib").util.find_spec("fastapi") is not None
    and (
        __import__("importlib").util.find_spec("httpx2") is not None
        or __import__("importlib").util.find_spec("httpx") is not None
    ),
    "Web dependencies are not installed.",
)
class TimerWebRevisionV3Tests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from lifetxt.webapp import create_app

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.state = os.path.join(self.temp.name, "timer.json")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")
        config = {
            "web": {
                "revision_mode": "required",
                "revision_metrics_path": os.path.join(self.temp.name, "metrics.json"),
            },
            "timer": {"state_file": self.state},
            "transactions": {
                "journal_dir": os.path.join(self.temp.name, "transactions")
            },
        }
        self.client = TestClient(
            create_app([self.life], writable_path=self.life, config=config)
        )

    def test_required_web_timer_returns_428_then_chains_revisions(self):
        missing = self.client.post("/api/timer", json={"action": "start", "id": "t1"})
        self.assertEqual(428, missing.status_code)
        started = self.client.post(
            "/api/timer",
            json={
                "action": "start",
                "id": "t1",
                "item_revision": mutation.read_text_snapshot(self.life).content_hash,
                "timer_revision": mutation.MISSING_HASH,
            },
        )
        self.assertEqual(200, started.status_code, started.text)
        payload = started.json()
        self.assertTrue(payload["transaction_id"])
        stopped = self.client.post(
            "/api/timer",
            json={
                "action": "stop",
                "item_revision": payload["item_revision"],
                "timer_revision": payload["timer_revision"],
            },
        )
        self.assertEqual(200, stopped.status_code, stopped.text)
        self.assertTrue(stopped.json()["elapsed_written"])

    def test_observe_timer_fallback_is_persisted(self):
        from fastapi.testclient import TestClient
        from lifetxt.webapp import create_app

        other = os.path.join(self.temp.name, "observe.txt")
        state = os.path.join(self.temp.name, "observe-timer.json")
        metrics = os.path.join(self.temp.name, "observe-metrics.json")
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")
        client = TestClient(
            create_app(
                [other],
                writable_path=other,
                config={
                    "web": {
                        "revision_mode": "observe",
                        "revision_metrics_path": metrics,
                    },
                    "timer": {"state_file": state},
                },
            )
        )
        response = client.post("/api/timer", json={"action": "start", "id": "t1"})
        self.assertEqual(
            "used", response.headers.get("X-Lifetxt-Legacy-Revision-Fallback")
        )
        report = client.get("/api/revision-metrics").json()
        self.assertEqual(1, report["legacy_fallback_by_path"]["/api/timer"])


if __name__ == "__main__":
    unittest.main()
