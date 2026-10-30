"""Behavior of shipped Overview helpers; no optional Web dependencies."""

import json
import shutil
import subprocess
import unittest

from tests.test_web_drawer_edit_js import _extract_function, _extract_script


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DrawerOverviewTests(unittest.TestCase):
    def test_data_dates_and_state_actions(self):
        source = _extract_script()
        names = [
            "escapeHtml",
            "jsLiteral",
            "drawerText",
            "drawerDateValue",
            "drawerOverviewFields",
            "_drawerRestoreButtons",
            "_topClockSettings",
            "_validClockZone",
            "_parseClockFormat",
            "_clockParts",
            "_clockCalendarDate",
            "_clockOffsetText",
        ]
        snippet = "\n".join(
            _extract_function(source, "function " + n + "(") for n in names
        )
        harness = r"""
const _clockFormatters = new Map();
let lang = 'ja';
const currentLanguage = () => lang;
const appConfig = {ids:{key:'uid'}, web:{top_clock:{main_timezone:'Asia/Tokyo', timezone:'UTC'}}};
const node = {innerHTML:''};
const document = {getElementById:()=>node};
const result = {};
result.date = drawerDateValue('2026-10-30T20:10:17Z');
result.invalid = ['2026-02-30T12:00:00Z', 'invalid', '2026-10-30', '2026-10-30T12:00:00'].map(drawerDateValue);
const item = {type:'T',status:'[ ]',editable:true,id:'id-fallback',details:{uid:['abc'],due:['2026-10-30'],do:['2026-10-31'],done:['2026-10-30T20:10:17Z'],custom:['Done','<img onerror="bad">'],constructor:['custom-constructor'],toString:['custom-toString'],file:['/private/reference'],body:['body'],parent:['x" onclick="bad']}};
const before=JSON.stringify(item);
result.fields=drawerOverviewFields(item);
result.unchanged = before === JSON.stringify(item);
_drawerRestoreButtons(item);result.open=node.innerHTML;
_drawerRestoreButtons({...item,status:'[x]'});result.done=node.innerHTML;
_drawerRestoreButtons({...item,status:'[-]'});result.cancelled=node.innerHTML;
_drawerRestoreButtons({...item,editable:false});result.readonly=node.innerHTML;
lang='en';result.english=drawerOverviewFields(item);
appConfig.web.top_clock.main_timezone='host';appConfig.web.top_clock.main_utc_offset_minutes=-330;
result.host=drawerDateValue('2026-10-30T20:10:17Z');
console.log(JSON.stringify(result));
"""
        run = subprocess.run(
            ["node", "-e", snippet + harness],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, run.returncode, run.stderr)
        data = json.loads(run.stdout)
        self.assertIn("2026-10-31 05:10:17 JST", data["date"])
        self.assertIn('title="2026-10-30T20:10:17Z"', data["date"])
        self.assertEqual(
            ["2026-02-30T12:00:00Z", "invalid", "2026-10-30", "2026-10-30T12:00:00"],
            data["invalid"],
        )
        self.assertIn("2026-10-30 14:40:17 UTC-05:30", data["host"])
        self.assertTrue(data["unchanged"])
        self.assertIn("期限", data["fields"]["important"])
        self.assertIn("実施予定", data["fields"]["important"])
        self.assertIn("Due", data["english"]["important"])
        self.assertIn("Done", data["fields"]["other"])
        self.assertIn("custom-constructor", data["fields"]["other"])
        self.assertIn("custom-toString", data["fields"]["other"])
        self.assertIn("&lt;img", data["fields"]["other"])
        self.assertNotIn("<img", data["fields"]["other"])
        self.assertNotIn("/private", json.dumps(data["fields"]))
        self.assertIn("abc", data["fields"]["technical"])
        self.assertIn('id="drawer-done-btn"', data["open"])
        for state in ("done", "cancelled"):
            self.assertNotIn('id="drawer-done-btn"', data[state])
            self.assertNotIn('id="drawer-done-date-btn"', data[state])
            self.assertIn('id="drawer-edit-btn"', data[state])
            self.assertLess(
                data[state].index("drawer-overflow-menu"),
                data[state].index('id="drawer-delete-btn"'),
            )
        self.assertIn(
            'id="drawer-edit-btn" onclick="drawerEdit()" disabled', data["readonly"]
        )


if __name__ == "__main__":
    unittest.main()
