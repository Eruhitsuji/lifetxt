# life.txt VS Code support

Format 1.0 static highlighting and all nine record snippets work without Python
or Node dependencies. Dates use explicit `YYYY-MM-DD` tabstops; enter the intended
date before saving. Weekly `.txt` files require selecting the life.txt language;
generic `.txt` files are not claimed.

## Optional language server

VS Code 1.82+, trusted workspace, Python 3.10+ with this lifetxt module installed.
The read-only server is opt-in. It provides unsaved-buffer diagnostics, contextual
completion and plaintext Hover from Core metadata. It never writes your source,
executes commands, installs dependencies or sends network requests.

1. Explicitly install lifetxt in the interpreter you will use.
2. In this directory, run `npm ci --omit=dev --ignore-scripts` if dynamic support
   is wanted. Copy this directory including production `node_modules` into your
   VS Code extensions folder; reload. For static-only use copying without Node
   dependencies is sufficient.
3. Set `lifetxt.languageServer.enabled` to `true` and
   `lifetxt.languageServer.python` to the interpreter executable path in VS Code
   user settings, then reload. No shell arguments. Remote Development uses the
   extension host's interpreter.

Both settings are non-secret, added in 0.2.0, and require a window reload.
`enabled` is boolean/default false/window scope; `python` is string/default
`python`/machine scope. The manifest is their registry; Core `config explain`
does not apply. Untrusted workspaces stay static-only. Missing Python or client
package produces an actionable warning while static features remain available.
Disable the setting and reload to restore static-only behavior. Disable before
using a lifetxt version without `lifetxt.lsp`; remove the copied directory and
reload to uninstall. Once dependencies are prepared, operation is offline.

See the full [English](../../../docs/en/editor.md) and
[Japanese](../../../docs/ja/editor.md) guides for scope, limits and Neovim.
This is local installation support; no Marketplace publication is implied.

## Verification

With dev dependencies installed (`npm ci --ignore-scripts`):

```sh
npm run test:grammar
node test/activation.cjs
# Run from repository root, with Python containing lifetxt:
node editors/vscode/lifetxt/test/protocol.cjs
```

`test/extension-host.cjs` is an actual VS Code test-host entry point. It is kept
separate from host doubles and the Microsoft protocol test; these do not prove
GUI acceptance. Neovim's actual-client probe is `editors/neovim/probe.lua`.
