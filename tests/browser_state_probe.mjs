import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import http from 'node:http';
import {launch} from './browser_revision_support.mjs';

const [browserPath, file, screenshot] = process.argv.slice(2);
const html = await readFile(file, 'utf8');
const setup = `
window.__posts=[];window.__error=0;window.__delay=false;
window.__record={person:'self',active:true,state:'busy',title:'Safe <img src=x onerror=alert(1)> '+('x'.repeat(160)),from:'2031-02-03T09:00',to:'',details:{note:['A note']}};
window.__revision='"r0"';
window.fetch=async (path,options={})=>{
 const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','ETag':window.__revision,'X-Lifetxt-Timezone':'UTC'}});
 if(options.method==='POST'){
  const payload=JSON.parse(options.body);window.__posts.push({payload,headers:options.headers});
  const save=()=>{if(window.__error)return response({},window.__error);const same=!payload.force&&!payload.end&&window.__record?.state===payload.state;
   if(payload.end)window.__record=null;else if(!same)window.__record={person:'self',active:true,state:payload.state,title:payload.title||payload.state,from:'2031-02-03T10:00',to:'',details:{note:payload.note?[payload.note]:[]}};
   if(!same)window.__revision='"r'+window.__posts.length+'"';return response({unchanged:same?payload.state:'',closed:[],opened:payload.end?'':'new'});};
  if(window.__delay)return new Promise(resolve=>window.__release=()=>resolve(save()));return save();
 }
 if(String(path).includes('/api/config'))return response({current_datetime:'2031-02-03T10:00:00Z',web:{presence:{commuting:'p-focus'}}});
 if(String(path).includes('/api/health'))return response({read_only:new URL(location.href).searchParams.has('readonly'),writable_path:'life.txt'});
 return response({records:[{person:'aaa',active:true,state:'meeting',title:'Other'},...(window.__record?[window.__record]:[])]});
};`;
const server = http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});response.end(html);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const driver=await launch(browserPath);
const {command,evaluate,wait}=driver;
const base=`http://127.0.0.1:${server.address().port}/state`;
async function open(query='') {
  await command('Page.navigate',{url:base+query});
  await wait(`location.href===${JSON.stringify(base+query)}&&document.querySelector('#sync')?.textContent.match(/Up to date|最新の状態/)`, 'State boot');
}
const matrix=[];
try {
 await command('Page.addScriptToEvaluateOnNewDocument',{source:setup});
 for(const width of [320,360,390,430,740])for(const language of ['en','ja'])for(const theme of ['light','dark']){
  const height=width===740?360:844;
  await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:true});
  await open(`?lang=${language}&theme=${theme}`);
  await evaluate(`document.querySelector('#more-states').open=true;document.querySelector('#details').open=true`);
  const report=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,language:document.documentElement.lang,theme:document.documentElement.dataset.theme,primary:document.querySelectorAll('#primary-states .tile').length,all:document.querySelectorAll('.tile').length,minHeight:Math.min(...[...document.querySelectorAll('.tile')].map(n=>n.getBoundingClientRect().height)),pressed:document.querySelector('[data-state=busy]').getAttribute('aria-pressed'),safe:!document.querySelector('#activity img'),override:document.querySelector('[data-state=commuting]').classList.contains('p-focus'),labels:[...document.querySelectorAll('.tile')].every(n=>n.textContent.trim()),fields:[...document.querySelectorAll('input,textarea,select')].every(n=>n.labels.length>0)})`);
  assert.equal(report.width,width);assert.ok(report.scroll<=width);assert.equal(report.language,language);assert.equal(report.theme,theme);assert.equal(report.primary,6);assert.equal(report.all,9);assert.ok(report.minHeight>=44);assert.equal(report.pressed,'true');assert.ok(report.safe&&report.override&&report.labels&&report.fields);
  await command('Accessibility.enable');
  const ax=await command('Accessibility.getFullAXTree');
  assert.ok(ax.nodes.some(node=>node.role?.value==='button'&&node.name?.value.includes(language==='ja'?'集中':'Focus')));
  matrix.push(report);
 }
 await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await open('?lang=en&theme=light');
 await evaluate(`window.__delay=true;document.querySelector('[data-state=focus]').focus()`);
 await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await wait('window.__posts.length===1','keyboard submission');
 assert.equal(await evaluate(`document.querySelector('#current-state').textContent`),'Busy');
 assert.ok(await evaluate(`[...document.querySelectorAll('.tile')].every(n=>n.disabled)`));
 await evaluate(`document.querySelector('[data-state=away]').click();window.__release()`);
 await wait(`document.querySelector('#current-state').textContent==='Focus'&&!document.querySelector('#refresh').disabled`,'confirmed save');
 assert.equal(await evaluate('window.__posts.length'),1);
  assert.equal(await evaluate('document.activeElement.dataset.state'),'focus');
 assert.deepEqual(await evaluate('window.__posts[0].payload'),{state:'focus'});
 assert.equal(await evaluate(`window.__posts[0].headers['If-Match']`),'"r0"');
  await command('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
  await evaluate(`window.__delay=false;document.querySelector('[data-state=away]').scrollIntoView({block:'center'})`);
  const point=await evaluate(`(()=>{const r=document.querySelector('[data-state=away]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...point,id:1}]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await wait(`document.querySelector('#current-state').textContent==='Away'&&!document.querySelector('#refresh').disabled`,'native touch save');
 await evaluate(`window.__delay=false;document.querySelector('#more-states').open=true;document.querySelector('#custom-open').click()`);
 assert.equal(await evaluate('document.activeElement.id'),'custom-state');
 await command('Input.insertText',{text:'custom <img src=x onerror=alert(1)>'});
 await evaluate(`document.querySelector('#activity-input').value='<b>Untrusted title</b>';document.querySelector('#activity-input').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#save').click()`);
 await wait(`document.querySelector('#current-state').textContent.startsWith('custom ')&&!document.querySelector('#refresh').disabled`,'custom save');
 assert.equal(await evaluate(`document.querySelector('#activity').innerHTML`),'&lt;b&gt;Untrusted title&lt;/b&gt;');
 assert.equal(await evaluate(`document.querySelector('#current-state img')`),null);
 await command('Emulation.setDeviceMetricsOverride',{width:390,height:300,deviceScaleFactor:1,mobile:true});
 await evaluate(`document.querySelector('#save').scrollIntoView({block:'center'})`);
 assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth&&document.querySelector('#save').getBoundingClientRect().top>=0&&document.querySelector('#save').getBoundingClientRect().bottom<=innerHeight`));
 await open('?lang=ja&readonly=1');
 assert.ok(await evaluate(`[...document.querySelectorAll('.tile')].every(n=>n.disabled)&&document.querySelector('#detail-fields').disabled`));
 assert.ok(await evaluate(`document.querySelector('#write-access').textContent.includes('読み取り専用')`));
 await open('?lang=en&theme=dark');
 await command('Emulation.setEmulatedMedia',{features:[{name:'forced-colors',value:'active'}]});
 assert.ok(await evaluate(`parseFloat(getComputedStyle(document.querySelector('[data-state=busy]')).outlineWidth)>=3`));
 await command('Emulation.setEmulatedMedia',{features:[]});
 if(screenshot){await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await open('?lang=ja&theme=light');const shot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(screenshot,Buffer.from(shot.data,'base64'));}
 console.log(JSON.stringify({matrix,interaction:'keyboard, native touch, pending guard, canonical payload/revision, custom focus, XSS, short viewport, read-only, AX, forced colors passed'}));
} finally {await driver.close();await new Promise(resolve=>server.close(resolve));}
