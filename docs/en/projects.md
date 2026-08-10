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
$ cat plan.json   # review before applying -- share it, diff it, hold it
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
| tamper check failed (`plan_hash` mismatch) | The plan file was edited after `--emit-plan` wrote it | Re-emit and review a fresh plan; never hand-edit a plan file |
| stale source/destination revision | A scanned source or the archive destination changed since the plan was emitted | Re-run `--dry-run --emit-plan` to produce a current plan |
| workspace/config drift | The active workspace's configuration changed since emission | Re-run `--dry-run --emit-plan` |
| selection drift | The candidate set re-derived from current state no longer matches the plan's frozen item-ID list | Re-run `--dry-run --emit-plan`; investigate what changed the selection (edited status, new someday tag, etc.) |
| recovery evidence unreachable | The transaction journal/backup directory is missing or not writable | Fix storage access before applying |

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

## Transparent derivations

Every derived number states how it was computed:

- **progress** = `done_tasks / non_cancelled_tasks * 100`. When a project has no
  non-cancelled work, progress is `null` with an explicit reason.
- **health** = `red` for an open critical/high risk, or overdue work with
  progress below 50%; `yellow` for overdue, blocked, or open medium/low risk;
  `green` otherwise. Each report lists its reasons and any missing-data
  limitations (for example, "overdue not evaluated: no reference date").
