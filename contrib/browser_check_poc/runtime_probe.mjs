// Execute only the hash-validated pinned runtime; no optional package loading.
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const directory = resolve(process.argv[2]);
const {loadPyodide} = await import(pathToFileURL(resolve(directory, 'pyodide.mjs')));
const runtime = await loadPyodide({indexURL: directory + '/'});
console.log(runtime.runPython(`
import json, sqlite3, _zstd, unicodedata, sysconfig
json.dumps({"sqlite": sqlite3.sqlite_version, "zstd": _zstd.zstd_version,
            "ucd": unicodedata.unidata_version, "legacy_ucd": unicodedata.ucd_3_2_0.unidata_version,
            "with_mimalloc": sysconfig.get_config_var("WITH_MIMALLOC")}, sort_keys=True)
`));
