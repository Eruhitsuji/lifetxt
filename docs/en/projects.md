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

## Transparent derivations

Every derived number states how it was computed:

- **progress** = `done_tasks / non_cancelled_tasks * 100`. When a project has no
  non-cancelled work, progress is `null` with an explicit reason.
- **health** = `red` for an open critical/high risk, or overdue work with
  progress below 50%; `yellow` for overdue, blocked, or open medium/low risk;
  `green` otherwise. Each report lists its reasons and any missing-data
  limitations (for example, "overdue not evaluated: no reference date").
