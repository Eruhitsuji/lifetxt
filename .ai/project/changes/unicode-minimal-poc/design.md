# Unicode-minimal CPython source-only PoC design

## Summary

Create a reproducible isolated candidate from the pinned HKSCS-free CPython
source used in the historical profile2 artifact. This does not produce a
buildable or reviewed runtime, and never modifies profile1/profile2.

## Interfaces and Contracts

- ADDED: `python -m contrib.browser_check_poc.unicode_minimal SOURCE OUTPUT`
  reads a source tar.gz whose SHA-256 must match the recorded curated
  CPython input and writes to a previously nonexistent separate output path.
- ADDED: deterministic sorted tar members/metadata, reported input and output
  SHA-256, removed-source digest, and remaining internal codec candidate list.
- MODIFIED: none of the actual lifetxt parser, JS Worker or site.
- REMOVED: only in the experimental new tar; mapping source files, CJK codec
  implementation and generated tables, and nonallowlisted encoding wrappers
  and aliases. The original pinned archives are unchanged.

## Alternatives

Independently accept the already located ICU data grant without rebuilding;
or exclude only GB18030 and retain other legacy codecs. The Owner chose an
experimental UTF-8-first minimal candidate to assess longer-term scope.

## Risks

- A removed source file does **not** prove that a compiled WASM is free of
  derived tables. A new Setup.local/build/object/WASM/stdlib proof is required.
- The candidate codec allowlist is intentionally unverified against Pyodide's
  full import graph, and may need expansion during future compile/boot tests.
- Archive processing is deliberately fail-closed for SHA mismatch, unexpected
  names, duplicates, nonregular members and existing destination.
- Third-party Unicode data may still remain; licence clearance is a separate
  review and must not be inferred from this experiment.

## Operations Impact

No deployment, repository runtime pin changes, data migrations or
externally served artifacts. Undo by reverting this PR. Experimental tar
outputs remain out of git.

## Compatibility Impact

No current checker behavior change. Follow-on work: #1436 actual profile3
runtime; #1437 checker integration, full source/manifest and browser tests.
Owner-reviewed distribution and Pages approval remain in #1398/#1400.
