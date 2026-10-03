"""CPython evidence harness for the Worker adapter's shared-core calls."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from entry import check_text, shared_core_smoke  # noqa: E402


def fixture(count):
    return "".join(
        '[ ] T "日本語 task {0}" id:poc_{0:04d} due:2026-10-03\n'.format(i)
        for i in range(count)
    )


def timed(fn):
    start = time.perf_counter()
    value = fn()
    return round(time.perf_counter() - start, 6), value


def main():
    rows = []
    for count in (0, 1, 10, 100, 500):
        elapsed, result = timed(lambda: check_text(fixture(count)))
        rows.append({"records": count, "elapsed_seconds": elapsed, "result": result})
    valid = fixture(1)
    return {
        "python": sys.version,
        "rows": rows,
        "shared_core": shared_core_smoke(valid),
        "invalid": check_text('[ ] T "unterminated\n'),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2, default=str))
