import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base]=process.argv.slice(2);
let browser;
const allEvents=[];
const api=async(route,options={})=>{
  const r=await fetch(base+route,{...options,signal:AbortSignal.timeout(10000)});assert(r.ok,route+': '+r.status);return r.json();
};
async function start(){
  browser=await launch(browserPath);
  await browser.command('Page.addScriptToEvaluateOnNewDocument',{source:`
    window.uploadPosts=[];window.probeFault=null;const original=fetch;window.fetch=async(input,init={})=>{
      if(input==='/api/attachments/upload'&&init.method==='POST'&&probeFault){
        const headers=new Headers(init.headers);headers.delete('If-Match');
        if(probeFault==='missing')headers.delete('X-Lifetxt-Expected-Revision');
        else headers.set('X-Lifetxt-Expected-Revision','unknown');
        init={...init,headers,credentials:'omit'};
      }
      const response=await original(input,init);
      if(input==='/api/attachments/upload'&&init.method==='POST')uploadPosts.push({status:response.status,revision:new Headers(init.headers).get('X-Lifetxt-Expected-Revision')});
      return response;
    };`});
}
async function open(navigate=true){
  if(navigate)await browser.command('Page.navigate',{url:base+'/?view=items&lang=en'});
  await browser.wait("typeof mountAttachmentUpload==='function' && currentItems.length>0",'app ready');
  await browser.evaluate("(async()=>{const data=await api('/api/items/id/upload-test');openDrawer(data.item,'none');})()");
  await browser.wait("attachmentUploadView?.ready&&!attachmentUploadView.needsRefresh&&!attachmentUploadView.input.disabled",'upload ready');
}
async function select(name){
  await browser.evaluate(`(()=>{const files=new DataTransfer();files.items.add(new File(['synthetic'],${JSON.stringify(name)},{type:'text/plain'}));const input=document.getElementById('attachment-upload-file');input.files=files.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
}
async function send(){
  const before=await browser.evaluate('uploadPosts.length');
  await browser.evaluate("document.getElementById('attachment-upload-submit').click()");
  await browser.wait(`uploadPosts.length===${before+1}&&!attachmentUploadPending`,'upload response');
  return browser.evaluate('uploadPosts.at(-1)');
}
async function refreshUpload(){
  await browser.evaluate('window.revisionOldUploadView=attachmentUploadView;attachmentUploadView.refresh.click()');
  await browser.wait("attachmentUploadView!==window.revisionOldUploadView&&attachmentUploadView?.ready&&!attachmentUploadView.needsRefresh&&!attachmentUploadPending&&!attachmentUploadView.input.disabled",'fresh upload view');
}
async function close(){allEvents.push(...browser.events);await browser.close();browser=null;}
try {
  await start();const engine=browser.version.product;const firstProcess=browser.processId,firstProfile=browser.profileId;
  await open();await select('interrupted.txt');
  const before=await api('/__test/state');
  await api('/__test/mode/interrupt',{method:'POST'});
  const failed=await send();assert.equal(failed.status,503);assert.match(failed.revision,/^[a-f0-9]{64}$/);
  assert(await browser.evaluate("attachmentUploadView.needsRefresh&&attachmentUploadView.input.disabled&&!document.getElementById('attachment-upload-receipt').textContent.includes('Attached')&&attachmentUploadView.feedback.textContent.includes('uncertain')"));
  const interrupted=await api('/__test/state');assert.equal(interrupted.source,before.source);assert.deepEqual(interrupted.attachments,before.attachments);
  assert.equal(interrupted.journals.filter(x=>x.recovery_required).length,1);
  assert.equal(interrupted.journals.find(x=>x.recovery_required).state,'prepared');
  assert.equal(interrupted.fault_points[0].point,'after_journal_publish');
  const postCount=interrupted.requests.length;
  await browser.command('Page.reload');await open(false);
  assert(await browser.evaluate("!attachmentUploadView.file && !document.getElementById('attachment-upload-receipt').textContent.includes('Attached')"));
  const afterReload=await api('/__test/state');assert.equal(afterReload.source,interrupted.source);assert.equal(afterReload.requests.length,postCount);
  // A full process stop and new disposable profile, distinct from Page.reload.
  await close();await start();assert.notEqual(firstProcess,browser.processId);assert.notEqual(firstProfile,browser.profileId);await open();
  assert(await browser.evaluate("!attachmentUploadView.file && !document.getElementById('attachment-upload-receipt').textContent.includes('Attached')"));
  const afterRestart=await api('/__test/state');assert.equal(afterRestart.source,interrupted.source);assert.equal(afterRestart.requests.length,postCount);
  const recovered=await api('/__test/operator-resume',{method:'POST'});assert.equal(recovered.state,'committed');
  assert.equal(recovered.id,interrupted.journals.find(x=>x.recovery_required).id);
  await refreshUpload();
  const committed=await api('/__test/state');assert.notEqual(committed.source,interrupted.source);
  assert.equal(Object.keys(committed.attachments).length,1);assert(Object.values(committed.attachments).every(x=>Buffer.from(x,'hex').toString()==='synthetic'));
  assert.equal(committed.journals.filter(x=>x.recovery_required).length,0);assert.equal(committed.requests.length,postCount);
  assert.equal((Buffer.from(committed.source,'hex').toString().match(/file:/g)||[]).length,1);
  // Explicit refresh learns the latest exact file revision; stale upload is never retried.
  await select('stale.txt');
  const revision=(await fetch(base+'/api/revision')).headers.get('etag');
  await api('/api/items',{method:'POST',headers:{'Content-Type':'application/json','If-Match':revision},body:JSON.stringify({status:'[ ]',type:'T',title:'Concurrent',details:{}})});
  const beforeStale=await api('/__test/state');const stale=await send();assert.equal(stale.status,409);
  const afterStale=await api('/__test/state');assert.equal(beforeStale.source,afterStale.source);assert.deepEqual(beforeStale.attachments,afterStale.attachments);
  assert(await browser.evaluate('attachmentUploadView.needsRefresh&&attachmentUploadView.input.disabled'));
  await refreshUpload();
  await select('fresh.txt');const fresh=await send();assert.equal(fresh.status,201);assert.notEqual(fresh.revision,stale.revision);
  await browser.wait("attachmentUploadView?.ready&&!attachmentUploadView.needsRefresh&&!attachmentUploadPending&&!attachmentUploadView.input.disabled",'successful upload refreshed');
  const final=await api('/__test/state');assert.equal(Object.keys(final.attachments).length,2);assert.equal(final.requests.length,postCount+2);
  assert.equal(final.journals.filter(x=>x.recovery_required).length,0);assert.equal((Buffer.from(final.source,'hex').toString().match(/file:/g)||[]).length,2);
  const malformedStatuses=[];
  for(const fault of ['missing','invalid']) {
    await refreshUpload();
    await select(fault+'.txt');await browser.evaluate(`probeFault=${JSON.stringify(fault)}`);
    const beforeFault=await api('/__test/state');const rejection=await send();
    assert.equal(rejection.status,fault==='missing'?428:400);malformedStatuses.push(rejection.status);
    const afterFault=await api('/__test/state');assert.equal(beforeFault.source,afterFault.source);assert.deepEqual(beforeFault.attachments,afterFault.attachments);assert.deepEqual(beforeFault.journals,afterFault.journals);
    assert(await browser.evaluate('attachmentUploadView.needsRefresh&&attachmentUploadView.input.disabled'));
    await browser.evaluate('probeFault=null');
  }
  await browser.evaluate("fetch('/favicon.ico').then(r=>{if(r.status!==204)throw Error('favicon');})");
  allEvents.push(...browser.events);
  for(const event of allEvents.filter(x=>x.method==='Network.loadingFailed'||x.method==='Runtime.exceptionThrown'||(x.method==='Runtime.consoleAPICalled'&&x.params.type==='error')||(x.method==='Network.responseReceived'&&x.params.response.status>=400)||(x.method==='Log.entryAdded'&&x.params.entry.level==='error'))){
    const r=event.params.response,e=event.params.entry,url=r?.url||e?.url||'';
    assert(url===base+'/api/attachments/upload'&&([503,409,428,400].includes(r?.status)||(e&&/\b503\b|\b409\b|\b428\b|\b400\b/.test(e.text))),JSON.stringify(event));
  }
  process.stdout.write(JSON.stringify({engine,node:process.version,os:process.platform,mode:'required',fault_point:'after_journal_publish',interrupted_status:failed.status,
    reload_no_replay:true,new_process_and_profile_no_replay:true,operator_resume:'committed',same_transaction:true,stale_status:stale.status,fresh_status:fresh.status,attachment_count:2,malformed_statuses:malformedStatuses,browser_process_changed:true,profile_changed:true,
    work_session_frontend_verified:false,work_session_gap:'This attachment suite does not verify work-session controls; run the separate shipped-UI work-session probe.'}));
} finally {if(browser)await browser.close();}
