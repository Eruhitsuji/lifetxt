"""Compare shared behavior and explicit compatibility gaps with Python Core."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from lifetxt.model import DATETIME_KEYS, DATE_KEYS, DATE_OR_DATETIME_KEYS, TIME_OR_DATETIME_KEYS
from lifetxt.model import REFERENCE_KEYS, STATUS_STATE_VALUES
from lifetxt.parser import parse_text


JS_CODES = {
    "E006": "json-detail-separator",
    "E010": "invalid-detail",
    "E018": "unclosed-quote",
    "E019": "orphan-body",
    "E020": "dangling-line-join",
    "E021": "line-join-into-body",
    "E022": "ambiguous-body",
    "E023": "invalid-json-detail",
    "E024": "invalid-requires",
    "E025": "detail-expects-text",
    "E201": "status-missing-from",
    "E202": "status-invalid-from",
    "E203": "status-missing-state",
    "E204": "status-invalid-to",
    "W005": "unknown-escape",
    "W201": "invalid-date",
    "W202": "invalid-datetime",
    "W203": "invalid-date-or-datetime",
    "W204": "invalid-time-or-datetime",
    "W205": "invalid-repeat",
    "W206": "event-end-before-start",
    "W207": "unknown-state",
    "W208": "status-closed-marker",
    "W209": "status-open-marker",
    "W213": "duplicate-id",
    "W214": "invalid-id",
    "W215": "missing-reference",
    "W216": "self-reference",
    "W217": "reference-cycle",
    "W218": "ambiguous-reference",
    "W219": "expected-positive-integer",
    "W220": "indent-no-parent",
    "W221": "indent-parent-no-id",
    "W223": "invalid-rrule",
    "W224": "completed-with-open-dependency",
    "W225": "closed-parent-with-open-children",
}


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    core: tuple[tuple[str, str, int, int | None], ...] = ()
    # None derives the JS expectations from the mapped Core codes.
    js: tuple[tuple[str, str, int], ...] | None = None
    same_items: bool = True
    diagnostic_keys: tuple[str, ...] = ()
    diagnostic_parts: tuple[str, ...] = ()
    duplicate_ids: tuple[tuple[str, int], ...] = ()
    reference_targets: tuple[str, ...] = ()
    cycle_paths: tuple[tuple[str, ...], ...] = ()
    child_counts: tuple[int, ...] = ()
    check_cli: bool = False

    def expected_js(self):
        if self.js is not None:
            return self.js
        return tuple(
            (severity, JS_CODES[code], line)
            for severity, code, line, _ in self.core
        )


def cases():
    return [
        Case(
            "official website sample",
            Path("website/example.txt").read_text(encoding="utf-8"),
        ),
        Case(
            "Unicode, CRLF, quotes, repeated details and body",
            '#! format_version: 1\r\n'
            '[ ] T "日本語😀 \\"引用\\"" tag:one tag:"two words" custom:ok\r\n'
            '[N] J Journal on:2026-11-07\r\n'
            '| Text\r\n'
            '| 続き\r\n',
            core=(("warning", "W106", 2, None),),
            js=(),
        ),
        Case(
            "malformed detail after a Unicode title",
            "# comment\n[ ] T 日本😀 tag=value\n[ ] T next\n",
            core=(("error", "E010", 2, 11),),
            same_items=False,
        ),
        Case(
            "unclosed title",
            '# comment\r\n[ ] T "bad\r\n[ ] T next\r\n',
            core=(("error", "E018", 2, 7),),
            same_items=False,
        ),
        Case(
            "orphan body",
            "# comment\n| orphan\n[ ] T next\n",
            core=(("error", "E019", 2, 1),),
        ),
        Case(
            "unknown quoted escape",
            '# comment\n[ ] T "\\q"\n',
            core=(("warning", "W005", 2, 8),),
        ),
        Case(
            "chained backslash joins with CRLF and a subsequent body line",
            '# comment\r\n[ ] T "long\\  \r\n  title" \\ \r\n'
            ' tag:one\r\n| body\r\n[ ] T next\r\n',
        ),
        Case(
            "dangling backslash before a final newline",
            "[ ] T title \\\n tag:one\\ \n",
            core=(("error", "E020", 2, 8),),
        ),
        Case(
            "backslash joins into a body line",
            "[ ] T title\\\n  |body\n[ ] T next\n",
            core=(("error", "E021", 2, 1),),
        ),
        Case(
            "multiline JSON object, tabs, quoted marker and following detail",
            '[ ] T title options:json<<\r\n\t{"note":"a >> b","nested":[1,true,null]}\r\n'
            '>> tag:after\r\n[ ] T next',
            core=(("warning", "W106", 1, None),),
            js=(),
        ),
        Case(
            "JSON top-level array, empty array and nested array",
            '[ ] T title tag:a tag:json<< ["b","c"] >> tag:d '
            'options:json<< [] >> map:json<< [["a"]] >>',
            core=(("warning", "W106", 1, None), ("warning", "W106", 1, None)),
            js=(),
        ),
        Case(
            "malformed JSON recovers at a following detail",
            '[ ] T title tag:json<<\n  ["inside >> string",]\n>> tag:after\n[ ] T next',
            core=(("error", "E023", 1, 17),),
        ),
        Case(
            "unclosed JSON recovers at the next item",
            '[ ] T title tag:json<<\n  ["inside >> string"]\n[ ] T next',
            core=(("error", "E023", 1, 17),),
        ),
        Case(
            "duplicate JSON key after escape decoding",
            '[ ] T title tag:json<< {"k":1,"\\u006b":2} >>',
            core=(("error", "E023", 1, 17),),
        ),
        Case(
            "non-finite JSON number",
            "[ ] T title tag:json<< 1e999 >>",
            core=(("error", "E023", 1, 17),),
        ),
        Case(
            "JSON marker literals",
            "[ ] T title tag:json<< tag:after\n[ ] T next tag:json<<",
        ),
        Case(
            "JSON with backslash line joins and a body line",
            '[ ] T title \\\n tag:json<<\n ["one"]\n >> \\\n tag:two\n| body',
        ),
        Case(
            "empty JSON body value list may be followed by a body line",
            "[ ] T title body:json<< [] >>\n| body",
        ),
        Case(
            "non-text JSON body cannot be followed by a body line",
            "[ ] T title body:json<< null >>\n| body",
            core=(("error", "E022", 2, 1),),
        ),
        Case(
            "nearest parent across comments, body lines, siblings and roots",
            "[ ] T Root id:root\n  [ ] T Child id:child\n    | child body\n"
            "# separator\n\n    [ ] T Grandchild\n  [ ] T Sibling\n"
            "[ ] T New id:new\n  [ ] T Child\n",
        ),
        Case(
            "explicit parent takes precedence and empty JSON parent can be inferred",
            "[N] N Other id:other\n[ ] T Parent id:parent\n"
            "  [ ] T Overrides parent:other\n"
            "  [ ] T Empty parent:json<< [] >> tag:keep\n",
        ),
        Case(
            "unavailable parent warnings and no fallback to a more distant ancestor",
            "  [ ] T Orphan\n[ ] T Root id:root\n"
            "  [ ] T WithoutId\n    [ ] T Grandchild\n  [ ] T Sibling\n",
            core=(("warning", "W220", 1, 3), ("warning", "W221", 4, 5)),
        ),
        Case(
            "valid leap dates and clock offsets in all supported shapes",
            "[ ] T title on:2000-02-29 from:0001-01-01T00:00Z "
            "to:9999-12-31T23:59:59.999999+2359 "
            "due:2024-02-29 at:23:59:59.1-00:30 at:2024-02-29T12:00\n",
        ),
        Case(
            "invalid calendar day, date-only and date-or-time distinctions",
            "[ ] T title due:2026-02-30 on:2024-02-29T12:00 "
            "from:2024-02-29 at:2024-02-29",
            core=(
                ("warning", "W203", 1, None), ("warning", "W201", 1, None),
                ("warning", "W202", 1, None), ("warning", "W204", 1, None),
            ),
            diagnostic_keys=("due", "on", "from", "at"),
        ),
        Case(
            "date values must be text with one error per field",
            '[ ] T title due:json<< ["invalid", null, 1] >> on:json<< "2024-02-29" >>',
            core=(("error", "E025", 1, None),),
            diagnostic_keys=("due",),
        ),
        Case(
            "repeat values are each checked, while malformed item syntax suppresses format warnings",
            "[ ] T title due:2024-02-29 due:1900-02-29 due:2024-04-31\n"
            "[ ] T malformed due:invalid body:a body:b\n| ambiguous",
            core=(("warning", "W203", 1, None), ("warning", "W203", 1, None),
                  ("error", "E022", 3, 1)),
            diagnostic_keys=("due", "due"),
        ),
        Case(
            "event end is earlier by one microsecond",
            "[ ] E title from:2026-12-01T09:00:00.000002 to:2026-12-01T09:00:00.000001",
            core=(("warning", "W206", 1, None),),
            diagnostic_keys=("to",),
        ),
        Case(
            "event compares the first endpoint values and accepts equal datetimes",
            "[ ] E title from:0001-01-01T00:00:00.0 "
            "to:0001-01-01T00:00 to:0001-01-01T00:00:00.000001",
        ),
        Case(
            "invalid event endpoint is reported without a range warning",
            "[ ] E title from:2026-12-01T09:00 to:2026-12-01T24:00",
            core=(("warning", "W202", 1, None),),
            diagnostic_keys=("to",),
        ),
        Case(
            "wrong temporal value type suppresses the range warning",
            "[ ] E title from:2026-12-01T09:00 to:json<< [\"2026-12-01T08:00\",null] >>",
            core=(("error", "E025", 1, None),),
            diagnostic_keys=("to",),
        ),
        Case(
            "valid simple repeats and explicit recurrence bounds",
            "[ ] T title repeat:daily repeat:weekly repeat:monthly repeat:yearly "
            "repeat:weekdays interval:+2 count:1_000 until:2026-12-31",
        ),
        Case(
            "valid RRULEs, last value for repeated parts and mixed-case part names",
            "[ ] E title repeat:RRULE:freq=yearly;BYMONTH=1,12;BYDAY=-1fr;BYMONTHDAY=-1,31;"
            "WKST=su;INTERVAL=2;COUNT=4;UNTIL=20281231T235959Z "
            "repeat:RRULE:FREQ=HOURLY;FREQ=WEEKLY;BYDAY=MO,TU;UNTIL=20281231T235959+0900",
        ),
        Case(
            "invalid simple recurrence, interval and count",
            "[ ] T title repeat:Daily repeat:rrule:FREQ=DAILY interval:0 count:2.5",
            core=(("warning", "W205", 1, None), ("warning", "W205", 1, None),
                  ("warning", "W219", 1, None), ("warning", "W219", 1, None)),
            diagnostic_keys=("repeat", "repeat", "interval", "count"),
        ),
        Case(
            "non-text recurrence fields report one error per key",
            '[ ] T title repeat:json<< ["invalid",null] >> interval:json<< 2 >> '
            'count:json<< true >>',
            core=(("error", "E025", 1, None),) * 3,
            diagnostic_keys=("repeat", "interval", "count"),
        ),
        Case(
            "RRULE primary warnings retain Core's order and suppress fallback checks",
            "[ ] E title repeat:RRULE:FREQ=HOURLY;X=1;Z=2;COUNT=0;INTERVAL=-1;"
            "UNTIL=20260230;BYDAY=2MO;BYMONTH=13;JUNK",
            core=(("warning", "W223", 1, None),) * 6,
            diagnostic_keys=("repeat",) * 6,
            diagnostic_parts=("FREQ", "KEY", "INTERVAL", "COUNT", "UNTIL", "BYDAY"),
        ),
        Case(
            "short and nested JSON requirements with known reference targets",
            '[ ] T Review id:review\n[ ] T Materials id:materials\n'
            '[ ] T Submit requires:review=in_progress,done requires:"materials=[ ]" '
            'requires:json<< {"all":[{"id":"review","state":["done","[?]"]},'
            '{"any":["materials=not_started","review=[x]"]}]} >>\n',
        ),
        Case(
            "invalid requires value reports one error per value in order",
            '[ ] T Submit requires:bad() requires:=done requires:review=done, '
            'requires:json<< [true,{"id":42,"state":"done"},{"id":"a\\u0085b","state":"done"},'
            '{"id":"a","state":[]},{"id":"a","state":"done","extra":true},{"any":[]}] >>\n',
            core=(("error", "E024", 1, None),) * 9,
            diagnostic_keys=("requires",) * 9,
            diagnostic_parts=("shape", "id", "state", "shape", "id", "id", "state", "shape", "shape"),
        ),
        Case(
            "requires group reports only its first invalid child",
            '[ ] T Submit requires:json<< {"any":["=done","review=unknown"]} >>',
            core=(("error", "E024", 1, None),),
            diagnostic_keys=("requires",),
            diagnostic_parts=("id",),
        ),
        Case(
            "allows 32 nested requires groups",
            '[ ] T Review id:review\n[ ] T Submit requires:json<< '
            + '{"all":[' * 32 + '"review=done"' + ']}' * 32 + ' >>',
        ),
        Case(
            "rejects 33 nested requires groups",
            '[ ] T Submit requires:json<< '
            + '{"any":[' * 33 + '"review=done"' + ']}' * 33 + ' >>',
            core=(("error", "E024", 1, None),),
            diagnostic_keys=("requires",),
            diagnostic_parts=("depth",),
        ),
        Case(
            "compact ID syntax and Core trailing LF behavior",
            '[ ] T title id:Cal.1@host/path:code_2-test id:9 '
            'id:json<< "legacy\\n" >>',
        ),
        Case(
            "invalid ID characters, position and empty values",
            '[ ] T title id:_leading id:"has space" id:日本語 id:"" id:""',
            core=(("warning", "W214", 1, None),) * 5,
            diagnostic_keys=("id",) * 5,
        ),
        Case(
            "duplicate IDs in original order and subsequent items",
            "[ ] T one id:Example id:example id:Example id:other\n"
            "[ ] T two id:other id:Example\n",
            core=(("warning", "W213", 1, None), ("warning", "W213", 2, None),
                  ("warning", "W213", 2, None)),
            diagnostic_keys=("id",) * 3,
            duplicate_ids=(("Example", 1), ("other", 1), ("Example", 1)),
        ),
        Case(
            "only one non-text ID error per field",
            '[ ] T title id:json<< [1,null,"has space"] >>',
            core=(("error", "E025", 1, None),),
            diagnostic_keys=("id",),
        ),
        # These expectations document gaps for the staged Core-compatible checker.
        Case(
            "JSON integer outside JavaScript's safe integer range",
            "[ ] T title options:json<< 9007199254740993 >>",
            core=(("warning", "W106", 1, None),),
            js=(("unsupported", "json-integer-precision", 1),),
            same_items=False,
        ),
        Case(
            "non-ASCII digits accepted by Core outside the documented date format",
            "[ ] T title on:２０２４-02-29",
            js=(("warning", "invalid-date", 1),),
            diagnostic_keys=("on",),
        ),
        Case(
            "Core also indexes truthy non-text IDs after reporting a type error",
            "[ ] T One id:json<< true >>\n[ ] T Two id:True",
            core=(("error", "E025", 1, None), ("warning", "W213", 2, None)),
            js=(("error", "detail-expects-text", 1),),
            diagnostic_keys=("id",),
        ),
        Case(
            "regular and requires references are reported in separate passes",
            "[ ] T Lookup id:lookup requires:missing=done ref:unknown\n"
            "[ ] T Target id:dup id:dup\n"
            '[ ] T Source id:source ref:dup related:source '
            'requires:json<< {"any":["dup=done","dup=maybe","source=done"]} >>\n',
            core=(("warning", "W213", 2, None), ("warning", "W215", 1, None),
                  ("warning", "W218", 3, None), ("warning", "W216", 3, None),
                  ("warning", "W215", 1, None), ("warning", "W218", 3, None),
                  ("warning", "W216", 3, None)),
            diagnostic_keys=("id", "ref", "ref", "related", "requires", "requires", "requires"),
            duplicate_ids=(("dup", 2),),
            reference_targets=("unknown", "dup", "source", "missing", "dup", "source"),
        ),
        Case(
            "all standard reference keys use Core's order and exact ID matching",
            "[ ] T Target id:Known\n[ ] T Source "
            + " ".join(f"{key}:known" for key in reversed(REFERENCE_KEYS)),
            core=(("warning", "W106", 2, None),) * 4
                 + (("warning", "W215", 2, None),) * len(REFERENCE_KEYS),
            js=(("warning", "missing-reference", 2),) * len(REFERENCE_KEYS),
            diagnostic_keys=REFERENCE_KEYS,
            reference_targets=("known",) * len(REFERENCE_KEYS),
        ),
        Case(
            "invalid reference token still participates in string lookup",
            '[ ] T Source parent:"has space"\n[ ] T Target id:"has space"',
            core=(("warning", "W214", 1, None), ("warning", "W214", 2, None)),
            js=(("warning", "invalid-reference-id", 1), ("warning", "invalid-id", 2)),
            diagnostic_keys=("parent", "id"),
        ),
        Case(
            "cycles in all supported graphs, including inverse blocks",
            "[ ] T A id:a parent:b depends_on:b blocks:b duplicate_of:b "
            "replaced_by:b follows:b realizes:b\n"
            "[ ] T B id:b parent:a duplicate_of:a replaced_by:a follows:a realizes:a",
            core=(("warning", "W106", 1, None),) * 4
                 + (("warning", "W106", 2, None),) * 4
                 + tuple(("warning", code, 1, None)
                         for code in ("W217", "W227", "W228", "W229", "W230", "W231")),
            js=(("warning", "reference-cycle", 1),) * 6,
            diagnostic_keys=("parent", "depends_on", "duplicate_of", "replaced_by", "follows", "realizes"),
            cycle_paths=(("a", "b", "a"),) * 6,
        ),
        Case(
            "ambiguous IDs do not form a cycle",
            "[ ] T A id:a parent:b\n[ ] T B id:b parent:a\n[ ] T Copy id:b",
            core=(("warning", "W213", 3, None), ("warning", "W218", 1, None)),
            diagnostic_keys=("id", "parent"),
            duplicate_ids=(("b", 2),),
            reference_targets=("b",),
        ),
        Case(
            "inferred parent closes a cycle before requires diagnostics",
            "[ ] T A id:a parent:b requires:missing=done\n  [ ] T B id:b",
            core=(("warning", "W217", 1, None), ("warning", "W215", 1, None)),
            diagnostic_keys=("parent", "requires"),
            reference_targets=("missing",),
            cycle_paths=(("a", "b", "a"),),
        ),
        Case(
            "temporal reference warnings run in Core order and use authored dates",
            "[ ] T Old id:old on:2026-10-10\n"
            "[ ] T Replacement id:replacement on:2026-10-07\n"
            "[ ] T Source id:source due:2026-10-08T23:30-11:00 "
            "do:2026-10-15 follows:old replaced_by:replacement",
            core=(("warning", "W106", 3, None), ("warning", "W106", 3, None),
                  ("warning", "W244", 3, None), ("warning", "W244", 3, None)),
            js=(("warning", "temporal-reference-order", 3),) * 2,
            diagnostic_keys=("replaced_by", "follows"),
            reference_targets=("replacement", "old"),
        ),
        Case(
            "invalid first value falls back to the next temporal field",
            "[ ] T Old id:old from:2026-10-09T00:00Z\n"
            "[ ] T New id:new due:invalid due:2026-10-12 do:2026-10-08 follows:old",
            core=(("warning", "W203", 2, None), ("warning", "W106", 2, None),
                  ("warning", "W244", 2, None)),
            js=(("warning", "invalid-date-or-datetime", 2),
                ("warning", "temporal-reference-order", 2)),
            diagnostic_keys=("due", "follows"),
            reference_targets=("old",),
        ),
        Case(
            "same authored dates remain comparable as equal across offsets",
            "[ ] T Old id:old due:2026-10-09T00:00+14:00\n"
            "[ ] T New id:new due:2026-10-09T23:59-10:00 replaced_by:old",
            core=(("warning", "W106", 2, None),),
            js=(),
        ),
        Case(
            "completed item has open prerequisites and explicit and inferred children",
            "[x] T Parent id:p done:2026-10-01 depends_on:child requires:missing=done\n"
            "  [/] T Child id:child\n"
            "[?] T Other parent:p\n[x] T ClosedChild parent:p done:2026-10-01",
            core=(("warning", "W224", 1, None), ("warning", "W215", 1, None),
                  ("warning", "W225", 1, None)),
            diagnostic_keys=("depends_on", "requires", "id"),
            reference_targets=("child", "missing", "p"),
            child_counts=(2,),
            check_cli=True,
        ),
        Case(
            "ambiguous prerequisite and last matching parent",
            "[ ] T Old id:p\n[-] T Last id:p\n"
            "[x] T Done done:2026-10-01 depends_on:p\n[>] T Child parent:p",
            core=(("warning", "W213", 2, None), ("warning", "W218", 3, None),
                  ("warning", "W218", 4, None), ("warning", "W225", 2, None)),
            diagnostic_keys=("id", "depends_on", "parent", "id"),
            duplicate_ids=(("p", 1),),
            reference_targets=("p", "p", "p"),
            child_counts=(1,),
            check_cli=True,
        ),
        Case(
            "resolved closed prerequisite and closed children are accepted",
            "[x] T Parent id:p done:2026-10-01 depends_on:child\n"
            "  [-] T Child id:child\n  [N] N Note",
            check_cli=True,
        ),
        Case(
            "status items accept every known state and open or closed markers",
            "\n".join(f"[/] S Working from:2026-10-01T09:00+0900 state:{value}"
                      for value in STATUS_STATE_VALUES)
            + "\n[x] S Done from:2026-10-01T09:00 to:2026-10-01T10:00 state:custom",
        ),
        Case(
            "status item missing required details and marker",
            "[ ] S Missing",
            core=(("error", "E201", 1, None), ("error", "E203", 1, None),
                  ("warning", "W209", 1, None)),
            diagnostic_keys=("from", "state", "to"),
        ),
        Case(
            "status datetime warnings precede strict errors",
            "[/] S Working from:2026-10-01 from:no to:invalid state:unknown",
            core=tuple((severity, code, 1, None) for severity, code in (
                ("warning", "W202"), ("warning", "W202"), ("warning", "W202"),
                ("warning", "W207"), ("error", "E202"), ("error", "E202"),
                ("error", "E204"), ("warning", "W208"),
            )),
            diagnostic_keys=("from", "from", "to", "state", "from", "from", "to", "to"),
        ),
        Case(
            "status type error suppresses its item-level checks",
            "[ ] S Wrong state:json<< 3 >>",
            core=(("error", "E025", 1, None),),
            diagnostic_keys=("state",),
        ),
        Case(
            "status checks use key presence for empty JSON value lists",
            "[x] S Empty from:json<< [] >> to:json<< [] >> state:json<< [] >>",
        ),
        Case(
            "non-text reference produces a type error and is not resolved in JS",
            '[ ] T Source ref:json<< [null,"missing"] >>',
            core=(("error", "E025", 1, None), ("warning", "W215", 1, None),
                  ("warning", "W215", 1, None)),
            js=(("error", "detail-expects-text", 1), ("warning", "missing-reference", 1)),
            diagnostic_keys=("ref", "ref"),
            reference_targets=("missing",),
        ),
    ] + [
        Case(
            f"invalid RRULE: {rule}",
            f"[ ] E title repeat:RRULE:{rule}",
            core=(("warning", "W223", 1, None),),
            diagnostic_keys=("repeat",),
            diagnostic_parts=(part,),
        )
        for rule, part in (
            ("COUNT=2", "FREQ"),
            ("FREQ=MONTHLY;BYDAY=2XX", "BYDAY"),
            ("FREQ=MONTHLY;BYDAY=MO,", "BYDAY"),
            ("FREQ=MONTHLY;BYDAY=0MO", "BYDAY"),
            ("FREQ=MONTHLY;BYDAY=xxMO", "BYDAY"),
            ("FREQ=WEEKLY;BYDAY=MO;BYMONTHDAY=1", "BYMONTHDAY"),
            ("FREQ=MONTHLY;BYMONTHDAY=-32", "BYMONTHDAY"),
            ("FREQ=MONTHLY;BYMONTH=13", "BYMONTH"),
            ("FREQ=MONTHLY;BYMONTH=", "BYMONTH"),
            ("FREQ=WEEKLY;WKST=XX", "WKST"),
            ("FREQ=MONTHLY;JUNK", "KEY=VALUE"),
            ("FREQ=DAILY;UNTIL=2026-02-28t01:00", "UNTIL"),
        )
    ] + [
        Case(
            f"temporal key group: {key}",
            f"{'[x]' if key == 'done' else '[ ]'} T title {key}:invalid",
            core=(("warning", code, 1, None),),
            diagnostic_keys=(key,),
        )
        for keys, code in (
            (DATE_KEYS, "W201"),
            (DATETIME_KEYS, "W202"),
            (DATE_OR_DATETIME_KEYS, "W203"),
            (TIME_OR_DATETIME_KEYS, "W204"),
        )
        for key in keys
    ]


def parse_js(inputs):
    run = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import {readFileSync} from 'node:fs';"
            "import {parse} from './contrib/lifetxt-js-check/parser.mjs';"
            "console.log(JSON.stringify(JSON.parse(readFileSync(0, 'utf8')).map(parse)));",
        ],
        input=json.dumps(inputs),
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    )
    return json.loads(run.stdout)


class CoreComparisonTests(unittest.TestCase):
    def test_records_and_diagnostics(self):
        self.check_cases(cases())

    @unittest.skipUnless(hasattr(time, "tzset"), "requires a configurable local timezone")
    def test_event_ranges_use_core_local_wall_clock(self):
        # The same input has different ordering in UTC and during the New York
        # fall-back hour. Scope the timezone change to these fixtures.
        mixed = "[ ] E title from:2026-02-01T08:00 to:2026-02-01T12:30Z"
        fold = "[ ] E title from:2026-11-01T01:55:00.000001-0400 to:2026-11-01T01:10-05:00"
        equal = "[ ] E title from:2026-02-01T09:00+0900 to:2026-02-01T00:00Z"
        for zone in ("UTC", "America/New_York"):
            expected = (("warning", "W206", 1, None),) if zone == "America/New_York" else ()
            keys = ("to",) if expected else ()
            try:
                with patch.dict(os.environ, {"TZ": zone}):
                    time.tzset()
                    self.check_cases([
                        Case(f"{zone}: mixed offsets", mixed, core=expected, diagnostic_keys=keys),
                        Case(f"{zone}: fall-back hour", fold, core=expected, diagnostic_keys=keys),
                        Case(f"{zone}: equal instants", equal),
                    ])
            finally:
                time.tzset()

    def check_cases(self, fixtures):
        js_results = parse_js([case.text for case in fixtures])
        self.assertEqual(len(js_results), len(fixtures))
        for case, js in zip(fixtures, js_results, strict=True):
            core, diagnostics = parse_text(case.text)
            core_diagnostics = tuple(
                (d.severity, d.code, d.line, d.column) for d in diagnostics
            )
            if case.check_cli:
                # The full CLI adds W225 and initializes legacy compatibility
                # hooks. Run it separately from the direct Core fixtures.
                run = subprocess.run(
                    [sys.executable, "-m", "lifetxt", "check", "--no-files", "--format", "json", "-"],
                    input=case.text, capture_output=True, encoding="utf-8", check=True,
                )
                core_diagnostics = tuple(
                    (d["severity"], d["code"], d.get("line"), d.get("column"))
                    for d in json.loads(run.stdout)
                )
            js_diagnostics = tuple(
                (d["severity"], d["code"], d["line"]) for d in js["diagnostics"]
            )
            expected_js = case.expected_js()
            expected_items = [
                {
                    "line": item.line,
                    "indent": item.indent,
                    "status": item.status,
                    "type": item.kind,
                    "title": item.title,
                    "details": [[key, values] for key, values in item.details.items()],
                }
                for item in core
            ]
            with self.subTest(case=case.name, check="Python Core diagnostics"):
                self.assertEqual(core_diagnostics, case.core)
            with self.subTest(case=case.name, check="JS diagnostics"):
                self.assertEqual(js_diagnostics, expected_js)
                self.assertEqual(
                    tuple(d["key"] for d in js["diagnostics"] if "key" in d),
                    case.diagnostic_keys,
                )
                self.assertEqual(
                    tuple(d["part"] for d in js["diagnostics"] if "part" in d),
                    case.diagnostic_parts,
                )
                self.assertEqual(
                    tuple((d["value"], d["firstLine"]) for d in js["diagnostics"]
                          if "firstLine" in d),
                    case.duplicate_ids,
                )
                self.assertEqual(
                    tuple(d["value"] for d in js["diagnostics"]
                          if "value" in d and "firstLine" not in d),
                    case.reference_targets,
                )
                self.assertEqual(
                    tuple(tuple(d["path"]) for d in js["diagnostics"] if "path" in d),
                    case.cycle_paths,
                )
                self.assertEqual(
                    tuple(d["childCount"] for d in js["diagnostics"] if "childCount" in d),
                    case.child_counts,
                )
                self.assertEqual(js["diagnosticCount"], len(expected_js))
                severities = {severity for severity, _, _ in expected_js}
                self.assertEqual(js["hasErrors"], "error" in severities)
                self.assertEqual(js["incomplete"], "unsupported" in severities)
            with self.subTest(case=case.name, check="parsed records"):
                if case.same_items:
                    self.assertEqual(js["items"], expected_items)
                else:
                    self.assertNotEqual(
                        js["items"], expected_items, "Remove the resolved record gap."
                    )


if __name__ == "__main__":
    unittest.main()
