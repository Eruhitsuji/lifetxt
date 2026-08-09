# Requirements Document

## Project Description (Input)
`lifetxt/atomic.py` and `lifetxt/transaction_journal.py` each define their own
copy of the `_REPLACE_PERMISSION_RETRY_OS_NAMES`/
`_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS` constants (the Windows-only
transient-`PermissionError` retry policy for `os.replace`). This was a
deliberate decision at the time (`windows-atomic-replace-retry`'s
`decisions.md`, 2026-08-06): sharing the *retry loop* would have meant
editing `transaction_journal.py`, which is incident-hardened and
fault-injection-tested, and which that change package placed in forbidden
scope. `tests/test_replace_retry_policy.py` (added by #116) exists solely to
keep the two constant copies from silently drifting apart, since nothing
else enforces that they stay equal.

That same `decisions.md` entry explicitly left the door open: "A future spec
could migrate `transaction_journal.py` onto the shared helper; not this
change." This change is that future spec, narrowed to the part that can be
shared safely: the two constants become a single definition, imported by
`transaction_journal.py` from `atomic.py` rather than redefined. The retry
*loop* in `transaction_journal._replace_file` is explicitly **not** migrated
to call `atomic.replace_with_retry` -- it must keep its own loop because it
interleaves a `fault_point()` hook on every attempt, which the existing
crash-recovery fault-injection test matrix
(`tests/test_transaction_journal_v3.py`) depends on and which
`atomic.replace_with_retry` does not (and should not) provide.

## Requirements

### Requirement 1: A single source of truth for the retry policy constants
**Objective:** As a maintainer, I want the Windows replace-retry policy's
platform set and delay schedule defined exactly once, so that the two
modules cannot silently diverge and the existing drift-guard test is
enforcing a structural guarantee rather than hand-syncing.

#### Acceptance Criteria
1. `lifetxt/atomic.py` shall remain the sole definition site for
   `_REPLACE_PERMISSION_RETRY_OS_NAMES` and
   `_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS`.
2. `lifetxt/transaction_journal.py` shall import both constants from
   `lifetxt/atomic.py` instead of defining its own copies.
3. The imported names shall remain patchable via `mock.patch.object` on the
   `transaction_journal` module in existing tests, unchanged from today's
   test authoring style.

### Requirement 2: No change to transaction_journal's retry behavior
**Objective:** As a maintainer relying on `transaction_journal.py`'s crash
recovery guarantees, I want its replace-retry loop's actual behavior,
including its fault-injection hooks, to be completely unchanged by this
refactor.

#### Acceptance Criteria
1. `transaction_journal._replace_file`'s retry loop, including its
   per-attempt `fault_point("before_file_replace", ...)` call, shall be
   unchanged.
2. `transaction_journal._replace_file` shall not be changed to call
   `atomic.replace_with_retry`.
3. Every existing test in `tests/test_transaction_journal_v3.py`,
   `tests/test_fault_matrix_v6.py`, and `tests/test_fault_drill_v5.py` shall
   continue to pass unmodified.

### Requirement 3: The drift-guard test reflects the new reality
**Objective:** As a future maintainer reading
`tests/test_replace_retry_policy.py`, I want its documentation and failure
message to describe the current shared-constant/separate-loop arrangement,
not the fully-duplicated arrangement it replaces.

#### Acceptance Criteria
1. The test file's module docstring shall describe the constants as shared
   (imported) and the retry loop as intentionally separate, referencing why.
2. The equality assertions shall remain (as a regression guard against a
   future accidental reintroduction of a second literal definition).
