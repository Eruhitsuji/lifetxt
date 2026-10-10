# Decisions

On 2026-10-10 the maintainer approved the additive endpoint, exact-input/context
identity, legacy compatibility, source re-resolution/read-only boundaries in chat.
The contract/DoR is recorded on #1182. #1187 merged before implementation.

Standard assurance, justified M, complexity 6: one coherent endpoint/UI review
contract with internal Core reuse and focused integration tests; save/recovery
already decomposed into #1188/#1189. No write contract changes or new dependency.
Independent human latest-head review is pending; self-review is not approval.

This is post-Stable 1.0.3 hardening of existing bulk input (#1176), under the
explicit implementation/API approval. Historical first-Stable freeze (#283)
does not require a second approval; no release/deployment is performed.
