import {Worker} from 'node:worker_threads';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const directory=resolve(process.argv[2]);
const worker=new Worker(new URL('./node_worker.mjs',import.meta.url),{workerData:{directory}});
const messages=[];
let ticks=0;
const heartbeat=setInterval(()=>ticks++,10);
let seq=0;
function request(text) {
  return new Promise((resolve,reject)=>{
    const id=++seq;
    const timeout=setTimeout(()=>reject(new Error('Probe timeout')),30000);
    const listener=data=>{
      messages.push(data);
      if(data.id!==id || !['result','error'].includes(data.stage))return;
      worker.off('message',listener);clearTimeout(timeout);resolve(data);
    };
    worker.on('message',listener);worker.postMessage({id,text});
  });
}
try {
  const cold=await request('[ ] T "Read"');
  const coldTicks=ticks;
  const warm=await request('[ ] T "Read"\n'.repeat(2000));
  const over=await request('あ'.repeat(22000));
  const fixtures=JSON.parse(await readFile(resolve(directory,'fixtures.json'),'utf8'));
  const matches=[];
  for(const f of fixtures) {
    const r=await request(f.text); matches.push({name:f.name,match:JSON.stringify(r.result)===JSON.stringify(f.expected)});
  }
  // Actual worker termination, including termination during pending initialization.
  await worker.terminate();
  const fresh=new Worker(new URL('./node_worker.mjs',import.meta.url),{workerData:{directory}});
  fresh.postMessage({id:999,text:'[ ] T "Read"'});
  await fresh.terminate();
  const evidence={environment:'Node worker_threads with browser-worker shim; not a browser',cold,warm,
    startup:messages.find(m=>m.stage==='ready'),
    heartbeat_ticks_during_startup:coldTicks,over_limit_refused:over.stage==='error',matches,
    source_asset_reads:messages.filter(m=>m.stage==='asset-read').map(m=>m.url),
    termination_completed:true};
  await writeFile(process.argv[3],JSON.stringify(evidence,null,2)+'\n');
  console.log(JSON.stringify({ticks:coldTicks,match:matches.every(m=>m.match),over_limit_refused:evidence.over_limit_refused,
    source_asset_reads:evidence.source_asset_reads}));
  if(!coldTicks||matches.some(m=>!m.match)||!evidence.over_limit_refused)process.exitCode=1;
} finally {clearInterval(heartbeat);await worker.terminate();}
