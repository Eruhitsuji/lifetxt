"""Execute notification record rendering in both UI languages (#1507)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE
from tests.test_web_i18n import _ja_dictionary


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class NotificationRecordTests(unittest.TestCase):
    def test_actions_localize_without_translating_record_or_changing_handlers(self):
        source = HTML_PAGE[
            HTML_PAGE.index("    async function loadNotifications()") : HTML_PAGE.index(
                "    async function ackMessage("
            )
        ]
        escape = HTML_PAGE[
            HTML_PAGE.index("    function escapeHtml(") : HTML_PAGE.index(
                "    function escapeHtml("
            )
            + 500
        ]
        escape = escape[: escape.index("\n    }", 1) + 6]
        script = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
for(const lang of ['en','ja'])for(const hasId of [true,false]){
 const record={title:'Ack <private>',sender:'Snooze & sender',recipients:['Retry <recipient>'],when:'',id:hasId?'id\"<&':null};
 const node={innerHTML:'',insertAdjacentHTML:(_,html)=>node.innerHTML+=html},calls=[],notified=[];
 const sandbox={appConfig:{notifications:{snooze_default:'15m'}},window:{},URLSearchParams,
 document:{getElementById:()=>node},query:()=>new URLSearchParams(),firstParam:()=> '0m',
 t:s=>lang==='ja'?(input.dictionary[s]||s):s,jsLiteral:JSON.stringify,
 api:async(url,options)=>{calls.push([url,options]);return {records:[record]}},
 notifStateBadge:()=>'',relativeTime:()=>'',showBrowserNotification:r=>notified.push(r)};
 vm.createContext(sandbox);vm.runInContext(input.escape+input.source,sandbox);
 await vm.runInContext('loadNotifications()',sandbox);
 assert.equal(calls.length,1);assert.equal(calls[0][1],undefined);assert.equal(notified[0],record);
 assert.ok(node.innerHTML.includes('Ack &lt;private&gt;'));
 assert.ok(node.innerHTML.includes('Snooze &amp; sender'));
 assert.ok(node.innerHTML.includes('Retry &lt;recipient&gt;'));
 if(hasId){
  for(const label of lang==='ja'?['既読にする','スヌーズ 15m','カスタム…','再送','実行','ブラウザ通知を再送']:['Ack','Snooze 15m','Custom…','Retry','Go','Re-send browser notification'])assert.ok(node.innerHTML.includes(label),label);
  for(const handler of ['ackMessage','snoozeMessage','snoozeMessageCustom','retryBrowserNotification'])assert.ok(node.innerHTML.includes(handler+'('));
  assert.ok(node.innerHTML.includes('id\\&quot;&lt;&amp;'));
  assert.ok(node.innerHTML.includes('value="15m"'));
 }else{assert.ok(!node.innerHTML.includes('<button'));}
}
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(
                {"source": source, "escape": escape, "dictionary": _ja_dictionary()}
            ),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
