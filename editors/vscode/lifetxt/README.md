# life.txt VS Code support

This directory contains a lightweight VS Code extension for life.txt files.

## Features

- Syntax highlighting for comments, status, type, title, detail keys, quoted strings, dates, times, body continuations, and ID references.
- Snippets for common item types: task, event, status, message, journal, habit, nested task, and recurrence.
- Snippet completions for common detail keys such as `id:`, `parent:`, `depends_on:`, `blocks:`, `due:`, `from:/to:`, `project:`, and `tag:`.
- File association for `life.txt`, `*.life.txt`, `*_life.txt`, `.life.txt`, and `.lifetxt`.

## Local installation

For development, copy or symlink this directory into your VS Code extensions
directory, then reload VS Code.

Windows example:

```powershell
$target = "$env:USERPROFILE\.vscode\extensions\lifetxt"
New-Item -ItemType Directory -Force $target
Copy-Item -Recurse -Force .\editors\vscode\lifetxt\* $target
```

The workspace also includes `.vscode/settings.json` with `files.associations`
for `life.txt`, `*.life.txt`, `*_life.txt`, `.life.txt`, and `.lifetxt`.
This makes `*_life.txt` files use the `lifetxt` language inside this project
even if filename pattern matching from the extension manifest is not applied by
the editor.

Alternatively, open this directory in VS Code and press `F5` to start an
Extension Development Host.

## Design notes

This extension intentionally starts with static TextMate grammar and snippets.
That keeps editor support dependency-free and easy to copy into local setups.

Future dynamic features should be implemented as a language server that reuses
the Python parser and validator:

- diagnostics from `python -m lifetxt check`
- context-aware detail-key completion by type/status
- ID completion for `parent:`, `ref:`, `depends_on:`, `blocks:`, and `related:`
- hover help from the detail-key descriptions
- commands for `agenda`, `status`, `links`, and `assist`

The static extension and a future language server can coexist: keep TextMate
highlighting in this package and add dynamic behavior through an optional VS
Code client/server layer.
