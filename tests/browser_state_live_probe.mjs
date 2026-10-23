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
  await command('Page.navigate',{url:base+'/state?lang=en'});await settled();
  assert.equal(await evaluate(`document.querySelector('#current-state').textContent`),'No current status');
  await click('[data-state=focus]');await wait(`document.querySelector('#current-state').textContent==='Focus'`,'focus persisted');await settled();
  const first=(await data('/api/status?person=self&active=true')).records[0];
  assert.equal(first.state,'focus');assert.equal(first.person,'self');
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
  console.log(JSON.stringify({writes:5,legacyFallback:metrics.legacy_fallback_total,kind:'real browser/API persistence'}));
} finally {await driver.close();}
