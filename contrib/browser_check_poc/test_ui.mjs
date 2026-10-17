// Deterministic lifecycle checks with fake DOM/Worker; not a rendering test.
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const elements=Object.fromEntries(['input','check','cancel','status','output'].map(id=>[id,{
  value:'[ ] T "Read"',textContent:'',disabled:false,
  addEventListener(event,fn){this[event]=fn;},
}]));
const workers=[];const timers=new Map();let timerId=0;
class FakeWorker{
  constructor(url,opts){assert.equal(url,'./worker.mjs');assert.equal(opts.type,'module');workers.push(this);}
  postMessage(data){this.sent=data;}
  terminate(){this.terminated=true;}
}
const context={document:{querySelector:s=>elements[s.slice(1)]},Worker:FakeWorker,TextEncoder,
  setTimeout(fn,ms){timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id)};
vm.runInNewContext(await readFile(new URL('./ui.mjs',import.meta.url),'utf8'),context);
assert.equal(workers.length,0); // Lazy load: input editing cannot create a runtime.
elements.check.click();assert.equal(workers.length,1);assert.equal(elements.check.disabled,true);
const first=workers[0];
first.onmessage({data:{id:first.sent.id,stage:'ready'}});
assert.equal([...timers.values()][0].ms,5000);
first.onmessage({data:{id:first.sent.id,stage:'result',result:{message:'<script>bad</script>'}}});
assert.match(elements.output.textContent,/<script>bad<\/script>/); // Text, never HTML.
assert.equal(elements.check.disabled,false);
elements.check.click();assert.equal(workers.length,1);assert.equal([...timers.values()][0].ms,5000);
elements.cancel.click();assert.equal(first.terminated,true);assert.equal(elements.input.value,'');
const cleared=elements.output.textContent;
first.onmessage({data:{id:first.sent.id,stage:'result',result:{late:true}}});
assert.equal(elements.output.textContent,cleared);
elements.input.value='あ'.repeat(22000);elements.check.click();assert.equal(workers.length,1);
assert.match(elements.status.textContent,/exceeds/);
elements.input.value='[ ] T "Again"';elements.check.click();assert.equal(workers.length,2);
[...timers.values()][0].fn();assert.equal(workers[1].terminated,true);assert.equal(elements.input.value,'');
console.log('UI lifecycle: lazy load, warm reuse, byte limit, text output, timeout, cancel, stale results OK');
