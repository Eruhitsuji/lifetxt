// Microsoft protocol layer used by vscode-languageclient; not a GUI test.
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const fs = require('node:fs');
const protocol = require('vscode-languageserver-protocol/node');
const fixture = require('../../../../tests/fixtures/editor/interop.json');
(async () => {
  const child = cp.spawn(process.env.LIFETXT_TEST_PYTHON || 'python', ['-m', 'lifetxt.lsp', '--stdio'], {stdio: ['pipe', 'pipe', 'pipe']});
  const connection = protocol.createProtocolConnection(child.stdout, child.stdin, {error:()=>{}, warn:()=>{}, info:()=>{}, log:()=>{}});
  let done;
  const diagnostics = new Promise(resolve => done = resolve);
  connection.onNotification(protocol.PublishDiagnosticsNotification.type, done);
  connection.listen();
  const timeout = setTimeout(() => {child.kill(); throw new Error('LSP timeout');}, 10000);
  try {
    const init = await connection.sendRequest(protocol.InitializeRequest.type, {processId: process.pid, capabilities: {general: {positionEncodings: ['utf-16']}}, rootUri: null});
    assert.equal(init.capabilities.positionEncoding, 'utf-16');
    connection.sendNotification(protocol.InitializedNotification.type, {});
    const uri = 'untitled:interop.life.txt';
    connection.sendNotification(protocol.DidOpenTextDocumentNotification.type, {textDocument:{uri, languageId:'lifetxt', version:1, text:fixture.text}});
    const d = await diagnostics;
    assert(d.diagnostics.length);
    const hover = await connection.sendRequest(protocol.HoverRequest.type, {textDocument:{uri}, position:fixture.hover});
    assert(hover.contents.value.includes('Deadline'));
    connection.sendNotification(protocol.DidChangeTextDocumentNotification.type, {textDocument:{uri, version:2}, contentChanges:[{text:fixture.completionText}]});
    const c = await connection.sendRequest(protocol.CompletionRequest.type, {textDocument:{uri}, position:{line:0, character:fixture.completionText.length}});
    const labels = c.map(x => x.label);
    assert.deepEqual(labels, fixture.expectedCompletion);
    const result = {client:'Microsoft vscode-languageserver-protocol 3.17.5 (GUI not exercised)', diagnostics:d.diagnostics.map(({code,severity,range})=>({code,severity,range})), completion:labels, hover};
    if (process.env.LIFETXT_TEST_OUTPUT) fs.writeFileSync(process.env.LIFETXT_TEST_OUTPUT, JSON.stringify(result, null, 2));
    await connection.sendRequest(protocol.ShutdownRequest.type);
    await connection.sendNotification(protocol.ExitNotification.type);
    await new Promise(resolve => child.once('exit', resolve));
    console.log('Microsoft protocol fixture passed');
  } finally { clearTimeout(timeout); connection.dispose(); if(child.exitCode === null) child.kill(); }
})().catch(e => {console.error(e); process.exitCode = 1;});
