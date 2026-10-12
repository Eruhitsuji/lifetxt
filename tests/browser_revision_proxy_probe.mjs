import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base,mode]=process.argv.slice(2);
const browser=await launch(browserPath);
const {command,evaluate,wait,events}=browser;
const control=async route=>{
  const r=await fetch(base+'/__test/'+route,{method:'POST',signal:AbortSignal.timeout(20000)});
  assert(r.ok);return r.json();
};
try {
  await command('Page.addScriptToEvaluateOnNewDocument',{source:`
    window.probePosts=[];window.probeReads=[];
    const original=window.fetch;window.fetch=async(input,init={})=>{
      const response=await original(input,init);
      const row={path:String(input),status:response.status,etag:response.headers.get('ETag'),revision:response.headers.get('X-Lifetxt-Revision'),fallback:response.headers.get('X-Lifetxt-Legacy-Revision-Fallback'),sent:new Headers(init.headers).get('If-Match')};
      ((init.method||'GET')==='POST'?probePosts:probeReads).push(row);return response;
    };`});
  const open=async fault=>{
    await control('fault/'+fault);
    await command('Page.navigate',{url:base+'/planner?lang=en'});
    await wait("document.querySelector('#feedback')?.textContent==='Today'",'Planner load');
  };
  const submit=async title=>{
    await evaluate(`document.getElementById('new-note').click();document.getElementById('editor-title').value=${JSON.stringify(title)};document.getElementById('editor-body').value='synthetic';document.getElementById('editor-form').requestSubmit()`);
    await wait("!document.querySelector('#editor-form [type=submit]').disabled && (!document.getElementById('editor').open || document.getElementById('editor-feedback').textContent.length>0)",'editor result');
    return evaluate("({posts:probePosts,open:document.getElementById('editor').open,error:document.getElementById('editor-feedback').textContent})");
  };
  const reports=[];
  for(const fault of ['strip','strip-all','rewrite']) {
    await open(fault);const before=await control('state');
    const result=await submit('Proxy_'+fault);
    const after=await control('state');
    const reads=await evaluate('probeReads');
    const revisionReads=reads.filter(x=>x.path.startsWith('/api/') && x.revision);
    if(fault==='strip') {
      assert(revisionReads.length>0);assert(revisionReads.every(x=>x.etag===null));
      assert.equal(result.posts.at(-1).status,201);assert.equal(result.open,false);
      assert.equal(result.posts.at(-1).fallback,null);
      assert.notDeepEqual(before.sources,after.sources);
    } else {
      assert.equal(result.open,true);assert.match(result.error,/revision|reload/);
      assert.deepEqual(before.sources,after.sources);
      if(fault==='strip-all')assert.equal(result.posts.length,0);
      else {assert.equal(result.posts.at(-1).status,409);assert.equal(result.posts.at(-1).sent,'"'+'a'.repeat(64)+'"');}
    }
    assert.equal(after.metrics.legacy_fallback_total,2);
    reports.push({fault,reads:reads.filter(x=>x.path.startsWith('/api/')).map(x=>({etag:x.etag,revision:x.revision})),statuses:result.posts.map(x=>x.status),unchanged:fault!=='strip'});
  }
  await open('none');await control('fault/missing');
  const beforeMissing=await control('state');const missing=await submit('Proxy_missing');const afterMissing=await control('state');
  assert.equal(afterMissing.wire.at(-1).precondition,null);
  if(mode==='required') {
    assert.equal(missing.posts.at(-1).status,428);assert(missing.open);assert.match(missing.error,/revision/);
    assert.deepEqual(beforeMissing.sources,afterMissing.sources);assert.equal(afterMissing.metrics.legacy_fallback_total,2);
  } else {
    assert.equal(missing.posts.at(-1).status,201);assert.equal(missing.posts.at(-1).fallback,'used');assert(!missing.open);
    assert.equal(afterMissing.metrics.legacy_fallback_total,3);
  }
  // Explicit reload with healthy proxy fetches authoritative headers; no auto retry.
  await open('none');const recovered=await submit('Proxy_recovered');assert.equal(recovered.posts.at(-1).status,201);assert(!recovered.open);
  const beforeRestart=await control('state');const restart=await control('restart');assert.notEqual(restart.before_pid,restart.after_pid);
  const afterRestart=await control('state');assert.deepEqual(beforeRestart.sources,afterRestart.sources);
  for(const key of ['server_instance_id','observation_started_at','legacy_fallback_total','legacy_fallback_by_path','last_reset_at'])
    assert.deepEqual(beforeRestart.metrics[key],afterRestart.metrics[key],key);
  assert.equal(afterRestart.metrics.schema_version,1);assert.equal(afterRestart.metrics.revision_mode,mode);assert(!('obsolete_counter' in afterRestart.metrics));
  await open('none');const afterServerRestart=await submit('After_server_restart');assert.equal(afterServerRestart.posts.at(-1).status,201);
  await evaluate("fetch('/favicon.ico').then(r=>{if(r.status!==204)throw Error('favicon');})");
  for(const event of events.filter(x=>x.method==='Network.loadingFailed'||x.method==='Runtime.exceptionThrown'||
    (x.method==='Runtime.consoleAPICalled'&&x.params.type==='error')||
    (x.method==='Network.responseReceived'&&x.params.response.status>=400)||
    (x.method==='Log.entryAdded'&&x.params.entry.level==='error'))) {
    const r=event.params.response,e=event.params.entry,url=r?.url||e?.url||'';
    assert(url===base+'/api/items' && (r?.status===409||(r?.status===428&&mode==='required')||
      (e&&(/\b409\b/.test(e.text)||(mode==='required'&&/\b428\b/.test(e.text))))),JSON.stringify(event));
  }
  process.stdout.write(JSON.stringify({engine:browser.version.product,node:process.version,os:process.platform,mode,proxy:reports,
    missing_status:missing.posts.at(-1).status,server_process_changed:true,source_bytes_preserved_on_restart:true,
    metrics_before:beforeRestart.metrics,metrics_after:afterRestart.metrics,recovery_status:afterServerRestart.posts.at(-1).status}));
} finally {await browser.close();}
