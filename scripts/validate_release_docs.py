#!/usr/bin/env python
"""Validate bounded release-document links and safe CLI help examples."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


DOCS = (
    "cli.md",
    "config.md",
    "release-baselines.md",
    "release-compatibility-policy.md",
    "release-policy-gates.md",
    "release-safety-foundations.md",
    "release-artifact-evidence.md",
    "remote.md",
    "remote-compatibility.md",
    "transaction-recovery-and-strict-timers.md",
    "timezone-revision-workspace-safety.md",
    "public-surface-revisions.md",
)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
COMMAND_RE = re.compile(r"^\s*python -m lifetxt ([a-z][a-z-]*)\b")


def slug(text):
    text = unicodedata.normalize("NFKC", text).replace("`", "")
    text = re.sub(r"[^\w -]", "", text, flags=re.UNICODE).lower().replace(" ", "-")
    return re.sub(r"-+", "-", text).strip("-")


def anchors(text):
    return {slug(match.group(1)) for match in HEADING_RE.finditer(text)}


def validate_docs(root):
    docs_root = root / "docs" / "en"
    errors = []
    checked_links = 0
    commands = set()
    for name in DOCS:
        path = docs_root / name
        if not path.exists():
            errors.append(
                {"document": name, "error": "missing release-critical document"}
            )
            continue
        text = path.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = unquote(raw)
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            checked_links += 1
            relative = parsed.path
            target_path = path.parent / relative if relative else path
            if not target_path.exists():
                errors.append(
                    {"document": name, "target": raw, "error": "missing link target"}
                )
                continue
            if parsed.fragment and parsed.fragment not in anchors(
                target_path.read_text(encoding="utf-8")
            ):
                errors.append(
                    {"document": name, "target": raw, "error": "missing anchor"}
                )
        for line in text.splitlines():
            match = COMMAND_RE.match(line)
            if match:
                commands.add(match.group(1))
    command_results = []
    for command in sorted(commands):
        result = subprocess.run(
            [sys.executable, "-m", "lifetxt", command, "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        command_results.append({"command": command, "returncode": result.returncode})
        if result.returncode:
            errors.append({"command": command, "error": "help command failed"})
    return {
        "schema": "lifetxt-release-doc-validation-v1",
        "documents": list(DOCS),
        "checked_internal_links": checked_links,
        "checked_cli_help_commands": command_results,
        "external_or_sensitive_examples": "not executed",
        "errors": errors,
        "ok": not errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = validate_docs(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"ok": report["ok"], "errors": len(report["errors"])}, sort_keys=True
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
