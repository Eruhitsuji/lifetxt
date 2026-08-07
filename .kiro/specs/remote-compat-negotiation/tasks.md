# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> GitHub Issue #120 is the actionable task source for this spec (`.ai/managed/core/TASK_MANAGEMENT.md`).
> This breakdown is the execution plan for that issue's single PR on `ai/claude/120-remote-compat-negotiation`.

## Tasks

- [ ] 1. Foundation: add a regression test pinning the current two-argument `evaluate_compatibility` output before any implementation change
  - Assert the existing fixtures in `tests/test_remote_compatibility_v21.py` produce identical output when called with only `(capabilities, requested_protocol)`, with no `required_contracts` or `capability_revision_header` argument
  - Observable completion: the new test passes against the pre-change implementation, then continues to pass unmodified after tasks 2-4 land
  - _Requirements: 2.1, 2.2_

- [ ] 2. Core: domain-aware contract warnings
- [ ] 2.1 Add the `required_contracts` parameter with presence checking and fail-fast validation
  - Accept an iterable of contract-domain names; for each, look up the domain in the published `contracts` map and append one warning naming the domain when it is absent or unavailable
  - Raise `ValueError` immediately, naming the valid domains, when a supplied domain name is not one of the known contract domains
  - Leave behavior unchanged when `required_contracts` is not supplied
  - Observable completion: calling `evaluate_compatibility` with a required domain missing from the manifest returns a `warnings` entry naming that domain; calling it with an unknown domain name raises `ValueError` before any warning logic runs
  - _Requirements: 1.1, 1.2, 1.5_

- [ ] 2.2 Extend `required_contracts` to accept a domain-to-minimum-version mapping
  - When a domain entry specifies a minimum version, compare it against the domain's published `current` version and append a warning naming the domain and the shortfall when the server is below it
  - Continue to accept the plain iterable-of-names form from 2.1 unchanged (presence-only check, no version comparison)
  - Observable completion: a required domain present but below its specified minimum version produces a warning distinct from the absent-domain warning in 2.1; a domain meeting its minimum produces no warning
  - _Requirements: 1.3, 1.4_

- [ ] 3. Core: add the sentinel-defaulted `capability_revision_header` parameter and header-vs-body comparison
  - Introduce a module-private sentinel default so "parameter not supplied" is distinguishable from "supplied and is `None`"
  - When supplied, compare the value against the capability body's own revision field and set a `header_status` result key to one of the three defined values, adding a warning for the two non-consistent cases
  - Leave the result unchanged (no `header_status` key, no new warnings) when the parameter is not supplied
  - Observable completion: passing a header value that differs from the body's revision field yields `header_status == "mismatch"` plus a warning; passing `None` yields `header_status == "missing"` plus a warning; passing a matching value yields `header_status == "present-and-consistent"` with no new warning; omitting the parameter entirely yields no `header_status` key at all
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 4. Integration: update the client compatibility wrapper's call site and add an end-to-end stub test
  - Pass the already-fetched header value from the wrapped connection result into `evaluate_compatibility`'s new parameter at the wrapper's existing call site
  - Add a test that installs the wrapper over a stubbed connection function (no real network) and asserts `header_status` reaches the wrapper's returned report for a header/body mismatch case and a consistent case
  - Observable completion: the stub-based test fails if the wrapper's call site does not forward the header value, and passes once it does
  - _Depends: 3_
  - _Requirements: 3.1_

- [ ] 5. Validation: documentation and traceability
- [ ] 5.1 (P) Update the English compatibility documentation
  - Document the `required_contracts` parameter (both accepted forms) and the resulting warning behavior
  - Document the `header_status` values and what each one means for an operator running `lifetxt remote test`
  - Observable completion: `docs/en/remote-compatibility.md` describes both additions without describing any change to what the server publishes
  - _Requirements: 4.1_
  - _Boundary: docs/en_

- [ ] 5.2 (P) Update the Japanese compatibility documentation
  - Mirror the English update from 5.1 in Japanese
  - Observable completion: `docs/ja/remote-compatibility.md` covers the same two additions as the English document
  - _Requirements: 4.2_
  - _Boundary: docs/ja_

- [ ] 5.3 Register the capability and traceability chain for this change
  - Add a `cap-remote-compatibility-negotiation` entry to `.ai/project/CAPABILITIES.yml` describing the evaluator extension delivered by tasks 1-4
  - Add a chain row to `.ai/project/TRACEABILITY.yml` linking requirement `req-remote-compatibility-domain-awareness`, the new capability, Issue #120, and this work's pull request
  - Observable completion: `tests.test_traceability_gate` passes for the resulting diff, and Issue #120's traceability acceptance criterion is satisfied
  - _Depends: 2, 3, 4_
