# Research & Design Decisions Template

---
**Purpose**: Capture discovery findings, architectural investigations, and rationale that inform the technical design.

**Usage**:
- Log research activities and outcomes during the discovery phase.
- Document design decision trade-offs that are too detailed for `design.md`.
- Provide references and evidence for future audits or reuse.
---

## Summary
- **Feature**: `windows-atomic-replace-retry`
- **Discovery Scope**: Extension (light discovery; existing hardened pattern reused, no new external dependency)
- **Key Findings**:
  - Every direct `os.replace` call site in `lifetxt/` was already enumerated in `requirements.md`. Confirmed again during design discovery: exactly four sites exist — `atomic.py:73`, `config_writer.py:96`, `config_writer.py:125` (unprotected), and `transaction_journal.py:962` (already protected, #86/#94). No other call site exists.
  - `lifetxt/atomic.py` has zero internal (`lifetxt.*`) imports — it is the project's lowest dependency layer. `config_writer.py` already imports from it. `transaction_journal.py` does not import it and is explicitly out of boundary for this spec.
  - `config_writer.py`'s two unprotected call sites are already wrapped in `try/except OSError: pass` (best-effort backup/rejected-candidate rotation). Since `PermissionError` is an `OSError` subclass, a retry helper that re-raises on exhaustion is automatically swallowed by the existing wrapping — no new exhaustion-handling code is needed at those call sites to satisfy Requirement 2.3/2.4.
  - `transaction_journal.py`'s existing `_replace_file()` retry loop is exercised through `fault_point`/`fault_injection` hooks from `transaction_policy.py`, a testing mechanism specific to the transaction journal's fault-injection matrix (`tests/test_fault_matrix_v6.py`, `tests/test_fault_drill_v5.py`). `atomic.py` and `config_writer.py` have no such hook today; introducing one would be new instrumentation outside this spec's boundary, so the new helper is tested by mocking `os.replace` and `time.sleep` directly instead.

## Research Log

### Existing bounded retry pattern (`transaction_journal.py`)
- **Context**: Requirement 3 mandates reusing the existing retry policy exactly. Needed to confirm its precise parameters before generalizing it.
- **Sources Consulted**: `lifetxt/transaction_journal.py:50-51` (constants), `lifetxt/transaction_journal.py:944-965` (`_replace_file`), `tests/test_transaction_journal_v3.py:50-111` (behavioral tests).
- **Findings**:
  - `_REPLACE_PERMISSION_RETRY_OS_NAMES = frozenset(("nt",))` — Windows only.
  - `_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS = (0.01, 0.05, 0.1, 0.25)` — total attempts = 1 initial + 4 retries.
  - Only `PermissionError` triggers a retry; the loop retries `attempts = len(retry_delays) + 1` times, sleeping the corresponding delay between attempts, and re-raises the original exception unchanged once the budget is exhausted.
  - Tests mock the two module-level constants and `time.sleep` rather than sleeping for real, and use `fault_injection` to raise `PermissionError` at the `before_file_replace` fault point.
- **Implications**: The new shared helper must expose equivalent, independently mockable constants and match this exact attempt/delay contract so Requirement 3's "identical policy" and "same ~0.41s budget" criteria hold verifiably, not just approximately.

### Call site inventory and dependency direction
- **Context**: Requirements Boundary Context states all `os.replace` call sites are accounted for and that `transaction_journal.py` is out of boundary. Needed to verify both claims against the current tree and determine where a shared helper can safely live without creating an import cycle.
- **Sources Consulted**: `grep -rn "os\.replace" lifetxt/*.py`, import headers of `atomic.py`, `config_writer.py`, `transaction_journal.py`, `mutation.py`.
- **Findings**:
  - Four call sites confirmed, matching `requirements.md` exactly.
  - `atomic.py` imports only `json`, `os`, `stat`, `tempfile` (no `lifetxt.*` imports).
  - `mutation.py` imports `atomic_write_bytes` from `atomic.py` (per `atomic.py`'s own module docstring).
  - `config_writer.py` already imports `atomic_write_text` from `.atomic` and also imports `mutation`.
  - `transaction_journal.py` imports `mutation`, `transaction_policy`; it does not import `atomic.py` and is not imported by it.
- **Implications**: `atomic.py` is the only module all other candidate call sites can depend on without introducing a cycle or reaching across an existing boundary. Placing the shared helper there keeps the dependency direction consistent with the project's existing layering (`atomic` → `mutation` → everything else) and requires no new module.

### Error-handling divergence between call sites
- **Context**: Requirement 1 requires exhaustion to propagate loudly; Requirement 2 requires exhaustion to stay silent. Needed to determine whether the shared helper must itself branch on this, or whether existing call-site code already provides the divergence.
- **Sources Consulted**: `lifetxt/atomic.py` (`atomic_write_bytes`, no surrounding try/except around the replace call), `lifetxt/config_writer.py` (`_rotate_backups`, `_retain_rejected`, both wrap the replace call in `try/except OSError: pass`).
- **Findings**: The two call sites already differ in how they handle any `OSError` from `os.replace`, independent of this feature. `atomic_write_bytes` lets it propagate (inside a `finally` that only cleans up the temp file); the rotation functions swallow it.
- **Implications**: The shared helper needs exactly one behavior — retry on Windows for a transient `PermissionError`, then re-raise unchanged on exhaustion. It must not special-case its caller. The differing observable outcomes required by Requirement 1 vs. Requirement 2 fall out of the existing, unmodified call-site error handling. This avoids adding a parameter or mode flag to the helper (Simplification).

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| A. Duplicate the retry loop at each of the 2 new call sites | Copy `transaction_journal.py`'s loop shape inline into `atomic.py` and `config_writer.py` | No new shared surface | Violates Requirement 3.1 (identical policy) by construction risk of drift between 3 independent copies over time | Rejected |
| B. Shared `replace_with_retry` helper in `atomic.py` | One function + two constants, reused by `atomic_write_bytes` and both `config_writer.py` rotation call sites | Matches existing dependency direction (`atomic` has zero internal deps); no new module; single source of truth for the policy used by the 2 new sites | `transaction_journal.py` still has its own independent copy of the same values (by design — out of boundary) | **Selected** |
| C. Shared helper in a new module (e.g. `lifetxt/replace_retry.py`) | Same behavior as B, but in a dedicated module | Slightly clearer single-purpose module | Adds a new module for a ~20-line function when an appropriate existing lowest-layer module (`atomic.py`) already exists; unnecessary indirection | Rejected (Simplification) |
| D. Refactor `transaction_journal.py` to delegate to the new shared helper too | Full unification across all 3+1 call sites | Strongest form of "identical policy" | Modifies the incident-hardened, fault-injection-tested `_replace_file()` (#86/#94) that `requirements.md` Boundary Context explicitly places out of scope | Rejected (explicit requirements boundary) |

## Design Decisions

### Decision: Shared retry helper lives in `lifetxt/atomic.py` as `replace_with_retry(source, destination)`
- **Context**: Requirements 1 and 2 both need the identical bounded retry behavior (Requirement 3) at three call sites across two modules, without touching `transaction_journal.py`.
- **Alternatives Considered**:
  1. Duplicate the loop at each site (Option A above).
  2. New dedicated module (Option C above).
  3. Refactor `transaction_journal.py` to share the same helper (Option D above).
- **Selected Approach**: Add `replace_with_retry(source, destination)` plus two private module-level constants (`_REPLACE_PERMISSION_RETRY_OS_NAMES`, `_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS`, values identical to `transaction_journal.py`'s) to `lifetxt/atomic.py`. `atomic_write_bytes` calls it in place of the raw `os.replace(temp_path, path)`. `config_writer.py` imports it and calls it in place of the raw `os.replace(older, newer)` inside `_rotate_backups` and `_retain_rejected`, inside their existing `try/except OSError: pass` blocks.
- **Rationale**: `atomic.py` is the only module with no internal dependencies, so it can be depended on by both `config_writer.py` (already does) and, implicitly, everything downstream of `mutation.py`, without creating a cycle. This keeps the change to two files, matches the project's existing dependency direction, and produces exactly one implementation of the new call sites' policy — satisfying Requirement 3.1 by construction rather than by convention.
- **Trade-offs**: `transaction_journal.py` keeps its own independent constants and loop rather than sharing code with the new helper. This means the *values* must be kept in sync by convention (both encode 0.01/0.05/0.1/0.25s, Windows-only) rather than by a single shared constant — an accepted trade-off because unifying them would require modifying code this spec's Boundary Context places out of scope.
- **Follow-up**: If a future spec revisits `transaction_journal.py`, consider migrating it onto `replace_with_retry` as well; record that as a candidate follow-up rather than doing it here.

### Decision: No new observability for configuration rotation exhaustion (Requirement 2.4)
- **Context**: `_rotate_backups`/`_retain_rejected` already swallow any `OSError`, including today's un-retried `PermissionError`. The retry helper re-raises the same exception type on exhaustion.
- **Alternatives Considered**:
  1. Add a log line or return-value signal when rotation fails after retrying.
  2. Leave the existing `except OSError: pass` unmodified.
- **Selected Approach**: Option 2 — no change to the exception handling at the two rotation call sites.
- **Rationale**: This was confirmed directly with the requirements owner during requirements clarification (see `requirements.md` Boundary Context, "Out of scope"). Backup/rejected-candidate rotation is documented as best-effort recovery, not correctness-critical, and doctor's existing `rejected_candidates()` reporting is a separate mechanism (surfacing successfully retained candidates from refused compare-and-set writes, not rotation replace failures).
- **Trade-offs**: An operator cannot currently distinguish "rotation succeeded" from "rotation silently failed even after retrying" through any lifetxt surface. Accepted as the smallest change consistent with the explicit requirement.
- **Follow-up**: None planned; would need a new requirement if revisited.

## Risks & Mitigations
- **Risk**: A future edit to `transaction_journal.py`'s retry constants drifts from `atomic.py`'s copy, silently breaking Requirement 3.1's "identical policy" claim. — **Mitigation**: `tests/test_mutation.py` asserts the exact delay tuple and OS-name set on `atomic.py`'s constants; a follow-up test can additionally assert equality against `transaction_journal._REPLACE_PERMISSION_RETRY_DELAYS_SECONDS` at import time to catch drift mechanically. Recorded as a testing task, not a design change.
- **Risk**: Retrying only `PermissionError` misses a differently-typed transient Windows error in the future. — **Mitigation**: Matches the existing, already-validated `transaction_journal.py` contract; no evidence in #96 or #86/#94 of any other exception type being involved. Out of scope to broaden without new evidence.
- **Risk**: Adding retry to `atomic_write_bytes` (the shared commit primitive used by nearly every write path) could mask a *non*-transient permission problem behind a ~0.41s delay before the same failure surfaces. — **Mitigation**: The delay is bounded and small (≈0.41s), matches the precedent already accepted for the transaction journal, and only triggers on Windows for `PermissionError`; the final failure is unchanged (same exception propagates), so no failure becomes silent that wasn't already going to fail.

## References
- `lifetxt/transaction_journal.py:944-965` — existing `_replace_file()` retry implementation reused as the policy source of truth.
- `tests/test_transaction_journal_v3.py:50-111` — existing retry behavior tests used as the pattern for the new tests.
- https://github.com/Eruhitsuji/lifetxt/issues/96 — incident report that triggered this spec (`atomic.py:73` transient failure observed during `tests.test_mutation`).
- https://github.com/Eruhitsuji/lifetxt/issues/86 and https://github.com/Eruhitsuji/lifetxt/issues/94 (PR) — prior work that established the retry pattern being reused here.
