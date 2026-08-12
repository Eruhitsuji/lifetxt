#!/usr/bin/env python
"""Report oversized source/test files as an informational review signal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_CLASSIFICATION = Path(
    "config/maintainability/oversized-file-classification-v1.json"
)


def report(root, classification_path):
    data = json.loads(classification_path.read_text(encoding="utf-8"))
    rows = []
    for entry in data["files"]:
        path = root / entry["path"]
        if not path.exists():
            rows.append({**entry, "status": "missing"})
            continue
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                **entry,
                "current_bytes": path.stat().st_size,
                "current_lines": len(text.splitlines()),
                "byte_delta": path.stat().st_size - entry["bytes"],
                "line_delta": len(text.splitlines()) - entry["lines"],
                "status": "review",
            }
        )
    return {
        "schema": "lifetxt-oversized-file-report-v1",
        "thresholds": {
            "bytes": data["review_threshold_bytes"],
            "lines": data["review_threshold_lines"],
        },
        "blocking": False,
        "classification_source": str(classification_path.relative_to(root)),
        "files": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--classification", default=DEFAULT_CLASSIFICATION, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    classification = args.classification
    if not classification.is_absolute():
        classification = root / classification
    result = report(root, classification)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "files": len(result["files"]), "blocking": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
