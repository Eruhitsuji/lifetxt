"""Compare record syntax in the documented JS/Python Core intersection."""

import json
from pathlib import Path
import subprocess

from lifetxt.parser import parse_text


def main():
    sample = Path("website/example.txt").read_text(encoding="utf-8")
    shared = (
        '#! format_version: 1\n'
        '[ ] T "日本語😀 \\"引用\\"" tag:one tag:"two words" custom:ok\n'
        '[N] J Journal on:2026-11-07\n'
        '| Text\n'
        '| 続き\n'
    )
    inputs = [sample, shared]
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
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    for text, js in zip(inputs, json.loads(run.stdout), strict=True):
        core, diagnostics = parse_text(text)
        if any(d.severity == "error" for d in diagnostics):
            raise SystemExit("Reference fixture is invalid in Core")
        expected = [
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
        if js["items"] != expected or js["hasErrors"] or js["incomplete"]:
            raise SystemExit(f"Shared syntax diverges: {js!r} != {expected!r}")
    print("Core/JS shared syntax matches both fixtures")


if __name__ == "__main__":
    main()
