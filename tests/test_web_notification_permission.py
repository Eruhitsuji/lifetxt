"""Notification permission presentation across languages (#1501)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE
from tests.test_web_i18n import _ja_dictionary


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class NotificationPermissionTests(unittest.TestCase):
    def test_states_and_settings_help_are_localized_without_requesting_permission(self):
        start = HTML_PAGE.index("    function updateNotifPermissionDisplay()")
        end = HTML_PAGE.index("    // ── Git status badge", start)
        script = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for(const lang of ['en','ja'])for(const state of ['granted','denied','default','unsupported']){
  const bar={style:{},innerHTML:'',textContent:''},toasts=[];
  const permission={permission:state,requestPermission(){throw Error('must not request permission')}};
  const sandbox={window:state==='unsupported'?{}:{Notification:permission},Notification:permission,
    document:{getElementById:()=>bar},t:s=>lang==='ja'?(input.dictionary[s]||s):s,
    escapeHtml:s=>s,showToast:(...args)=>toasts.push(args)};
  vm.createContext(sandbox);vm.runInContext(input.source,sandbox);
  vm.runInContext('updateNotifPermissionDisplay();showNotificationSettingsHelp()',sandbox);
  const text=bar.textContent+bar.innerHTML;
  assert.equal(bar.style.display,'');
  if(lang==='ja'){assert.match(text,/[぀-ヿ一-鿿]/);assert.match(toasts[0][0],/ブラウザ/)}
  else{assert.match(text,/notifications|Notifications/);assert.match(toasts[0][0],/browser/)}
  if(state==='denied'){
    assert.match(bar.className,/notif-perm-denied/);
    assert.match(bar.innerHTML,/onclick="showNotificationSettingsHelp\(\)"/);
    assert.ok(bar.innerHTML.includes(lang==='ja'?'設定方法':'How'));
  }else assert.equal(bar.innerHTML,'');
  if(state==='default'&&lang==='ja')assert.match(text,/未要求/);
  assert.equal(toasts[0][1],'info');assert.equal(toasts[0][2],8000);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(
                {"source": HTML_PAGE[start:end], "dictionary": _ja_dictionary()}
            ),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
