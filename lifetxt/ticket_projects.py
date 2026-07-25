"""Shared read-only ticket/project reporting and standalone CLI."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from .ticket_project_report import build_ticket_project_report
from .ticket_project_values import (
    DEFAULT_HIGH_SEVERITIES, DEFAULT_STALE_DAYS, DEFAULT_TERMINAL_STATUSES,
    REPORT_SCHEMA, parse_datetime, parse_duration_hours, ticket_is_terminal,
)

__all__ = [
    "REPORT_SCHEMA", "build_ticket_project_report", "format_attention",
    "format_board", "format_summary", "parse_datetime",
    "parse_duration_hours", "ticket_is_terminal",
]


def _extract_items(parsed: Any) -> List[Any]:
    if parsed is None:
        return []
    if isinstance(parsed, tuple):
        for part in parsed:
            if isinstance(part, list):
                return part
    if isinstance(parsed, list):
        return parsed
    for name in ("items", "records"):
        value = getattr(parsed, name, None)
        if isinstance(value, list):
            return value
    try:
        return list(parsed)
    except TypeError as exc:
        raise ValueError("Unsupported parse_text result shape: {0}".format(exc))


def load_items(paths: Sequence[str]) -> List[Any]:
    try:
        from .parser import parse_text
    except ImportError:  # pragma: no cover
        from lifetxt.parser import parse_text
    items = []
    for raw_path in paths:
        parsed = parse_text(Path(raw_path).read_text(encoding="utf-8"))
        items.extend(_extract_items(parsed))
    return items


def format_summary(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Tickets: {total} total, {open} open, {terminal} terminal, {progress}% count progress".format(
            progress="-" if summary["progress_percent"] is None else summary["progress_percent"], **summary
        ),
        "Attention: {blocked} blocked, {dependency_unknown} dependency unknown, {overdue} overdue, "
        "{unassigned} unassigned, {high_severity} high severity, {stale} stale".format(**summary),
        "",
        "PROJECT | OPEN/TOTAL | PROGRESS | BLOCKED | DEP-UNKNOWN | OVERDUE | UNASSIGNED | HIGH | STALE",
    ]
    for project in report["projects"]:
        progress = "-" if project["progress_percent"] is None else "%.2f%%" % project["progress_percent"]
        lines.append(
            "{project} | {open}/{total} | {progress} | {blocked} | {dependency_unknown} | {overdue} | "
            "{unassigned} | {high_severity} | {stale}".format(progress=progress, **project)
        )
    return "\n".join(lines) + "\n"


def format_board(report: Mapping[str, Any]) -> str:
    lines = []
    for status, rows in report["board"].items():
        lines.append("## %s (%d)" % (status, len(rows)))
        for row in rows:
            due = " due:%s" % row["due"] if row["due"] else ""
            assignee = " assignee:%s" % row["assignee"] if row["assignee"] else " assignee:(unassigned)"
            lines.append("- [%s] %s — %s%s%s" % (row["id"] or "(no-id)", row["project"], row["title"], due, assignee))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_attention(report: Mapping[str, Any]) -> str:
    lines = []
    for category, rows in report["attention"].items():
        lines.append("## %s (%d)" % (category, len(rows)))
        lines.extend("- [%s] %s — %s" % (row["id"] or "(no-id)", row["project"], row["title"]) for row in rows)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m lifetxt.ticket_projects", description="Read-only ticket/project reports.")
    parser.add_argument("mode", choices=("summary", "board", "attention"))
    parser.add_argument("paths", nargs="+", metavar="life.txt")
    parser.add_argument("--project")
    parser.add_argument("--at", help="ISO reference date/datetime; defaults to now.")
    parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_DAYS, metavar="DAYS")
    parser.add_argument("--terminal-status", action="append", dest="terminal_statuses", help="Repeat to replace built-in terminal statuses.")
    parser.add_argument("--high-severity", action="append", dest="high_severities", help="Repeat to replace built-in high severities.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.stale_after < 0:
        raise ValueError("--stale-after must be zero or greater.")
    reference = parse_datetime(args.at) if args.at else None
    if args.at and reference is None:
        raise ValueError("--at must be an ISO date or datetime.")
    report = build_ticket_project_report(
        load_items(args.paths), reference_time=reference,
        stale_after_days=args.stale_after, project=args.project,
        terminal_statuses=args.terminal_statuses or DEFAULT_TERMINAL_STATUSES,
        high_severities=args.high_severities or DEFAULT_HIGH_SEVERITIES,
    )
    if args.format == "json":
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
    else:
        sys.stdout.write({"summary": format_summary, "board": format_board, "attention": format_attention}[args.mode](report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        raise SystemExit(1)
