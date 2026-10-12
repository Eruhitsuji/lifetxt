import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base,mode]=process.argv.slice(2);
let browser;const events=[];
const http=async(route,options={})=>{const r=await fetch(base+route,{...options,headers:{'X-Lifetxt-Client-Time':'2031-02-03T12:00:00Z',...(options.headers||{})},signal:AbortSignal.timeout(10000)});assert(r.ok,route+':'+r.status);return r.json();};
async function launchUI(){
  browser=await launch(browserPath);
  await browser.command('Page.addScriptToEvaluateOnNewDocument',{source:`
    const RealDate=Date;window.Date=class extends RealDate{constructor(...args){super(...(args.length?args:['2031-02-03T12:00:00Z']));}static now(){return new RealDate('2031-02-03T12:00:00Z').getTime();}};
    window.workPosts=[];window.workFault=null;const native=fetch;window.fetch=async(input,init={})=>{
      if(input==='/api/work-session'&&init.method==='POST'&&workFault){const body=JSON.parse(init.body),headers=new Headers(init.headers);
        if(workFault==='missing'){delete body.item_revision;delete body.timer_revision;headers.delete('If-Match');headers.delete('X-Lifetxt-Expected-Revision');init={...init,credentials:'omit'};}
        else body.timer_revision='a'.repeat(64);
        init={...init,headers,body:JSON.stringify(body)};
      }
      const r=await native(input,init);if((input==='/api/work-session'||(String(input).startsWith('/api/items/')&&init.method==='PUT'))&&init.method&&init.method!=='GET')workPosts.push({path:String(input),status:r.status,header:new Headers(init.headers).get('If-Match'),body:JSON.parse(init.body),fallback:r.headers.get('X-Lifetxt-Legacy-Revision-Fallback')});return r;
    };`});
}
async function open(navigate=true,language="en"){
  if(navigate)await browser.command('Page.navigate',{url:base+'/?view=items&lang='+language});
  await browser.wait("typeof mountWorkSession==='function'&&currentItems.length>0",'app');
  await browser.evaluate("(async()=>{const data=await api('/api/items/id/upload-test');openDrawer(data.item,'none');})()");
  await browser.wait('workSessionView?.ready&&!workSessionView.needsRefresh','work ready');
}
async function click(id){
  const before=await browser.evaluate('workPosts.length');
  await browser.evaluate(`document.getElementById(${JSON.stringify(id)}).click();document.getElementById(${JSON.stringify(id)}).click()`);
  await browser.wait(`workPosts.length===${before+1}&&!workSessionPending`,'work result');
  return browser.evaluate('workPosts.at(-1)');
}
async function refresh(){await browser.evaluate("document.getElementById('work-session-refresh').click()");await browser.wait('workSessionView?.ready&&!workSessionView.needsRefresh','explicit refresh');}
async function external(){const rev=(await fetch(base+'/api/revision')).headers.get('etag');await http('/api/items',{method:'POST',headers:{'Content-Type':'application/json','If-Match':rev},body:JSON.stringify({status:'[ ]',type:'T',title:'External',details:{}})});}
async function close(){events.push(...browser.events);await browser.close();browser=null;}
try {
  await launchUI();const engine=browser.version.product,firstPid=browser.processId,firstProfile=browser.profileId;
  await open();const start=await click('work-session-start');assert.equal(start.status,200);assert.equal(start.body.timer_revision,'<missing>');assert.match(start.body.item_revision,/^[a-f0-9]{64}$/);assert.equal(start.header,'"'+start.body.item_revision+'"');assert.equal(start.fallback,null);
  await browser.wait('workSessionView?.ownSession&&!document.getElementById("work-session-stop").disabled','running');
  let state=await http('/__test/state');assert(state.timer);assert(Buffer.from(state.source,'hex').toString().includes('[/] T'));assert(Buffer.from(state.source,'hex').toString().includes(' S '));assert.equal(state.requests.length,1);assert.equal(state.journals.length,1);
  const beforeOther=state.requests.length;
  await browser.evaluate("(async()=>{const data=await api('/api/items/id/other');openDrawer(data.item,'none');})()");
  await browser.wait('workSessionView?.ready','other task');assert(await browser.evaluate('!workSessionView.ownSession&&document.getElementById("work-session-stop").disabled&&document.getElementById("work-session-start").disabled'));
  assert.equal((await http('/__test/state')).requests.length,beforeOther);await open(false);
  // Existing record editor uses the same frozen task source snapshot.
  await browser.evaluate("document.getElementById('drawer-edit-btn').click();document.getElementById('drawer-edit-title').value='Edited fixture';document.querySelector('.drawer-edit-form').requestSubmit()");
  await browser.wait('!drawerEditing&&!workSessionPending&&workSessionView?.ready','edit saved');
  const edit=await browser.evaluate('workPosts.find(x=>x.path.startsWith("/api/items/"))');assert.equal(edit.status,200);assert.match(edit.header,/^"[a-f0-9]{64}"$/);
  const stopped=await click('work-session-stop');assert.equal(stopped.status,200);assert.match(stopped.body.timer_revision,/^[a-f0-9]{64}$/);await browser.wait('workSessionView?.ready&&!workSessionView.running','stopped');
  state=await http('/__test/state');assert.equal(state.timer,null);
  // A known interruption is not displayed as success; reload/new process never replay it.
  await http('/__test/mode/interrupt',{method:'POST'});const beforeInterrupt=await http('/__test/state');
  const interrupted=await click('work-session-start');assert.equal(interrupted.status,500);assert(await browser.evaluate('workSessionView.needsRefresh&&workSessionView.feedback.textContent.includes("uncertain")'));
  const afterInterrupt=await http('/__test/state');assert.equal(beforeInterrupt.source,afterInterrupt.source);assert.equal(afterInterrupt.timer,null);assert.equal(afterInterrupt.journals.filter(x=>x.recovery_required).length,1);const postCount=afterInterrupt.requests.length;
  await browser.command('Page.reload');await open(false);assert.equal((await http('/__test/state')).requests.length,postCount);assert.equal(await browser.evaluate('workSessionView.running'),false);
  await close();await launchUI();assert.notEqual(firstPid,browser.processId);assert.notEqual(firstProfile,browser.profileId);await open();assert.equal((await http('/__test/state')).requests.length,postCount);
  const recovered=await http('/__test/operator-resume',{method:'POST'});assert.equal(recovered.state,'committed');await refresh();assert(await browser.evaluate('workSessionView.ownSession'));assert.equal((await http('/__test/state')).requests.length,postCount);
  await external();const beforeStale=await http('/__test/state');const stale=await click('work-session-stop');assert.equal(stale.status,409);const afterStale=await http('/__test/state');assert.equal(beforeStale.source,afterStale.source);assert.equal(beforeStale.timer,afterStale.timer);
  assert(await browser.evaluate('workSessionView.needsRefresh&&document.getElementById("work-session-stop").disabled'));await refresh();const complete=await click('work-session-complete');assert.equal(complete.status,200);await browser.wait('workSessionView?.ready&&!workSessionView.running','completed');
  state=await http('/__test/state');assert.equal(state.timer,null);assert(Buffer.from(state.source,'hex').toString().includes('[x] T "Edited fixture"'));assert(Buffer.from(state.source,'hex').toString().includes('done:'));assert.equal(state.journals.filter(x=>x.recovery_required).length,0);
  // Stale record editor keeps authored input; background reads cannot upgrade it.
  await browser.evaluate('document.getElementById("drawer-edit-btn").click();document.getElementById("drawer-edit-title").value="Keep this input"');await external();
  const beforeEditStale=await http('/__test/state');await browser.evaluate("document.querySelector('.drawer-edit-form').requestSubmit()");await browser.wait('!!document.getElementById("work-session-edit-feedback")&&!workSessionPending','editor conflict');
  const afterEditStale=await http('/__test/state');assert.equal(beforeEditStale.source,afterEditStale.source);assert.equal(await browser.evaluate('document.getElementById("drawer-edit-title").value'),'Keep this input');
  await browser.evaluate('drawerCancelEdit()');await browser.wait('workSessionView?.ready&&!workSessionView.needsRefresh','cancelled edit');
  // A fresh task for transport failures and correct observe-vs-required boundary.
  const rev=(await fetch(base+'/api/revision')).headers.get('etag');const item=(await http('/api/items/id/upload-test')).item;
  await http('/api/items/id/upload-test',{method:'PUT',headers:{'Content-Type':'application/json','If-Match':rev},body:JSON.stringify({...item,status:'[ ]'})});await refresh();
  await browser.evaluate('workFault="invalid"');const beforeInvalid=await http('/__test/state');const invalid=await click('work-session-start');assert.equal(invalid.status,409);const afterInvalid=await http('/__test/state');assert.equal(beforeInvalid.source,afterInvalid.source);assert.equal(beforeInvalid.timer,afterInvalid.timer);
  await browser.evaluate('workFault=null');await refresh();await browser.evaluate('workFault="missing"');const beforeMissing=await http('/__test/state');const missing=await click('work-session-start');
  if(mode==='required'){assert.equal(missing.status,428);const after=await http('/__test/state');assert.equal(beforeMissing.source,after.source);assert.equal(beforeMissing.timer,after.timer);}
  else {assert.equal(missing.status,200);assert.equal(missing.fallback,'used');await browser.wait('workSessionView?.ownSession','legacy accepted');}
  await browser.evaluate('workFault=null');await refresh();
  if(mode==='observe')await click('work-session-stop');
  await browser.wait('workSessionView?.ready&&!workSessionPending','healthy');
  state=await http('/__test/state');assert.equal(state.metrics.legacy_fallback_total,mode==='observe'?1:0);
  // Other session, read-only and missing-id records never gain stop/start authority.
  await browser.evaluate("openDrawer({...drawerItem,editable:false},'none')");assert.equal(await browser.evaluate('!!document.getElementById("work-session-start")'),false);
  await open();await browser.evaluate("openDrawer({...drawerItem,id:'',details:{}},'none')");assert.equal(await browser.evaluate('!!document.getElementById("work-session-start")'),false);
  await http('/__test/mode/readonly',{method:'POST'});await browser.evaluate("(async()=>{const data=await api('/api/items/id/upload-test');openDrawer(data.item,'none');})()");
  await browser.wait('!workSessionView || workSessionView.needsRefresh','readonly');assert(await browser.evaluate('!document.getElementById("work-session-start") || document.getElementById("work-session-start").disabled'));
  await http('/__test/mode/normal',{method:'POST'});await open(true,'ja');assert.equal(await browser.evaluate('document.getElementById("work-session-start").textContent'),'作業開始');
  events.push(...browser.events);
  for(const event of events.filter(x=>x.method==='Network.loadingFailed'||x.method==='Runtime.exceptionThrown'||(x.method==='Runtime.consoleAPICalled'&&x.params.type==='error')||(x.method==='Network.responseReceived'&&x.params.response.status>=400)||(x.method==='Log.entryAdded'&&x.params.entry.level==='error'))){const r=event.params.response,e=event.params.entry,url=r?.url||e?.url||'';assert((url===base+'/api/work-session'||url.startsWith(base+'/api/items/'))&&([409,428,500].includes(r?.status)||(e&&/\b409\b|\b428\b|\b500\b/.test(e.text))),JSON.stringify(event));}
  process.stdout.write(JSON.stringify({engine,node:process.version,os:process.platform,mode,work_session_frontend_verified:true,start_status:start.status,stop_status:stopped.status,edit_status:edit.status,stale_status:stale.status,invalid_status:invalid.status,missing_status:missing.status,fault_point:'after_journal_publish',operator_resume:recovered.state,reload_and_restart_no_replay:true,legacy_fallback_total:state.metrics.legacy_fallback_total}));
} finally {if(browser)await browser.close();}
