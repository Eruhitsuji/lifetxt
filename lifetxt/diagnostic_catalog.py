"""Human-readable explanation catalog for a bounded, explicitly documented
set of `lifetxt check` diagnostic codes (#641): what the code means, why it
fires, how to fix it, and a valid/invalid example where one is useful.

The code itself, its `category` (from `lifetxt/diagnostic_contract.py`,
never duplicated here), and its `severity` (derived from the `E`/`W`
prefix every diagnostic code already follows) remain locale-independent
machine identity, exactly like `check --format json`'s existing stable
fields. Only the human-facing `summary` text is registered with the
locale catalog (`lifetxt/i18n.py`) in this first slice; `remediation` text
is sourced from the same `PARSER_DIAGNOSTIC_HINTS`/
`VALIDATOR_DIAGNOSTIC_HINTS` dictionaries `check`'s own `hint` field
already uses (English-only today, matching that existing, documented
limitation -- see docs/en/cli.md's Localization section) rather than a
second, hand-duplicated remediation registry.

This module owns explanation metadata only. It never re-implements a
parsing or validation rule, and adding an entry here can never change what
`check` accepts, flags, or how it exits.

First slice: the parser/validator codes a Beginner Profile user is most
likely to hit (`E001`-`E005`, `E010`), plus three commonly-seen validator/
other-producer codes explicitly named as examples in the originating
issue (`W106`, `W207`, `W213`, `W225`). An unbounded, code-by-code lookup
against every stable code in the system is an explicit non-goal of this
first slice; codes with no catalog entry raise `ValueError` naming the
documented set rather than guessing a near-match.
"""

from __future__ import unicode_literals

import json
from collections import OrderedDict

from .diagnostic_contract import diagnostic_category
from .i18n import register_messages, translate as _t
from .parser import PARSER_DIAGNOSTIC_HINTS
from .validator import VALIDATOR_DIAGNOSTIC_HINTS


class _CodeOnly(object):
    """Minimal `.code`-only stand-in so `diagnostic_category()` -- which
    only ever reads `.code` off its argument -- can be reused here without
    constructing a real `Diagnostic`."""

    __slots__ = ("code",)

    def __init__(self, code):
        self.code = code


def category_for_code(code):
    return diagnostic_category(_CodeOnly(code))


def severity_for_code(code):
    normalized = str(code or "").upper()
    if normalized.startswith("E"):
        return "error"
    if normalized.startswith("W"):
        return "warning"
    return ""


#: code -> {"examples": (str, ...), "remediation": str (only when no
#: existing parser/validator hint covers it)}. `summary` text lives in the
#: locale catalog below, keyed by message id `diagnostic.<code>.summary`.
_CATALOG_ENTRIES = OrderedDict(
    (
        ("E001", {"examples": ()}),
        ("E002", {"examples": ()}),
        (
            "E003",
            {
                "examples": (
                    'Invalid: [X] T "Write report"',
                    'Valid:   [x] T "Write report"',
                )
            },
        ),
        ("E004", {"examples": ()}),
        (
            "E005",
            {
                "examples": (
                    'Invalid: [ ] Z "Write report"',
                    'Valid:   [ ] T "Write report"',
                )
            },
        ),
        (
            "E010",
            {
                "examples": (
                    "Invalid: [ ] T Title key value",
                    "Valid:   [ ] T Title key:value",
                )
            },
        ),
        ("W101", {"examples": ()}),
        ("W102", {"examples": ()}),
        (
            "W103",
            {
                "examples": (
                    'Invalid: [x] T "Buy milk"',
                    'Valid:   [x] T "Buy milk" done:2026-01-01',
                )
            },
        ),
        (
            "W106",
            {
                "examples": (
                    "Typo:   priorty:high",
                    "Fixed:  priority:high",
                )
            },
        ),
        (
            "W207",
            {
                "examples": (
                    "Typo:   state:buzy",
                    "Fixed:  state:busy",
                )
            },
        ),
        (
            "W213",
            {
                "remediation": "Give each item a unique id:, or intentionally scope duplicate ids to a single source file.",
                "examples": (
                    "Duplicate: id:task_001 (twice)",
                    "Fixed:     id:task_001 / id:task_002",
                ),
            },
        ),
        (
            "W225",
            {
                "remediation": (
                    "To resolve W225, either (1) close children manually, "
                    "(2) run archive --orphan-children adopt, or "
                    "(3) run archive --orphan-children promote."
                ),
                "examples": (),
            },
        ),
    )
)

register_messages(
    {
        "diagnostic.E001.summary": {
            "en": "A tab character was used where a single space separator is required.",
            "ja": "single space の区切りが必要な箇所で tab 文字が使われています。",
        },
        "diagnostic.E002.summary": {
            "en": "The line does not start with a valid status marker such as [ ].",
            "ja": "行が [ ] のような valid な status marker で始まっていません。",
        },
        "diagnostic.E003.summary": {
            "en": "The item's status marker is not one of the supported Format 1.0 status tokens.",
            "ja": "item の status marker が、対応している Format 1.0 の status token のいずれでもありません。",
        },
        "diagnostic.E004.summary": {
            "en": "The status marker is not followed by an item type letter.",
            "ja": "status marker の直後に item type の文字がありません。",
        },
        "diagnostic.E005.summary": {
            "en": "The item type letter is not one of the supported Format 1.0 types.",
            "ja": "item type の文字が、対応している Format 1.0 の type のいずれでもありません。",
        },
        "diagnostic.E010.summary": {
            "en": "A detail after the title is not written in key:value form.",
            "ja": "title の後の detail が key:value の形式で書かれていません。",
        },
        "diagnostic.W101.summary": {
            "en": "The [N] status is recommended only for note (N) or journal (J) items.",
            "ja": "[N] status は note（N）または journal（J）の item にのみ推奨されます。",
        },
        "diagnostic.W102.summary": {
            "en": "Note (N) and journal (J) items are recommended to use status [N].",
            "ja": "note（N）と journal（J）の item は status [N] の使用が推奨されます。",
        },
        "diagnostic.W103.summary": {
            "en": "A completed item ([x]) has no done: date recording when it finished.",
            "ja": "completed（[x]）の item に、完了日を記録する done: がありません。",
        },
        "diagnostic.W106.summary": {
            "en": "This detail key is not a known or recommended key for the item's type; it is kept as custom data.",
            "ja": "この detail key は、その item type の known/recommended key ではありません。custom data としてそのまま保持されます。",
        },
        "diagnostic.W207.summary": {
            "en": "The state: value is not one of the commonly used presence states.",
            "ja": "state: の値が、一般的に使われる presence state のいずれでもありません。",
        },
        "diagnostic.W213.summary": {
            "en": "Two items share the same id: value within the same id namespace.",
            "ja": "同じ id namespace 内で、2つの item が同じ id: 値を共有しています。",
        },
        "diagnostic.W225.summary": {
            "en": "A completed or canceled parent item still has open (unfinished) children.",
            "ja": "completed または canceled の parent item に、まだ open（未完了）の child が残っています。",
        },
        "diagnostic.catalog_hint": {
            "en": "Run `lifetxt help diagnostic CODE` for details on any code above.",
            "ja": "上記いずれかの code の詳細は `lifetxt help diagnostic CODE` で確認できます。",
        },
    }
)


def known_codes():
    """Every diagnostic code this catalog documents, in a stable order."""
    return list(_CATALOG_ENTRIES.keys())


def _remediation_for(code):
    entry = _CATALOG_ENTRIES[code]
    remediation = entry.get("remediation")
    if remediation is not None:
        return remediation
    return (
        PARSER_DIAGNOSTIC_HINTS.get(code) or VALIDATOR_DIAGNOSTIC_HINTS.get(code) or ""
    )


def explain_record(code):
    """One code's full explanation as an `OrderedDict`, or raise
    `ValueError` naming the documented set when `code` is not cataloged.

    Never guesses a near-match for an unrecognized code -- an unknown code
    is reported as unknown, not silently mapped to the closest documented
    one.
    """
    normalized = str(code or "").strip().upper()
    entry = _CATALOG_ENTRIES.get(normalized)
    if entry is None:
        raise ValueError(
            "Unknown diagnostic code: %r. Documented codes: %s."
            % (code, ", ".join(known_codes()))
        )
    return OrderedDict(
        (
            ("code", normalized),
            ("category", category_for_code(normalized)),
            ("severity", severity_for_code(normalized)),
            ("summary", _t("diagnostic.%s.summary" % normalized)),
            ("remediation", _remediation_for(normalized)),
            ("examples", list(entry.get("examples", ()))),
        )
    )


def _dumps(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_code_text(code):
    record = explain_record(code)
    lines = [
        "%s — %s" % (record["code"], record["summary"]),
        "Category: %s" % record["category"],
        "Severity: %s" % record["severity"],
    ]
    if record["remediation"]:
        lines.append("")
        lines.append("Remediation:")
        lines.append("  %s" % record["remediation"])
    if record["examples"]:
        lines.append("")
        lines.append("Example:")
        for example in record["examples"]:
            lines.append("  %s" % example)
    return "\n".join(lines) + "\n"


def render_code_json(code):
    record = explain_record(code)
    record = OrderedDict(record)
    record["schema"] = "lifetxt-diagnostic-explain-v1"
    record.move_to_end("schema", last=False)
    return _dumps(record)


def overview_payload():
    return OrderedDict(
        (
            ("schema", "lifetxt-diagnostic-catalog-v1"),
            (
                "codes",
                [
                    OrderedDict(
                        (
                            ("code", code),
                            ("category", category_for_code(code)),
                            ("severity", severity_for_code(code)),
                            ("summary", _t("diagnostic.%s.summary" % code)),
                        )
                    )
                    for code in known_codes()
                ],
            ),
        )
    )


def render_overview_text():
    lines = ["Documented diagnostic codes:", ""]
    for code in known_codes():
        lines.append("  %-6s %s" % (code, _t("diagnostic.%s.summary" % code)))
    lines.append("")
    lines.append(_t("diagnostic.catalog_hint"))
    return "\n".join(lines) + "\n"


def render_overview_json():
    return _dumps(overview_payload())
