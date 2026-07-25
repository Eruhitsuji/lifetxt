# Unified Inbox and Proposals

Quick captures and AI suggestions do not write straight into life.txt. They are
staged as reviewable **proposals** in an operational store. A person reviews each
one and accepts, edits, rejects, defers, or batch-applies it. Only on accept is
the change appended to the workspace write target through the same validated,
atomic writer as every other authoritative mutation.

The store is operational, not authoritative: it holds pending intentions, never
the life.txt truth. Accepting is the single point where an intention becomes a
record.

## Staging

```console
$ lifetxt proposal add "Buy milk" --project home --due 2026-08-01
$ lifetxt proposal add "Call Bob" --assignee bob --source mcp
```

AI clients stage proposals through the MCP `stage_proposal` tool, which writes
only to the proposal store — never to life.txt.

## Reviewing

```console
$ lifetxt proposal list                 # all proposals with a line preview
$ lifetxt proposal list --status pending
$ lifetxt proposal show P-1a2b3c4d
```

## Editing before acceptance

```console
$ lifetxt proposal edit P-1a2b3c4d --title "Buy oat milk" --project home
```

Only pending proposals can be edited.

## Accepting, rejecting, deferring

```console
$ lifetxt proposal accept P-1a2b3c4d              # append to the write target
$ lifetxt proposal accept P-1 P-2 P-3             # batch apply
$ lifetxt proposal reject P-9
$ lifetxt proposal defer P-8
```

Accept appends the proposal's item to the workspace write target (or `--to`) and
marks it `accepted`. Batch apply reports a per-proposal outcome and continues
past individual failures.

## Configuration

```json
{ "inbox": { "proposals_file": ".cache/lifetxt/proposals.json" } }
```

## MCP

- `list_proposals` (read-only) — review staged proposals
- `stage_proposal` — stage a create proposal for human review (operational store
  only; a person accepts it later)

Proposals follow `inbox-proposal-v1.schema.json` (an extension of
`proposal-v1`).
