import unittest

from scripts import benchmark_core


class StorageBenchmarkTests(unittest.TestCase):
    def test_fixture_generation_is_deterministic_and_representative(self):
        first = benchmark_core.synthetic_text(12)
        self.assertEqual(first, benchmark_core.synthetic_text(12))
        self.assertIn("T", first)
        self.assertIn("E", first)
        self.assertIn("N", first)
        self.assertIn("".join(chr(code) for code in (26085, 26412, 35486)), first)
        self.assertIn("project:benchmark", first)

    def test_report_schema_records_both_layouts(self):
        report = benchmark_core.benchmark(".", (4,))
        self.assertEqual(report["schema"], "lifetxt-storage-benchmark-v1")
        self.assertEqual(
            [row["layout"] for row in report["layouts"]],
            ["single-file", "multi-source"],
        )
        self.assertEqual(report["reference_date"], "2026-09-24")
        for row in report["layouts"]:
            self.assertEqual(row["records"], 4)
            self.assertIn("fixture_sha256", row)
            self.assertIn("query", row["operations"])
            self.assertIn("today", row["operations"])


if __name__ == "__main__":
    unittest.main()
