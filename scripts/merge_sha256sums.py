#!/usr/bin/env python
"""Merge one or more SHA256SUMS-format files into one de-duplicated manifest.

`release.yml` and `standalone-binaries.yml` each publish a GitHub Release
asset literally named `SHA256SUMS`, generated independently (wheel/sdist in
one, the five platform binaries in the other) and previously uploaded with
`gh release upload ... --clobber`. Whichever workflow ran last silently
replaced the other's `SHA256SUMS` asset instead of merging with it, so the
published manifest never actually covered every downloadable release file at
once. See issue #583.

Usage (as used by both workflows' `github-release` job, in priority order --
a later input's entry wins over an earlier input's entry for a colliding
filename):

    python scripts/merge_sha256sums.py \\
        --output SHA256SUMS \\
        existing-SHA256SUMS dist-evidence/SHA256SUMS

A missing input file is skipped rather than treated as an error, since the
caller does not know in advance whether a previous workflow run has already
published a SHA256SUMS asset for this release.
"""

from __future__ import print_function

import argparse
import sys
from collections import OrderedDict
from pathlib import Path


def parse_sha256sums(text):
    """Parse ``<hash>  <filename>`` lines into an ordered ``(hash, filename)`` list.

    Blank lines are skipped. Any run of whitespace between the hash and the
    filename is accepted, matching both this repository's own two-space
    generator convention and plain `sha256sum` output. A line that does not
    split into exactly a hash and a filename is rejected rather than
    silently dropped, since a truncated or corrupted upstream file should
    fail loudly rather than merge a partial manifest.
    """
    entries = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(
                "Line %d does not look like '<hash>  <filename>': %r"
                % (lineno, raw_line)
            )
        digest, filename = parts
        entries.append((digest, filename.strip()))
    return entries


def merge_entries(*entry_lists):
    """Merge several ``(hash, filename)`` lists into one, sorted by filename.

    A later list's entry for a given filename overrides an earlier list's
    entry for the same filename, so the caller controls precedence by
    ordering its inputs. Sorting the result makes the merged manifest
    deterministic and reviewable regardless of upload order.
    """
    by_filename = OrderedDict()
    for entries in entry_lists:
        for digest, filename in entries:
            by_filename[filename] = digest
    return sorted(by_filename.items(), key=lambda pair: pair[0])


def render_sha256sums(entries):
    return "".join("%s  %s\n" % (digest, filename) for filename, digest in entries)


def merge_files(paths):
    """Read every existing path in ``paths`` and return its merged entries.

    Returns ``(entries, files_found)``; ``files_found`` lets the caller
    distinguish "every input was missing" from "every input was present but
    empty" without a second filesystem check.
    """
    entry_lists = []
    files_found = 0
    for path in paths:
        candidate = Path(path)
        if not candidate.is_file():
            continue
        files_found += 1
        entry_lists.append(parse_sha256sums(candidate.read_text(encoding="utf-8")))
    return merge_entries(*entry_lists), files_found


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help=(
            "SHA256SUMS-format files to merge, in priority order (a later "
            "file's entry wins over an earlier file's entry for the same "
            "filename). A missing input file is skipped, not an error."
        ),
    )
    parser.add_argument(
        "--output", required=True, help="Path to write the merged SHA256SUMS to"
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        merged, files_found = merge_files(args.inputs)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if files_found == 0:
        print(
            "None of the given input files exist; nothing to merge.",
            file=sys.stderr,
        )
        return 1
    Path(args.output).write_text(
        render_sha256sums(merged), encoding="utf-8", newline="\n"
    )
    print("OK: wrote %d checksum entries to %s" % (len(merged), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
