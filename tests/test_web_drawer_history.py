"""Readable history and latest-request isolation using the shipped JS."""

import json
import shutil
import subprocess
import unittest

from tests.test_web_drawer_edit_js import _extract_function
from tests.test_web_native_timeline_visual import (
    _extract_script,
    _extract_functions_under_test,
)


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DrawerHistoryTests(unittest.TestCase):
    def test_localized_evidence_dates_queries_and_stale_responses(self):
        source = _extract_script()
        extra = "\n".join(
            _extract_function(source, "function " + name + "(")
            for name in [
                "drawerDateValue",
                "_topClockSettings",
                "_validClockZone",
                "_parseClockFormat",
                "_clockParts",
                "_clockCalendarDate",
                "_clockOffsetText",
            ]
        )
        script = (
            _extract_functions_under_test(source)
            + "\n"
            + extra
            + r"""
let lang='ja';const currentLanguage=()=>lang;
const appConfig={web:{top_clock:{main_timezone:'Asia/Tokyo',timezone:'UTC'}}};
const _clockFormatters=new Map();
const payload={complete:false,bounds:{returned_events:1,total_valid_events:3,truncated:true},limitations:['item_history_incomplete','event_limit_truncated','<img onerror=x>'],invalid_events:[{note:'<script>bad</script>'}],diagnostics:[{code:'W-unknown',message:'Done'}],events:[{record_kind:'item_event',event:'completed',at:'2026-10-30T20:00:00Z',record_id:'evt1',transaction:'transaction-1',payload:{before_status:'[ ]',after_status:'[x]',item_title:'Done'},valid:true}]};
const before=JSON.stringify(payload);
const result={unknown:nativeTimelineEventLabel({event:'constructor'}),status:nativeTimelineStatus('constructor'),html:renderNativeTimelinePanel(payload),day:nativeTimelineDateKey(payload.events[0].at),unchanged:JSON.stringify(payload)===before};
lang='en';result.en=renderNativeTimelinePanel(payload);lang='ja';
let container={innerHTML:''},fields={};
for(const key of ['since','until','event','limit'])fields['nt-filter-'+key]={value:''};
fields['nt-advanced']={open:true};
const document={getElementById:id=>id==='drawer-native-timeline'?container:fields[id]};
let drawerItem={id:'one'},drawerEditing=false;const _drawerIdFor=i=>i?.id;
let requests=[];const api=(path)=>new Promise((resolve,reject)=>requests.push({path,resolve,reject}));
(async()=>{
_ntCurrentItemId='one';
fields['nt-filter-event'].value='completed';
fields['nt-filter-since'].value='2026-10-30T00:00:00+09:00';
fields['nt-filter-limit'].value='5';
const first=reloadNativeTimelinePanel();
fields['nt-filter-event'].value='created';
const second=reloadNativeTimelinePanel();
requests[1].resolve({...payload,events:[],bounds:{returned_events:0,total_valid_events:3}});await second;
const newest=container.innerHTML;requests[0].reject(Error('stale error'));await first;
result.latest=container.innerHTML===newest;
result.query=requests[0].path;
const third=reloadNativeTimelinePanel();drawerItem={id:'two'};_ntCurrentItemId='two';
requests[2].resolve(payload);await third;result.otherItem=container.innerHTML.includes('evt1')===false;
const fourth=reloadNativeTimelinePanel();const previous=container;container={innerHTML:'new mounted panel'};
requests[3].resolve(payload);await fourth;result.remount=container.innerHTML==='new mounted panel';
console.log(JSON.stringify(result));
})();
"""
        )
        run = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(0, run.returncode, run.stderr)
        data = json.loads(run.stdout)
        self.assertEqual("constructor", data["unknown"])
        self.assertEqual("constructor", data["status"])
        self.assertEqual("2026-10-31", data["day"])
        self.assertTrue(data["unchanged"])
        for text in [
            "確認可能な履歴は一部",
            "履歴は不完全",
            "1/3 件を表示",
            "2026-10-31 05:00:00 JST",
            "2026-10-30T20:00:00Z",
            "未完了 [ ]",
            "完了 [x]",
            "transaction-1",
            "evt1",
            "W-unknown",
            "Done",
            "&lt;img",
        ]:
            self.assertIn(text, data["html"])
        self.assertNotIn("<img", data["html"])
        self.assertNotIn("<script>", data["html"])
        self.assertIn("Partial / limited history", data["en"])
        for key in ["latest", "otherItem", "remount"]:
            self.assertTrue(data[key], key)
        self.assertIn("event=completed", data["query"])
        self.assertIn("limit=5", data["query"])
        self.assertIn("%2B09%3A00", data["query"])
