"""Kiosk auto-scroll pauses under effective reduced motion (#1516)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class KioskMotionTests(unittest.TestCase):
    def test_pause_resume_wrap_and_timer_lifecycle(self):
        start = HTML_PAGE.index("    function _kioskStartScroll()")
        end = HTML_PAGE.index("    function _kioskAddProgressBar()", start)
        script = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let reduced=true,kiosk=true,missing=false,next=0;
const timers=new Map(),calls=[];
const list={scrollTop:0,scrollHeight:1000,clientHeight:200,
 scrollTo:o=>calls.push(['to',JSON.parse(JSON.stringify(o))]),
 scrollBy:o=>calls.push(['by',JSON.parse(JSON.stringify(o))])};
const sandbox={_kioskScrollTimer:null,isKioskMode:()=>kiosk,
 document:{body:{classList:{contains:n=>n==='reduce-motion'&&reduced}},
 getElementById:()=>missing?null:list,
 documentElement:{style:{getPropertyValue:()=> '15'}}},
 setInterval:(fn,ms)=>{assert.equal(ms,15000);timers.set(++next,fn);return next},
 clearInterval:id=>timers.delete(id)};
vm.createContext(sandbox);vm.runInContext(source,sandbox);
const run=()=>vm.runInContext('_kioskStartScroll()',sandbox);
const tick=()=>{assert.equal(timers.size,1);[...timers.values()][0]()};
run();
for(const top of [0,400,800]){list.scrollTop=top;tick();assert.deepEqual(calls,[])}
reduced=false;list.scrollTop=400;tick();
assert.deepEqual(calls.pop(),['by',{top:160,behavior:'smooth'}]);
list.scrollTop=800;tick();
assert.deepEqual(calls.pop(),['to',{top:0,behavior:'smooth'}]);
reduced=true;tick();assert.deepEqual(calls,[]);
reduced=false;tick();assert.equal(calls.length,1);calls.length=0;
run();assert.equal(timers.size,1);
kiosk=false;reduced=true;tick();assert.equal(timers.size,0);
assert.equal(sandbox._kioskScrollTimer,null);
kiosk=true;run();missing=true;run();assert.equal(timers.size,0);
assert.deepEqual(calls,[]);
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(HTML_PAGE[start:end]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
