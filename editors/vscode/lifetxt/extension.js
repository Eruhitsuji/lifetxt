'use strict';
const vscode = require('vscode');
let client;
async function activate(context) {
  // Lazy import: static-only installs do not need Node packages or Python.
  const config = vscode.workspace.getConfiguration('lifetxt');
  if (!vscode.workspace.isTrusted || !config.get('languageServer.enabled', false)) return;
  try {
    const { LanguageClient } = require('vscode-languageclient/node');
    const python = config.get('languageServer.python', 'python');
    if (typeof python !== 'string' || !python.trim()) throw new Error('Invalid Python executable');
    client = new LanguageClient('lifetxt', 'life.txt', {
      command: python,
      args: ['-m', 'lifetxt.lsp', '--stdio'],
      options: { shell: false }
    }, {
      documentSelector: [{ language: 'lifetxt', scheme: 'file' }, { language: 'lifetxt', scheme: 'untitled' }],
      diagnosticCollectionName: 'lifetxt',
      markdown: { isTrusted: false },
      connectionOptions: { maxRestartCount: 0 },
      synchronize: { configurationSection: undefined },
      initializationOptions: {},
    });
    context.subscriptions.push(client);
    await client.start();
  } catch (_) {
    // Details remain in the LSP output channel; do not expose paths/text here.
    await vscode.window.showWarningMessage('life.txt language server could not start. Install lifetxt in the selected Python environment, check the life.txt output channel, then reload. Static highlighting and snippets remain available.');
  }
}
async function deactivate() {
  if (client) { await client.stop(); client = undefined; }
}
module.exports = { activate, deactivate };
