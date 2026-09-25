# Projects and Portfolio

A project is any value used in a `project:` detail. lifetxt aggregates the items
that share a project, merges optional static metadata from the configuration
registry, and reports progress, health, workload, milestones, risks, decisions,
and meetings — without introducing a new item type.

## Records

Describe a project and its artifacts with ordinary items tagged by `record:`:

| Record            | Type | Key fields                                   |
| ----------------- | ---- | -------------------------------------------- |
| `record:project`  | N    | `project:`, `owner:`, `area:`, `state:`, `due:`, `do:` (start), `visibility:` |
| `record:milestone`| D    | `project:`, `due:`, `owner:`                 |
| `record:risk`     | N    | `project:`, `severity:`, `state:`, `owner:`  |
| `record:issue`    | N    | `project:`, `severity:`, `state:`            |
| `record:decision` | N/J  | `project:`, `on:` (decision date)            |
| `record:meeting`  | E    | `project:`, `on:`, `at:`                     |

Ordinary tasks and deadlines carrying `project:` are counted as project work.
A task is **blocked** when a `depends_on:` target is not yet done, and
**overdue** when its `due:` date is before today.

## Registry

Static, slow-changing metadata lives under `projects` in configuration:

```json
{
  "projects": {
    "web": {
      "display_name": "Website Revamp",
      "aliases": ["website"],
      "default_assignee": "alice",
      "default_area": "work",
      "visibility": "shared"
    }
  }
}
```

Aliases resolve to the canonical project name in every command. Changing data —
progress, risks, decisions — stays in life.txt records, never in configuration.

## Commands

```console
$ lifetxt project list                 # progress + health per project
$ lifetxt project show web             # aggregated hub for one project
$ lifetxt project health --all         # health label with its formula
$ lifetxt project timeline web         # dated items in order
$ lifetxt project workload web         # per-assignee open/done/overdue
$ lifetxt project risks web            # risks by severity
$ lifetxt portfolio                    # compare all projects
```

Create records (append to the workspace write target):

```console
$ lifetxt project new payments --owner carol --area finance --due 2026-12-01
$ lifetxt project add milestone web "Launch MVP" --due 2026-08-15
$ lifetxt project add risk web "Latency spike" --severity high --owner bob
$ lifetxt project add decision web "Use Postgres" --on 2026-06-20
$ lifetxt project add meeting web "Kickoff" --on 2026-06-01
```

Add `--dry-run` to print the line without writing.

## Archiving

`lifetxt project archive NAME` moves one project's done/canceled records (and
any `record:ticket_event`/`record:time_entry` history that follows a done
ticket by `parent:`) to the workspace's configured `role: archive` source,
using the same atomic multi-file transaction engine as generic `archive`.

```console
$ lifetxt project archive web --dry-run   # preview only, no changes made
$ lifetxt project archive web             # requires --revision for every
                                           # scanned source and the archive
                                           # destination (see below)
```

Because a live `project archive` writes to an authoritative file, it requires
an exact `--revision PATH=SHA256` for every scanned source and the
destination; `--dry-run` prints the exact set to copy. This precondition,
plus a same-invocation zero-byte and parser-error refusal, were added after a
production incident (#183) where the safety of a live archive run could not
be confirmed after the fact.

### Reviewable archive plans (`--emit-plan` / `--apply-plan`)

For a review step between "what will be archived" and "actually archive it,"
`--dry-run --emit-plan PATH` writes an `archive-plan-v1` JSON document instead
of only printing text: the resolved workspace/config identity, exact source
and destination revisions, the frozen list of selected item IDs, external
references to archived items, and writer/process provenance. Nothing is
written to `life.txt` by `--emit-plan` itself.

`selected_item_ids` only lists items that carry an explicit `id:` (or
configured `id_key`) detail; an item with no ID is still archived correctly
but contributes nothing to that field. For a workspace without automatic ID
assignment enabled, review the plan alongside the dry-run text output rather
than `selected_item_ids` alone -- this does not weaken `--apply-plan`'s
safety guarantee, which comes from the source/destination revision check
(byte-identical input reproduces the same selection deterministically), not
from `selected_item_ids` itself.

```console
$ lifetxt project archive web --dry-run --emit-plan plan.json
Archive plan written to plan.json.
$ cat plan.json   # review before applying
$ lifetxt project archive web --apply-plan plan.json
Archive plan verified against current state (reserved_transaction_id=...).
No changes made.
Re-run the same command with --yes to apply it.
$ lifetxt project archive web --apply-plan plan.json --yes
Applying archive plan (reserved_transaction_id=...).
Archived 3 item(s) to ...
```

`--apply-plan` re-verifies every fact the plan recorded against *current*
state before writing anything, refusing loudly (with no files touched) when:

| Rejection | Meaning | Recommended action |
| --- | --- | --- |
| unsupported `plan_version` | The plan was produced by a newer/older `lifetxt` than this one understands | Re-emit the plan with the matching version |
| consistency check failed (`plan_hash` mismatch) | The plan file does not match its own recorded hash -- it was hand-edited or corrupted since `--emit-plan` wrote it | Re-emit and review a fresh plan; never hand-edit a plan file |
| stale source/destination revision | A scanned source or the archive destination changed since the plan was emitted | Re-run `--dry-run --emit-plan` to produce a current plan |
| workspace/config drift | The active workspace's configuration changed since emission | Re-run `--dry-run --emit-plan` |
| selection drift | The candidate set re-derived from current state no longer matches the plan's frozen item-ID list | Re-run `--dry-run --emit-plan`; investigate what changed the selection (edited status, new someday tag, etc.) |
| recovery evidence unreachable | The transaction journal/backup directory is missing or not writable | Fix storage access before applying |

**`plan_hash` is a self-consistency checksum, not a signature.** It is
computed from, and stored inside, the plan file itself, so it detects
accidental hand-edits or corruption -- it does not authenticate the plan's
origin or protect against someone who deliberately edits the file (they can
recompute a matching hash after any change). Treat a `plan.json` file with
the same trust as any other local input to this command: keep it under your
own control between `--emit-plan` and `--apply-plan`, the same way you would
an unsigned config file, rather than passing it through an untrusted
intermediary and relying on the consistency check to catch tampering.

`--apply-plan` is mutually exclusive with `--revision`, explicit source paths,
and `--dest` -- the plan already freezes all three. Applying without `--yes`
only verifies and reports the reserved transaction ID; it writes nothing.

As with the `--revision` path, a rejection leaves every source and
destination file byte-for-byte unchanged and does not consume a backup
generation. Recovery from a completed archive uses the same backup/journal
contract as any other multi-file write (see
[Safe Writes, Attachments, and Work Sessions](safe-writes-attachments-and-work-sessions.md));
a shell-side defense such as `set -o noclobber` is a reasonable extra
precaution when scripting `--emit-plan`/`--apply-plan` around an
untrusted or hand-edited plan path.

### `lifetxt maintenance plan`: orchestration over `--emit-plan`

`lifetxt maintenance plan NAME --emit-plan PATH` is a thin, plan-only
orchestration layer over `project archive --dry-run --emit-plan`. It reuses
the exact same `project archive` candidate-selection policy and
`archive-plan-v1` builder -- there is no second mutation engine or plan
schema. In this first slice, "maintenance" always means one thing: moving a
project's already-eligible done/canceled records (and their ticket history)
into the workspace's configured `role: archive` source, the same as a plain
`project archive --dry-run --emit-plan` call.

```console
$ lifetxt maintenance plan web --emit-plan plan.json
Maintenance requested: explicit operator request via `lifetxt maintenance plan` (no automatic Storage Health recommendation is available yet; see #945)
Project: web
Selection policy: project archive selection (status=done,canceled, before=(none), max_items=(none), orphan_children=block, block_on_external_refs=False)
Candidates: 3 item(s)
Plan written to plan.json.
No workspace file was changed. Review the plan, then apply it with:
  lifetxt project archive --apply-plan plan.json
```

The report always states why maintenance was requested. Today that is
always an explicit operator invocation, since the Storage Health
recommendation engine this command is designed to eventually front-end
(#945) has not shipped yet; once it exists, its recommendation text will
appear in the same `reason` field, still triggered by an operator or script
that chooses to act on it -- `maintenance plan` never runs or applies
anything on its own.

When no eligible candidate exists (or the selection is blocked -- open
children, external references with `--block-on-external-refs`), no plan
file is written and the command exits non-zero, matching `project archive
--dry-run --emit-plan`'s own no-op behavior; nothing is fabricated.

`maintenance plan` never writes to `life.txt` or the archive destination
itself -- the only file it can create is the plan document at `PATH`.
Applying a generated plan uses the exact same, independently re-verified
`lifetxt project archive --apply-plan PATH` path described above; there is
no `lifetxt maintenance apply`.

This first slice deliberately does not archive Notes, Journals, Events,
Messages, Status records, or any other non-project history merely because
it is old, and does not introduce yearly/monthly archive-file rotation --
see [issue #946](https://github.com/Eruhitsuji/lifetxt/issues/946) for the
full boundary.

## Transparent derivations

Every derived number states how it was computed:

- **progress** = `done_tasks / non_cancelled_tasks * 100`. When a project has no
  non-cancelled work, progress is `null` with an explicit reason.
- **health** = `red` for an open critical/high risk, or overdue work with
  progress below 50%; `yellow` for overdue, blocked, or open medium/low risk;
  `green` otherwise. Each report lists its reasons and any missing-data
  limitations (for example, "overdue not evaluated: no reference date").
