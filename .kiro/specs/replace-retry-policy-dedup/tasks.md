# Implementation Plan

- [x] 1. Import the shared retry-policy constants into transaction_journal.py instead of redefining them
  - _Requirements: 1.1, 1.2, 1.3_
- [x] 2. Confirm transaction_journal's retry loop and fault-injection hooks are unchanged
  - _Requirements: 2.1, 2.2, 2.3_
- [x] 3. Update test_replace_retry_policy.py's documentation to describe the new shared-constant state
  - _Requirements: 3.1, 3.2_
