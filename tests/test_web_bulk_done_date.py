"""Explicit bulk completion integrity and recovery (#1479 / #1480)."""

import os
import json
import socket
import tempfile
import threading
import time
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class BulkCompletionTests(unittest.TestCase):
    def run_js(self, scenario, timezone="Asia/Tokyo"):
        source = Path("lifetxt/web_assets_js_23.js").read_text(encoding="utf-8")
        harness = r"""
const assert = require('node:assert/strict');
const clone = x => JSON.parse(JSON.stringify(x));
const task = (id,line,extra={}) => ({id,line,source:'/fixture/life.txt',editable:true,type:'T',title:id || 'No ID',status:'[ ]',details:id?{id:[id],tag:['keep']}:{tag:['keep']},...extra});
let currentItems = [task('a',1),task('b',2)], database = clone(currentItems);
let bulkSelectedLines = new Set(currentItems.map(i=>i.line+'|'+i.source)), appConfig={};
let version=1, failId=null, loseReceipt=false, race=false, changeRead=false, pause=false, release;
let readonly=false, writable='/fixture/life.txt';
const hash = () => String(version).padStart(64,'0');
const writes=[];
const elements = new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,{value:id==='bulk-done-mode'?'now':'',textContent:'',innerHTML:'',disabled:false,hidden:false,setAttribute(){},classList:{contains:()=>true}});return elements.get(id);}};
const t = x=>x;
const escapeHtml = x=>String(x).replaceAll('<','&lt;');
let opened=false, refreshFail=false;
const openManagedModal=()=>{opened=true;};
const closeManagedModal=()=>{opened=false;};
const refreshAll=async()=>{if(refreshFail)throw Error('refresh'); currentItems=clone(database);};
const api=async(path,options={})=>{
 if(path==='/api/health')return {read_only:readonly,writable_path:writable,paths:[writable]};
 if(path==='/api/revision')return {revision:hash()};
 if(path==='/api/items'){if(changeRead){version++;changeRead=false;}return {items:clone(database)};}
 assert.equal(options.method,'PUT');
 const item=path.includes('/id/')?database.find(i=>bulkDoneId(i)===decodeURIComponent(path.split('/id/')[1])):database.find(i=>i.line===Number(path.split('/').pop()) && i.source===writable);
 if(race){version++;race=false;}
 if(options.headers['If-Match']!=='"'+hash()+'"')throw Object.assign(Error('stale'),{status:409});
 if(failId && item.id===failId)throw Object.assign(Error('denied'),{status:403});
 writes.push({path,payload:JSON.parse(options.body)});
 if(pause)await new Promise(resolve=>release=resolve);
 Object.assign(item,JSON.parse(options.body)); version++;
 if(loseReceipt){loseReceipt=false;throw Error('network');}
 return {item:clone(item)};
};
"""
        script = (
            harness
            + source
            + "\n(async()=>{\n"
            + scenario
            + "\n})().catch(e=>{console.error(e);process.exit(1)});"
        )
        result = subprocess.run(
            [shutil.which("node"), "-e", script],
            text=True,
            capture_output=True,
            timeout=20,
            env={**os.environ, "TZ": timezone},
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_cancel_eligible_and_custom_id_configuration(self):
        self.run_js(r"""
bulkDoneDate();closeBulkDone();assert.equal(writes.length,0);
appConfig={ids:{key:'uid'}};
currentItems=[task(null,1,{details:{uid:['custom'],note:['a','b']}})];
database=clone(currentItems);bulkSelectedLines=new Set(currentItems.map(bulkDoneKey));
bulkDoneDate();await confirmBulkDone();assert.equal(writes[0].path,'/api/items/id/custom');
assert.deepEqual(writes[0].payload.details.note,['a','b']);
""")

    def test_shared_now_atomic_payload_metadata_and_undo(self):
        self.run_js(r"""
const original=clone(database);
bulkDoneDate(); await confirmBulkDone();
assert.equal(writes.length,2);
assert.equal(writes[0].payload.details.done[0],writes[1].payload.details.done[0]);
assert.match(writes[0].payload.details.done[0],/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
for(const write of writes){assert.equal(write.payload.status,'[x]');assert.deepEqual(write.payload.details.tag,['keep']);}
assert.equal(bulkSelectedLines.size,0);
await runBulkDone(true);
assert.deepEqual(database,original);
assert.ok(bulkDoneView.rows.every(r=>r.state==='Restored'));
""")

    def test_custom_dates_invalid_dates_and_dst(self):
        self.run_js(r"""
assert.equal(bulkDoneValue('date','2026-09-19',''),'2026-09-19');
assert.equal(bulkDoneValue('time','2026-09-19','00:15'),'2026-09-18T15:15:00Z');
for(const date of ['','2026-02-30','0000-01-01','2026-13-01'])assert.throws(()=>bulkDoneValue('date',date,''));
assert.throws(()=>bulkDoneValue('time','2026-09-19',''));
bulkDoneDate();document.getElementById('bulk-done-mode').value='date';await confirmBulkDone();assert.equal(writes.length,0);
""")
        self.run_js(
            "assert.throws(()=>bulkDoneValue('time','2026-03-08','02:30'));",
            timezone="America/New_York",
        )

    def test_exclusions_cancel_and_zero_targets(self):
        self.run_js(r"""
currentItems=[task('a',1,{type:'H'}),task('b',2,{editable:false}),task('c',3,{status:'[x]'}),task('d',4,{status:'[-]'}),task('e',5,{details:{done:[]}}),task('f',6,{details:{repeat:['daily']}}),task('g',7,{generated:true})];
bulkSelectedLines=new Set(currentItems.map(bulkDoneKey));
bulkDoneDate();assert.equal(bulkDoneView.rows.filter(r=>!r.reason).length,0);
await confirmBulkDone();closeBulkDone();assert.equal(writes.length,0);assert.equal(opened,false);
assert.ok(document.getElementById('bulk-done-skips').textContent.includes('Repeating task: 1'));
""")

    def test_partial_failure_explicit_retry_and_no_duplicate_success(self):
        self.run_js(r"""
failId='b';bulkDoneDate();await confirmBulkDone();
assert.deepEqual(bulkDoneView.rows.map(r=>r.state),['Completed','Failed']);assert.equal(bulkSelectedLines.size,1);
const value=bulkDoneView.value;
failId=null;await runBulkDone();assert.equal(writes.length,2);assert.equal(database[1].details.done[0],value);
await runBulkDone();assert.equal(writes.length,2);
""")

    def test_changed_record_source_duplicate_id_and_read_race_refused(self):
        for change in [
            "database[0].title='Other';",
            "database[0].source='/fixture/other.txt';",
            "database.push(task('a',8));",
            "writable='/fixture/other.txt';",
            "readonly=true;",
            "changeRead=true;",
            "race=true;",
        ]:
            with self.subTest(change=change):
                self.run_js(
                    "bulkSelectedLines=new Set([bulkDoneKey(currentItems[0])]);bulkDoneDate();"
                    + change
                    + "await confirmBulkDone();assert.equal(writes.length,0);assert.equal(bulkDoneView.rows[0].state,'Failed');"
                )

    def test_idless_line_is_verified_in_full_multi_source_list(self):
        self.run_js(r"""
currentItems=[task(null,1),task('external',1,{source:'/fixture/external.txt',editable:false})];
database=clone(currentItems);bulkSelectedLines=new Set(currentItems.map(bulkDoneKey));
bulkDoneDate();await confirmBulkDone();assert.equal(writes.length,1);assert.equal(writes[0].path,'/api/items/1');
assert.equal(database[1].status,'[ ]');await runBulkDone(true);assert.equal(database[0].status,'[ ]');
""")

    def test_undo_does_not_clobber_external_changes_and_retains_retry(self):
        self.run_js(r"""
bulkDoneDate();await confirmBulkDone();
const saved=clone(database[0]);database[0].details.tag=['external'];version++;
await runBulkDone(true);
assert.equal(database[0].status,'[x]');assert.deepEqual(database[0].details.tag,['external']);
assert.deepEqual(bulkDoneView.rows.map(r=>r.state),['Undo failed','Restored']);
database[0]=saved;version++;await runBulkDone(true);assert.equal(database[0].status,'[ ]');
assert.equal(writes.length,4);
""")

    def test_unknown_success_is_not_written_again_and_double_submit_blocked(self):
        self.run_js(r"""
bulkSelectedLines=new Set([bulkDoneKey(currentItems[0])]);bulkDoneDate();loseReceipt=true;
await confirmBulkDone();assert.equal(writes.length,1);await runBulkDone();assert.equal(writes.length,1);
assert.equal(bulkDoneView.rows[0].state,'Failed');
""")
        self.run_js(r"""
pause=true;bulkDoneDate();const pending=confirmBulkDone();
while(!release)await new Promise(resolve=>setImmediate(resolve));
await confirmBulkDone();await runBulkDone();await runBulkDone(true);closeBulkDone();assert.equal(opened,true);
pause=false;release();await pending;assert.equal(writes.length,2);
""")


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(
    all(importlib.util.find_spec(name) for name in ("fastapi", "uvicorn")),
    "Web extras unavailable",
)
class BulkCompletionApiTests(unittest.TestCase):
    def test_shipped_js_against_required_revision_server(self):
        import uvicorn
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "life.txt"
            path.write_text(
                "[ ] T First id:a tag:keep\n[ ] T Second id:b tag:keep\n"
                "[ ] T WithoutID tag:keep\n",
                encoding="utf-8",
            )
            app = webapp.create_app(
                [str(path)],
                writable_path=str(path),
                config={"web": {"revision_mode": "required"}},
            )
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            server = uvicorn.Server(
                uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
            )
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            self.addCleanup(lambda: thread.join(timeout=10))
            self.addCleanup(setattr, server, "should_exit", True)
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            self.assertTrue(server.started)
            source = Path("lifetxt/web_assets_js_23.js").read_text(encoding="utf-8")
            script = r"""
const assert=require('node:assert/strict');
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,{value:id==='bulk-done-mode'?'date':id==='bulk-done-date'?'2026-10-30':'',setAttribute(){}});return elements.get(id);}};
let appConfig={},currentItems=[],bulkSelectedLines=new Set();
const t=x=>x,escapeHtml=x=>String(x),openManagedModal=()=>{},closeManagedModal=()=>{};
let puts=0, deny=false;
const api=async(path,options={})=>{
 if(options.method==='PUT'){
   puts++;
   if(deny && path.endsWith('/b'))throw Object.assign(Error('denied'),{status:403});
 }
 const response=await fetch(BASE+path,options);
 if(!response.ok)throw Object.assign(Error(await response.text()),{status:response.status});
 return response.json();
};
const refreshAll=async()=>{currentItems=(await api('/api/items')).items;};
""".replace("BASE", json.dumps(f"http://127.0.0.1:{port}"))
            script += (
                source
                + r"""
(async()=>{
 await refreshAll();const original=JSON.parse(JSON.stringify(currentItems));
 bulkSelectedLines=new Set(currentItems.map(bulkDoneKey));
 bulkDoneDate();deny=true;await confirmBulkDone();
 assert.deepEqual(bulkDoneView.rows.map(r=>r.state),['Completed','Failed','Completed']);
 deny=false;await runBulkDone();
 const rows=(await api('/api/items')).items.filter(i=>i.type==='T');
 assert.equal(rows.length,3);
 for(const row of rows){assert.equal(row.status,'[x]');assert.deepEqual(row.details.done,['2026-10-30']);assert.deepEqual(row.details.tag,['keep']);}
 const history=(await api('/api/items')).items.filter(i=>i.details?.event?.[0]==='completed');
 assert.equal(history.length,2); // ID-less ordinary updates do not emit ID-linked history.
 await runBulkDone();assert.equal(puts,4);
 await runBulkDone(true);
 assert.deepEqual(bulkDoneView.rows.map(r=>r.state),['Restored','Restored','Restored']);
 const restored=(await api('/api/items')).items.filter(i=>i.type==='T');
 assert.ok(restored.every((row,i)=>bulkDoneSame(row,original[i])));
})().catch(error=>{console.error(error);process.exit(1)});
"""
            )
            result = subprocess.run(
                [shutil.which("node"), "-e", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
