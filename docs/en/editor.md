# Editor Support

This project includes basic VS Code support in
[`editors/vscode/lifetxt`](../../editors/vscode/lifetxt), described below, and a
separate, code-level mechanism for opening `life.txt` in **any** external
editor safely from the CLI, the TUI, and `fzf`/`peco` selections. The
"Editing From The CLI" and "The Editor Safety Contract" sections further down
this document cover that mechanism; it does not depend on the VS Code
extension at all.

## Current Scope

Static editor support includes:

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

## Static Format 1.0 coverage

All nine record types have snippets: `task`, `event`, `deadline`, `reminder`, `habit`, `note`, `status`, `message`, `journal`. `do` inserts planned execution; `due` inserts a deadline. Date tabstops say `YYYY-MM-DD`: replace these before saving; no old sample date is silently accepted. Titles and text detail placeholders are quoted. `|` body text stays plain. Highlighting includes metadata, all reference keys and the trailing `\` continuation marker; it is display assistance, not validation.

Weekly names such as `2026-W42.txt` require choosing **life.txt** in the language selector, or an explicit `files.associations` setting such as `"2026-W*.txt": "lifetxt"`. Generic `*.txt` is never captured. Static support needs neither Python nor an LSP.

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


## Optional language server (local, read-only)

Python **3.10+** with lifetxt installed can run `python -m lifetxt.lsp --stdio`.
No LSP Python extra is needed. Install explicitly in your chosen environment
(`python -m pip install -e .` from this checkout, or install a release containing
this module). Once installed, the server works offline. It never installs tools,
loads Core configuration, scans disk, follows symlinks, sends network requests,
executes commands, or writes life.txt. Editor saves still write directly;
`safe_edit` protects only the CLI/TUI temporary-copy workflow described above.

Implemented: lifecycle, full document synchronization, versioned diagnostics,
UTF-16 completion edits and plaintext Hover. Core parser/validator codes and
severity are retained, with `F110` additionally reporting unsupported Format
metadata from the existing Core policy helper. Unknown end spans stay zero-width;
logical continuation columns map back to physical lines. No formatting,
format-on-save, automatic fixes, code actions, symbols or definition provider.
Completion avoids unfinished quotes, titles, comments, body and joined-line
contexts. Free/custom keys are preserved. Help currently reuses English Core
metadata; both installation guides are maintained.

### VS Code (1.82+)

The extension remains usable by copying its directory for static support.
Dynamic support additionally needs its **optional** Node client dependency:
run `npm ci --omit=dev --ignore-scripts` in `editors/vscode/lifetxt` before copying
that directory (including installed production `node_modules`). This install is
explicit and is not performed by the extension. An already prepared copy can be
used offline. No Marketplace publication is implied.

In VS Code user settings:

```json
{
  "lifetxt.languageServer.enabled": true,
  "lifetxt.languageServer.python": "/absolute/path/to/python"
}
```

On Windows use a Python executable path, for example
`"C:\\Python312\\python.exe"`; do not put shell arguments in it. In Remote
Development the Python path refers to the **extension host**, not your desktop.
Virtual URI providers are static-only; `file` and `untitled` buffers are selected.
Reload the window after changing any server setting. Startup failure shows a warning;
inspect the life.txt output channel, install lifetxt in that interpreter and
reload. Missing Python/client dependency does not disable static features.
Untrusted workspaces always stay static-only, even when enabled in settings.

| Extension setting | Type/default | Scope/provenance | Restart/secrets/compatibility |
| --- | --- | --- | --- |
| `lifetxt.languageServer.enabled` | boolean / `false` | VS Code window setting; trusted workspace required | Reload window; non-secret; added 0.2.0; disable for static fallback |
| `lifetxt.languageServer.python` | string / `python` | VS Code machine/user setting, executable only | Reload window; non-secret; added 0.2.0; set the interpreter containing the matching lifetxt version |
| `lifetxt.languageServer.idKey` | string / `id` | VS Code window setting; explicit equivalent of Core `ids.key` | Reload window; non-secret; added 0.2.0; older clients ignore it; return to `id` for default behavior |

These settings belong to the extension manifest, not the lifetxt config schema;
`lifetxt config explain` does not report them. There is no Core config migration.
Older extension copies ignore them; disable the LSP before downgrading to a
lifetxt version without this module. To uninstall, disable the setting and remove
the copied extension directory, then reload.

### Neovim (0.11+)

Explicitly load [`editors/neovim/lifetxt.lua`](../../editors/neovim/lifetxt.lua)
from your trusted `init.lua`, replacing `python` with the installed interpreter.
It uses built-in `vim.lsp.config` / `vim.lsp.enable`, with no lspconfig plugin.
Weekly files use `:setfiletype lifetxt`. Disable with
`vim.lsp.enable('lifetxt', false)` and remove the config to uninstall. Python is
optional for plain-text use, required only while this LSP configuration is on.

### Resource and compatibility limits

The server accepts at most 32 open buffers, 256 KiB UTF-8 per buffer, 200
completion/diagnostic entries, 2 MiB frames and 8 KiB headers. It rejects out-of-
order document versions and incremental edits (full sync is advertised).
For rejected documents, inspect the client log and close/reopen to resynchronize;
old valid snapshots remain intact but are suspended from diagnostics, completion,
Hover and cross-buffer candidate/reference resolution. A full update newer than
the rejected version also resumes assistance; equal/older versions cannot resume it. Requests run synchronously; client debounce
reduces traffic, cancellation does not interrupt Core parsing already running.
No background workspace scan, telemetry or automatic source mutation occurs.

## Open-buffer workspace and rollout status

All life.txt buffers explicitly opened in the same server session share ID,
project, tag, person and other Core completion values, including unsaved changes.
Closing a buffer removes its candidates and republishes remaining reference
warnings. Root paths and filesystem URIs are opaque: opening a workspace folder
alone never authorizes scanning its files. This scope includes multiple roots in
one client session; use separate windows/server sessions when those buffers must
not share candidates. Unopened files cannot satisfy references.

For a custom Core `ids.key`, explicitly set `lifetxt.languageServer.idKey` in
VS Code or append `--id-key uid` to Neovim's `cmd`. The server never silently loads
Core configuration. Incompatible Format declarations do not contribute IDs to
current documents. Very deep Core reference graphs produce adapter diagnostic
`LSP001`; local syntax diagnostics remain available, but graph validation is
incomplete. Simplify the chain or close unrelated buffers. No source is changed.

| Surface | Delivered support | Verification / remaining boundary |
| --- | --- | --- |
| Plain text editor | Existing templates, minimum grammar and manual workflow | No Python, LSP or network required |
| VS Code static (1.80+) | All types, snippets, associations and TextMate grammar | Core snippet checks and actual TextMate/Oniguruma corpus |
| VS Code dynamic (1.82+) | Optional pinned client, diagnostics/completion/Hover | Microsoft protocol and host doubles verified; GUI host/Windows/macOS acceptance tracked in #1373 |
| Neovim (0.11+ config API) | Built-in LSP configuration | Actual Neovim 0.12.6 Linux common fixture verified; 0.11/other OS not exercised |
| Zed | Not integrated | Needs language metadata, Tree-sitter grammar/queries and extension adapter investigation |
| Sublime Text | Not integrated | Needs syntax plus community LSP client configuration and acceptance |
| JetBrains | Not integrated | Select concrete IDE/API-supported version and plugin design before claiming support |

## Official Windows editor support and release artifacts (#1389)

**Supported editor clients:** VS Code (1.82+ for optional LSP; static features
also work on 1.80+) and Neovim (0.11+) **on Windows only**. This support
statement is limited to editor assistance and does not redefine Core/CLI/server
operating system support. Regular Vim/Vim9, Marketplace/Open VSX publishing and
Linux/macOS editor guarantees are outside this release scope.

The existing human-approved GitHub Release pipeline includes two Windows
editor archives, both bound to the same lifetxt release tag/source SHA and
SHA256SUMS:

- `lifetxt-vscode-<lifetxt-version>.vsix`
- `lifetxt-neovim-windows-<lifetxt-version>.zip`

These become downloadable **only after an authorized Release**; a preflight
build or merged PR is not proof that a specific public version exists.
The VS Code extension has its own three-component extension version (currently
`0.2.0`), distinct from the lifetxt application release `X.Y.Z[.N]`.
Both archives contain a release provenance record linking the extension version,
application version, candidate digest, and source SHA. Verify the published
SHA256SUMS before installing; a file in a non-public CI artifact is not an
approved public release.

### Install VSIX on Windows

1. Download the `.vsix` and `SHA256SUMS` from the *same* GitHub Release.
   Verify the listed SHA256 using `Get-FileHash .\lifetxt-vscode-*.vsix -Algorithm SHA256`.
2. In VS Code choose Extensions → `...` → **Install from VSIX...**,
   or run `code --install-extension .\lifetxt-vscode-<version>.vsix`.
3. Reload VS Code, open `life.txt`, and confirm language `life.txt`.
   Static syntax/snippets work without Python; no LSP is started by default.
4. For optional diagnostics/completion/Hover, separately install the matching
   lifetxt Python package into Python 3.10+, then in VS Code user settings set
   `lifetxt.languageServer.enabled` to `true` and
   `lifetxt.languageServer.python` to the full Windows path to that interpreter
   (for example `C:\\Python312\\python.exe`; JSON requires escaped backslashes).
   Reload. The path must contain **only** the executable, no CLI arguments.
   If IDs use a non-default key, explicitly set `lifetxt.languageServer.idKey`.
5. To return to static-only support set `enabled=false` and reload.
   To uninstall, use Extensions → life.txt → Uninstall (or
   `code --uninstall-extension lifetxt.lifetxt`) and reload.
   Disable LSP before downgrading lifetxt to a version without
   `lifetxt.lsp`. A missing Python or LSP client never requires modifying
   `life.txt`; static editing remains possible.

### Install Neovim configuration on Windows

1. Download the same-release Neovim ZIP, verify SHA256, then safely extract
   `lifetxt.lua`, `release.json` and `INSTALL-WINDOWS.md` into a
   trusted local directory; read the included instructions.
2. Separately install lifetxt in Python 3.10+ only if LSP is desired.
   Review the Lua file, edit its `cmd` Python executable, and explicitly add
   `dofile([[C:\path\to\lifetxt.lua]])` to your own `init.lua`.
   This turns on Neovim built-in LSP for the `lifetxt` filetype; no
   `nvim-lspconfig` plugin is required. Ordinary manual editing needs none of it.
3. Reload Neovim; open `life.txt`. Weekly `.txt` files require
   `:setfiletype lifetxt`. To stop LSP:
   `:lua vim.lsp.enable('lifetxt', false)`.
   To uninstall/remove opt-in, delete the added `dofile` line and the
   extracted directory, then restart. Do not overwrite the rest of `init.lua`.

Windows GUI and Neovim actual-client core scenarios were recorded in
[#1373](https://github.com/Eruhitsuji/lifetxt/issues/1373);
the Owner explicitly left additional edge cases unexecuted. Neither CI archive
inspection nor that focused acceptance proves every Unicode/path/offline/reconnect
combination, nor certifies other operating systems. A failing LSP is read-only
and optional: disable it and continue static/manual editing.

Marketplace/registry publication is not included. Symbol/definition/action providers
and disk-backed workspace discovery remain future work, not advertised capabilities.

For local performance regression monitoring run
`python -m editors.benchmark_lsp > baseline.json`, then
`python -m editors.benchmark_lsp --baseline baseline.json --max-ratio 2` on the
same Python/OS/machine. The 1,000-item/two-buffer fixture measures parsing,
compact position mapping, reference diagnostics and completion with tracemalloc.
The initial Linux/Python 3.12 observation was about 137 ms median and 4.3 MB peak
Python allocations; it is a local observation, not a universal latency guarantee.
