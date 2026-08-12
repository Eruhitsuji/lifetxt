# Stable compatibility policy

This policy defines what lifetxt promises after the first stable release. It
does not promote an experimental surface or change an existing contract. The
authoritative release metadata is `.ai/project/STABLE_RELEASE.yml` under
`stable_release.compatibility_policy`.

## Versioning

The current `0.y.z` line is development software. It is not covered by the
stable compatibility promise, although compatibility-impacting changes still
need release notes and tests.

The first stable release is `1.0.0`:

- Patch releases (`1.0.z`) contain compatible fixes, security fixes, and
  documentation corrections.
- Minor releases (`1.y.0`) preserve existing stable contracts and may add
  backward-compatible commands, fields, or capabilities.
- A major release may remove or alter a stable contract only after the
  deprecation and migration process below has completed.

The package version is the version of the installed lifetxt distribution. A
life.txt format version, canonical serialization version, schema version, and
Remote/MCP protocol version are separate contracts and must not be inferred
from the package version alone.

## Covered contracts

The compatibility promise covers the following when the stable support matrix
classifies the surface as `supported`:

- life.txt format and declared `format_version` behavior;
- `LIFETXT_CANON_V1` canonical serialization rules;
- CLI command names, flags, output modes, and exit semantics;
- versioned machine-readable schemas, capability documents, and diagnostic
  codes;
- configuration keys, types, defaults, and documented migration behavior; and
- read-only client surfaces, including Remote and MCP resources, once their
  required release evidence is recorded.

Stable support does not mean that every implementation detail is frozen. Human
readable diagnostic prose, terminal layout, colors, glyphs, interactive
presentation, Web visual layout, and non-contractual accessibility wording are
not byte-stable unless a separate contract says otherwise.

## Deprecation lifecycle

1. **Announce.** Release notes and the relevant English and Japanese
   documentation identify the deprecated contract and link its replacement or
   migration path.
2. **Warn.** The supported behavior emits a stable diagnostic or warning when
   the deprecated path is used. The warning must not expose secrets or change a
   successful result merely because it is present.
3. **Remove.** Removal or incompatible change occurs only in a later major
   release after at least one minor release has carried the deprecation.

The deprecation record must state the affected contract, first release carrying
the warning, replacement or migration, and planned removal major version.

## Unsafe compatibility changes

A security or data-loss risk may require shortening the normal deprecation
lifecycle. The responsible Issue and release notes must explain the risk,
affected contracts, mitigation or migration, and required human approval. This
exception is for reducing unsafe exposure, not for avoiding compatibility work
or simplifying an implementation.

## Excluded surfaces

Experimental, deferred, and unsupported surfaces are outside the stable
compatibility promise until the support matrix is explicitly changed and the
required evidence is recorded. In particular, Remote and MCP write operations
must not be advertised as stable merely because an implementation exists.

Release notes must list compatibility-impacting changes, migrations, known
limitations, and the support classification of affected surfaces. Upgrade and
downgrade guidance must link this policy and the relevant format, schema,
configuration, policy, or journal migration documentation.
