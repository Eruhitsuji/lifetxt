# Unified Inbox and Proposals

Quick captures and AI suggestions do not write straight into life.txt. They are
staged as reviewable **proposals** in an operational store
(`lifetxt/inbox.py`). A person reviews each one and accepts, edits, rejects,
defers, or batch-applies it. Only on accept is the change appended to the
workspace write target through the same validated, atomic writer
(`append_life_records`) as every other authoritative mutation.

The store is operational, not authoritative: it holds pending intentions, never
the life.txt truth. Accepting is the single point where an intention becomes a
record.

> **Not to be confused with `lifetxt inbox`.** The CLI also has an unrelated
> `lifetxt inbox` command that lists open tasks with no `project:`, `due:`, or
> `assignee:` (GTD-style triage of already-authoritative items, with an
> optional `--process` interactive prompt) — see `lifetxt inbox --help`. It
> shares the "inbox" name with this feature by coincidence and has nothing to
> do with the proposal store described on this page; a proposal accepted with
> no project/due/assignee will, in fact, show up there once it lands in
> life.txt, which is exactly how this distinction was confirmed.

## Staging

```console
$ lifetxt proposal add "Buy milk" --project home --due 2026-08-01
Staged proposal P-12471d4d

$ lifetxt proposal add "Call Bob" --assignee bob --source mcp
Staged proposal P-e123f000
```

The generated ID is `P-` followed by 8 hex characters (`new_proposal_id`,
`uuid4().hex[:8]`) — not sequential, so proposal IDs from different sessions or
machines will not collide. `proposal add` always stages a **create**
proposal (`--kind` defaults to `T`); `--project`, `--due`, `--assignee`,
`--priority`, and repeatable `--tag` become the item's details, exactly the
same detail keys `quick`/`assist` would write. `--source` is a free-form label
(`manual` by default) recorded on the proposal, not validated against a fixed
list.

AI clients stage proposals through the MCP `stage_proposal` tool
(`lifetxt/mcp.py`), which writes only to the proposal store — never to
life.txt. Its `source` defaults to `mcp` instead of `manual`. Both paths call
the same `stage_create` function, so a proposal staged by an AI client and one
staged with `proposal add` are indistinguishable once stored — same ID scheme,
same schema, same review flow.

`stage_proposal` (and the underlying `stage_create` function) accepts an
optional `idempotency_key`. Without one, retrying the identical call — for
example after a dropped or timed-out MCP response — stages a second,
independent proposal, exactly as before. Supplying the same key on a retry
with the same title/kind/details returns the already-staged proposal instead
of creating a duplicate; reusing the key for a materially different request
fails loudly (`ValueError`) rather than silently creating a second proposal
or silently reusing a mismatched one. `proposal add` has no equivalent flag —
a human typing the command already sees whether they already ran it.

`create` is currently the only proposal `operation` either path produces; the
stored schema's `operation` field is a free string (`inbox-proposal-v1`
inherits it from `proposal-v1`), but nothing in this codebase stages or
accepts a non-`create` proposal today — `apply_proposal` looks for a `changes`
entry with `"op": "create"` and raises if none exists.

## Reviewing

```console
$ lifetxt proposal list                 # all proposals with a line preview
P-12471d4d   [pending ] manual   [ ] T "Buy milk" project:home due:2026-08-01
P-e123f000   [pending ] mcp      [ ] T "Call Bob" assignee:bob
(2 total: pending=2)

$ lifetxt proposal list --status pending
$ lifetxt proposal show P-12471d4d
{
  "proposal_version": "1",
  "id": "P-12471d4d",
  "operation": "create",
  "source": "manual",
  "expected_revision": "9a1c...e7f2",
  "staged_target": "life.txt",
  "idempotency_key": "",
  "changes": [
    {
      "op": "create",
      "kind": "T",
      "status": "[ ]",
      "title": "Buy milk",
      "details": { "project": ["home"], "due": ["2026-08-01"] }
    }
  ],
  "warnings": [],
  "status": "pending",
  "provenance": { "source": "manual" },
  "created": "2026-08-10T10:30:19"
}
```

`expected_revision` and `staged_target` are captured automatically when the
proposal is staged: `staged_target` is the same default write target
`proposal accept` would resolve (`inbox.write_file`, falling back to the
first configured path, falling back to `life.txt`), and `expected_revision`
is that file's real content-hash revision at that moment (the sentinel
`"<missing>"` when the target does not exist yet). `provenance` currently
records only `source`, echoed from the field above it. See
[Staleness](#staleness) for how these two fields are used at accept time.
`idempotency_key` is empty unless the caller supplied one.

`proposal show` always prints the full JSON record; there is no plain-text
form. `--status` on `proposal list` accepts `pending`, `accepted`, `rejected`,
or `deferred`. The trailing summary line (`(N total: ...)`) always reflects
every proposal in the store, independent of any `--status` filter on the list
above it. `proposal list --json` returns the raw proposal array without the
summary line or preview text.

Proposals — across every status — also show up in
[search.md](search.md)'s global search, matched against both the rendered
line preview and `source`:

```console
$ lifetxt find "milk" --type proposal
1 match(es) for 'milk':
proposal (1):
  P-12471d4d           [accepted] [ ] T "Buy oat milk" project:home due:2026-08-01
```

## Editing before acceptance

```console
$ lifetxt proposal edit P-12471d4d --title "Buy oat milk" --project home
Edited proposal P-12471d4d
```

Only pending proposals can be edited — editing an already-accepted, rejected,
or deferred proposal fails loudly:

```console
$ lifetxt proposal edit P-12471d4d --title x
ERROR: Only pending proposals can be edited.
```

(exit 1, and the proposal is left unchanged). `edit` merges `--project`/`--due`/
`--assignee`/`--priority` into the existing details rather than replacing the
whole detail set, so omitted flags keep their prior values; `--title` and
`--kind` replace the corresponding field outright. There is no `--tag` flag on
`edit` (unlike `add`).

## Accepting, rejecting, deferring

```console
$ lifetxt proposal accept P-12471d4d              # append to the write target
Accepted P-12471d4d -> life.txt
  [ ] T "Buy oat milk" project:home due:2026-08-01

$ lifetxt proposal accept P-1 P-2 P-3             # batch apply
$ lifetxt proposal reject P-9
$ lifetxt proposal defer P-8
```

Accept appends the proposal's item to the workspace write target (or `--to`)
and marks it `accepted`. The accepted item's title is written **quoted**
(`"Buy oat milk"`) through the normal item serializer, not
underscore-joined the way `quick`/`assist`/`message send` write a typed title
— both are valid life.txt syntax and `lifetxt check` accepts either form.

A ticket-shaped proposal (`--kind T` with a `record:ticket` detail and an
`id:`) also gets its `created` `record:ticket_event` appended in the same
write, matching what `lifetxt ticket new` produces — see
[tickets.md](tickets.md#workflow-append-only-history-and-time). A
non-ticket-shaped proposal, or a ticket-shaped one missing `id:` (staging
does not auto-generate one the way `ticket new` does), is unaffected.

An already-accepted proposal, an unknown ID, and editing/re-accepting after
acceptance are all reported instead of silently no-op'd:

```console
$ lifetxt proposal accept P-12471d4d              # already accepted
ERROR: P-12471d4d: Proposal 'P-12471d4d' is already accepted.
Applied 0/1.

$ lifetxt proposal reject P-nosuch
ERROR: Unknown proposal 'P-nosuch'.
```

Batch apply reports a per-proposal outcome and continues past individual
failures — one bad ID in a batch does not stop the rest from applying:

```console
$ lifetxt proposal accept P-b627dcd8 P-nosuch
ERROR: P-nosuch: Unknown proposal 'P-nosuch'.
Accepted P-b627dcd8 -> life.txt
  [ ] T "Untyped item"
Applied 1/2.
```

(exit code is 0 only when every ID in the batch applied; here it is 1 even
though the valid ID succeeded). `batch_apply` accepts an optional
`expected_revision` for the whole batch and clears it after the first
successful append; the CLI's `proposal accept` never supplies one, so a
plain accept relies on each proposal's own `staged_target`/`expected_revision`
captured when it was staged (see [Staleness](#staleness)) rather than a
caller-supplied revision.

## Staleness

Accepting a proposal checks the workspace against the revision captured when
it was staged, not just whatever the target file happens to contain right
now:

```console
$ lifetxt proposal accept P-12471d4d
ERROR: P-12471d4d: Proposal 'P-12471d4d' is stale: life.txt changed since it
  was staged. Review the current file and re-stage if the change still
  applies.
Applied 0/1.
```

This fires when the accept target matches the proposal's own `staged_target`
and the target's current content hash no longer matches its
`expected_revision` — i.e. something else changed the file after the
proposal was staged. It does **not** fire when:

- accepting into a different file than `staged_target` (the captured revision
  does not describe that file, so the check is skipped rather than compared
  against unrelated content);
- a caller passes an explicit `expected_revision` to `accept`/`batch_apply`,
  which always takes precedence over the proposal's own stored value;
- accepting the *second or later* proposal in one `proposal accept P-1 P-2
  P-3` batch call, once an earlier proposal in the same batch has already
  been applied — each earlier write is expected to move the target past what
  any later proposal in the batch itself saw when staged, so only the first
  proposal in a batch is checked against its own stage-time snapshot.

A concurrent external edit is still caught either way: even when the
stage-time check does not apply, every accept goes through
`append_life_records`, the same validated, atomic writer used everywhere
else, which still performs its own compare-and-set against the file's
current revision at the moment of the write.

## Configuration

```json
{ "inbox": { "proposals_file": ".cache/lifetxt/proposals.json" } }
```

`inbox.proposals_file` is the only configuration key for this feature. It
supports `~` expansion and is created (including parent directories) on first
write; a missing or unreadable/corrupt store is treated as empty rather than
an error (`load_proposals` catches `OSError`/`ValueError` and returns `[]`).

## MCP

- `list_proposals` (read-only) — review staged proposals, optionally filtered
  by `status`. Returns `{"proposals": [...], "counts": {...}, "total": N}` —
  the same per-status counts `proposal list`'s trailing summary line shows.
- `stage_proposal` — stage a create proposal for human review (operational
  store only; a person accepts it later). Requires `title`; accepts `kind`
  (default `T`), `details` (an object — repeat-count details like `tag` still
  take a JSON array), and `source` (default `mcp`). Raises `ValueError` when
  `title` is missing.

There is no MCP tool for `accept`/`reject`/`defer`/`edit` — those stay
human-only operations, and today only the CLI implements them at all (neither
`lifetxt/tui.py`/`lifetxt/tui_app.py` nor `lifetxt/webapp.py` currently expose
any proposal-review surface). This matches the design intent that accepting is
"the single point where an intention becomes a record" and should not be
automatable by the same class of client that proposes changes. See
[messaging.md](messaging.md#mcp) for the read-only
MCP tools around the messaging feature, which follows the same "AI proposes,
human accepts" split for anything that would otherwise write to life.txt
directly.

Proposals follow `inbox-proposal-v1.schema.json` (an extension of
`proposal-v1`); the `status` enum is `pending`/`accepted`/`rejected`/`deferred`.
