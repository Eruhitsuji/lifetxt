# Design

Distilled from `.kiro/specs/windows-atomic-replace-retry/design.md`, which remains the full
working document (architecture rationale, Mermaid diagrams, per-component contracts, full test
list). This file summarizes the decisions a reviewer needs; the spec is the deeper reference.

## Summary

Add one new function, `replace_with_retry(source, destination)`, to `lifetxt/atomic.py` — the
project's lowest-dependency module (no internal imports). It wraps `os.replace` with a
Windows-only bounded retry (initial attempt plus up to 4 retries at 0.01/0.05/0.1/0.25s,
identical to the values already proven in `lifetxt/transaction_journal.py`'s `_replace_file()`,
#86 / #94) for a transient `PermissionError` (`WinError 5`). It retries nothing else, and on
non-Windows platforms or any other exception type it behaves exactly as a bare `os.replace` call
does today.

Two existing call sites are wired to it:

- `atomic_write_bytes` (`lifetxt/atomic.py:73`) — the shared low-level commit primitive nearly
  every write in the project passes through. On exhaustion it propagates the same
  `PermissionError` it already would, unchanged.
- `_rotate_backups` / `_retain_rejected` (`lifetxt/config_writer.py:96`, `:125`) — best-effort
  `.bak` / `.rejectedN` rotation, already wrapped in `except OSError: pass`. On exhaustion that
  existing handler silently absorbs the re-raised `PermissionError`, unchanged.

`lifetxt/transaction_journal.py:962` is untouched. It keeps its own independent constants and
loop; only the *values* are matched, not the code.

## Interfaces and Contracts

- **ADDED**: `lifetxt.atomic.replace_with_retry(source, destination)` — service-style function,
  no new public API surface beyond the module. Preconditions/postconditions identical to a bare
  `os.replace(source, destination)` call on success; raises the same `PermissionError` type on
  exhaustion (no wrapping).
- **ADDED**: two private module-level constants in `lifetxt/atomic.py` defining the retry policy
  (OS-name set, delay tuple), values identical to
  `transaction_journal._REPLACE_PERMISSION_RETRY_OS_NAMES` /
  `_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS`.
- **MODIFIED**: `atomic_write_bytes` (`lifetxt/atomic.py`) — internal replace step only; public
  signature, preconditions, and postconditions unchanged.
- **MODIFIED**: `_rotate_backups`, `_retain_rejected` (`lifetxt/config_writer.py`) — internal
  replace step only; public signatures and observable behavior unchanged (best-effort silence on
  failure is preserved).
- **REMOVED**: none.

## Alternatives

Full comparison in `.kiro/specs/windows-atomic-replace-retry/research.md` (Architecture Pattern
Evaluation). Summary of the four options considered and why this one was selected:

1. Duplicate the retry loop at each of the two new call sites — rejected, risks policy drift
   across independent copies.
2. Shared helper in `lifetxt/atomic.py` (**selected**) — matches the existing dependency
   direction (`atomic.py` has zero internal dependencies; `config_writer.py` already depends on
   it), no new module.
3. Shared helper in a new dedicated module — rejected as unnecessary indirection for one ~20-line
   function.
4. Refactor `transaction_journal.py` to share the same helper — rejected: it would modify the
   incident-hardened, fault-injection-tested `_replace_file()` (#86 / #94), which is out of
   boundary for this change (see `change.yml` forbidden_scope).

## Risks

- Retry masking a non-transient permission problem behind a bounded ~0.41s delay before the same
  failure surfaces. Mitigated: the delay is small and bounded, matches the already-accepted
  transaction-journal precedent, and the final failure is unchanged — nothing that would have
  failed becomes silent that wasn't already going to fail.
- Future drift between `atomic.py`'s retry constants and `transaction_journal.py`'s copy, since
  the values are matched by convention rather than shared code. Mitigated by an explicit unit
  test asserting the exact values on `atomic.py`'s constants (see verification.yml); a follow-up
  test can additionally assert equality against `transaction_journal`'s constants at import time.
- Retrying only `PermissionError` could miss a differently-typed transient Windows error in the
  future. Accepted: no evidence in #96 or #86/#94 of any other exception type being involved;
  broadening without evidence is out of scope.

## Operations Impact

None. No new configuration, no new log output, no new diagnostic surface, no deployment or
migration step. `lifetxt doctor` output is unchanged.

## Compatibility Impact

None for callers. `atomic_write_bytes`'s public signature and exception contract on exhaustion
are unchanged (same exception type, same conditions). `_rotate_backups` / `_retain_rejected`'s
public signatures and silent-failure behavior on exhaustion are unchanged. The only observable
difference is that a subset of previously-guaranteed-to-fail transient Windows errors now succeed
after a bounded wait instead of failing immediately.
