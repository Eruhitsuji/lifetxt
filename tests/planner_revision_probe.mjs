// Real Planner handlers and HTTP, with a minimal DOM adapter (no layout claims).
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const [base, scriptPath] = process.argv.slice(2);
const source = await readFile(scriptPath, 'utf8');
class Element {
  constructor(tag='div') {
    this.tagName=tag; this.children=[]; this.dataset={}; this.value='';
    this.textContent=''; this.disabled=false; this.hidden=false; this.open=false;
    this.listeners={}; this.classList={add(){},remove(){},toggle(){}};
  }
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children=nodes;}
  get childElementCount() {return this.children.length;}
  get firstElementChild() {return this.children[0];}
  setAttribute() {}
  addEventListener(name, fn) {this.listeners[name]=fn;}
  closest() {return this;}
  querySelector() {return this.submit ||= new Element('button');}
  showModal() {this.open=true;}
  close() {this.open=false;}
  focus() {}
}
const event={preventDefault(){},stopPropagation(){}};
function planner(transport, language='en') {
  const nodes=new Map(), $=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const document={readyState:'loading',visibilityState:'visible',documentElement:{},
    getElementById:$,createElement:tag=>new Element(tag),querySelectorAll:()=>[],addEventListener(){}};
  const sandbox={document,Headers,URL,URLSearchParams,Date,performance,AbortController,
    location:{href:base+'/planner?lang='+language,search:'?lang='+language},navigator:{language},
    localStorage:{getItem(){return null;},setItem(){},removeItem(){}},history:{replaceState(){}},
    setInterval(){return 0;},clearInterval(){},fetch:transport,addEventListener(){}};
  sandbox.window=sandbox;
  vm.createContext(sandbox);
  // Expose lexical functions only in this disposable test copy; ship no test API.
  const instrumented=source.replace(/\}\)\(\);\s*$/, `globalThis.probe={api,boot,load,openEditor,syncToday,
    get revision(){return revision}, get edit(){return edit}, get sourceRevision(){return sourceRevision}};})();`);
  assert.notEqual(instrumented,source);
  vm.runInContext(instrumented,sandbox);
  return {p:sandbox.probe,$};
}
const calls=[];
async function transport(path, options={}) {
  const response=await fetch(base+path,options);
  calls.push({path,method:options.method||'GET',headers:new Headers(options.headers),
    body:options.body,status:response.status,etag:response.headers.get('etag')});
  return response;
}
const {p,$}=planner(transport);
const writes=()=>calls.filter(c=>c.method!=='GET');
const data=async path=>(await fetch(base+path)).json();
async function externalWrite() {
  const revision=(await fetch(base+'/api/revision')).headers.get('etag');
  const response=await fetch(base+'/api/items',{method:'POST',headers:{'Content-Type':'application/json','If-Match':revision},
    body:JSON.stringify({status:'[ ]',type:'T',title:'External_'+calls.length,details:{}})});
  assert.equal(response.status,201);
}
async function submitEditor(kind,title,body,item=null) {
  p.openEditor(kind,item);$('editor-title').value=title;$('editor-body').value=body;
  await $('editor-form').onsubmit(event);
  assert.equal($('editor').open,false,$('editor-feedback').textContent);
}
function action(section,title,label=null) {
  const card=$(section).children.find(row=>row.children?.[0]?.children?.[0]?.textContent===title);
  assert.ok(card,section+': '+title);
  const button=card.children.find(node=>node.className==='card-actions')?.children.find(node=>node.tagName==='button'&&(!label||node.textContent===label));
  assert.ok(button,title+' action');
  return ()=>button.listeners.click(event);
}
await p.boot();
assert.equal($('feedback').textContent,'Today');
// All actual form/button paths, including repeated submit prevention.
$('open-capture').onclick();$('capture-text').value='Captured';
await Promise.all([$('capture-form').onsubmit(event),$('capture-form').onsubmit(event)]);
assert.equal($('capture-dialog').open,false,$('capture-feedback').textContent);
assert.equal(writes().filter(c=>c.path==='/api/items/capture').length,1);
assert.ok(JSON.parse(writes()[0].body).expected_source_revision);
await submitEditor('N','New_Note','Created note');
let note=(await p.api('/api/items?type=N')).items.find(i=>i.id==='n1');
await submitEditor('N','Note','Edited note',note);
await $('edit-journal').onclick();$('editor-body').value='Created journal';
await Promise.all([$('editor-form').onsubmit(event),$('editor-form').onsubmit(event)]);
assert.equal($('editor').open,false,$('editor-feedback').textContent);
await $('edit-journal').onclick();$('editor-body').value='Updated journal';
await $('editor-form').onsubmit(event);
assert.equal($('editor').open,false,$('editor-feedback').textContent);
await action('tasks','Task')();
await action('tasks','Line_Task')();
await action('habits','Habit')();
const recordMinimum=action('habits','Minimum_Habit','Record minimum');
const recordUsual=action('habits','Minimum_Habit','Mark done');
const beforeMinimum=writes().length;
await Promise.all([recordMinimum(),recordUsual(),recordMinimum()]);
assert.equal(writes().length,beforeMinimum+1);
const today=(await data('/api/config')).today;
const items=(await data('/api/items')).items;
assert.equal(items.find(i=>i.id==='t1').status,'[x]');
assert.equal(items.find(i=>i.title==='Line_Task').status,'[x]');
assert.deepEqual(items.find(i=>i.id==='h1').details.done,[today]);
assert.equal(items.find(i=>i.id==='h1').details.habit_minimum_done,undefined);
const recordedMinimum=items.find(i=>i.id==='h3');
assert.equal(recordedMinimum.status,'[ ]');
assert.deepEqual(recordedMinimum.details.done,['2000-01-01',today]);
assert.deepEqual(recordedMinimum.details.habit_minimum_done,['2000-01-01',today]);
assert.deepEqual(recordedMinimum.details.habit_cue,['After breakfast']);
assert.deepEqual(recordedMinimum.details.habit_minimum,['One word']);
const minimumCard=$('habits').children.find(row=>row.children[0].children[0].textContent==='Minimum_Habit');
assert.equal(minimumCard.children[0].children[1].textContent,'Minimum version recorded');
assert.deepEqual(minimumCard.children[1].children.map(button=>button.textContent),['Details']);
assert.equal(items.find(i=>i.type==='J').details.body[0],'Updated journal');

// Rest is mutually exclusive with both completion actions and stays out of Stats.
const restToday=action('habits','Rest_Habit','Rest today');
const completeRestHabit=action('habits','Rest_Habit','Mark done');
const minimumRestHabit=action('habits','Rest_Habit','Record minimum');
const beforeRest=writes().length;
await Promise.all([restToday(),completeRestHabit(),minimumRestHabit()]);
assert.equal(writes().length,beforeRest+1);
const restHabit=async ()=>(await data('/api/items')).items.find(i=>i.id==='h4');
let rested=await restHabit();
assert.equal(rested.status,'[ ]');
assert.deepEqual(rested.details.habit_rest,['2000-01-02',today]);
assert.deepEqual(rested.details.done,['2000-01-01']);
assert.equal(rested.details.habit_minimum_done,undefined);
const restCard=$('habits').children.find(row=>row.children[0].children[0].textContent==='Rest_Habit');
assert.equal(restCard.children[0].children[1].textContent,'Rest day recorded');
assert.deepEqual(restCard.children[1].children.map(button=>button.textContent),['Undo rest','Details']);
const stats=await data('/api/chart/habits-heatmap?from='+today+'&to='+today);
assert.deepEqual(stats.habits.find(habit=>habit.title==='Rest_Habit').dates,{});
assert.deepEqual(stats.habits.find(habit=>habit.title==='Minimum_Habit').dates,{[today]:1});
await action('habits','Rest_Habit','Undo rest')();
rested=await restHabit();
assert.deepEqual(rested.details.habit_rest,['2000-01-02']);
assert.deepEqual(rested.details.done,['2000-01-01']);
await action('habits','Rest_Habit','Mark done')();
assert.deepEqual((await restHabit()).details.done,['2000-01-01',today]);

// Freeze an edit, then background config and other reads learn a newer revision.
for (const kind of ['N','J']) {
  const item=(await p.api('/api/items?type='+kind)).items.find(i=>kind==='N'?i.id==='n1':i.type==='J');
  p.openEditor(kind,item);$('editor-body').value='Unsaved draft';
  const frozen=p.edit.revision;
  await externalWrite();await p.syncToday();
  assert.notEqual(p.revision,frozen);
  const before=writes().length;
  await $('editor-form').onsubmit(event);
  assert.equal(writes().length,before+1); // no automatic retry
  assert.equal(writes().at(-1).status,409);
  assert.equal(writes().at(-1).headers.get('If-Match'),frozen);
  assert.equal($('editor').open,true);
  assert.equal($('editor-body').value,'Unsaved draft');
  assert.match($('editor-feedback').textContent,/reload/);
  assert.equal($('editor-form').querySelector().disabled,false);
  assert.notEqual((await data('/api/items')).items.find(i=>item.id?i.id===item.id:i.line===item.line).details.body[0],'Unsaved draft');
  $('editor').close();
}
// Capture freezes its generic header when opened; JSON retains the compatibility field.
await p.load();const captureSource=p.sourceRevision;
await externalWrite();await p.syncToday();
$('open-capture').onclick();$('capture-text').value='Conflicted_capture';
await $('capture-form').onsubmit(event);
assert.equal(writes().at(-1).status,409);
assert.equal(JSON.parse(writes().at(-1).body).expected_source_revision,captureSource);
assert.equal($('capture-text').value,'Conflicted_capture');
assert.equal($('capture-dialog').open,true);
assert.match($('capture-feedback').textContent,/reload/);
$('capture-dialog').close();

// A fresh task action also remains tied to its read after background refreshes.
await p.load();const complete=action('tasks','Captured');
await externalWrite();await p.syncToday();await complete();
assert.equal(writes().at(-1).status,409);
assert.match($('feedback').textContent,/reload/);
assert.equal((await data('/api/items')).items.find(i=>i.title==='Captured').status,'[ ]');

// Failed habit actions must neither mutate the displayed snapshot nor silently retry.
await p.load();
const habitAction=action('habits','Stale_Habit','Record minimum');
const staleRest=action('habits','Stale_Habit','Rest today');
await externalWrite();await p.syncToday();
const beforeHabit=writes().length;
await habitAction();
assert.equal(writes().at(-1).status,409);
assert.equal(JSON.parse(writes().at(-1).body).details.done.length,1);
await staleRest();
assert.equal(writes().length,beforeHabit+2);
assert.equal(writes().at(-1).status,409);
assert.deepEqual(JSON.parse(writes().at(-1).body).details.habit_rest,[today]);
const staleHabit=(await data('/api/items')).items.find(i=>i.id==='h2');
assert.equal(staleHabit.details.done,undefined);
assert.equal(staleHabit.details.habit_minimum_done,undefined);
assert.equal(staleHabit.details.habit_rest,undefined);

// First write discovers revision; next write must consume the successful response token.
const fresh=planner(transport).p;
const payload={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'[N]',type:'N',title:'Sequential',details:{}})};
await fresh.api('/api/items',payload);
const first=writes().at(-1);
assert.equal(first.status,201);
await fresh.api('/api/items',payload);
assert.equal(writes().at(-1).headers.get('If-Match'),first.etag);
assert.equal(writes().at(-1).status,201);
for (const c of writes()) {
  assert.match(c.headers.get('If-Match'),/^"[a-f0-9]{64}"$/);
  assert.notEqual(c.status,428);
}

// Discovery failures fail closed, including success without a revision header.
for (const status of [200,401,503]) {
  const seen=[];
  const client=planner(async (path,options={})=>{seen.push(options.method||'GET');return new Response('{}',{status});}).p;
  await assert.rejects(()=>client.api('/api/items',payload));
  assert.deepEqual(seen,['GET']);
}
// Alternative authoritative header, explicit missing snapshot, and Japanese conflict text.
const seen=[];
const mocked=planner(async (path,options={})=>{seen.push(options);return new Response('{}',{
  status:options.method?409:200,headers:{'X-Lifetxt-Revision':'a'.repeat(64)}});},'ja').p;
await assert.rejects(()=>mocked.api('/api/items',payload),/再読み込み/);
assert.equal(new Headers(seen[1].headers).get('If-Match'),'"'+'a'.repeat(64)+'"');
assert.equal(mocked.revision,'"'+'a'.repeat(64)+'"');
await assert.rejects(()=>mocked.api('/api/items',{...payload,expectedRevision:null}),/再読み込み/);
assert.equal(seen.length,2);
const metrics=await data('/api/revision-metrics');
assert.equal(metrics.legacy_fallback_total,0);
console.log(JSON.stringify({legacy_fallback_total:metrics.legacy_fallback_total,revision_mode:metrics.revision_mode,protected_writes:writes().length}));
