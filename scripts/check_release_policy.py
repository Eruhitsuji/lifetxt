#!/usr/bin/env python
"""Run the full release policy and emit a machine-readable manifest."""

from __future__ import print_function

import argparse
import json
import os
import sys


def build_parser():
    parser = argparse.ArgumentParser(description="Validate lifetxt release policy gates.")
    parser.add_argument("paths", nargs="*", help="Optional life.txt examples to validate.")
    parser.add_argument("--root", help="Repository root. Defaults to the parent of scripts/.")
    parser.add_argument("--output", help="Write the manifest to this path as JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--allow-missing-jsonschema",
        action="store_true",
        help="Run the dependency-free subset instead of failing when jsonschema is absent.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = os.path.abspath(
        args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if root not in sys.path:
        sys.path.insert(0, root)
    from lifetxt.release_policy import release_manifest

    manifest = release_manifest(
        root,
        paths=args.paths,
        require_validator=not args.allow_missing_jsonschema,
    )
    text = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=args.pretty,
    ) + "\n"
    if args.output:
        directory = os.path.dirname(os.path.abspath(args.output))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    sys.stdout.write(text)
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
