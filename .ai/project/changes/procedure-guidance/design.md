# Phase 0 design record

Reviewable contract: [English](../../../../docs/en/procedure-guidance-design.md)
and [日本語](../../../../docs/ja/procedure-guidance-design.md).

No product capability is implemented. req-procedure-guidance-v1 and
cap-procedure-guidance remain proposed. Global registries are outside #1333's
scope; downstream implementation contracts must include their updates.

Discovery / Requirements / Architecture; adaptive-default / W-model.
Review: semantic boundaries, legacy warnings, alternatives, exact revisions,
single domain-event authority, privacy, bounds, termination and task size.
Tests: current check/parser/interchange now; later graph/transition/concurrency/
browser acceptance in the bilingual matrix. Coding: no production code or new
dependencies. Security: data only, no automatic effects or secret payload copies.
Operations: no release/migration; docs-only revert.

Branch docs/1333-procedure-contract from origin/main at change.yml base commit;
one Issue/branch/PR into main, no integration branch. Children #1334–#1343
follow approval and #1333 merge, retaining individual Ready/dependency gates.
Generic sequential implementation authorization does not approve unseen schema
choices. Owner/reviewer/merge authority Eruhitsuji; executor Codex.
