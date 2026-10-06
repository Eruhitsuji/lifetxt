# Decisions and authority

- Parent #1101 recommendations accepted: https://github.com/Eruhitsuji/lifetxt/issues/1101#issuecomment-6013396280.
- Current task-through-PR request authorizes preparing a concrete reviewable proposal.
  It is not treated as acceptance of the new envelope or authorization configuration.
- Proposed initial consumer is Remote protocol 2, restricted dedicated bearer-only;
  no browser/session/proxy consumer or raw-manifest bootstrap. Browser scope may be
  approved separately later with its required isolation and CSRF/Origin protections.
- Additional attachment:read comes from explicit principal scope, never from read/role.
  Current workspace read membership must be checked even on these read-classified POSTs.
- Choose three exact POST routes in the existing Remote namespace, binary full/chunk,
  no URL refs/credentials, no Range/If-Range/latest fallback. Separate feature header
  negotiates resource-reference-v1; header alone cannot change principal mode.
- Six new schemas will use the next unused extension (candidate v33) only after explicit
  concrete approval and Ready. Legacy attachment v1 is never regenerated into this shape.
- Proposed hard limits and catalog are in EN/JA sections 4–6; uncertain platform or raw
  route isolation refuses enablement. Schema-only delivery never advertises capability.
- Self-review correction: define protected out-of-band selector provisioning to avoid
  depending on the raw workspace manifest that restricted clients are required to deny.
- Self-review correction: explicitly preserve non-v1 bounded grammar outcome and token
  inspection cap from #1100; no unsupported-version reinterpretation.
- Pending owner decision: accept EN/JA sections 1–7 and schema pipeline plan; then
  refine issue/contract write scope to Ready and continue on the same PR.

- Final metadata review: package state is in-review once the Draft PR is linked;
  this does not approve its proposed design or mark schema delivery implemented.

## Concrete approval and Ready supersession (2026-10-06)

Owner explicitly approved the prior-turn concrete proposal. Approval record: https://github.com/Eruhitsuji/lifetxt/issues/1110#issuecomment-6015909957. Earlier pending-design notes above describe the proposal stage and are superseded. Ready refinement selects schema_extensions_v33.py, the existing bootstrap extension range, six generated schemas and tests/test_resource_reference_contract.py. No runtime/settings/legacy schema change. Independent integration/merge review is still pending.

- Direct compatibility maintenance updates five existing bundle inventory/count tests
  from 86 to 92 and adds the six exact filenames to the inventory set; assertions
  remain strict. Generated old artifacts are preserved unchanged.
- Self-review corrected traceability list indentation; the initial full run exposed
  that package parse error, the outdated inventories and missing editable installation.
  Full output is retained; revalidation uses the configured dev setup in an isolated
  environment. No source changed while the initial full run was executing.

- Final committed-gate review preserves indented sequence items in the shared
  traceability record; syntactically valid indentless YAML was not recognized by
  the existing evidence gate. The gate was not changed or weakened. Final full
  dev suite: 5,161 tests OK (349 optional/environment skips); committed focused
  checks: 29 OK. Independent implementation/security/integration approvals remain
  pending the published final head.
