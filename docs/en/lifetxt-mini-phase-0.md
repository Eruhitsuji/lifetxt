# lifetxt-mini Phase 0 contract and spike decision

> Historical decision record for Issue #894 / PR #895. This records the Phase
> 0 design state and is not the current product specification. See
> lifetxt-mini/README.md for current usage.

## Current status after Phases 1 E

Later issues resolved the open Phase 0 decisions:

| Decision | Current outcome |
| --- | --- |
| Runtime/toolchain | Rust + std |
| Repository layout | lifetxt-mini/ in this repository |
| Official OS and architectures | Linux x86_64 and Linux AArch64 |
| Release targets | x86_64-unknown-linux-musl and aarch64-unknown-linux-musl |
| Mutation model | Source-preserving atomic replacement with stale-source protection |
| Daily-use command | Bounded today --date YYYY-MM-DD |
| Distribution | Tagged GitHub Release artifacts with SHA-256 checksums |
| Version identity | Core, Mini, and repository release use one version |

The current command surface is list, show, Mini-profile check, add, done, and
today --date YYYY-MM-DD. The Mini runtime remains a strict subset of Python
Core. See lifetxt-mini-distribution.md for current installation guidance.

Status: design/spike evidence for Issue #894. The Python Core remains the
reference implementation.

## Decision

**PROCEED WITH CHANGES.** Keep the native runtime optional and begin Phase 1
with the narrow profile below, Rust + `std` first, x86_64 Linux first, and
source-preserving mutation. Phase 0 does not justify hard resource CI gates
until a Linux builder produces repeatable measurements.

## Normative Mini-1 profile

| Area | Supported/writable | Preserved or rejected |
| --- | --- | --- |
| status | `[ ]`, `[x]`, `[N]` | other markers are opaque; never rewritten |
| type | `T`, `E`, `N` | all other record types are opaque |
| keys | `id`, `due`, `on`, `from`, `to`, `project`, `tag` | unknown and repeated keys are preserved verbatim |
| values | quoted titles/values and UTF-8 | malformed quoting is an error, not normalization |
| layout | comments, blank lines, continuation/body lines, LF or CRLF | no canonical whole-file serialization |
| input | explicit path, then documented default `life.txt` in Phase 1 | stdin is deferred |
| identity | exact `id:` selector; duplicate IDs are an error | fuzzy/title selection is unsupported |
| errors | malformed supported syntax fails closed | unsupported valid records remain opaque |

The writable grammar is a strict subset of the existing life.txt Beginner
Profile. There is no mini-only persisted syntax and no new data model.

## Preservation architecture

The document is represented as an ordered sequence of source spans: supported
record spans, opaque record spans, comments, blanks, and body/continuation
spans. A bounded mutation replaces only the status-marker bytes in the
selected supported span. The PoC fixture and unit test demonstrate the
observable contract: the task line changes from `[ ]` to `[x]`; the unsupported
Habit, Journal, custom key, comment, blank line, and body remain byte-for-byte
unchanged. Known limitations are duplicate-ID handling and line-ending edge
cases, both Phase 1 work.

## Toolchain and platforms

Rust is selected over C and Go for memory safety around source spans, a small
dependency surface, and practical cross compilation. The PoC uses only `std`.
The repository layout is the existing repository under `lifetxt-mini/`, so
fixtures, Core conformance, release automation, and traceability remain
together.

At the time of this Phase 0 record, x86_64 Linux was the Phase 1 target and
AArch64 was deferred. That sequencing is superseded: the current official
support boundary is Linux x86_64 and Linux AArch64, with static musl release
targets and native execution checks. ARMv7 remains unsupported. Static musl is
now the established release direction.

## Measurements

The statements in this section are historical Phase 0 observations. Phase 4
release CI now records final artifact size, linkage, startup/RSS evidence,
target triple, and toolchain. Those later measurements do not rewrite what was
known during the spike, and remain evidence rather than permanent hard gates.

The reproducible commands are in `lifetxt-mini/README.md`. This Windows host
does not provide a Linux, musl, or Docker builder, so Linux binary size,
dependency, startup, and RSS values are intentionally **not claimed** by this
spike. At the time, the planned Phase 1 work was to record the actual stripped size, `ldd` result, startup
method, peak RSS, target triple, and toolchain before setting budgets. The
aspirational `<2 MiB` binary / `<5 MiB` RSS values therefore remain goals, not
requirements.

## Conformance plan

Phase 1/2 should share fixtures for: minimal task/event/note, quoted values,
Japanese/Unicode, custom and repeated keys, comments/blanks, multiline body,
mixed supported/unsupported records, and preservation regression. Every
mini-generated supported fixture must pass `python -m lifetxt check`; every
Core Beginner Profile fixture must produce the same supported interpretation
in mini. Differences in presentation are allowed, differences in persisted
meaning are not.

## Phase 1 entry recommendation (historical)

Proceed with changes: keep the profile narrow, add a real path resolver and
strict parser, add Linux CI measurement, and make duplicate IDs / malformed
input fail closed before adding user-facing commands. Do not begin `list`,
`show`, `add`, or broad format parity in this Phase 0 change.
