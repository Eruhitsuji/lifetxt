# Decisions and evidence limits

2026-10-24 Owner approved performing steps 1-3: runtime/source relationship,
notices and source acquisition. #1409 separates this follow-up from merged
#1407 under one Issue/branch/PR. Scope additions for the local-only checker
builder and source_probe.py are recorded in the Issue. No publication inferred.

Official core release SHA256 matches GitHub release metadata and all five npm
runtime bytes match exactly. CPython original source matches recipe SHA256;
zlib/bzip2 archive SHA512s match Emscripten port recipes. All nine CPython patches
apply with --fuzz=0. All 567 regular stdlib files are classified: 535 CPython,
29 Pyodide, 2 upstream-patched CPython and 1 generated Python config already
present as source in the shipped ZIP. There are no unexplained stdlib files in
this bounded probe. It does not map every linked WASM object or prove a signed/
reproducible upstream build.

Seven new notice documents bring the retained inventory to 23. The HACL/decimal
aggregates preserve distinct complete leading licence comments from 40/41 files;
full source archives preserve other per-file notices. The upstream CPython
incorporated-software document itself states that its list is incomplete.
Remaining Unicode-data and whole-WASM licence/attribution evaluation remains
explicit. No compiler/library removal or binary rebuilding was performed.

MPL source access can use an appropriate upstream location; self-hosting is an
operational choice. Both delivery modes are labelled, availability was tested,
and hosting continuity remains an operator/reviewer responsibility. Mozilla MPL
2.0 sections 3.1/3.2 and official FAQ are interpretation references, not a legal
approval of this artifact. complete_distribution_audit/public_distribution_approved
remain false; the publication command still fails after integrity succeeds.

A stale intermediate artifact was rejected after metadata changed. Fresh current
builds were then audited; the stale artifact was not reported as a pass. All
raw local transient logs remain local; retained evidence contains source/member
paths and hashes, never user records or host filesystem paths.
