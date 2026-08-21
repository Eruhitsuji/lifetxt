# Format 1.0 Finalization Review

This is the bounded release-contract review required by
[#454](https://github.com/Eruhitsuji/lifetxt/issues/454) before Stable 1.0. It
confirms that the documented Format 1.0 contract matches the implemented
parser and canonical serializer. It is a review record, not a new
implementation phase; any concrete defect found is filed as its own Issue
rather than fixed inline here.

## Review scope

Per #454, this review confirms:

1. the user-visible Format 1.0 grammar/version semantics match the
   implemented parser and canonical serializer;
2. unsupported newer format versions fail safely before mutation;
3. Format 1.0 migration/downgrade behavior is documented sufficiently for the
   first stable release;
4. Format 1.0 canonical round-trip/idempotency regression tests pass;
5. the human release decision that Format 1.0 is the compatibility baseline
   for Stable 1.0.

## 1. Grammar and version semantics match documentation

[`lifetxt/parser.py`](../../lifetxt/parser.py) declares `FORMAT_VERSION = "1"`
and classifies every parsed document into exactly one of three states based on
the `#! format_version:` directive:

| Directive | `format_version_state` |
| --- | --- |
| absent | `unversioned` |
| equal to `"1"` | `current` |
| any other value | `unsupported` |

This matches the version matrix in
[Format 1.0 compatibility matrix](format-compatibility-matrix.md): an
unversioned document is legacy input eligible for lossless migration, a
`format_version: 1` document is the current writable version, and any other
declared value (below 1, above 1, or non-numeric) is unsupported until a
mapping is explicitly approved. `ParseResult` exposes `format_version` and
`format_version_state` while remaining tuple-compatible with every existing
`(items, diagnostics)` caller
(`tests/test_parser_format_metadata.py::ParserFormatMetadataTests::test_result_remains_tuple_compatible`).

Canonical serialization is pinned separately by `LIFETXT_CANON_V1`
(`lifetxt/release_policy.py`, `tests/golden/policy-v1.json`), confirmed
idempotent by the golden corpus
(`tests/test_roundtrip_golden.py::GoldenRoundTripTests::test_canonical_output_is_idempotent`).
Format-version state and canonical-output state are independent contracts;
this review confirms both are internally consistent with each other and with
their respective documents.

**Result: confirmed, no drift found.**

## 2. Unsupported versions fail safely before mutation

`format migrate` (`lifetxt/extra_safety.py`, `action == "migrate"`) checks
`version["state"] == "unsupported"` before computing or writing any
replacement text. On an unsupported source it returns
`{"action": "refuse", "changed": False, "written": False}` and a non-zero
exit; `write_text` is never called on that path, so the authoritative file is
provably unmutated on refusal
(`tests/test_lifetxt.py`, `docs/en/format-migration.md`: "a document declaring
an unsupported version is rejected without writing").

`format downgrade` never writes at all: `writable` is hardcoded `False` in
every response, whether or not the requested target is supported
(`lifetxt/extra_safety.py`, `action == "downgrade"`). A requested downgrade
target other than the current version reports
`losses: ["No Format 1.0 downgrade mapping is defined."]` and a failing exit
code, matching the version matrix's "no writable downgrade" classification.

`format canon --write` and `format migrate --write` both route through the
existing revision-checked `write_text(..., expected_hash=snapshot.content_hash)`
contract, so even a permitted write is compare-and-swap against the
last-read revision, not an unconditional overwrite.

**Result: confirmed. No code path mutates the authoritative file for an
unsupported source or an unsupported downgrade target.**

## 3. Migration/downgrade documentation is sufficient for Stable 1.0

[Format 1.0 Migration Boundary](format-migration.md) and the
[Format 1.0 compatibility matrix](format-compatibility-matrix.md) together
state, in user-facing terms:

- the one supported, lossless write transition (unversioned to
  `format_version: 1`);
- that a current-version document is a no-op;
- that legacy-below-1, unknown, and future versions are refused before write;
- that `format downgrade` is inspection-only and defines no mapping today;
- the five-gate approval process (fixtures, deterministic preview with loss
  categories, refusal-before-write proof, revision/backup/recovery/idempotency
  definition, maintainer approval) required before any future legacy mapping
  or writable downgrade is added.

This is sufficient for a first stable release: it tells an operator exactly
what will and will not be rewritten today, and it does not promise a mapping
that does not exist. No documentation gap was found during this review.

**Result: confirmed.**

## 4. Canonical round-trip / idempotency regression coverage passes

Executed on this review's branch:

```text
python -m unittest tests.test_roundtrip_golden tests.test_randomized_roundtrip tests.test_parser_format_metadata
```

Result: `Ran 19 tests ... OK` (golden corpus idempotency, deterministic
randomized-fixture round-trip at `random.Random(358)`, and format-version
metadata coverage all passed with no failures or errors).

**Result: confirmed, evidence recorded.**

## 5. Human release decision

Items 1-4 above are investigation and are confirmed by this review. Recording
Format 1.0 as the accepted compatibility baseline for Stable 1.0 is a human
release-authority decision per #454's task contract ("Human approval:
required for final Format 1.0 baseline confirmation") and is tracked
separately as the sign-off on this document rather than asserted by the
review itself.

- [x] Format 1.0 is confirmed as the Stable 1.0 compatibility baseline
      (release authority sign-off, recorded here or on #454).

**Decision: approved.** Format 1.0, as reviewed in sections 1-4 above, is
accepted by the repository owner (Eruhitsuji) as the Stable 1.0 compatibility
baseline, based on the finalization evidence recorded in
[PR #455](https://github.com/Eruhitsuji/lifetxt/pull/455). Recorded
2026-08-21 in [#457](https://github.com/Eruhitsuji/lifetxt/issues/457) and
linked from [#454](https://github.com/Eruhitsuji/lifetxt/issues/454).

## Defects found during this review

None. If a future review finds a concrete grammar, parser, or documentation
mismatch, file it as its own dedicated Issue rather than expanding this
document's scope.
