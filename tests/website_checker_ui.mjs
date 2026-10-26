// Fake DOM/Worker verification only; does not render a browser.
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=(await readFile(new URL('../website/checker/ui.mjs',import.meta.url),'utf8')).replace(/^import .*\n/, '');
for (const lang of ['ja','en']) {
  const elements=Object.fromEntries(['input','check','cancel','status','output','bytes'].map(id=>[id,{
    value:'',textContent:'',disabled:false,addEventListener(event,fn){this[event]=fn;},
  }]));
  const timers=new Map(), workers=[], events={};let timer=0, failConstruction=false;
  class FakeWorker {
    constructor(url, options) { if(failConstruction)throw Error('fail'); assert.equal(url,'../../checker/worker.mjs'); assert.equal(options.type,'module'); workers.push(this); }
    postMessage(data){this.sent=data;}
    terminate(){this.terminated=true;}
  }
  const context={document:{documentElement:{lang},querySelector:s=>elements[s.slice(1)]},window:{addEventListener:(event,fn)=>events[event]=fn},
    Worker:FakeWorker,TextEncoder,MAX_BYTES:16384,COLD_MS:120000,WARM_MS:5000,
    setTimeout:(fn,ms)=>{timers.set(++timer,{fn,ms});return timer;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source,context);
  assert.equal(workers.length,0);
  elements.input.value='#'+'あ'.repeat(5461);elements.input.input();elements.check.click();
  assert.equal(workers.length,1); assert.equal(elements.input.readOnly,true);
  assert.equal([...timers.values()][0].ms,120000);
  const first=workers[0], result={valid:false,supported_format:false,items:0,diagnostic_count:500,diagnostics:[{line:1,column:7,severity:'error',code:'E018',message:'<img src=x onerror=alert(1)>',hint:'Close the quote.'},{severity:'warning',code:'W101',message:'No position'}]};
  first.onmessage({data:{id:first.sent.id,stage:'ready'}});assert.equal([...timers.values()][0].ms,5000);
  first.onmessage({data:{id:first.sent.id,stage:'result',result}});
  assert.equal(elements.input.readOnly,false); assert.match(elements.output.textContent,/<img src=x/);
  assert.match(elements.output.textContent,/500/);
  assert.match(elements.output.textContent,lang==='ja' ? /行 1 · 列 7 エラー E018:/ : /Line 1 · Column 7 Error E018:/);
  assert.match(elements.output.textContent,lang==='ja' ? /ヒント: Close the quote/ : /Hint: Close the quote/);
  assert.ok(!elements.output.textContent.includes('undefined'));
  elements.input.input();
  assert.match(elements.status.textContent,lang==='ja' ? /読み込み済み/ : /Runtime loaded/);
  elements.check.click(); assert.equal(workers.length,1); assert.equal([...timers.values()][0].ms,5000);
  elements.cancel.click(); assert.equal(first.terminated,true); assert.equal(elements.input.value,'');
  first.onmessage({data:{id:first.sent.id,stage:'result',result}}); assert.equal(elements.output.textContent,'');
  elements.input.value='#'+'あ'.repeat(5461)+'x';elements.check.click();assert.equal(workers.length,1);
  const retained='[ ] T "Keep this input"';
  elements.input.value=retained;elements.check.click();assert.equal(workers.length,2);
  [...timers.values()][0].fn();assert.equal(elements.input.value,retained);assert.equal(workers[1].terminated,true);
  assert.equal(elements.input.readOnly,false);
  elements.input.input();assert.match(elements.status.textContent,lang==='ja' ? /読み込みます/ : /load the runtime/);
  elements.check.click();workers.at(-1).onmessage({data:{id:workers.at(-1).sent.id,stage:'error'}}); assert.equal(elements.check.disabled,false);assert.equal(elements.input.value,retained);
  elements.check.click();workers.at(-1).onerror(); assert.equal(elements.cancel.disabled,false);assert.equal(elements.input.value,retained);
  elements.check.click();workers.at(-1).onmessageerror();assert.equal(elements.input.value,retained);
  failConstruction=true;elements.check.click();assert.equal(elements.check.disabled,false);assert.equal(elements.input.value,retained);
  elements.cancel.click();assert.equal(elements.input.value,'');
  elements.input.value=retained;
  failConstruction=false;elements.check.click();events.pagehide();assert.equal(workers.at(-1).terminated,true);assert.equal(elements.input.value,'');
}
console.log('UI lifecycle: JA/EN, lazy/warm, bytes, safe output, errors, cancel, stale, timeout, pagehide PASS (fake DOM)');
