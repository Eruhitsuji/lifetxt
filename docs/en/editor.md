# Editor Support

This project includes basic VS Code support in
[`editors/vscode/lifetxt`](../../editors/vscode/lifetxt).

## Current Scope

The current editor support is intentionally lightweight:

- TextMate syntax highlighting for comments, item starts, statuses, types,
  titles, detail keys, quoted strings, dates/times, body continuation lines,
  and ID references.
- VS Code snippets for common item types and detail keys.
- File association for `life.txt`, `*.life.txt`, `*_life.txt`, `.life.txt`, and `.lifetxt`.

This works without running a background process and can be copied into a local
VS Code installation.

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

For richer completion, the recommended next step is an optional language server
that reuses the Python parser and validator.

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
