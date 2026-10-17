// Node WASM evidence is intentionally labelled separately from browser evidence.
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';
const directory = resolve(process.argv[2]);
const output = process.argv[3];
const {loadEngine} = await import(pathToFileURL(resolve(directory, 'engine.mjs')));
const startup = performance.now();
const engine = await loadEngine(new Uint8Array(await readFile(resolve(directory,'core.zip'))),
  await readFile(resolve(directory,'adapter.py'),'utf8'), resolve(directory,'runtime')+'/');
const startupMs = performance.now()-startup;
const fixtures = JSON.parse(await readFile(resolve(directory,'fixtures.json'),'utf8'));
const cases = [];
for (const fixture of fixtures) {
  const before = performance.now();
  const result = engine.check(fixture.text);
  cases.push({name:fixture.name,match:JSON.stringify(result)===JSON.stringify(fixture.expected),
    check_ms:performance.now()-before,result});
}
const loads = [];
for (const lines of [1,100,1000,2000]) {
  const text = '[ ] T "Read paper"\n'.repeat(lines);
  const before=performance.now(); const result=engine.check(text);
  loads.push({lines,utf8_bytes:Buffer.byteLength(text),check_ms:performance.now()-before,
    items:result.items,runtime:engine.info()});
}
let oversizedRejected=false;
try {engine.check('あ'.repeat(22000));} catch (_) {oversizedRejected=true;}
const result={environment:'Node.js WASM, not a browser or mobile measurement',node:process.version,
  runtime:engine.info(),startup_ms:startupMs,cases,loads,oversizedRejected};
await writeFile(output,JSON.stringify(result,null,2)+'\n');
engine.dispose();
console.log(JSON.stringify({startup_ms:startupMs,runtime:result.runtime,cases:cases.length,
  matches:cases.filter(x=>x.match).length,oversizedRejected,loads},null,2));
if(cases.some(x=>!x.match)||!oversizedRejected) process.exitCode=1;
