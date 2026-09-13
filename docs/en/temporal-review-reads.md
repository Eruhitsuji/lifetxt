# Temporal review read surfaces

The read-only Personal Context CLI exposes three bounded projections:

- `decision-review --format json`: follows only explicit `realizes:` links from
  recorded decisions and never infers causality.
- `change-feed --since OFFSET --until OFFSET --format json`: returns typed,
  meaningful historical changes, separate from current attention state.
- `future-intent --cutoff OFFSET --until OFFSET --format json`: returns only
  explicitly authored future time fields.

Text and JSON are rendered from the same domain result. Missing evidence is
reported as unresolved or incomplete rather than inferred from current state.
