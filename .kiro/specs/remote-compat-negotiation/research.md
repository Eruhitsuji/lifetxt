# Research & Design Decisions

## Summary
- **Feature**: `remote-compat-negotiation`
- **Discovery Scope**: Extension (light discovery per `design-discovery-light.md`)
- **Key Findings**:
  - `evaluate_compatibility()` already receives the full `contracts` map inside `capabilities` but never reads it — the domain-aware check only needs new logic inside this existing function, not a new data source.
  - The capability-revision header and the body's `capability_revision` field are set from the *same* computed value server-side (`remote_access.protocol_response_headers` calls `capability_revision(config)`, which is `_capability_v2(config)["capability_revision"]` — the identical value embedded in the JSON body). A client can therefore detect header loss/rewriting by comparing the header to the body field it already fetched, with no need to recompute a SHA-256 hash client-side.
  - Because of the finding above, `lifetxt/remote_client.py` does not need to change. The header/body comparison fits entirely inside `remote_compatibility_v21.py`'s existing `install_remote_client_compatibility_v21()` wrapper, which already has both values in scope (`result.get("capability_revision")` from the header, `result.get("capabilities")` from the body). This narrows the original issue's write scope from two modules to one plus its tests and docs.

## Research Log

### Extension Point Analysis
- **Context**: Where does `required_contracts` and header-loss detection naturally attach without new plumbing?
- **Sources Consulted**: `lifetxt/remote_compatibility_v21.py`, `lifetxt/remote_client.py`, `lifetxt/remote_access.py`, `tests/test_remote_compatibility_v21.py`.
- **Findings**:
  - `evaluate_compatibility(capabilities, requested_protocol=None)` is a pure function already computing `warnings`; it is the single existing seam for advisory compatibility text.
  - `install_remote_client_compatibility_v21()` wraps `remote_client.test_connection` and is the only call site of `evaluate_compatibility` today (`remote_compatibility_v21.py:279-294`).
  - `remote_access._capability_v2` computes `capability_revision` once and both the header (`protocol_response_headers`) and the JSON body (`capability_v2` return value, extended by the v21 wrapper) carry that same value.
- **Implications**: Both new behaviors can be implemented as additions to `evaluate_compatibility()`'s signature and body, called with one extra keyword argument from the existing wrapper. No new module, no change to `remote_client.py`, no change to the wire format.

### Backward-Compatibility Mechanism
- **Context**: Requirement 2 demands byte-identical output when the new inputs are not supplied. `required_contracts=None` is unambiguous (no legitimate caller today passes an empty check). The header case is not: a caller who *does* ask for the check might legitimately observe `capability_revision_header is None` (proxy stripped it), which must not collapse with "caller did not ask."
- **Findings**: A module-private sentinel object (not `None`) distinguishes "parameter not supplied" from "supplied and is None/missing" cleanly, without adding a second boolean flag parameter.
- **Implications**: `evaluate_compatibility` gains `capability_revision_header=_UNSET` (private sentinel default). Only `capability_revision_header is not _UNSET` triggers the new `header_status` computation and key.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Extend `evaluate_compatibility` in place | Add two new optional parameters to the existing pure function | No new module, no new call sites, backward-compatible by construction | Function grows two responsibilities (protocol overlap + domain/header checks) | Selected — matches Simplification lens; the function is already the project's one compatibility-reporting seam |
| New `evaluate_contract_compatibility` sibling function | Separate function for domain/header checks, composed by the caller | Smaller individual functions | Two functions to call together everywhere; splits one compatibility report into two payloads that must be merged by every caller | Rejected — adds composition burden without a second real caller to justify it |
| Recompute SHA-256 client-side and compare to header | Client independently derives the hash the server would have computed | Would work even if a future server exposed the header without echoing the value in the body | Couples the client to the server's private hash construction (`payload.pop` / `json.dumps` ordering) in `install_remote_compatibility_v21`; that construction is not part of the documented contract | Rejected — the body already carries the same value the header carries; comparing the two published fields is sufficient and does not depend on server-internal hashing details |

## Design Decisions

### Decision: Single sentinel-defaulted parameter for header status, not a second boolean flag
- **Context**: Requirement 3 must stay fully opt-in (Requirement 2 applies to it too), but `None` is a valid observed value for a stripped header.
- **Alternatives Considered**:
  1. Add `check_capability_revision_header: bool = False` alongside a separate `capability_revision_header` parameter.
  2. A private sentinel default (`_UNSET`) for `capability_revision_header` itself.
- **Selected Approach**: Option 2 — sentinel default.
- **Rationale**: One parameter instead of two; "not supplied" and "supplied but empty" are structurally distinct without a second flag that could disagree with the first (e.g., `check=True` with no value supplied).
- **Trade-offs**: A private sentinel is slightly less discoverable in an IDE than a plain default, mitigated by a docstring on the parameter.
- **Follow-up**: None.

### Decision: `required_contracts` accepts either a plain domain list or a domain-to-minimum-version mapping
- **Context**: Requirement 1 needs both "does this domain exist" (AC 1.2) and "is its version high enough" (AC 1.3) checks from one parameter.
- **Alternatives Considered**:
  1. Two separate parameters (`required_contract_domains`, `minimum_contract_versions`).
  2. One parameter accepting `Iterable[str]` (presence-only) or `Mapping[str, Optional[int]]` (presence + optional minimum version).
- **Selected Approach**: Option 2.
- **Rationale**: Callers who only care about presence keep the ergonomic `["ticket_workflow", "attachment"]` form; callers who also need version enforcement pass `{"ticket_workflow": 2}` without a second parameter to keep in sync with the first.
- **Trade-offs**: The function must branch on the parameter's runtime type (`dict` vs. other iterable); documented and unit-tested for both forms.
- **Follow-up**: None.

### Decision: Unknown domain names raise `ValueError` immediately
- **Context**: Design principle "Fail Fast: validate early and clearly" (`design-principles.md`).
- **Alternatives Considered**:
  1. Silently warn forever for any domain name not present in the manifest (indistinguishable from a real server-side gap).
  2. Validate the domain name against `_CONTRACT_PATTERNS.keys()` and raise `ValueError` naming the valid domains when it does not match.
- **Selected Approach**: Option 2.
- **Rationale**: A misspelled domain name is a caller bug, not a server compatibility gap; the two must not be reported identically.
- **Trade-offs**: A caller integrating against a *future* server with a new domain name the current client does not recognize yet would need a client upgrade to add that domain name — acceptable, since `_CONTRACT_PATTERNS` is the client's own registry of domains it knows how to interpret.
- **Follow-up**: None.

## Risks & Mitigations
- Risk: A caller passes `required_contracts` expecting server-side enforcement. — Mitigation: requirements, design, and documentation state explicitly that this is client-side advisory reporting only; the server does not reject any request based on it.
- Risk: Future changes to `_capability_v2`'s hashing move the `capability_revision` value out of the JSON body while keeping it in the header, breaking the header/body comparison. — Mitigation: `Revalidation Triggers` in `design.md` names this exact change as a trigger to re-check this feature.

## References
- `lifetxt/remote_compatibility_v21.py` — existing compatibility manifest and evaluator.
- `lifetxt/remote_access.py:451-528` — `_capability_v2`, `capability_revision`, `protocol_response_headers`.
- `docs/en/remote-compatibility.md` — currently published client-behavior contract.
- GitHub Issue #120 — task-level scope, out-of-scope, and acceptance criteria.
