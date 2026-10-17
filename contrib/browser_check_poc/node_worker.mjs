// Node-only shim for exercising the browser Worker module; not browser evidence.
import {parentPort, workerData} from 'node:worker_threads';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
globalThis.self = {postMessage:data=>parentPort.postMessage(data)};
globalThis.fetch = async url => {
  if (!['./core.zip','./adapter.py'].includes(url)) throw new Error('Unexpected network access');
  parentPort.postMessage({stage:'asset-read',url});
  const data=await readFile(resolve(workerData.directory,url));
  return {ok:true,arrayBuffer:async()=>data,text:async()=>data.toString('utf8')};
};
await import(pathToFileURL(resolve(workerData.directory,'worker.mjs')));
parentPort.on('message',data=>self.onmessage({data}));
