# Editor Support

This project includes basic VS Code support in
[`editors/vscode/lifetxt`](../../editors/vscode/lifetxt), described below, and a
separate, code-level mechanism for opening `life.txt` in **any** external
editor safely from the CLI, the TUI, and `fzf`/`peco` selections. The
"Editing From The CLI" and "The Editor Safety Contract" sections further down
this document cover that mechanism; it does not depend on the VS Code
extension at all.

## Current Scope

The current editor support is intentionally lightweight:

- TextMate syntax highlighting for comments, item starts, statuses, types,
  titles, detail keys, quoted strings, dates/times, body continuation lines,
  and ID references.
- VS Code snippets for common item types and detail keys.
- File association for `life.txt`, `*.life.txt`, `*_life.txt`, `.life.txt`, and `.lifetxt`.

This works without running a background process and can be copied into a local
VS Code installation.

The current grammar highlights all implemented item types:

```txt
T E D R H N S M J
```

The title capture uses a separate scope from detail values, so themes can color
the title differently from detail keys and quoted strings.

## Local Installation

Windows example:

```powershell
$target = "$env:USERPROFILE\.vscode\extensions\lifetxt"
New-Item -ItemType Directory -Force $target
Copy-Item -Recurse -Force .\editors\vscode\lifetxt\* $target
```

Reload VS Code after copying. The workspace also contains `.vscode/settings.json`
so files named `*_life.txt` are associated with the `lifetxt` language inside
this project. You can also open `editors/vscode/lifetxt` in VS Code and press
`F5` to start an Extension Development Host.

## Completion Strategy

Static snippets cover the common cases:

- `task`, `event`, `status`, `message`, `journal`, `habit`
- `subtask`, `body`, `ibody`
- `id`, `parent`, `depends_on`, `blocks`
- `due`, `fromto`, `dtz`, `project`, `tag`

These snippets intentionally mirror the current format profile:

- `status` inserts type `S` with `from:`, `state:`, and `person:`.
- `message` inserts type `M` with `sender:`, `recipient:`, `notify_at:`, and
  `body:`.
- `journal` inserts type `J` with a `|` body continuation line.
- `repeat-limited` inserts `repeat:`, `interval:`, `until:`, and `count:`.
- `dtz` inserts a datetime with seconds, fractional seconds, and timezone.

For richer completion, the recommended next step is an optional language server
that reuses the Python parser and validator.

## Editing From The CLI: `lifetxt edit`

Besides the TUI's `/edit` command and `fzf --action edit` (see
[`cli.md`](./cli.md), sections 13.1 `tui` and 13.2 `fzf`), lifetxt has a
dedicated standalone command for opening one item's source file in an
external editor:

```sh
python -m lifetxt edit t1 life.txt --show-diff
```

```txt
python -m lifetxt edit ID [paths ...]
  --editor CMD    Override EDITOR/VISUAL/config for this run.
  --dry-run       Print the resolved editor command and exit; do not launch it.
  --review-only   Open a temporary copy and print the diff without applying it.
  --reconcile     Conservatively merge non-overlapping external edits made while the editor is open.
  --keep-temp     Keep the edited temporary copy on disk for manual recovery.
  --show-diff     Print the applied diff after a successful edit.
```

`ID` is looked up the same way `lifetxt show` and `lifetxt next` look up an
item; if it is not found, the command exits with an error rather than opening
an editor. `--dry-run` prints the exact argv lifetxt would run, without a
temporary file involved, which is useful for confirming what an unfamiliar
`EDITOR` value resolves to:

```console
$ EDITOR=code python -m lifetxt edit t1 life.txt --dry-run
code -g 'C:\path\to\life.txt:1'
```

`--review-only` and `--show-diff` both print a unified diff produced by
`difflib.unified_diff`, one before the write and one after it; `--review-only`
never writes, `--show-diff` writes and then shows what changed. Verified with
a scripted stand-in editor: `--review-only` left the source file byte-for-byte
identical while still reporting the change the editor made in its temporary
copy, and running the same edit again without `--review-only` applied it and
printed the same diff.

## The Editor Safety Contract

`lifetxt edit`, `fzf --action edit`, and the TUI's `/edit` all route through
one function, `lifetxt.editor_safety.safe_edit`, instead of opening
`life.txt` in place. That function is the "delegated-mutation-proposal
contract" this document is about: the editor is treated as an untrusted,
long-running external process, and its output is only trusted after three
checks pass.

1. **Edit a copy, not the source.** `safe_edit` copies the source file into a
   fresh temporary directory (`lifetxt-edit-*`) and points the editor at that
   copy. The editor process can crash, hang, or be closed with unsaved
   changes without ever touching `life.txt`.
2. **Validate before writing.** Once the editor exits, the temporary copy is
   parsed with `lifetxt.parser.parse_text`. An editor session that leaves the
   file syntactically invalid never reaches the write step; the parse error is
   reported instead.
3. **Revision-checked write.** Both the original read and the eventual write
   go through lifetxt's normal revision-checked mutation path
   (`lifetxt.mutation`), the same one every other lifetxt write uses. If
   `life.txt` changed on disk while the editor was open, the plain (no
   `--reconcile`) case fails loudly with a `MutationConflict` naming the
   expected and found revisions, and nothing is written — confirmed by
   editing through a scripted stand-in editor that also modified the source
   file "externally" mid-session.

### Conflict reconciliation (`--reconcile`)

`--reconcile` (`lifetxt edit` only; `fzf --action edit` and the TUI always use
the plain, fail-on-any-change path) attempts a conservative three-way merge
instead of refusing outright. It diffs the original text against both the
editor's result and the file's current on-disk content
(`difflib.SequenceMatcher`), and only accepts the merge when the two sets of
changed line ranges do not overlap; if they do, it raises
`EditorReconcileConflict` naming the overlapping range instead of guessing
which side should win:

```text
The editor and source changed the same line range (1:2).
```

This check operates on `difflib`'s diff hunks, not on which fields you
touched — verified live: editing two lines that were adjacent to (but not
literally the same as) a concurrently-changed line was still reported as
overlapping, because `SequenceMatcher` grouped the nearby changes into one
hunk. Treat `--reconcile` as "merges edits that are clearly far apart in the
file," not as line-level precision merging.

### `--keep-temp` and recovery

`--keep-temp` prevents the temporary directory from being deleted after the
command finishes and prints its path. Combined with `--review-only`, this is
a way to inspect or manually salvage an editor session without ever writing
to `life.txt`: nothing is applied, and the edited copy remains on disk for
you to diff or copy from by hand.

### Default editor resolution differs by entry point

Both entry points look for `EDITOR`, then `VISUAL`, then the config file's
`editor` key (see [`cli.md`](./cli.md)'s "Choosing an editor" section for the
exact resolution order, executable lookup through `PATH`, and per-editor
line-number argument conventions). What happens when **none** of those is set
differs:

- `fzf --action edit` and the TUI's `/edit`
  (`lifetxt.fzf_helper.resolve_editor`) return `None` and the command fails
  with the same "No editor configured" message `cli.md` documents.
- `lifetxt edit` (`lifetxt.extra_core.command_edit`'s `_resolve_editor`
  helper) instead falls back to a hardcoded default: `notepad` on Windows,
  `vi` everywhere else — verified by clearing `EDITOR`/`VISUAL` and
  confirming `lifetxt edit --dry-run` still printed a runnable command
  instead of erroring.

If you rely on a specific editor, set `EDITOR`/`VISUAL` (or the config
`editor` key) explicitly rather than depending on `lifetxt edit`'s fallback,
since the fallback differs from what `fzf`/TUI editing does and is not
configurable per invocation except via `--editor`.

## Planned Language Server Features

A future LSP implementation should provide:

- Diagnostics equivalent to `python -m lifetxt check`.
- Type/status-aware detail-key completion.
- ID completion for `parent:`, `ref:`, `depends_on:`, `blocks:`, and
  `related:`.
- Hover help from the format specification.
- Document symbols grouped by type, project, tag, and hierarchy.
- Commands or code actions for `links`, `agenda`, `status`, and ID assignment.

Keep the static extension dependency-free. Put dynamic behavior behind an
optional language-server package so CLI users and plain text users are not
forced to install editor dependencies.
