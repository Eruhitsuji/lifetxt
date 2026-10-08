"""Repeatable core benchmark; timings are evidence, never flaky CI assertions.

python -m tests.test_daily_flow_performance --benchmark
"""

import argparse
import datetime as dt
import json
import platform
import statistics
import time
import tracemalloc
import unittest

from lifetxt.daily_flow import build_daily_flow
from lifetxt.parser import parse_text


def fixture(dense=False):
    tasks = [f"[ ] T Task-{i} id:t{i} est:1m priority:A\n" for i in range(1000)]
    # Include missing estimates and stable equal rank keys in the same scale.
    tasks[-10:] = [f"[ ] T Unknown-{i} id:u{i}\n" for i in range(10)]
    events = []
    for i in range(100):
        start = dt.datetime(2026, 10, 9, 10) + dt.timedelta(
            minutes=0 if dense else i * 3
        )
        end = start + dt.timedelta(minutes=30 if dense else 1)
        events.append(
            f"[ ] E Event-{i} id:e{i} from:{start.isoformat()} to:{end.isoformat()}\n"
        )
    return "".join(tasks + events)


def run(data):
    return build_daily_flow(
        data,
        date="2026-10-09",
        day_start="09:00",
        day_end="17:00",
        timezone="Asia/Tokyo",
        evaluated_at="2026-10-08T18:00+09:00",
        occupancy_complete=True,
    )


def benchmark():
    measurements = []
    for dense in (False, True):
        text = fixture(dense)
        parsed, _ = parse_text(text)
        for item in parsed:
            item.source = "benchmark.txt"
        for _ in range(3):
            run(parsed)
        core, parsing = [], []
        for _ in range(20):
            before = time.perf_counter()
            parse_text(text)
            parsing.append((time.perf_counter() - before) * 1000)
            before = time.perf_counter()
            result = run(parsed)
            core.append((time.perf_counter() - before) * 1000)
        tracemalloc.start()
        run(parsed)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        measurements.append(
            {
                "scenario": "dense-overlap" if dense else "many-gaps",
                "tasks": 1000,
                "events": 100,
                "warmup": 3,
                "runs": 20,
                "core_p50_ms": statistics.median(core),
                "core_p95_ms": sorted(core)[18],
                "parse_p50_ms": statistics.median(parsing),
                "parse_p95_ms": sorted(parsing)[18],
                "incremental_peak_mib": peak / (1024 * 1024),
                "candidate_count": sum(
                    r["kind"] == "candidate" for r in result["timeline"]
                ),
                "complete_inventory_count": len(result["unplaced"])
                + sum(r["kind"] == "candidate" for r in result["timeline"]),
            }
        )
    return {
        "python": platform.python_version(),
        "os": platform.system(),
        "machine": platform.machine(),
        "cpu": platform.processor() or "unreported",
        "seed": 0,
        "scenarios": measurements,
    }


class DailyFlowScaleTests(unittest.TestCase):
    def test_representative_scale_keeps_all_tasks_and_is_deterministic(self):
        for dense in (False, True):
            data, _ = parse_text(fixture(dense))
            result = run(data)
            self.assertEqual(result, run(list(reversed(data))))
            self.assertEqual(
                1000,
                len(result["unplaced"])
                + sum(row["kind"] == "candidate" for row in result["timeline"]),
            )
            self.assertEqual("certified", result["completeness"]["occupancy"])
            self.assertEqual("partial", result["completeness"]["state"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    if args.benchmark:
        print(json.dumps(benchmark(), indent=2))
    else:
        unittest.main(argv=[__file__])
