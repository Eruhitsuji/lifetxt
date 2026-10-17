// Exercise this extension's trust/opt-in and failure fallback with host doubles.
const Module = require('node:module');
const assert = require('node:assert/strict');
const original = Module._load;
let imports = 0, starts = 0, warnings = 0, options;
const vscode = {workspace:{isTrusted:false, getConfiguration:()=>({get:(key, fallback)=>key==='languageServer.enabled'?true:fallback})},window:{showWarningMessage:async()=>warnings++}};
class LanguageClient {
  constructor(id, name, server, client) { options={server,client}; }
  async start() { starts++; throw new Error('missing interpreter'); }
  async stop() {}
}
Module._load = function(name, ...args) {
  if(name==='vscode') return vscode;
  if(name==='vscode-languageclient/node') {imports++; return {LanguageClient};}
  return original.call(this,name,...args);
};
(async () => {
  try {
    const ext = require('../extension');
    const context={subscriptions:[]};
    await ext.activate(context); assert.equal(imports,0);
    vscode.workspace.isTrusted=true;
    vscode.workspace.getConfiguration=()=>({get:(key,fallback)=>key==='languageServer.enabled'?false:fallback});
    await ext.activate(context); assert.equal(imports,0);
    vscode.workspace.getConfiguration=()=>({get:(key,fallback)=>key==='languageServer.enabled'?true:fallback});
    await ext.activate(context);
    assert.equal(starts,1); assert.equal(warnings,1); assert.equal(options.server.options.shell,false);
    assert.deepEqual(options.server.args,['-m','lifetxt.lsp','--stdio']);
    assert(!options.client.documentSelector.some(x=>x.language==='plaintext'));
    await ext.deactivate();
    console.log('Trust, opt-in, executable argv and failure fallback passed');
  } finally {Module._load=original;}
})().catch(e=>{console.error(e);process.exitCode=1;});
