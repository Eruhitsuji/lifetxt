import {Worker} from 'node:worker_threads';
import {readFile, writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
const [directory, fixturePath, output] = process.argv.slice(2);
const worker = new Worker(new URL('./website_checker_node_worker.mjs', import.meta.url), {workerData:{directory}});
let sequence = 0, ticks = 0;
const timer = setInterval(()=>ticks++, 10);
const messages = [];
function request(text) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    function cleanup() {
      clearTimeout(timeout);
      worker.off('message', listener);
      worker.off('error', onError);
    }
    const timeout = setTimeout(()=>{cleanup();reject(new Error('Worker timeout'));}, 30000);
    const onError = error => {cleanup();reject(error);};
    const listener = data => {
      messages.push(data);
      if (data.id !== id || !['result','error'].includes(data.stage)) return;
      cleanup(); resolve(data);
    };
    worker.once('error', onError); worker.on('message',listener); worker.postMessage({id,text});
  });
}
try {
  const cases = [];
  for (const fixture of JSON.parse(await readFile(fixturePath,'utf8'))) {
    const started = performance.now(), reply = await request(fixture.text);
    if (fixture.reject) assert.equal(reply.stage,'error', fixture.name);
    else assert.deepEqual(reply.result,fixture.expected,fixture.name);
    cases.push({name:fixture.name,stage:reply.stage,worker_ms:reply.check_ms,elapsed_ms:performance.now()-started});
  }
  const repeated = [];
  for (let i=0;i<30;i++) {
    const reply = await request('[ ] T "Read"\n'.repeat(1000));
    assert.equal(reply.result.items,1000); repeated.push(reply.check_ms);
  }
  assert.ok(ticks>0);
  await writeFile(output,JSON.stringify({environment:'Node worker_threads/WASM; not browser acceptance',node:process.version,cases,repeated_ms:repeated,heartbeat_ticks:ticks,startup:messages.find(m=>m.stage==='ready')},null,2));
  console.log(`Node WASM: ${cases.length} cases, 30 repeats; browser acceptance is separate.`);
} finally {clearInterval(timer); await worker.terminate();}
