# lifetxt-mini

lifetxt-mini is a Python-free standalone Linux runtime and a strict subset of
the life.txt Format. It provides source-preserving bounded read and write
operations for small or offline systems. Python lifetxt remains the
full/reference implementation; Mini is not a replacement and does not define
a second persisted format.

## Current commands

    lifetxt-mini --help
    lifetxt-mini --version
    lifetxt-mini list path/to/life.txt
    lifetxt-mini show --id=t1 path/to/life.txt
    lifetxt-mini check path/to/life.txt
    lifetxt-mini add "Buy milk" --type task path/to/life.txt
    lifetxt-mini done --id=t1 path/to/life.txt
    lifetxt-mini today --date 2026-09-24 path/to/life.txt

check reports Mini-profile semantics, not full Core validation. show and done
use exact canonical id: selection. add supports the Mini Task, Event, and Note
subset and the documented date/project/tag details. today requires an explicit
ISO date and uses only bounded due, on, and from rules; completed records are
excluded. Unsupported Core arguments are rejected instead of silently weakened.

Mini understands [ ], [x], and [N] records of types T, E, and N. Unknown or
repeated details and unsupported Full Format records remain source-backed or
opaque and are not guessed into Mini semantics. Japanese and other UTF-8 text
are preserved.

## Input and mutation safety

Input resolution is: explicit path, then LIFETXT_FILE, then ./life.txt.
Read-only commands do not modify the input. add and done write a sibling
temporary file, flush and sync it, then atomically replace the source. They
preserve Unix mode where practical, reject symbolic-link mutation targets,
detect a source changed since read, clean temporary files after failures where
possible, and preserve unrelated bytes outside the intentional insertion or
status span.

## Version and support

Core CLI version, lifetxt-mini version, and repository release version are the
same. The Mini build receives the canonical version from pyproject.toml. Same
version does not mean the same feature set: Python Core remains broader.

Official Mini release support is Linux x86_64 and Linux AArch64, using
static-musl-oriented artifacts. Installation, architecture selection,
checksums, and GitHub Release details are in
docs/en/lifetxt-mini-distribution.md and
docs/ja/lifetxt-mini-distribution.md.

The Phase 0 design record is historical evidence, not the current product
specification. See docs/en/lifetxt-mini-phase-0.md for the original reasoning
and its current-status notes.
