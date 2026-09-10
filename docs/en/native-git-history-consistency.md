# Native History and Git consistency

`lifetxt history-check PATH [PATH ...]` performs a read-only, bounded semantic
comparison between Native History in the current life.txt and state transitions
observable in reachable Git revisions.

```bash
lifetxt history-check life.txt
lifetxt history-check life.txt --id task-1
lifetxt history-check life.txt --commit-limit 50 --json
```

The default commit limit is 100 and the accepted range is 1–500. The command
does not compare raw lines, formatting, comments, or commit counts. It projects
item creation, lifecycle status, progress, `follows`/`realizes`/`replaced_by`,
and `on`/`due`/`from`/`to`/`at` changes from adjacent Git states, then matches
that bounded transition set against normalized Native events. One commit may
verify any number of events. Exact source-content revision provenance is used
to prefer a match when available; timestamps alone never establish identity.

Results are classified as:

- `verified`: both sources declare the same semantic transition;
- `native_only`: no matching Git transition is reachable in the window;
- `git_only`: a Git transition has no Native event, normally a coverage gap;
- `conflict`: comparable evidence exists but before/after meaning disagrees;
- `unverifiable`: Native evidence is malformed/non-authoritative or its record
  kind has no deterministic Git projection in v1.

Git is optional. Outside a repository, Native History and `timeline` continue
to work; `history-check` reports Git unavailable and classifies otherwise-valid
Native changes as `native_only`. Shallow history, missing paths, and commit-limit
truncation are explicit limitations and can never produce `complete:true`.
Ticket events and time entries remain visible in the Native Timeline but are
`unverifiable` in v1 unless a deterministic Git semantic projection is added.

The verifier never repairs, backfills, reorders, or writes Native History or
Git. Existing `timeline`, `thread --revision`, `thread --as-of`, and
`thread --diff` behavior is unchanged. JSON output follows
[`native-git-history-consistency-v1.schema.json`](../../dist/schemas/native-git-history-consistency-v1.schema.json).
