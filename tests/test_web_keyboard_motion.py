"""Keyboard item navigation honors effective reduced motion (#1514)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class KeyboardMotionTests(unittest.TestCase):
    def test_motion_toggle_boundaries_and_empty_items(self):
        start = HTML_PAGE.index("    let _kbIndex = -1;")
        end = HTML_PAGE.index("    function kbFocusedItem()", start)
        script = r"""
const vm=require('node:vm'), assert=require('node:assert/strict');
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let reduced=false, nodes=[], scrolls=[];
const sandbox={document:{
 body:{classList:{contains:name=>name==='reduce-motion'&&reduced}},
 querySelectorAll:()=>nodes
}};
vm.createContext(sandbox);vm.runInContext(source,sandbox);
vm.runInContext('kbMove(1)',sandbox);
assert.equal(vm.runInContext('_kbIndex',sandbox),-1);
for(const reduce of [false,true,false])for(const first of [1,-1]){
 reduced=reduce;scrolls=[];
 nodes=Array.from({length:3},(_,i)=>({
  marked:false,
  classList:{remove(){nodes[i].marked=false},add(){nodes[i].marked=true}},
  scrollIntoView:options=>scrolls.push({i,...JSON.parse(JSON.stringify(options))})
 }));
 vm.runInContext('_kbIndex=-1',sandbox);
 for(const delta of [first,1,1,1,-1,-1,-1,-1]){
  const old=vm.runInContext('_kbIndex',sandbox);
  const next=old===-1?(delta>0?0:2):Math.max(0,Math.min(2,old+delta));
  vm.runInContext(`kbMove(${delta})`,sandbox);
  assert.equal(vm.runInContext('_kbIndex',sandbox),next);
  assert.deepEqual(nodes.map(n=>n.marked),nodes.map((_,i)=>i===next));
  assert.deepEqual(scrolls.at(-1),{i:next,block:'nearest',behavior:reduce?'instant':'smooth'});
 }
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(HTML_PAGE[start:end]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
