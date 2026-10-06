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
