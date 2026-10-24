import { loadEngine } from './engine.mjs';
import { MAX_BYTES } from './limits.mjs';
let engine;
self.onmessage = async ({data}) => {
  const {id, text} = data;
  try {
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > MAX_BYTES) {
      throw new Error('Invalid input');
    }
    const started = performance.now();
    if (!engine) {
      const [zip, adapter] = await Promise.all([
        fetch(new URL('./core.zip', import.meta.url)),
        fetch(new URL('./adapter.py', import.meta.url)),
      ]);
      if (!zip.ok || !adapter.ok) throw new Error('Package unavailable');
      engine = await loadEngine(new Uint8Array(await zip.arrayBuffer()), await adapter.text());
      self.postMessage({id, stage:'ready', startup_ms:performance.now()-started});
    }
    const startedCheck = performance.now();
    const result = engine.check(text);
    self.postMessage({id, stage:'result', result, check_ms:performance.now()-startedCheck});
  } catch (_) {
    // Python exceptions may contain the pasted input: never forward or log them.
    self.postMessage({id, stage:'error'});
  }
};
