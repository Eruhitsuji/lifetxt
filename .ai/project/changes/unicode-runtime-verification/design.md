# Technical verification design

Reuse req-browser-local-check-distribution-v1 and cap-official-website. Phase:
developer verification to integration verification; Investigation/High/S, score6
(scope1/dependency1/uncertainty1/test2/ops1). Upstream 1530 merged/reviewed.

Review: immutable candidate/checkpoint identities, bounded source replay,
config/linked archive correspondence, strict negative exception types, source-data
residuals versus runtime absence. Test: mutation of pins/payload/config/archive/
stdlib, real matching inputs, retained samples, parser cap/boundaries/Unicode.
Coding: stdlib-only helpers, existing source recipe/adapter/Core ZIP reuse, ruff.
Security: no live data, no unpinned runtime fallback, no distribution or deployment.

The verifier rehashes the manifest-bound build snapshot and reconstructs pinned
sources before interpreting static evidence. The Node probe independently checks
runtime bytes before actual execution. Neither is compiler attestation. The
retained original archives, samples and references are explicitly not claimed
absent or legally resolved. Runtime/website/Format remain unchanged.
