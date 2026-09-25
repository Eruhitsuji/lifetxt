import os
import tempfile
import unittest

from lifetxt.storage_health import measure


class StorageHealthTests(unittest.TestCase):
    def test_reports_facts_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[ ] T "Task" id:t1\n')
            with open(path, "rb") as handle:
                before = handle.read()
            result = measure([path])
            self.assertEqual(result["active_records"], 1)
            self.assertEqual(result["status"], "healthy")
            self.assertFalse(result["mutated"])
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), before)

    def test_threshold_recommendation_is_explainable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[ ] T "Task" id:t1\n')
            result = measure([path], active_threshold=1)
            self.assertEqual(result["status"], "maintenance_recommended")
            self.assertIn("active_bytes_at_or_above_threshold", result["reasons"])


if __name__ == "__main__":
    unittest.main()
