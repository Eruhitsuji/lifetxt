// End-to-end State UI against the real Web/API and filesystem mutation layer.
import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base] = process.argv.slice(2);
const driver=await launch(browserPath);
const {command,evaluate,wait}=driver;
const settled=()=>wait(`document.querySelector('#sync')?.textContent==='Up to date'&&!document.querySelector('#refresh').disabled`,'authoritative status reload');
const click=async selector=>{await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);};
const data=async path=>{const response=await fetch(base+path);assert.equal(response.status,200);return response.json();};
try {
  await command('Emulation.setDeviceMetricsOverride',{width:320,height:844,deviceScaleFactor:1,mobile:true});
  await command('Page.navigate',{url:base+'/?lang=en'});
  await wait(`document.querySelector('#nav-more-summary')&&typeof switchWorkspace==='function'`,'Web navigation ready');
  for(const view of ['team','status']){
    await evaluate(`switchWorkspace('${view}')`);
    await wait(`getComputedStyle(document.querySelector('[data-page="${view}"]')).display!=='none'`,'existing '+view+' view');
  }
  await evaluate(`document.querySelector('#nav-more-summary').click()`);
  await wait(`document.querySelector('#nav-more').open`,'More open');
  assert.ok(await evaluate(`(()=>{const n=document.querySelector('#nav-advanced a[href="/state"]');n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.height>=44;})()`),'phone State link fits with touch target');
  for(const route of ['/planner','/capture','/state'])assert.equal(await evaluate(`document.querySelectorAll('#nav-advanced a[href="${route}"]').length`),1);
  for(const view of ['team','status'])assert.ok(await evaluate(`!!document.querySelector('#nav-advanced button[data-view="${view}"]')`));
  await evaluate(`document.querySelector('#nav-advanced a[href="/state"]').focus()`);
  await command('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await command('Input.dispatchKeyEvent',{type:'char',key:'Enter',code:'Enter',text:'\r',unmodifiedText:'\r',windowsVirtualKeyCode:13});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await wait(`location.pathname==='/state'`,'native link navigation');await settled();
  const install=await evaluate(`(async()=>{const link=document.querySelector('link[rel=manifest]');const r=await fetch(link.href);return {url:new URL(link.href).pathname,type:r.headers.get('Content-Type'),cache:r.headers.get('Cache-Control'),manifest:await r.json()};})()`);
  assert.equal(install.url,'/state.webmanifest');assert.equal(install.type,'application/manifest+json');assert.equal(install.cache,'no-store');assert.equal(install.manifest.start_url,'/state');assert.equal(install.manifest.id,'/state');
  assert.equal(await evaluate(`document.querySelector('#current-state').textContent`),'No current status');
  await click('[data-state=focus]');await wait(`document.querySelector('#current-state').textContent==='Focus'`,'focus persisted');await settled();
  const first=(await data('/api/status?person=self&active=true')).records[0];
  assert.equal(first.state,'focus');assert.equal(first.person,'self');
  await command('Page.reload',{ignoreCache:true});await settled();
  assert.equal(await evaluate(`document.querySelector('#current-state').textContent`),'Focus');
  await evaluate(`document.querySelector('footer a[href="/"]').click()`);
  await wait(`location.pathname==='/'&&!!document.querySelector('#nav-more')`,'full Web return');
  await evaluate('history.back()');
  await wait(`location.pathname==='/state'&&!!document.querySelector('#sync')`,'browser back');await settled();
  assert.equal(await evaluate(`document.querySelector('#current-state').textContent`),'Focus');
  await click('[data-state=focus]');await wait(`document.querySelector('#feedback').textContent.includes('already current')`,'same-state no-op');await settled();
  assert.equal((await data('/api/status?person=self&active=true')).records[0].from,first.from);
  await evaluate(`document.querySelector('#details').open=true;document.querySelector('#form-state').value='busy';document.querySelector('#form-state').dispatchEvent(new Event('change'));document.querySelector('#activity-input').value='Deep work';document.querySelector('#note-input').value='Remember';document.querySelector('#note-input').dispatchEvent(new Event('input',{bubbles:true}))`);
  await click('#save');await wait(`document.querySelector('#current-state').textContent==='Busy'`,'details persisted');await settled();
  const details=(await data('/api/status?person=self&active=true')).records[0];assert.equal(details.title,'Deep work');assert.deepEqual(details.details.note,['Remember']);
  await click('[data-state=offline]');await wait(`document.querySelector('#current-state').textContent==='Offline'`,'offline persisted');await settled();
  assert.equal((await data('/api/status?person=self&active=true')).records[0].active,true);
  await click('#end');await wait(`document.querySelector('#current-state').textContent==='No current status'`,'end persisted');await settled();
  assert.equal((await data('/api/status?person=self&active=true')).records.length,0);
  assert.equal((await data('/api/status?person=self&active=false')).records[0].state,'offline');
  assert.equal((await data('/api/status?person=other&active=true')).records[0].state,'meeting');
  const metrics=await data('/api/revision-metrics');assert.equal(metrics.legacy_fallback_total,0);
  console.log(JSON.stringify({writes:5,legacyFallback:metrics.legacy_fallback_total,navigation:'Status/Team, More native link, return, reload, browser back',manifest:install.manifest.id,kind:'real browser/API persistence'}));
} finally {await driver.close();}
