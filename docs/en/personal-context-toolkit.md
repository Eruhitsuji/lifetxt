# Personal Context toolkit

The Personal Context toolkit is a thin deterministic layer over lifetxt's existing **Personal AI Memory** convention. It does not add a new record kind, database, AI provider dependency, or first-class Query vocabulary.

A Personal Context fact remains an ordinary Note, for example:

```text
[ ] N "Prefers dark mode in editors" id:pref-editor person:self tag:preference source:user updated:2026-08-24T10:00:00+09:00
```

The toolkit composes existing `person:`, `tag:`, `source:`, `updated:`, ID/link, Temporal Context, workspace, and Unified Inbox behavior.

## Context Health

Inspect whether Personal Context is current enough and internally connected:

```bash
lifetxt context health
lifetxt context health --format json --pretty
```

The report has mutually exclusive lifecycle states:

- `current` — not stale and not superseded;
- `stale` — the existing Temporal Context staleness rule reports `stale_since`;
- `superseded` — another authoritative record carries `corrects:<this-id>`.

It also reports independent quality findings:

- missing `source:` provenance;
- missing or ambiguous ID-based references.

Change the existing staleness threshold when needed:

```bash
lifetxt context health --stale-after-days 30
```

No health command writes to the workspace.

## Why does lifetxt remember this?

`context why` explains one item using deterministic stored/derived evidence:

```bash
lifetxt context why pref-editor
lifetxt context why pref-editor --format json --pretty
```

The report shows the stored provenance/time metadata, Personal Context tags/subject, current/stale/superseded state, and incoming/outgoing ID links. It is **not** an LLM explanation and does not expose or generate model chain-of-thought.

## Correct a memory without deleting history

When an explicit fact or preference changes, stage a replacement instead of rewriting the past:

```bash
lifetxt memory correct pref-editor "Prefers light mode in editors"
```

The command creates a pending Unified Inbox proposal. It does not change authoritative `life.txt`.

The proposed replacement is still an ordinary Note and preserves applicable `person:`, `tag:`, and `project:` values. It receives a lifetxt-generated ID plus:

```text
corrects:pref-editor source:manual updated:<current-time>
```

Review it with the normal proposal workflow:

```bash
lifetxt proposal list
lifetxt proposal show P-12345678
lifetxt proposal accept P-12345678
```

After acceptance, Context Health, Context Why, and Context Capsule treat the old `pref-editor` record as superseded because the new authoritative record points back with `corrects:pref-editor`.

`corrects:` is deliberately a **custom-detail convention** in this slice. It is not a new Format 1.0 key or Query field, and validators may report the normal non-blocking unknown-custom-key diagnostic. The value is preserved by the Format parser/serializer.

## Portable Context Capsule

Export a bounded provider-independent snapshot:

```bash
lifetxt context capsule --pretty
lifetxt context capsule --tag preference --pretty
lifetxt context capsule --tag goal --limit 20 --pretty
```

JSON is the default output. The capsule contains:

- `schema: personal-context-capsule-v1`;
- a deterministic SHA-256 `revision` for the selected context;
- the selected person/tags and bounds;
- deterministic item records.

Unchanged input plus unchanged options produces the same capsule revision. Superseded and stale memories are excluded by default; add `--include-stale` when historical/stale context is intentionally needed.

The capsule is a **generated read-only projection**, not another source of truth. ChatGPT, Claude, Gemini, local LLMs, IDE agents, or scripts may consume it without becoming authoritative storage for lifetxt.

Because export is explicit, review the selected workspace and records before sending a capsule to an external service. Operation permission and disclosure policy remain separate concerns.

## Decision Memory

A decision is still an ordinary Personal Context Note tagged `decision`:

```text
[ ] N "Use SQLite for the local cache" id:decision-cache person:self tag:decision project:demo source:user updated:2026-08-24T10:00:00+09:00
```

List decisions:

```bash
lifetxt decisions
lifetxt decisions --project demo
lifetxt decisions --format json --pretty
```

The view excludes stale and superseded decisions by default and uses the same Personal Context lifecycle rules as the capsule.

## Workspaces and multiple files

All read commands use the normal lifetxt workspace/path resolution:

```bash
lifetxt context health --workspace personal
lifetxt context capsule --workspace personal --tag preference
lifetxt decisions --workspace personal --project demo
```

Explicit paths remain supported as well. `memory correct` resolves the target from the selected read workspace and stages the proposal against the normal configured proposal/write target; authoritative mutation still occurs only when the proposal is accepted.

## Design boundary

This first toolkit intentionally does **not** add:

- a Personal Context record kind;
- `subject:`, `assertion:`, `confidence:`, `valid_from:`, or `valid_to:` contracts;
- Query syntax for `corrects:`;
- embeddings/vector storage/RAG corpora;
- provider-specific memory APIs;
- automatic AI writes to authoritative Personal Context.

The goal is to make existing user-owned plain-text memory more inspectable, correctable, and portable with the smallest coherent implementation surface.
