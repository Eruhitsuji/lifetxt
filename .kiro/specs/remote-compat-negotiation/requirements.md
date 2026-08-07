# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> For non-trivial work, and for anything at High or Regulated assurance, this content is distilled
> into `.ai/project/changes/<change-id>/requirements.yml`, which is what reviewers and the other
> executors read. See `.ai/project/changes/README.md` for when a change package is required at
> all — below that threshold, the issue and pull request carry the reasoning and no package is
> needed.
>
> This change is Standard assurance and S-sized (GitHub Issue #120), below the change-package
> threshold. This file is the working spec; Issue #120 and its pull request carry the authoritative
> record.

## Project Description (Input)

remote-compat-negotiation: Extend Remote compatibility negotiation (lifetxt/remote_compatibility_v21.py, lifetxt/remote_client.py::test_connection) with domain-aware contract warnings via an optional required_contracts parameter on evaluate_compatibility(), and capability-revision header-loss/mismatch detection in test_connection() (new header_status field: present-and-consistent / missing / mismatch). Fully backward compatible when required_contracts is omitted. See GitHub Issue #120 for full scope, out-of-scope, and acceptance criteria.

## Boundary Context

- **In scope**: client-side advisory warnings computed from data the server already publishes (the `contracts` map in the capability manifest, and the `X-Lifetxt-Remote-Capability-Revision` response header); the compatibility evaluation path used by the Remote client and by `lifetxt remote test`.
- **Out of scope**: any change to what the server publishes; any change to the Remote wire protocol version; any server-side enforcement or request rejection based on the new checks; any change to authorization, session, or permission behavior; any transport, pagination, or streaming behavior (tracked as a separate feature).
- **Adjacent expectations**: this feature depends on the already-published contract-domain map and capability-revision header continuing to exist in their current shape; it does not alter either.

## Requirements

### Requirement 1: Domain-aware contract compatibility warnings

**Objective:** As a Remote client operator, I want the compatibility check to tell me when a specific contract domain I depend on is missing or outdated on the server, so that I can diagnose a feature gap before attempting an operation rather than after it fails.

#### Acceptance Criteria

1. Where a caller supplies a required-contract-domain list, the Remote Compatibility Evaluator shall check each named domain against the server's published contracts.
2. When a required contract domain is absent from the server's published contracts, the Remote Compatibility Evaluator shall report a warning naming that domain.
3. When a required contract domain is present but its current version is below the version the client expects, the Remote Compatibility Evaluator shall report a warning naming that domain and the version shortfall.
4. When a required contract domain is present and meets the expected version, the Remote Compatibility Evaluator shall not report a warning for that domain.
5. Where no required-contract-domain list is supplied, the Remote Compatibility Evaluator shall perform no domain-level check and shall not add any warning from this requirement.

### Requirement 2: Backward-compatible default behavior

**Objective:** As an existing caller of the compatibility evaluator, I want the default output to stay unchanged, so that upgrading does not silently alter behavior for code that has not opted in.

#### Acceptance Criteria

1. The Remote Compatibility Evaluator shall accept the required-contract-domain list as optional input.
2. While the optional input is not supplied, the Remote Compatibility Evaluator shall produce the same result fields and warnings as it did before this feature, given the same protocol and manifest inputs.

### Requirement 3: Capability-revision header integrity reporting

**Objective:** As a Remote client operator connecting through a reverse proxy or cache, I want to know when the capability-revision header is missing or does not match the response body, so that I can tell a stale or mangled intermediary apart from a genuine server incompatibility.

#### Acceptance Criteria

1. When the Remote Client fetches server capabilities, the Remote Client shall compare the capability-revision header value against a value derived from the fetched capability body.
2. If the capability-revision header is absent from the response, the Remote Client shall report the header status as missing and include a warning in the compatibility report.
3. If the capability-revision header is present but does not match the value derived from the fetched capability body, the Remote Client shall report the header status as mismatched and include a warning in the compatibility report.
4. When the capability-revision header is present and matches the value derived from the fetched capability body, the Remote Client shall report the header status as consistent and shall not add a warning for it.

### Requirement 4: Documented contract

**Objective:** As a developer integrating with Remote, I want the compatibility documentation to describe the new optional check and header-status field, so that I can use them without reading source code.

#### Acceptance Criteria

1. The project documentation shall describe the optional required-contract-domain compatibility check, in English and in Japanese.
2. The project documentation shall describe the capability-revision header-status values and their meaning, in English and in Japanese.
