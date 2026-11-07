// Local exact candidate only: no optional packages, server, browser or telemetry.
import assert from 'node:assert/strict';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [directory,inputs,output]=process.argv.slice(2);
assert(directory&&inputs&&output,'usage: unicode_probe.mjs CANDIDATE PROBE_INPUTS OUTPUT');
const root=resolve(directory);
const evidence=JSON.parse(await readFile(new URL('./profiles/unicode-minimal-3/build-evidence.json',import.meta.url),'utf8'));
assert.deepEqual((await readdir(root)).sort(),Object.keys(evidence.files).sort());
for(const [name,pin] of Object.entries(evidence.files)){
 const bytes=await readFile(resolve(root,name));assert.equal(bytes.length,pin.bytes);
 assert.equal(createHash('sha256').update(bytes).digest('hex'),pin.sha256);
}
const {loadPyodide}=await import(pathToFileURL(resolve(root,'pyodide.mjs')));
const py=await loadPyodide({indexURL:root+'/',packages:[]});
const proof=JSON.parse(py.runPython(`
import sys, codecs, importlib, json, io, zipfile, datetime
blocked = ('_multibytecodec','_codecs_cn','_codecs_jp','_codecs_kr','_codecs_tw','_codecs_hk','_codecs_iso2022')
for module in blocked:
    assert module not in sys.builtin_module_names, module
    try: importlib.import_module(module)
    except ModuleNotFoundError as e: assert e.name == module, (module,str(e))
    else: raise AssertionError('builtin remains: '+module)
negative = ('gb18030','gbk','gb2312','shift_jis','cp932','euc_jp','iso2022_jp','big5','big5hkscs','cp950','euc_kr','cp949')
for name in negative:
    for operation in (lambda:codecs.lookup(name),lambda:'x'.encode(name),lambda:b'x'.decode(name)):
        try: operation()
        except LookupError: pass
        else: raise AssertionError('codec remains: '+name)
    try: importlib.import_module('encodings.'+name)
    except ModuleNotFoundError as e: assert e.name == 'encodings.'+name
    else: raise AssertionError('wrapper remains: '+name)
for name in ('ascii','latin_1','utf_8','utf_8_sig','utf_16','utf_16_le','utf_16_be','utf_32','unicode_escape','raw_unicode_escape','cp437'):
    assert 'abc'.encode(name).decode(name)=='abc'
text='日本語😀𠮷'
assert json.loads(json.dumps(text))==text
assert text.encode('utf-8').decode('utf-8')==text
assert datetime.date.fromisoformat('2026-11-07').isoformat()=='2026-11-07'
b=io.BytesIO()
with zipfile.ZipFile(b,'w') as z: z.writestr('x.txt',b'data')
# Legacy non-UTF8 name, not only ASCII: same-length change in both ZIP headers.
legacy=b.getvalue().replace(b'x.txt',b'\\x82.txt')
with zipfile.ZipFile(io.BytesIO(legacy)) as z:
    assert z.namelist()==['é.txt']
    assert z.read('é.txt')==b'data'
json.dumps({'blocked_builtins':list(blocked),'negative_codecs':list(negative),'lookup_encode_decode_rejected':True,'utf8_unicode':text,'legacy_cp437_zip':True,'python':sys.version})
`));
py.FS.writeFile('/core.zip',new Uint8Array(await readFile(resolve(inputs,'core.zip'))));
py.FS.writeFile('/adapter.py',await readFile(resolve(inputs,'adapter.py'),'utf8'));
py.FS.writeFile('/cases.json',await readFile(resolve(inputs,'cases.json'),'utf8'));
const parity=JSON.parse(py.runPython(`
import sys, json
sys.path.insert(0,'/core.zip')
namespace={}
exec(open('/adapter.py',encoding='utf-8').read(),namespace)
namespace['MAX_BYTES']=16384
cases=json.load(open('/cases.json',encoding='utf-8'))
results=[]
for case in cases:
    try: value=namespace['check_text'](case['text'])
    except ValueError:
        assert case.get('expected_error')=='ValueError',case['name']
        assert len(case['text'].encode('utf-8')) > 16384,case['name']
    else:
        assert 'expected_error' not in case,case['name']
        assert value==case['expected'],case['name']
        if case['name']=='diagnostic-cap':
            assert value['truncated'] and len(value['diagnostics'])==100
    results.append(case['name'])
json.dumps({'cases':len(results),'matches':len(results),'names':results})
`));
await writeFile(output,JSON.stringify({scope:'Node WASM technical checks; no browser/permission acceptance',node:process.version,runtime_files:evidence.files,probe_inputs:Object.fromEntries(await Promise.all(['core.zip','adapter.py','cases.json'].map(async name=>{const b=await readFile(resolve(inputs,name));return[name,{bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')}];}))),proof,parity,runtime_verified:false,complete_distribution_audit:false,public_distribution_approved:false},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({blocked:proof.blocked_builtins.length,negative:proof.negative_codecs.length,parity:parity.cases}));
