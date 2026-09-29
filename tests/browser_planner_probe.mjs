import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browser, file] = process.argv.slice(2);
const html = (await readFile(file, "utf8")).replace("<script>(() =>", `<script>
window.fetch=async url=>new Response(JSON.stringify(String(url).includes('/api/config')?{today:'2031-02-03',web:{language:'en'}}:String(url).includes('/api/health')?{read_only:false,writable_path:'life.txt'}:String(url).includes('/api/agenda')?{records:[]}:String(url).includes('/api/command-center')?{due_today:[],next_actions:[],blocked:[]}: {items:[]}),{status:200,headers:{'Content-Type':'application/json'}});
</script><script>(() =>`);
const server = http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end(html)});
await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
const profile=await mkdtemp(path.join(os.tmpdir(),'planner-chrome-'));
const proc=spawn(browser,['--headless=new','--disable-gpu','--no-sandbox','--no-first-run','--no-default-browser-check','--disable-dev-shm-usage','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore'});
const wait=ms=>new Promise(ok=>setTimeout(ok,ms));
async function port(){for(let i=0;i<100;i++){try{return +(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]}catch{await wait(100)}}throw Error('DevTools unavailable')}
let id=0;const pending=new Map();let ws;
function cmd(method,params={}){const n=++id;ws.send(JSON.stringify({id:n,method,params}));return new Promise((resolve,reject)=>pending.set(n,{resolve,reject}))}
async function evaljs(expression){return (await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value}
try{
 const dp=await port(), tabs=await(await fetch(`http://127.0.0.1:${dp}/json/list`)).json();ws=new WebSocket(tabs.find(x=>x.type==='page').webSocketDebuggerUrl);
 await new Promise((ok,no)=>{ws.addEventListener('open',ok,{once:true});ws.addEventListener('error',no,{once:true})});
 ws.addEventListener('message',e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}});
 await cmd('Page.enable');await cmd('Runtime.enable');await cmd('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:5});
 const out=[];
 for(const [width,height,lang] of [[320,640,'en'],[360,720,'ja'],[390,844,'en'],[430,932,'ja'],[667,320,'ja'],[390,360,'en']]){
  await cmd('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:2,mobile:true,screenWidth:width,screenHeight:height});
  await cmd('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/planner?lang=${lang}`});
  for(let i=0;i<100;i++){if(await evaljs("document.querySelector('#schedule')?.previousElementSibling?.textContent"))break;await wait(50)}
  out.push(await evaljs(`({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dateHeight:document.querySelector('#date').getBoundingClientRect().height,captureHeight:document.querySelector('#open-capture').getBoundingClientRect().height,schedule:document.querySelector('#schedule').previousElementSibling.textContent.trim()})`));
 }
 process.stdout.write(JSON.stringify(out));
}finally{if(ws)ws.close();if(proc.exitCode===null){proc.kill('SIGTERM');await new Promise(ok=>proc.once('exit',ok))}await new Promise(ok=>server.close(ok));await rm(profile,{recursive:true,force:true})}
