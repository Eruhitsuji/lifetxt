/* Real TextMate/Oniguruma tokenization; no regex-engine substitution. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const tm = require('vscode-textmate');
const onig = require('vscode-oniguruma');
(async () => {
  await onig.loadWASM(fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm')).buffer);
  const registry = new tm.Registry({onigLib: Promise.resolve({createOnigScanner: x => new onig.OnigScanner(x), createOnigString: x => new onig.OnigString(x)}), loadGrammar: async () => tm.parseRawGrammar(fs.readFileSync(path.join(__dirname, '../syntaxes/lifetxt.tmLanguage.json'), 'utf8'), 'lifetxt.json')});
  const grammar = await registry.loadGrammar('source.lifetxt');
  const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, '../../../..', 'tests/fixtures/editor/grammar.json'), 'utf8'));
  for (const fixture of fixtures) {
    const result = grammar.tokenizeLine(fixture.text, tm.INITIAL);
    for (const [needle, scope] of fixture.expect) {
      const start = fixture.text.indexOf(needle);
      assert(start >= 0);
      assert(result.tokens.some(t => t.startIndex <= start && t.endIndex >= start + needle.length && t.scopes.includes(scope)), JSON.stringify({fixture, tokens:result.tokens}));
    }
  }
  console.log(`${fixtures.length} TextMate fixtures passed`);
})().catch(e => {console.error(e); process.exitCode = 1;});
