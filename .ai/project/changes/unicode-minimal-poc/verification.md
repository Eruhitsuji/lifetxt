# #1434 Unicode-minimal source-only PoC — implementation / verification

- Owner approval: UTF-8-first minimal codec policy (2026-10-26), **PoC only**.
- Source baseline: main \`67e5806a5ae22d69e9e93fbffb6634726affa8fb\`.
- Phase: Investigation / Architecture / isolated implementation and developer verification.
- Development: adaptive-default Kanban + W-model; change type Investigation, High assurance due to third-party provenance and runtime security.
- Size: S; implementation scope is one isolated source curator, one focused unittest, one handoff document.
- Linked Issue: https://github.com/Eruhitsuji/lifetxt/issues/1434
- Parent public distribution gate: https://github.com/Eruhitsuji/lifetxt/issues/1398 (still BLOCKED).
- Requirement/capability reuse: \`req-browser-local-check-distribution-v1\` / \`cap-official-website\`; public checker/Format/Core/CLI API unchanged.
- Implements: isolated \`contrib/browser_check_poc/unicode_minimal.py\`. Tests: \`tests/test_unicode_minimal.py\`. Procedure: \`UNICODE_MINIMAL_POC.md\`.
- Review viewpoints: requirements (external UTF-8 contract), design (source exclusion before compile), implementation (archive/path/symlink/alias fail-closed), security (untrusted tar, no network/deploy), integration (profile2 unchanged, future profile3 separated), testing (synthetic and actual locked archive), operations (source retention/rollback).
- Forbidden: edit runtime profile1/2 and source pins, change \`mapping-attribution\` statuses or licence claims, modify Pages/deploy, release, merge, change publication flags.

## Verified by the implementer (NOT an independent reviewer)

\`\`\`text
python -m unittest tests.test_unicode_minimal
5 tests: PASS (including wrong input hash rejection)
\`\`\`

Historical profile2 artifact SHA \`a013d3773da97727542528f507c1f9ff8d9cbbc814a7e2ff92078781fe9eb039\` was available from local conversation files. Source payload SHA \`f862710e3d61091aae013d486d8bedbf1074188fd98086572d6340ec60b5392c\` matched the pinned profile2 curated CPython source. The isolated curated experiment returned output SHA \`eb80e7df3c4a4190ec5b83c72e231fbba33dc299a442ce6743ea03a54dea5619\`, retaining 4927 and removing 130 files, with a 18-entry candidate encoding allowlist. Output tar and original 82MB artifact were not committed.

## Explicit NOT RUN / blocks

- Actual Pyodide configure/Setup.local/compilation and object/WASM/stdlib inspection;
- Actual profile3 identity/lock/build, backend/Worker/browser compatibility, performance;
- Independent High review, third-party source-specific legal acceptance and published source delivery.
- Default CI not run until final PR; no claim of GitHub merge readiness without CI.
- Removed codec absence in the source tar **does not** prove absence in compiled WASM.
- The original source archive and all published runtime/library files remain unchanged.

## Independent review and rollout gate

Separate implementer and reviewer are required. Review current PR head implementation/security/integration and fresh CI. Owner decides whether to proceed with a **separately-scoped runtime profile3 build**. Do not merge automatically. Rollback: revert the PoC PR; no deployed or persisted user data changes.
