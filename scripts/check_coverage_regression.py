from __future__ import annotations
import argparse
import json
from pathlib import Path

def check(report: Path, baseline: Path) -> tuple[bool, str]:
    actual = json.loads(report.read_text(encoding="utf-8"))
    expected = json.loads(baseline.read_text(encoding="utf-8"))
    measured = actual["totals"]["percent_branches"]
    floor = expected["minimum_branch_percent"]
    message = f"branch coverage: {measured:.2f}% (minimum: {floor:.2f}%)"
    return measured >= floor, message

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    passed, message = check(args.report, args.baseline)
    print(message)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
