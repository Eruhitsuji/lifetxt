import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base,mode]=process.argv.slice(2);
assert(['observe','required'].includes(mode));
const browser=await launch(browserPath);
const {command,evaluate,wait,events}=browser;
const request=async (route,options={})=>{
  const response=await fetch(base+route,{...options,signal:AbortSignal.timeout(5000)});
  assert(response.ok,route+': '+response.status);return response.json();
};
try {
  await command('Page.addScriptToEvaluateOnNewDocument',{source:`
    window.probeWrites=[];window.probeReads=[];window.probeFault=null;
    const original=window.fetch;
    window.fetch=async (input,options={})=>{
      let init={...options};
      if(String(input)==='/api/items/capture' && init.method==='POST') {
        const headers=new Headers(init.headers);
        const body=JSON.parse(init.body);
        const originalRevision=headers.get('If-Match');
        if(window.probeFault==='missing') {
          headers.delete('If-Match');headers.delete('X-Lifetxt-Expected-Revision');
          delete body.expected_source_revision;init.credentials='omit';
        }
        init.headers=headers;init.body=JSON.stringify(body);
        const response=await original(input,init);
        window.probeWrites.push({status:response.status,originalRevision, sent:headers.get('If-Match'),
          source:body.expected_source_revision||null,fallback:response.headers.get('X-Lifetxt-Legacy-Revision-Fallback')});
        return response;
      }
      const response=await original(input,init);
      if((init.method||'GET')==='GET' && String(input).startsWith('/api/'))
        window.probeReads.push({path:String(input),etag:response.headers.get('ETag'),revision:response.headers.get('X-Lifetxt-Revision')});
      return response;
    };`});
  await command('Page.navigate',{url:base+'/planner?date=2031-02-03&lang=en'});
  await wait("document.querySelector('#feedback')?.textContent==='Today' && !document.getElementById('open-capture').disabled",'Planner ready');
  const submit=async title=>{
    const before=await evaluate('probeWrites.length');
    await evaluate(`document.getElementById('open-capture').click();document.getElementById('capture-text').value=${JSON.stringify(title)};document.getElementById('capture-form').requestSubmit()`);
    await wait(`probeWrites.length===${before+1} && !document.querySelector('#capture-form [type=submit]').disabled`,'capture response');
    return evaluate('probeWrites.at(-1)');
  };
  const normal=await submit('Browser_capture');
  assert.equal(normal.status,201);assert.equal(normal.fallback,null);
  assert.match(normal.sent,/^"[a-f0-9]{64}"$/);assert.equal(normal.source,normal.sent.slice(1,-1));
  await wait("!document.getElementById('capture-dialog').open",'successful capture UI');
  const normalState=await request('/__test/state');
  assert.equal(normalState.metrics.legacy_fallback_total,0);
  assert(Buffer.from(normalState.sources[0],'hex').toString('utf8').includes('Browser_capture'));
  // Open the form first; a separate HTTP writer then invalidates its snapshot.
  await evaluate("document.getElementById('open-capture').click();document.getElementById('capture-text').value='Stale_capture'");
  const revision=(await fetch(base+'/api/revision',{signal:AbortSignal.timeout(5000)})).headers.get('etag');
  await request('/api/items',{method:'POST',headers:{'Content-Type':'application/json','If-Match':revision},
    body:JSON.stringify({status:'[ ]',type:'T',title:'Concurrent_writer',details:{}})});
  const staleBefore=await request('/__test/state');
  await evaluate("document.getElementById('capture-form').requestSubmit()");
  await wait("probeWrites.length===2 && !document.querySelector('#capture-form [type=submit]').disabled",'stale rejection');
  const stale=await evaluate("({write:probeWrites.at(-1),open:document.getElementById('capture-dialog').open,input:document.getElementById('capture-text').value,error:document.getElementById('capture-feedback').textContent})");
  assert.equal(stale.write.status,409);assert(stale.open);assert.equal(stale.input,'Stale_capture');assert.match(stale.error,/reload/);
  const staleAfter=await request('/__test/state');assert.deepEqual(staleBefore.sources,staleAfter.sources);
  assert.equal(staleAfter.metrics.legacy_fallback_total,0);
  // Reload acquires a fresh source revision, then strip only the outgoing transport.
  await command('Page.reload');
  await wait("document.querySelector('#feedback')?.textContent==='Today' && probeReads.length>0",'reload');
  await evaluate("window.probeFault='missing'");
  const missingBefore=await request('/__test/state');
  const missing=await submit('Missing_capture');
  assert.match(missing.originalRevision,/^"[a-f0-9]{64}"$/);assert.equal(missing.sent,null);assert.equal(missing.source,null);
  const missingAfter=await request('/__test/state');
  if(mode==='required') {
    assert.equal(missing.status,428);assert.equal(missing.fallback,null);
    assert.deepEqual(missingBefore.sources,missingAfter.sources);
    assert.equal(missingAfter.metrics.legacy_fallback_total,0);
    assert(await evaluate("document.getElementById('capture-dialog').open && document.getElementById('capture-text').value==='Missing_capture' && document.getElementById('capture-feedback').textContent.includes('revision')"));
  } else {
    assert.equal(missing.status,201);assert.equal(missing.fallback,'used');
    assert.equal(missingAfter.metrics.legacy_fallback_total,1);
    assert.equal(missingAfter.metrics.legacy_fallback_by_path['/api/items/capture'],1);
    assert(Buffer.from(missingAfter.sources[0],'hex').toString('utf8').includes('Missing_capture'));
    assert.equal(await evaluate("document.getElementById('capture-dialog').open"),false);
  }
  const reads=await evaluate('probeReads');assert(reads.some(x=>x.etag && x.revision));
  const failures=events.filter(x=>x.method==='Network.loadingFailed' || x.method==='Runtime.exceptionThrown' ||
    (x.method==='Runtime.consoleAPICalled' && x.params.type==='error') ||
    (x.method==='Network.responseReceived' && x.params.response.status>=400) ||
    (x.method==='Log.entryAdded' && x.params.entry.level==='error'));
  for(const event of failures) {
    // Only actual intentional CAS rejection responses and their Chrome log entries.
    const response=event.params.response,entry=event.params.entry;
    const url=response?.url||entry?.url||'';
    const status=response?.status;
    assert((url===base+'/api/items/capture') &&
      (status===409 || (status===428 && mode==='required') ||
       (entry && (/\b409\b/.test(entry.text) || (mode==='required' && /\b428\b/.test(entry.text))))),JSON.stringify(event));
  }
  assert(missingAfter.writes.some(x=>x.precondition===null));
  process.stdout.write(JSON.stringify({engine:browser.version.product,node:process.version,os:process.platform,mode,
    normal,stale:stale.write,missing,legacy_fallback_total:missingAfter.metrics.legacy_fallback_total,
    rejected_sources_unchanged:true,revision_reads:reads.length,expected_rejections:failures.length}));
} finally {await browser.close();}
