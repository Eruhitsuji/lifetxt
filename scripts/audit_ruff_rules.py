#!/usr/bin/env python
"""Measure candidate Ruff rule families without changing source files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path


RULE_GROUPS = {
    "pycodestyle-correctness": ["E4", "E7", "E9"],
    "pyflakes": ["F"],
    "modernization": ["UP"],
    "simplification": ["SIM"],
    "bugbear": ["B"],
    "ruff-specific": ["RUF"],
}


def audit(root):
    root = Path(root).resolve()
    results = []
    for name, rules in RULE_GROUPS.items():
        command = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "lifetxt",
            "tests",
            "scripts",
            "--select",
            ",".join(rules),
            "--output-format",
            "json",
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode not in (0, 1):
            raise RuntimeError(completed.stderr.strip() or "Ruff audit failed")
        findings = json.loads(completed.stdout or "[]")
        counts = Counter(item["code"] for item in findings)
        results.append(
            {
                "group": name,
                "rules": rules,
                "finding_count": len(findings),
                "codes": dict(sorted(counts.items())),
            }
        )
    return {
        "schema": "lifetxt-ruff-rule-audit-v1",
        "audit_date": date.today().isoformat(),
        "command_scope": ["lifetxt", "tests", "scripts"],
        "results": results,
        "recommendation": {
            "first_batch": ["E741"],
            "reason": "Nine ambiguous-variable findings are bounded and reviewable.",
            "defer": [
                "E4",
                "E731",
                "UP",
                "SIM",
                "B",
                "RUF",
            ],
            "defer_reason": "Current finding volume or import/behavior risk is too high for a stabilization batch.",
        },
        "limitations": [
            "The audit is read-only and does not apply Ruff fixes.",
            "Counts are a point-in-time snapshot and include existing repository findings.",
            "A later implementation issue must review each E741 finding before enabling it as a gate.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"ok": True, "audit_date": evidence["audit_date"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
