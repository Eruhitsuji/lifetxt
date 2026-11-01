"""Notification empty/disabled chrome inside the record exclusion (#1503)."""

import json
import shutil
import subprocess
import unittest
from lifetxt.web_assets import HTML_PAGE
from tests.test_web_i18n import _ja_dictionary


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class NotificationEmptyTests(unittest.TestCase):
    def test_localized_empty_and_disabled_states_preserve_actions_and_query(self):
        source = HTML_PAGE[
            HTML_PAGE.index("    async function loadNotifications()") : HTML_PAGE.index(
                "    async function ackMessage("
            )
        ]
        helper = HTML_PAGE[
            HTML_PAGE.index("    function guidedEmptyState(") : HTML_PAGE.index(
                "    function enhanceItemsEmptyState("
            )
        ]
        script = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
for(const lang of ['en','ja'])for(const disabled of [false,'enabled','web']){
 const node={innerHTML:''},calls=[],config={notifications:{}};
 if(disabled)config.notifications[disabled]=false;
 const sandbox={appConfig:config,window:{},document:{getElementById:()=>node},URLSearchParams,
 query:()=>new URLSearchParams('recipient=fixture'),firstParam:()=> '5m',
 t:s=>lang==='ja'?(input.dictionary[s]||s):s,escapeHtml:s=>String(s),jsLiteral:JSON.stringify,
 api:async(url,options)=>{assert.equal(options,undefined);calls.push(url);return {records:[]}}};
 vm.createContext(sandbox);vm.runInContext(input.helper+input.source,sandbox);
 await vm.runInContext('loadNotifications()',sandbox);
 if(lang==='ja')assert.match(node.innerHTML,/[぀-ヿ一-鿿]/);
 if(disabled){assert.equal(calls.length,0);assert.ok(node.innerHTML.includes(lang==='ja'?'通知は無効です':'Notifications disabled.'))}
 else{
 assert.equal(calls.length,1);assert.match(calls[0],/recipient=fixture/);assert.match(calls[0],/lookahead=5m/);
 assert.match(node.innerHTML,/<code>notify<\/code>/);
 for(const action of ['enableNotifications','messages','help'])assert.ok(node.innerHTML.includes(JSON.stringify(action)));
 for(const label of lang==='ja'?['現在、通知はありません','通知を有効化','メッセージ',input.dictionary['Help']]:['No notifications right now','Enable alerts','Messages','Help'])assert.ok(node.innerHTML.includes(label),label);
 }
}
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(
                {"source": source, "helper": helper, "dictionary": _ja_dictionary()}
            ),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
