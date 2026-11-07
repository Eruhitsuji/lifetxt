# #1528 independent review remediation

Original review: https://github.com/Eruhitsuji/lifetxt/issues/1434#issuecomment-6699468862
Original merged head: b98e3935afd3c6eea435acf0c3451a08a14cbfd0.

Phase: implementation → developer verification → independent review. Bug / High / S.
Requirement req-browser-local-check-distribution-v1; reuse cap-official-website.
Write scope is the existing isolated source-only curator/tests/docs/package and narrow
shared traceability entry. No profile1/2 or Core/website/Pages changes.

## Review and test viewpoints

Implementation/security: bounded tar including extension-header expansion, immutable
hashed snapshot, no arbitrary public pin override, no-clobber atomic publication,
malformed paths/types/aliases, encoding subtree boundaries and fixed output receipt.
Integration: original source-only contract, unchanged codec allowlist and source/runtime
locks; independent review limited to original head must not approve the correction.
Coding: focused helpers and project ruff checks. Operations: hard-link unsupported
filesystems fail without partial target; rollback is revert this correction PR.

## Findings addressed

P2-1: regression cases for traversal, absolute/foreign/backslash path, duplicate,
hardlink/symlink/device/FIFO/root file, non-gzip, malformed aliases and missing codec.
P2-2: compressed/member/count/expanded budgets with streaming input hash and private
snapshot. The expanded stream cap also bounds tar extension headers/padding.
P2-3: production fixed input plus count/removal digest/output hash checks before
publication; reject non-Python/nested encoding subtree members. No ineffective assert.
P3: atomic no-clobber publication and cleanup, retained-file hashes, ruff formatting,
SHA responsibility documentation and historical conditional review/merge record.
cp437 runtime necessity is explicitly deferred to #1436 without changing this allowlist.

## Developer verification

Python 3.12 / Bash. Initial expanded suite: 14 tests, 1 ERROR because the test helper
failed to include gzip.BadGzipFile in expected rejection types. Full traceback retained
locally in .unicode-tests.log during diagnosis; corrected expected exception class.
No product acceptance was inferred from that error. No concurrent tree mutation during
runs. BashCompletionExecutionTests is outside these focused suites.

Final results are recorded in the PR/Issue. Actual curated source, historical counts
and output hash reproduction, SDK/build/object/WASM/browser/license review: NOT RUN.
Historical receipt is enforced fail-closed, not independently substantiated by this PR.
New correction needs independent Implementation/Security and Integration review plus
latest CI and Owner merge. Distribution flags remain false; no publication/deploy.
