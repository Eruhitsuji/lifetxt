// Test-only Node worker shim; does not establish browser acceptance.
import {parentPort, workerData} from 'node:worker_threads';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const directory = pathToFileURL(resolve(workerData.directory) + '/');
globalThis.self = {postMessage:data => parentPort.postMessage(data)};
globalThis.fetch = async url => {
  if (![new URL('core.zip', directory).href, new URL('adapter.py', directory).href].includes(url.href)) {
    throw new Error('Unexpected fetch');
  }
  const bytes = await readFile(url);
  return {ok:true, arrayBuffer:async()=>bytes, text:async()=>bytes.toString('utf8')};
};
await import(new URL('worker.mjs', directory));
parentPort.on('message', data => self.onmessage({data}));
