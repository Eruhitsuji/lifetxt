# Requirements Document

## Project Description (Input)
Issue #221: add an optional fuzzy/approximate search mode so users can
still find records and derived entities when the query contains a
small typo, omission, or near match. Current search paths (CLI
`search`, CLI `find`/global search, Web `/api/items?q=`) are
deterministic substring-only matching. Scoped for this first slice
(confirmed with the repository owner via AskUserQuestion, given the
issue's own full horizontal-review list spans CLI/TUI/Web/MCP/Remote
and has no fixed task size): one shared, deterministic fuzzy-matching
primitive, applied to CLI item-level `search`, CLI global `find`, and
the Web `/api/items` endpoint. TUI, MCP `global_search`, and Remote
read-only search resources are explicitly deferred to follow-up issues
recorded with evidence, not silently dropped.

## Requirements

### Requirement 1: Shared fuzzy-matching primitive
**Objective:** As a maintainer, I want one deterministic fuzzy-matching
module reused by every surface in scope, so behavior cannot silently
diverge between them.

#### Acceptance Criteria
1. THE SYSTEM SHALL provide one importable module implementing
   Unicode-normalized similarity scoring, with no new third-party
   dependency.
2. THE SYSTEM SHALL normalize compared text with NFKC plus casefold,
   so full-width/half-width Japanese variants and Latin case
   differences do not affect matching.
3. WHEN the query is an exact case/width-insensitive substring of the
   candidate text, THE SYSTEM SHALL treat it as a full-confidence
   match, ranked strictly above any approximate-only match for the
   same query.
4. WHEN the normalized query is shorter than 3 characters, THE SYSTEM
   SHALL only evaluate exact-substring matching for that query, never
   approximate scoring, since edit-distance scoring on very short
   strings produces unstable, low-signal results.
5. THE SYSTEM SHALL bound the cost of a single similarity comparison
   regardless of input length (a maximum compared-character length per
   string and a maximum number of tokens compared per field), so one
   pathologically long field or query cannot make a single comparison
   unbounded.
6. THE SYSTEM SHALL apply one fixed, documented similarity threshold
   and deterministic tie-breaking (score, then original scan order),
   so identical input always produces identical results.

### Requirement 2: Opt-in behavior preserved everywhere
**Objective:** As an existing user of `search`, `find`, or
`/api/items`, I want my current exact-substring results unchanged by
default, so this feature cannot silently change what I already rely
on.

#### Acceptance Criteria
1. WHEN fuzzy mode is not explicitly requested, THE SYSTEM SHALL
   produce byte-for-byte the same matching decisions as before this
   change, for all three in-scope surfaces.
2. THE SYSTEM SHALL require an explicit per-request opt-in (a CLI flag
   or an API query parameter) to enable fuzzy matching; there is no
   global always-on configuration setting in this slice.

### Requirement 3: CLI item-level search (`lifetxt search`)
**Objective:** As a CLI user, I want `search` to optionally tolerate a
typo in my pattern, so a near-miss does not require retyping.

#### Acceptance Criteria
1. WHEN `--fuzzy` is passed to `search`, THE SYSTEM SHALL match a
   field if it is an exact substring of the pattern OR scores at or
   above the shared threshold against the shared primitive.
2. WHEN `--fuzzy` is passed together with `--regex`, THE SYSTEM SHALL
   reject the combination with a clear error, since a compiled regex
   pattern has no meaningful fuzzy-similarity score.
3. WHEN `--fuzzy` is not passed, THE SYSTEM SHALL behave exactly as
   before (Requirement 2.1).
4. THE SYSTEM SHALL preserve `search`'s existing document-order output
   under `--fuzzy`; this slice does not add relevance ranking to
   `search`, which has no ranking concept today and whose output order
   is otherwise governed by document order alone.

### Requirement 4: CLI/global search (`lifetxt find`)
**Objective:** As a CLI user, I want `find` to optionally surface
near-miss matches across every entity type it already searches, ranked
so exact matches are never buried under approximate ones.

#### Acceptance Criteria
1. WHEN `--fuzzy` is passed to `find`, THE SYSTEM SHALL apply the
   shared primitive across every entity type `find` already searches
   (item, project, person, group, area, proposal), without a
   per-entity-type reimplementation.
2. WHEN `--fuzzy` is passed, THE SYSTEM SHALL order each entity type's
   result rows with exact-substring matches before approximate-only
   matches, breaking ties by original scan order.
3. WHEN `--fuzzy` is not passed, THE SYSTEM SHALL behave exactly as
   before (Requirement 2.1), including existing result order.

### Requirement 5: Web `/api/items` fuzzy query parameter
**Objective:** As a Web UI or API client, I want to opt into fuzzy
matching for the `q`/`text` filter, so the same tolerance is available
without a separate endpoint.

#### Acceptance Criteria
1. WHEN the `fuzzy=true` query parameter is present on `GET
   /api/items`, THE SYSTEM SHALL apply the shared primitive to the
   existing `q`/`text` filter using the same match/no-match semantics
   as Requirement 3.1.
2. WHEN `fuzzy` is absent or falsy, THE SYSTEM SHALL behave exactly as
   before (Requirement 2.1).
3. THE SYSTEM SHALL preserve `/api/items`' existing `sort`/`order`
   parameters as the sole ordering control; this slice does not add
   relevance ranking to `/api/items`, whose ordering is already an
   explicit, independent contract.

## Out of Scope (this slice)
- TUI search commands/views, MCP `global_search`, and Remote read-only
  search resources: recorded as follow-up candidates with evidence of
  where the shared primitive would need to be wired in, not
  implemented here.
- A persistent/rebuildable search index (`todo.md` already keeps this
  explicitly deferred).
- A Web UI toggle control for `fuzzy=true` (this slice is the API
  parameter only; a UI checkbox is a follow-up candidate).
- Result score/matched-field metadata surfaced in API responses beyond
  what already exists (`field`, `snippet` for `find`).
- Fuzzy semantics for structured filters (status/type/project/detail
  equality) -- those remain exact, unaffected by this change.
