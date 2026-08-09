# Design Document

## Overview
`transaction_journal.py` drops its own
`_REPLACE_PERMISSION_RETRY_OS_NAMES`/`_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS`
literals and imports both names from `atomic.py` instead. No other line in
either module's retry logic changes: `transaction_journal._replace_file`
keeps its own loop and its per-attempt `fault_point()` call exactly as
before, reading the same (now-imported) globals it always read by name.
`atomic.py`'s constants and `replace_with_retry()` are untouched in value
and behavior.

## Boundary Commitments
### This Spec Owns
- The two constant definitions/imports in `atomic.py` and
  `transaction_journal.py`.
- `tests/test_replace_retry_policy.py`'s documentation (not its assertions'
  meaning, which is unchanged).
### Out of Boundary
- `transaction_journal._replace_file`'s retry loop and `fault_point()`
  hook -- stays exactly as implemented today. Migrating it to call
  `atomic.replace_with_retry` remains explicitly out of scope, per the same
  reasoning `windows-atomic-replace-retry`'s `decisions.md` originally gave:
  it would touch incident-hardened, fault-injection-tested code, and
  `atomic.replace_with_retry` has no fault-injection hook for the
  crash-recovery test matrix to attach to.
- `config_writer.py`'s rotation call sites, which already call
  `atomic.replace_with_retry` directly and are unaffected.
### Allowed Dependencies
- `transaction_journal.py` importing `atomic.py` at module level. Confirmed
  cycle-free: `atomic.py` has no module-level import of `mutation`,
  `transaction_journal`, or anything that imports either (its only
  `mutation` reference is a lazy in-function import inside
  `atomic_write_text`). `transaction_journal.py` already imports
  `mutation`, which itself already imports `atomic.atomic_write_bytes` at
  module level, so this adds no new dependency direction.

## File Structure Plan
### Modified Files
- `lifetxt/atomic.py` -- comment update only (the constants' definitions and
  values are unchanged).
- `lifetxt/transaction_journal.py` -- replace the two literal definitions
  with an import from `.atomic`.
- `tests/test_replace_retry_policy.py` -- docstring/rationale update; the
  three test bodies keep the same assertions.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `transaction_journal.py`: `from .atomic import (_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS, _REPLACE_PERMISSION_RETRY_OS_NAMES)` replaces the two local assignments |
| 1.3 | `mock.patch.object(transaction_journal, "_REPLACE_PERMISSION_RETRY_OS_NAMES", ...)` sets the attribute on the `transaction_journal` module object regardless of whether the name was originally bound by assignment or by import -- verified by re-running the existing tests that do this unmodified |
| 2.1, 2.2 | `_replace_file`'s body is not touched at all in this change |
| 2.3 | Regression run of the three named test modules, unmodified |
| 3.1, 3.2 | `tests/test_replace_retry_policy.py`'s module docstring and `DELIBERATE` constant rewritten to describe the shared-constant/separate-loop state; `test_retry_platforms_match`/`test_retry_delays_match`/`test_both_copies_describe_a_bounded_budget` bodies unchanged |

## Testing Strategy
- Full regression of `tests/test_transaction_journal_v3.py`,
  `tests/test_replace_retry_policy.py`, `tests/test_fault_matrix_v6.py`,
  `tests/test_fault_drill_v5.py`, `tests/test_mutation.py`,
  `tests/test_transaction_policy_v4.py`, and `tests/test_config_validation.py`
  (the config rotation call sites also depend on `atomic.replace_with_retry`)
  -- all must pass unmodified, since this change deliberately introduces no
  behavior change.
- Full suite (`python -m unittest discover`) as final confirmation of no
  regression anywhere else.
