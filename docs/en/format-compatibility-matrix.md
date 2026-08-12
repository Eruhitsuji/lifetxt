# Format 1.0 Compatibility Matrix

This is the compatibility decision for the first stable release. It describes
what the current build may inspect or write; it does not infer support from an
unrecognized file.

## Version matrix

| Source declaration | `format check` | `format migrate` | `format downgrade` | Stable classification |
| --- | --- | --- | --- | --- |
| No `format_version` directive | inspect as legacy input | add `#! format_version: 1` with `--write` | not applicable | supported, lossless migration |
| `format_version: 1` | inspect | explicit no-op | inspection-only if a target is requested | current writable version |
| Declared legacy version below 1 | inspect/refuse according to parser diagnostics | refuse before write | inspection-only | no automatic mapping |
| Declared future or unknown version | inspect/refuse according to parser diagnostics | refuse before write | inspection-only | unsupported until a newer mapping is approved |
| Requested downgrade from 1.0 | inspect and report no mapping | not a migration path | report inspection-only | no writable downgrade |

The only stable write transition is an unversioned document to Format 1.0.
Legacy versions and downgrade targets must not be rewritten, even when the
content appears simple enough to transform. The refusal must happen before
the authoritative file is mutated.

## Loss categories

Any future mapping must report these stable category names for every affected
field or directive:

| Category | Meaning | Example |
| --- | --- | --- |
| `fields` | A field is removed, renamed, or changes type | a legacy priority field has no Format 1.0 representation |
| `directives` | A header/directive is removed or changes semantics | an unknown `#!` directive cannot be preserved as a stable directive |
| `repeated_values` | Repetition or ordering changes | repeated tags collapse into one value |
| `unicode_newline` | Encoding, Unicode normalization, or newline bytes change | CRLF is normalized to LF or a non-NFC value is rewritten |
| `write_semantics` | The operation changes mutation, revision, or recovery behavior | a conversion cannot preserve the revision-checked write contract |

An empty loss report is required for a lossless mapping. A non-empty report is
not automatically acceptable: it requires an explicit lossy-migration policy,
representative fixtures, user-visible preview output, and maintainer approval.

## Approval and implementation gate

Before adding any legacy mapping or writable downgrade:

1. Identify the source and target version and add fixtures covering valid,
   malformed, repeated, Unicode, and newline cases.
2. Produce a deterministic preview containing the source hash, target version,
   loss categories, and proposed output hash.
3. Prove refusal-before-write for unsupported and declined mappings.
4. Define revision, backup, recovery, and idempotency behavior.
5. Obtain explicit maintainer approval for the compatibility policy and update
   this matrix, the release support matrix, and traceability metadata in the
   same change.

Until all five gates are complete, the mapping remains inspection-only. This
document therefore intentionally creates no follow-up implementation promise
for an undocumented legacy version.
