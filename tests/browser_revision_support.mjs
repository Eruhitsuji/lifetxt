// CDP support confined to the revision probes; every command and cleanup is bounded.
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
export const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function launch(browserPath) {
  const profile = await mkdtemp(path.join(os.tmpdir(), 'lifetxt-revision-'));
  const browser = spawn(browserPath, ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
    '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], {stdio:'ignore'});
  let socket;
  const pending = new Map(), events = [];
  let id = 0;
  async function close() {
    socket?.close();
    for (const waiter of pending.values()) {clearTimeout(waiter.timer); waiter.reject(Error('Browser closed'));}
    pending.clear();
    if (browser.exitCode === null && browser.signalCode === null) {
      browser.kill('SIGTERM');
      for (let i=0;i<50 && browser.exitCode===null && browser.signalCode===null;i++) await delay(100);
      if (browser.exitCode===null && browser.signalCode===null) browser.kill('SIGKILL');
      for (let i=0;i<50 && browser.exitCode===null && browser.signalCode===null;i++) await delay(100);
      if (browser.exitCode===null && browser.signalCode===null) throw Error('Browser cleanup timed out');
    }
    await rm(profile, {recursive:true, force:true, maxRetries:10, retryDelay:100});
  }
  try {
    let port;
    for (let i=0;i<100;i++) {
      if(browser.exitCode!==null) throw Error('Browser exited before CDP startup');
      try {port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
      catch {await delay(100);}
    }
    if (!port) throw Error('CDP startup timed out');
    const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`, {signal:AbortSignal.timeout(5000)})).json();
    socket=new WebSocket(targets.find(x=>x.type==='page').webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('CDP connection timed out')),5000);
      socket.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
      socket.addEventListener('error',()=>{clearTimeout(timer);reject(Error('CDP connection failed'));},{once:true});
    });
    socket.addEventListener('message', event=>{
      const message=JSON.parse(event.data);
      if(!message.id) {events.push(message);return;}
      const waiter=pending.get(message.id);
      if(!waiter)return;
      pending.delete(message.id);clearTimeout(waiter.timer);
      if(message.error)waiter.reject(Error(message.error.message));else waiter.resolve(message.result);
    });
    const command=(method,params={})=>new Promise((resolve,reject)=>{
      const key=++id;
      const timer=setTimeout(()=>{pending.delete(key);reject(Error('CDP timed out: '+method));},10000);
      pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}));
    });
    const evaluate=async expression=>{
      const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
      if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    };
    const wait=async (expression,label)=>{
      for(let i=0;i<150;i++){if(await evaluate(expression))return;await delay(40);}
      throw Error('Timed out: '+label);
    };
    for(const name of ['Page','Runtime','Network','Log'])await command(name+'.enable');
    return {command,evaluate,wait,events,close,version:await command('Browser.getVersion')};
  } catch(error) {await close();throw error;}
}
