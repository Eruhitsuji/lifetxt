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

The report classifies every record into one of the seven currentness states described below (`current`/`future-effective`/`stale`/`superseded`/`expired`/`conflicting`/`historical-only`), computed by the shared currentness resolver -- `context health` never runs a separate classification rule.

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

The report shows the stored provenance/time metadata, Personal Context tags/subject, the resolved currentness state plus bounded evidence/reasons (see below), and incoming/outgoing ID links. It is **not** an LLM explanation and does not expose or generate model chain-of-thought.

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

## Currentness (derived read states)

Beyond the three lifecycle states above, a deterministic **currentness resolver** classifies every Personal Context record into one of seven derived *read* states, computed at query time and never persisted as a status field:

- `current` — usable now;
- `future-effective` — `valid_from:` is later than the evaluation time;
- `stale` — the existing Temporal Context staleness rule reports `stale_since`;
- `superseded` — a unique authoritative replacement exists (`corrects:` or `replaced_by:`);
- `expired` — `valid_to:` is earlier than the evaluation time;
- `conflicting` — malformed/reversed validity evidence, a supersession cycle, or competing replacements of the same record that cannot be auto-resolved;
- `historical-only` — explicitly requested as historical context by the caller.

`valid_from:`/`valid_to:` are optional **custom-detail conventions** in this slice, not new Format 1.0 or Query vocabulary:

```text
[ ] N "Q3 hiring freeze is in effect" id:policy-q3 person:self tag:policy valid_from:2026-07-01 valid_to:2026-09-30
```

Neither key is required. A file with no validity metadata keeps today's behavior unchanged. A malformed value, or `valid_from` later than `valid_to`, resolves to `conflicting` rather than silently to `current`.

Supersession reuses the existing `corrects:`/`replaced_by:` conventions unchanged: a linear chain resolves to one current terminal record with every predecessor marked `superseded`; a cycle, or more than one record correcting/replacing the same predecessor, resolves every record involved to `conflicting` rather than guessing a winner. Superseded, expired, and conflicting records are never deleted -- they remain fully inspectable through `context health` and `context why`.

Ordinary retrieval (Context Capsule, Decision Memory) returns `current` records only by default; `stale` may be included only through an explicit opt-in, and `future-effective`/`superseded`/`expired`/`conflicting`/`historical-only` records are never silently presented as current truth.

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

Unchanged input plus unchanged options produces the same capsule revision. Only `current` records are included by default; `--include-stale` adds `stale` records only -- `future-effective`, `superseded`, `expired`, `conflicting`, and `historical-only` records are never silently included, even with `--include-stale`.

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

The view uses the same shared currentness filtering as the capsule: only `current` records by default, with `--include-stale` adding `stale` records only.

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
- `subject:`, `assertion:`, or `confidence:` contracts;
- Format 1.x/Query promotion of `valid_from:`/`valid_to:` (they remain custom-detail conventions);
- Query syntax for `corrects:`;
- automatic conflict resolution or a `last_confirmed` freshness clock;
- embeddings/vector storage/RAG corpora;
- provider-specific memory APIs;
- automatic AI writes to authoritative Personal Context.

The goal is to make existing user-owned plain-text memory more inspectable, correctable, and portable with the smallest coherent implementation surface.
