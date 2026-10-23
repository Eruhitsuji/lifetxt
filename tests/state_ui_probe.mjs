// Execute the shipped State script with a minimal DOM. This checks interactions
// and transport contracts; the separate Chromium probe checks native layout/AX.
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const [htmlPath, scriptPath] = process.argv.slice(2);
const html = await readFile(htmlPath, 'utf8'), script = await readFile(scriptPath, 'utf8');
let checks = 0;
function expect(actual, expected, message) { assert.deepEqual(actual, expected, message); checks++; }
async function create({lang='en', query='', readonly=false, target='life.txt', initial=null, latest=null, failure=0, zone='UTC', clock='2031-02-03T10:00:00Z', overrides={}}={}) {
  const all = [], ids = new Map(), intervals = [], handlers = new Map();
  class Element {
    constructor(tag) { this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.attributes={};this.value='';this.disabled=false;this.hidden=false;this.checked=false;this.open=false;this.className='';this.ownText='';all.push(this); }
    append(...nodes) { for(const node of nodes){node.parent=this;this.children.push(node);if(this.tagName==='SELECT'&&!this.value)this.value=node.value;} }
    get options() { return this.children; }
    set textContent(value) {this.ownText=String(value);this.children=[];}
    get textContent() {return this.ownText+this.children.map(x=>x.textContent).join('');}
    setAttribute(key,value) {this.attributes[key]=String(value);}
    getAttribute(key) {return this.attributes[key]??null;}
    addEventListener(name,handler) {(this.listeners[name]??=[]).push(handler);}
    dispatchEvent(event) {event.preventDefault??=()=>{};for(const handler of this.listeners[event.type]||[])handler(event);if(event.bubbles&&this.parent)this.parent.dispatchEvent(event);}
    click() {for(let node=this;node;node=node.parent)if(node.disabled)return;this.dispatchEvent({type:'click'});}
    focus() {document.activeElement=this;}
    querySelector(selector) {return this.children.flatMap(child=>[child,...child.descendants()]).find(node=>node.className.split(' ').includes(selector.slice(1)))||null;}
    descendants() {return this.children.flatMap(child=>[child,...child.descendants()]);}
  }
  const root = new Element('html');
  const document = {documentElement:root,readyState:'complete',visibilityState:'visible',activeElement:null,
    getElementById:id=>ids.get(id),createElement:tag=>new Element(tag),
    querySelectorAll:selector=>all.filter(node=>selector==='.tile'?node.className.split(' ').includes('tile'):selector==='[data-i18n]'?Boolean(node.dataset.i18n):false),
    addEventListener:(name,handler)=>handlers.set('document:'+name,handler)};
  for(const match of html.matchAll(/<(\w+)([^>]*\bid="([^"]+)"[^>]*)>/g)) {
    const node=new Element(match[1]);node.id=match[3];ids.set(match[3],node);
    const key=match[2].match(/data-i18n="([^"]+)"/);if(key)node.dataset.i18n=key[1];
    node.disabled=/\bdisabled\b/.test(match[2]);
  }
  ids.get('status-form').append(ids.get('detail-fields'));
  for(const id of ['form-state','custom-state','activity-input','note-input','force','save'])ids.get('detail-fields').append(ids.get(id));
  const record=(state='busy')=>({person:'self',state,active:true,title:'Original activity',from:'2031-02-03T09:00',to:'',details:{note:['Original note']}});
  const model={current:initial??record(),latest,revision:'"r0"',readonly,failure,postError:0,postDelay:false,readDelay:false,readFailure:0,failAfterSave:false,posts:[],calls:[],held:[],zone,clock,overrides};
  const context={document,navigator:{language:lang,onLine:true},location:{search:query,href:'http://localhost/state'+query},URL,URLSearchParams,AbortController,Headers,Response,Intl,Date,performance,console,
    setTimeout,clearTimeout,setInterval:callback=>{intervals.push(callback);return intervals.length;},Event:class {constructor(type,options={}){this.type=type;Object.assign(this,options);}}};
  context.window=context;
  context.addEventListener=(name,handler)=>handlers.set('window:'+name,handler);
  context.history={replaceState:()=>{}};
  const other={person:'aaa',active:true,state:'meeting',title:'Other person',from:'2031-02-03T08:00',to:''};
  const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','ETag':model.revision,'X-Lifetxt-Timezone':model.zone}});
  context.fetch=async (path,options={})=>{
    model.calls.push({path,options});
    expect(options.cache,'no-store','all requests bypass cache');
    if(options.method==='POST'){
      const payload=JSON.parse(options.body);model.posts.push({payload,expected:options.headers['If-Match']});
      const save=()=>{
        if(model.postError==='network')throw Error('Network failed');
        if(model.postError)return response({},model.postError);
        if(options.headers['If-Match']!==model.revision)return response({},409);
        const unchanged=!payload.end&&!payload.force&&model.current?.state===payload.state;
        if(payload.end){model.latest=model.current?{...model.current,active:false,to:'2031-02-03T10:00'}:model.latest;model.current=null;}
        else if(!unchanged)model.current={...record(payload.state),title:payload.title||payload.state,details:{note:payload.note?[payload.note]:[]},from:'2031-02-03T10:00'};
        if(!unchanged)model.revision='"r'+model.posts.length+'"';
        if(model.failAfterSave)model.readFailure=503;
        return response({closed:[],opened:payload.end?'':'record',unchanged:unchanged?payload.state:''});
      };
      if(model.postDelay)return new Promise(resolve=>{model.releasePost=()=>resolve(save());});
      return save();
    }
    if(model.failure||model.readFailure)return response({},model.failure||model.readFailure);
    let data;
    if(path==='/api/config')data={current_datetime:model.clock,web:{language:lang,presence:model.overrides}};
    else if(path==='/api/health')data={read_only:model.readonly,writable_path:target};
    else if(path.endsWith('active=true'))data={records:[other,...(model.current?[model.current]:[])]};
    else data={records:[other,...(model.latest?[model.latest]:model.current?[model.current]:[])]};
    const captured=response(data);
    if(model.readDelay)return new Promise(resolve=>model.held.push(()=>resolve(captured)));
    return captured;
  };
  vm.createContext(context);vm.runInContext(script,context,{filename:scriptPath});
  const settle=async(predicate=()=>!ids.get('refresh').disabled)=>{
    for(let i=0;i<200;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,5));}
    throw Error('State UI did not settle: '+ids.get('sync').textContent+' / '+ids.get('feedback').textContent);
  };
  const input=(id,value)=>{const node=ids.get(id);node.value=value;node.dispatchEvent({type:'input',bubbles:true});};
  const choose=value=>{ids.get('form-state').value=value;ids.get('form-state').dispatchEvent({type:'change'});};
  const tile=state=>all.find(node=>node.className.split(' ').includes('tile')&&node.dataset.state===state);
  await settle();
  return {ids,context,model,handlers,intervals,settle,input,choose,tile,record,submit:()=>ids.get('status-form').dispatchEvent({type:'submit'})};
}

{
  const ui=await create();
  expect(ui.ids.get('current-state').textContent,'Busy','self only, not first other person');
  expect(ui.ids.get('elapsed').textContent,'1 h 0 min','workspace clock instead of client clock');
  expect(ui.ids.get('primary-states').children.length,6,'primary states');
  expect(ui.ids.get('extra-states').children.length,3,'extra states');
  expect(ui.ids.get('details').open,false,'details start closed');
  ui.model.postDelay=true;ui.tile('focus').click();ui.tile('away').click();
  expect(ui.model.posts.length,1,'duplicate submission is suppressed');
  expect(ui.ids.get('current-state').textContent,'Busy','no optimistic current state');
  expect(ui.ids.get('detail-fields').disabled,true,'pending form disabled');
  ui.model.releasePost();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'Focus','confirmed state after save');
  expect(ui.model.posts[0].payload,{state:'focus'},'tile sends canonical state only');
  expect(ui.tile('focus').getAttribute('aria-pressed'),'true','current selection is explicit');
  ui.model.postDelay=false;ui.tile('focus').click();await ui.settle();
  expect(ui.ids.get('feedback').textContent.includes('already current'),true,'same state no-op');
  ui.tile('offline').click();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'Offline','offline is an actual current status');
  ui.ids.get('end').click();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'No current status','end is not offline');
  expect(ui.model.posts.at(-1).payload,{end:true},'end payload');
  expect(ui.ids.get('previous').textContent.includes('Offline'),true,'previous ended state identified');
}
{
  const ui=await create();ui.ids.get('custom-open').click();
  ui.input('custom-state','独自 <img src=x onerror=evil()>');ui.input('activity-input','<script>evil()</script>');ui.input('note-input','Private note');
  ui.ids.get('force').checked=true;ui.submit();await ui.settle();
  expect(ui.model.posts[0].payload,{state:'独自 <img src=x onerror=evil()>',title:'<script>evil()</script>',note:'Private note',force:true},'custom form payload');
  expect(ui.ids.get('current-state').textContent,'独自 <img src=x onerror=evil()>','custom state is plain text');
  expect(ui.ids.get('activity').textContent,'<script>evil()</script>','title is plain text');
  expect(ui.ids.get('current-card').className,'current-card p-unknown','unknown fallback class');
}
for(const status of [400,401,403,409,500,'network']){
  const ui=await create();ui.choose('focus');ui.input('activity-input','Retain draft');ui.input('note-input','Retain note');ui.model.postError=status;ui.submit();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'Busy','failure retains confirmed state '+status);
  expect(ui.ids.get('activity-input').value,'Retain draft','failure retains title '+status);
  expect(ui.ids.get('note-input').value,'Retain note','failure retains note '+status);
  expect(ui.ids.get('feedback').dataset.error,'true','failure is visible '+status);
  expect(ui.model.posts.length,1,'no retry '+status);
}
{
  const ui=await create();ui.choose('focus');ui.input('activity-input','Draft');ui.model.current=ui.record('away');ui.model.revision='"external"';
  ui.handlers.get('window:focus')();await ui.settle();ui.submit();await ui.settle();
  expect(ui.model.posts[0].expected,'"r0"','edited details retain their original revision');
  expect(ui.ids.get('feedback').textContent.includes('Data changed'),true,'pinned conflict');
  ui.ids.get('refresh').click();await ui.settle();ui.submit();await ui.settle();
  expect(ui.model.posts[1].expected,'"external"','only explicit review rebases the form');
  expect(ui.ids.get('activity').textContent,'Draft','reviewed form can save');
}
{
  const ui=await create();ui.model.readDelay=true;ui.ids.get('refresh').click();
  const old=ui.model.held.splice(0);ui.model.readDelay=false;ui.model.revision='"new"';ui.model.current=ui.record('working');
  ui.handlers.get('window:focus')();await ui.settle();old.forEach(resolve=>resolve());await new Promise(resolve=>setTimeout(resolve,10));
  expect(ui.ids.get('current-state').textContent,'Working','old response cannot replace newer data');
  ui.model.failAfterSave=true;ui.tile('focus').click();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'Working','read failure after acknowledged save retains confirmed display');
  expect(ui.ids.get('feedback').textContent.includes('Save acknowledged'),true,'acknowledged but unconfirmed save is distinct');
  expect(ui.tile('away').disabled,true,'unconfirmed state blocks next mutation');
}
{
  const ui=await create({readonly:true,lang:'ja',overrides:{commuting:'p-focus',busy:'bad injected'}});
  expect(ui.ids.get('current-state').textContent,'取り込み中','Japanese label');
  expect(ui.tile('commuting').className,'tile p-focus','configured class override wins');
  expect(ui.tile('busy').className,'tile p-busy','unsafe class ignored');
  ui.tile('focus').click();expect(ui.model.posts.length,0,'read-only suppresses writes');
  expect(ui.ids.get('write-access').textContent.includes('読み取り専用'),true,'read-only explanation');
}
{
  const ui=await create({failure:401});
  expect(ui.ids.get('current-state').textContent,'Unavailable','initial fetch failure is not empty state');
  expect(ui.tile('focus').disabled,true,'initial failure disables writes');
  expect(ui.ids.get('sync').textContent.includes('Authentication'),true,'auth load failure');
}
{
  const ui=await create();ui.model.current=null;ui.model.latest=null;ui.ids.get('refresh').click();await ui.settle();
  expect(ui.ids.get('current-state').textContent,'No current status','unset state');
  expect(ui.ids.get('previous').textContent,'No status has been recorded yet.','never recorded is distinct');
  ui.context.navigator.onLine=false;ui.handlers.get('window:offline')();ui.tile('focus').click();
  expect(ui.model.posts.length,0,'network offline suppresses writes');
  expect(ui.ids.get('sync').textContent.includes('Device is offline'),true,'network status differs from canonical offline');
}
for(const [zone,from,clock,expected] of [
  ['Asia/Tokyo','2031-02-03T09:00','2031-02-03T10:00:00+09:00','1 h 0 min'],
  ['America/New_York','2026-11-01T01:30','2026-11-01T03:00:00-05:00','Unavailable'],
  ['America/New_York','2026-03-08T02:30','2026-03-08T04:00:00-04:00','Unavailable'],
]){
  const ui=await create({zone,clock,initial:{person:'self',active:true,state:'busy',title:'Activity',from,to:'',details:{}}});
  expect(ui.ids.get('elapsed').textContent,expected,'workspace zone / ambiguous clock '+zone+from);
}
for(const lang of ['en','ja']){
  const ui=await create({lang});
  for(const state of ['available','busy','focus','meeting','away','offline','commuting','working','sleeping']){
    ui.tile(state).click();await ui.settle();
    expect(ui.model.posts.at(-1).payload,{state},'all nine canonical values '+lang+state);
    expect(ui.tile(state).getAttribute('aria-pressed'),'true','all nine selection markers');
    expect(ui.tile(state).querySelector('.symbol').textContent.length>0,true,'state icon');
  }
}
{
  const ui=await create();ui.ids.get('custom-open').click();ui.input('custom-state','   ');ui.submit();
  expect(ui.model.posts.length,0,'empty custom state is not sent');
  expect(ui.context.document.activeElement.id,'custom-state','empty custom state focus');
}
{
  const ui=await create({target:''});
  expect(ui.tile('focus').disabled,true,'missing write target disables mutations');
  expect(ui.ids.get('write-access').textContent.includes('No writable target'),true,'missing target explanation');
}
console.log(JSON.stringify({checks,scenarios:22,kind:'DOM interaction and HTTP contract; not layout'}));
