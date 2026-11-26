"""Compare shared behavior and explicit compatibility gaps with Python Core."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

from lifetxt.model import DATETIME_KEYS, DATE_KEYS, DATE_OR_DATETIME_KEYS, TIME_OR_DATETIME_KEYS
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
    "E025": "detail-expects-text",
    "W005": "unknown-escape",
    "W201": "invalid-date",
    "W202": "invalid-datetime",
    "W203": "invalid-date-or-datetime",
    "W204": "invalid-time-or-datetime",
    "W206": "event-end-before-start",
    "W220": "indent-no-parent",
    "W221": "indent-parent-no-id",
}


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    core: tuple[tuple[str, str, int, int | None], ...] = ()
    # None derives the JS expectations from the mapped Core codes.
    js: tuple[tuple[str, str, int], ...] | None = None
    same_items: bool = True
    temporal_keys: tuple[str, ...] = ()

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
            temporal_keys=("due", "on", "from", "at"),
        ),
        Case(
            "date values must be text with one error per field",
            '[ ] T title due:json<< ["invalid", null, 1] >> on:json<< "2024-02-29" >>',
            core=(("error", "E025", 1, None),),
            temporal_keys=("due",),
        ),
        Case(
            "repeat values are each checked, while malformed item syntax suppresses format warnings",
            "[ ] T title due:2024-02-29 due:1900-02-29 due:2024-04-31\n"
            "[ ] T malformed due:invalid body:a body:b\n| ambiguous",
            core=(("warning", "W203", 1, None), ("warning", "W203", 1, None),
                  ("error", "E022", 3, 1)),
            temporal_keys=("due", "due"),
        ),
        Case(
            "event end is earlier by one microsecond",
            "[ ] E title from:2026-12-01T09:00:00.000002 to:2026-12-01T09:00:00.000001",
            core=(("warning", "W206", 1, None),),
            temporal_keys=("to",),
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
            temporal_keys=("to",),
        ),
        Case(
            "wrong temporal value type suppresses the range warning",
            "[ ] E title from:2026-12-01T09:00 to:json<< [\"2026-12-01T08:00\",null] >>",
            core=(("error", "E025", 1, None),),
            temporal_keys=("to",),
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
            temporal_keys=("on",),
        ),
        Case(
            "invalid requires expression",
            "[ ] T title requires:bad()\n",
            core=(("error", "E024", 1, None),),
            js=(),
        ),
        Case(
            "duplicate ID",
            "[ ] T one id:duplicate\n[ ] T two id:duplicate\n",
            core=(("warning", "W213", 2, None),),
            js=(),
        ),
        Case(
            "unresolved parent",
            "[ ] T child parent:missing\n",
            core=(("warning", "W215", 1, None),),
            js=(),
        ),
    ] + [
        Case(
            f"temporal key group: {key}",
            f"{'[x]' if key == 'done' else '[ ]'} T title {key}:invalid",
            core=(("warning", code, 1, None),),
            temporal_keys=(key,),
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
                        Case(f"{zone}: mixed offsets", mixed, core=expected, temporal_keys=keys),
                        Case(f"{zone}: fall-back hour", fold, core=expected, temporal_keys=keys),
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
                    case.temporal_keys,
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
