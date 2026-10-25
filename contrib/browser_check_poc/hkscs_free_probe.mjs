// Explicit candidate only. No network fallback or package downloads.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [directory, output] = process.argv.slice(2);
assert(directory && output, 'usage: node hkscs_free_probe.mjs CANDIDATE OUTPUT');
const root = resolve(directory);
const { loadPyodide } = await import(pathToFileURL(resolve(root, 'pyodide.mjs')));
const py = await loadPyodide({ indexURL: root + '/', packages: [] });
const report = JSON.parse(py.runPython(`
import codecs, importlib, json, sys
assert '_codecs_hk' not in sys.builtin_module_names, 'HKSCS builtin remains present'
blocked = []
for name in ('_codecs_hk', 'encodings.big5hkscs'):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        blocked.append(name)
    else:
        raise AssertionError('HKSCS module still present: ' + name)
for name in ('big5hkscs', 'big5_hkscs', 'hkscs', 'big5-hkscs'):
    try:
        codecs.lookup(name)
    except LookupError:
        blocked.append(name)
    else:
        raise AssertionError('HKSCS codec still present: ' + name)
for name in ('utf-8', 'shift_jis', 'euc_jp', 'iso2022_jp', 'big5', 'cp950'):
    text = '日本語' if name not in ('big5', 'cp950') else '中文'
    assert text.encode(name).decode(name) == text
json.dumps({'blocked': blocked, 'unicode': '日本語𠮷あ',
            'python': sys.version, 'builtin_count': len(sys.builtin_module_names)})
`));
report.profile = 'lifetxt-hkscs-free-1';
report.node = process.version;
report.environment = 'Node WASM; browser operation and independent review remain separate';
report.files = {};
for (const name of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  const data = await readFile(resolve(root, name));
  report.files[name] = { bytes: data.length, sha256: createHash('sha256').update(data).digest('hex') };
}
report.complete_distribution_audit = false;
report.public_distribution_approved = false;
await writeFile(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
