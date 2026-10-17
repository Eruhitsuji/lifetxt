// Identical adapter and WASM initialization used by browser Worker and Node probe.
import { loadPyodide } from './runtime/pyodide.mjs';
export async function loadEngine(archive, adapter, indexURL = new URL('./runtime/', import.meta.url).href) {
  if (indexURL.startsWith('file:')) indexURL = new URL(indexURL).pathname;
  const py = await loadPyodide({ indexURL, stdout: () => {}, stderr: () => {} });
  py.FS.writeFile('/core.zip', archive);
  py.runPython("import sys; sys.path.insert(0, '/core.zip')");
  py.runPython(adapter);
  const check = py.globals.get('check_json');
  return {
    check(text) { return JSON.parse(check(text)); },
    info() { return { pyodide: py.version, python: py.runPython('sys.version'),
      wasm_heap_bytes: py._module.HEAPU8.byteLength }; },
    dispose() { check.destroy(); },
  };
}
