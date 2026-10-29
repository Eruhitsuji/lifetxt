"""Source-safe, keyboard-accessible Dashboard attention actions (#1463)."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE
from tests.test_web_drawer_edit_js import _extract_function


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DashboardAttentionTests(unittest.TestCase):
    def test_attention_actions_preserve_identity_and_rendering(self):
        start = HTML_PAGE.index("    function _dashItemRow(")
        end = HTML_PAGE.index("    function dashNavigate(", start)
        source = _extract_function(HTML_PAGE, "function _drawerIdFor(")
        harness = r"""
const assert = require('node:assert/strict');
function escapeHtml(s) {return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
const appConfig={ids:{key:'uuid'}};
const STATUS_CLASS={'[ ]':'status-open'}, STATUS_ICON={'[ ]':'○'};
function buildDueRelLabel(item){return item.dueLabel || '';}
function _fmtDate(){return '2030-01-01';}
function itemDueSoonClass(item){return item.overdue?'overdue':'';}
function dashboardLimit(card,fallback){assert.equal(card,'needs_attention');assert.equal(fallback,7);return 6;}
const base={line:7,type:'T',status:'[ ]',details:{},editable:true};
const openItems=[
  {...base,source:'a.txt',id:'canonical "<&/id',title:'<img src=x onerror=oops>',overdue:true,dueLabel:'<span>Overdue</span>'},
  {...base,source:'b.txt',title:'IDなしB',overdue:true},
  {...base,source:'c.txt',title:'Configured ID',details:{uuid:['custom-id'],id:['wrong-key']},overdue:true},
  {...base,source:'d.txt',title:'Read only',editable:false,generated:true,overdue:true,details:{id:['not-configured']}},
];
let blockedItems=[
  openItems[0], // same line/source as overdue: deduplicate once
  {...base,source:'e.txt',id:'blocked-e',title:'Blocked E'},
  {...base,source:'f.txt',id:'blocked-f',title:'Blocked F'},
  {...base,source:'g.txt',id:'hidden',title:'Hidden by limit'},
];
const requests=[],ids=[],opened=[],selected=[];
function openItemByLine(){throw Error('ambiguous line-only lookup');}
function openItemById(id){ids.push(id);}
function openDrawer(item){opened.push(item);}
function selectItem(item){selected.push(item);}
async function api(url){
  requests.push(url);
  if(url==='/api/items?open_only=true')return {items:openItems};
  if(url==='/api/items?blocked=true&open_only=true')return {items:blockedItems};
  return {};
}
let rendered='',buttons=[];
const attentionEl={
  set innerHTML(html){
    rendered=html;
    buttons=[...html.matchAll(/<button type="button" class="dash-row-title review-click" data-dash-attention-index="(\d+)">/g)].map(match=>({
      dataset:{dashAttentionIndex:match[1]}, handlers:[],
      addEventListener(type,handler){this.handlers.push({type,handler});}
    }));
  },
  querySelectorAll(selector){assert.equal(selector,'[data-dash-attention-index]');return buttons;}
};
const document={getElementById(id){return id==='dash-overdue'?attentionEl:null;},querySelector(){return null;}};
(async()=>{
  await loadDashboard();
  assert.equal(requests.length,5);
  assert.equal(buttons.length,6); // seven distinct rows, configured limit six
  assert.ok(rendered.includes('View all 7'));
  assert.ok(!rendered.includes('Hidden by limit'));
  assert.ok(!rendered.includes('openItemByLine'));
  assert.ok(!rendered.includes('<img'));
  assert.ok(rendered.includes('&lt;img src=x onerror=oops&gt;'));
  assert.ok(rendered.includes('<span>Overdue</span>'));
  assert.equal((rendered.match(/IDなしB/g)||[]).length,1);
  assert.ok(rendered.indexOf('Configured ID')<rendered.indexOf('Read only'));
  assert.ok(rendered.indexOf('Read only')<rendered.indexOf('Blocked E'));
  for(const button of buttons){
    assert.equal(button.handlers.length,1);
    assert.equal(button.handlers[0].type,'click');
    button.handlers[0].handler();
  }
  assert.deepEqual(ids,['canonical "<&/id','custom-id','blocked-e','blocked-f']);
  assert.deepEqual(opened.map(item=>[item.source,item.line]),[['b.txt',7],['d.txt',7]]);
  assert.equal(selected[0],opened[0]);assert.equal(selected[1],opened[1]);
  assert.equal(opened[1].editable,false);assert.equal(opened[1].generated,true);
  assert.deepEqual(opened[1].details,{id:['not-configured']});
  assert.equal(requests.length,5); // opening ID-less rows makes no line-only API call
  openItems[1]={...base,source:'updated.txt',title:'Reloaded',overdue:true};
  await loadDashboard();
  assert.ok(buttons.every(button=>button.handlers.length===1));
  buttons[1].handlers[0].handler();
  assert.equal(opened.at(-1).source,'updated.txt');
  openItems.length=0;blockedItems=[];
  await loadDashboard();
  assert.equal(buttons.length,0);
  assert.ok(rendered.includes('Nothing overdue or blocked.'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(
            ["node", "-e", source + HTML_PAGE[start:end] + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
