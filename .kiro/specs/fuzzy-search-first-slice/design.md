# Design Document

## Overview
A new module `lifetxt/fuzzy_search.py` implements a dependency-free,
deterministic similarity primitive: NFKC + casefold normalization,
exact-substring short-circuit (score 1.0 family, always above any
approximate score), and a bounded token-level Levenshtein fallback for
everything else. Three existing surfaces import it behind an explicit
opt-in: `command_search`'s `--fuzzy` flag, `command_find`/
`global_search()`'s `--fuzzy` flag, and `/api/items`'s `fuzzy=true`
query parameter.

## Boundary Commitments
### This Spec Owns
- `lifetxt/fuzzy_search.py` (new): `normalize_text`, `similarity`,
  `fuzzy_contains`.
- The `--fuzzy` flag wiring in `command_search` (`lifetxt/cli.py`).
- The `--fuzzy` flag wiring in `command_find` and `global_search()`
  (`lifetxt/cli.py`, `lifetxt/global_search.py`).
- The `fuzzy` parameter wiring in `filter_items()`
  (`lifetxt/agenda.py`) and `/api/items` (`lifetxt/webapp.py`).

### Out of Boundary
- TUI, MCP, Remote search surfaces (recorded as follow-up candidates
  in the closing traceability entry, not touched here).
- `filter_agenda_records`, `filter_items`'s other filter parameters,
  and every non-text filter -- unchanged.
- A relevance-ranking system for `filter_items`/`search`/`/api/items`
  output order -- explicitly out of scope per requirements 3.4 and
  5.3; only `global_search()`'s per-entity-type result lists gain
  ranking, since that is the one surface already returning a "results"
  list rather than a document-order filter.

### Allowed Dependencies
- Python standard library only (`unicodedata`, `re`).

## Algorithm
```
similarity(query, text):
  q = normalize(query); t = normalize(text)
  if not q: return 0.0
  if q == t: return 1.0
  if q in t: return 0.999                      # exact substring, always > any fuzzy-only score
  if len(q) < 3: return 0.0                     # too short to score meaningfully; substring already checked above
  candidates = tokenize(t) + [t]                # bounded: first 50 tokens, each truncated to 200 chars
  best = max(1 - levenshtein(q, c) / max(len(q), len(c)) for c in candidates)
  return max(0.0, best)

fuzzy_contains(query, text, threshold=0.6):
  return similarity(query, text) >= threshold
```
`levenshtein` is the standard iterative dynamic-programming edit
distance (no external library); both operands are truncated to 200
characters first so one pathological field cannot make a single
comparison unbounded (Requirement 1.5). Tokenization splits on
whitespace and common punctuation; it is a plain `re.split`, no
Unicode segmentation library, which is an accepted first-slice
simplification -- contiguous CJK runs without spaces become one token
each, so exact-substring matching (checked first, unconditionally)
remains the primary path for that case rather than token-level fuzzy
scoring.

## Complexity and Data Scale
- `levenshtein(a, b)` is O(len(a) * len(b)) time and O(len(b)) space
  (rolling two rows), bounded to at most 200*200 per comparison by the
  truncation above.
- `similarity()` compares against at most 51 candidates (50 tokens +
  the full text), so one field-level call is bounded to roughly 51 *
  200 * 200 character-comparisons in the worst case -- small enough to
  run per-item, per-field, without a benchmark-driven optimization
  pass; life.txt workspaces in this project's own test fixtures and
  examples are on the order of hundreds of items, not the millions
  where this would matter.
- No index is built or cached; every call re-scans, matching every
  existing search path's current (non-fuzzy) behavior and `todo.md`'s
  explicit "no persistent index until benchmarks justify one."

## File Structure Plan
### New Files
- `lifetxt/fuzzy_search.py` -- the shared primitive.
- `tests/test_fuzzy_search.py` -- unit coverage for the primitive
  itself (normalization, thresholds, short-query bound, determinism,
  cost bound).

### Modified Files
- `lifetxt/cli.py` -- `command_search` (`--fuzzy`, `--regex`
  incompatibility check), `command_find` (`--fuzzy` argparse flag,
  passed through to `global_search()`).
- `lifetxt/global_search.py` -- `_match()` gains a `fuzzy` parameter;
  `global_search()` gains a `fuzzy` parameter and, when set, ranks
  each entity type's rows (exact first, then descending score, tied
  broken by scan order) instead of preserving raw scan order.
- `lifetxt/agenda.py` -- `filter_items()` gains a `fuzzy` parameter
  used only by the existing `text` filter.
- `lifetxt/webapp.py` -- `/api/items` gains a `fuzzy` query parameter,
  threaded into the existing `filter_items(text=...)` call.
- `docs/en/cli.md`, `docs/ja/cli.md`, `docs/en/web.md`,
  `docs/ja/web.md` -- document `--fuzzy` and `fuzzy=true`.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1-1.2 | `fuzzy_search.normalize_text` (NFKC + casefold) |
| 1.3 | `similarity()`'s `q in t` branch returns 0.999, always above the bounded fuzzy-only ceiling |
| 1.4 | `similarity()`'s `len(q) < 3` early return |
| 1.5 | 200-char truncation, 50-token cap |
| 1.6 | fixed `DEFAULT_THRESHOLD = 0.6`; sorting uses `(-exact, -score, original_index)` |
| 2.1-2.2 | every call site defaults `fuzzy=False`/flag absent, unchanged code path when falsy |
| 3.1-3.4 | `command_search`'s `_matches()` closure gains a fuzzy branch; `--regex`+`--fuzzy` argparse-time rejection; document order untouched |
| 4.1-4.3 | `_match()`/`global_search()` shared across all six entity searchers; ranking applied only under `fuzzy=True` |
| 5.1-5.3 | `/api/items`'s `fuzzy` param threaded to `filter_items`; `sort`/`order` params untouched |

## Testing Strategy
- Unit tests for `fuzzy_search.py` directly: normalization
  (full-width/half-width Japanese, Latin case), exact-substring always
  outranking fuzzy-only, sub-3-character queries falling back to
  substring-only, determinism (same input twice), and a bounded-cost
  smoke test with a long pathological string.
- `command_search --fuzzy` and `command_find --fuzzy`: typo fixtures
  reproduced through the real installed CLI, confirming a near-miss
  now matches and the non-fuzzy path is byte-for-byte unchanged.
- `/api/items?fuzzy=true`: exercised through a real `lifetxt serve`
  process with `curl`, confirming the same typo fixture matches only
  when `fuzzy=true` is present.
- Full suite re-run to confirm no regression in any of the many
  existing `filter_items`/`global_search`/`command_search` callers,
  none of which set the new parameter and so must be unaffected.
