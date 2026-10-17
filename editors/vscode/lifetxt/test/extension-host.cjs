// Run with the real VS Code --extensionTestsPath entrypoint.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');
const fixture = require('../../../../tests/fixtures/editor/interop.json');
const wait = ms => new Promise(r => setTimeout(r, ms));
async function run() {
  await vscode.workspace.getConfiguration('lifetxt').update('languageServer.enabled', true, vscode.ConfigurationTarget.Global);
  await vscode.workspace.getConfiguration('lifetxt').update('languageServer.python', process.env.LIFETXT_TEST_PYTHON, vscode.ConfigurationTarget.Global);
  const extension = vscode.extensions.getExtension('lifetxt.lifetxt');
  assert(extension);
  await extension.activate();
  const document = await vscode.workspace.openTextDocument({ language: 'lifetxt', content: fixture.text });
  const start = Date.now();
  while (!vscode.languages.getDiagnostics(document.uri).length && Date.now() - start < 15000) await wait(50);
  const diagnostics = vscode.languages.getDiagnostics(document.uri).map(d => ({ code: d.code, severity: d.severity + 1, range: d.range }));
  assert(diagnostics.length, 'No diagnostics from actual VS Code LSP client');
  const h = await vscode.commands.executeCommand('vscode.executeHoverProvider', document.uri, new vscode.Position(fixture.hover.line, fixture.hover.character));
  assert(h.length, 'No hover');
  const edit = new vscode.WorkspaceEdit();
  edit.replace(document.uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), fixture.completionText);
  await vscode.workspace.applyEdit(edit);
  const point = document.positionAt(document.getText().length);
  await wait(500);
  const result = await vscode.commands.executeCommand('vscode.executeCompletionItemProvider', document.uri, point);
  const labels = result.items.map(x => typeof x.label === 'string' ? x.label : x.label.label).filter(x => fixture.expectedCompletion.includes(x));
  assert.deepEqual(labels, fixture.expectedCompletion);
  const output = { client: 'VS Code ' + vscode.version, diagnostics, completion: labels, hover: h.map(x => x.contents) };
  fs.writeFileSync(process.env.LIFETXT_TEST_OUTPUT, JSON.stringify(output, null, 2));
  await extension.exports?.deactivate?.();
}
module.exports = { run };
