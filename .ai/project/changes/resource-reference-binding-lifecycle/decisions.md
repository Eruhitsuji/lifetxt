# Decisions and approval boundary

- Task: #1111; parent #1101; approved schema contract #1110.
- Current request authorizes investigation, refinement and Draft PR preparation.
- Issue explicitly requires its own concrete design/Ready gate; final requirements,
  public API/data model/authorization and High risk acceptance belong to the owner.
- Pending decision: accept design.md and proposed_runtime_write_scope as the
  implementation baseline. No pending approval is treated as granted.
- One integration branch, sequential store -> resolver -> policy/isolation -> delivery;
  #1114 policy/isolation and delivery need separately tracked S child contracts.
- Reuse the reviewed Linux helper. No browser/proxy principal, provider or dependency.
- Fresh startup epoch only; stable across-restart references are not implemented.
- Self-review: include tokens/tombstones in quota; no body/path leaks, mutable config
  revalidation and real worker-stop acknowledgement in transfer admission evidence.
- Independent design/security and final merge reviews remain pending.

## Approval supersession / implementation review

Owner explicitly approved the concrete three-point design in the active session on
2026-10-07. Original pending notes are proposal history, not current blockers.
Child units #1125/#1126 refine the approved #1114 decomposition. SQLite DELETE
journal intentionally refuses foreign recovery sidecars. Self-review found and fixed
O_PATH directory fsync, optional-module bootstrap order, route-wrapper placement,
pre-auth slot reservation, source restore continuity, failed-read reference retirement,
post-header abort handling and configuration/credential rechecks. No unrelated writer,
Format, browser, provider or required dependency change. Final independent review
remains pending. No claim that local tests certify a deployed host or D-state cleanup.

- Additional rollback self-review: memory epoch alone does not detect a same-epoch
  SQLite backup restored in place. Every index transaction now compares a persisted
  sequence to the current in-memory sequence and atomically increments it at commit.
  Same-epoch rollback cannot revive a detached ID; a deterministic SQLite backup
  restore regression covers it. New starts still retire all public authority.
