import { loadEngine } from './engine.mjs';
let engine;
self.onmessage = async ({data}) => {
  const {id, text} = data;
  try {
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > 65536) {
      throw new Error('Input must be text of at most 65536 UTF-8 bytes.');
    }
    const started = performance.now();
    if (!engine) {
      const [zip, adapter] = await Promise.all([
        fetch('./core.zip'), fetch('./adapter.py'),
      ]);
      if (!zip.ok || !adapter.ok) throw new Error('PoC package could not be loaded.');
      engine = await loadEngine(new Uint8Array(await zip.arrayBuffer()), await adapter.text());
      self.postMessage({id, stage:'ready', startup_ms:performance.now()-started, runtime:engine.info()});
    }
    const checking = performance.now();
    const result = engine.check(text);
    self.postMessage({id, stage:'result', result, check_ms:performance.now()-checking});
  } catch (_) {
    // Do not echo a Python exception that could include pasted input.
    self.postMessage({id, stage:'error', message:'Check failed. Cancel and retry; see the documented PoC limits.'});
  }
};
