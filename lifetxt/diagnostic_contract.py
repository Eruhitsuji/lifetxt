"""Stable diagnostic JSON contract shared by CLI, Web, and MCP surfaces."""

from __future__ import unicode_literals

from collections import OrderedDict
from typing import Any, Dict, Iterable, List


DIAGNOSTIC_CATEGORIES = (
    "syntax",
    "schema",
    "style",
    "time",
    "status",
    "message",
    "id",
    "reference",
    "recurrence",
    "duration",
    "workflow",
    "files",
    "semantic",
)


def diagnostic_category(diagnostic: Any) -> str:
    code = str(getattr(diagnostic, "code", "") or "").upper()
    if code.startswith("E0"):
        return "syntax"
    if code in ("E101", "E102"):
        return "schema"
    if code in ("E201", "E202", "E203", "E204", "W207", "W208", "W209"):
        return "status"
    if code in ("E205", "E206", "W210", "W211", "W212"):
        return "message"
    if code in ("W105", "W106"):
        return "style"
    if code in ("W201", "W202", "W203", "W204", "W206"):
        return "time"
    if code in ("W205", "W219", "W223"):
        return "recurrence"
    if code in ("W213", "W214"):
        return "id"
    if code in ("W215", "W216", "W217", "W218", "W227", "W228", "W229"):
        return "reference"
    if code in ("W101", "W102", "W103", "W104", "W224"):
        return "workflow"
    if code in ("W222", "W226"):
        return "duration"
    if code in ("W401", "W402", "W403", "W404", "W405", "W407"):
        return "files"
    return "semantic"


def diagnostic_to_output_dict(diagnostic: Any) -> Dict[str, Any]:
    data = diagnostic.to_dict()
    output = OrderedDict()
    for key, value in data.items():
        output[key] = value
        if key == "code":
            output["category"] = diagnostic_category(diagnostic)
    return output


def diagnostics_to_output(diagnostics: Iterable[Any]) -> List[Dict[str, Any]]:
    return [diagnostic_to_output_dict(diagnostic) for diagnostic in diagnostics]
