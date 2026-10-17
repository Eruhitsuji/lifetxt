// Actual pinned WASM runtime observations, not a complete binary SBOM (#1362).
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const directory = resolve(process.argv[2]);
const {loadPyodide} = await import(pathToFileURL(resolve(directory, 'runtime/pyodide.mjs')));
const runtime = await loadPyodide({indexURL: resolve(directory, 'runtime') + '/'});
const observed = JSON.parse(runtime.runPython(`
import json, sys, zlib, sqlite3, pyexpat, _bz2, _lzma, _ctypes, _zstd
json.dumps({
  "python": sys.version,
  "builtins": list(sys.builtin_module_names),
  "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
  "sqlite_runtime": sqlite3.sqlite_version,
  "expat_runtime": pyexpat.EXPAT_VERSION,
  "imported_extensions": ["_bz2", "_lzma", "_ctypes", "_zstd"],
})
`));
const manifest = JSON.parse(await readFile(resolve(directory, 'manifest.json'), 'utf8'));
const hashes = {};
for (const [name, expected] of Object.entries(manifest.files)) {
  if (!name.startsWith('runtime/')) continue;
  const data = await readFile(resolve(directory, name));
  const sha256 = createHash('sha256').update(data).digest('hex');
  if (sha256 !== expected.sha256) throw new Error('Artifact hash mismatch: ' + name);
  hashes[name] = {bytes: data.length, sha256};
}
await writeFile(process.argv[3], JSON.stringify({
  kind: 'Node execution of actual PoC WASM; not browser acceptance or complete SBOM',
  complete_distribution_audit: false, node: process.version,
  pyodide: runtime.version, runtime_files: hashes, observed,
}, null, 2) + '\n');
console.log(JSON.stringify({pyodide:runtime.version, builtins:observed.builtins.length,
  zlib:observed.zlib_runtime, sqlite:observed.sqlite_runtime, expat:observed.expat_runtime}));
