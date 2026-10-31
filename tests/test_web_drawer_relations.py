"""Relations presentation, context navigation and response isolation (#1486)."""

import json
import shutil
import subprocess
import unittest

from tests.test_web_drawer_edit_js import _extract_function
from tests.test_web_native_timeline_visual import _extract_script


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DrawerRelationsTests(unittest.TestCase):
    def test_relations_and_navigation_contract(self):
        source = _extract_script()
        names = [
            "escapeHtml",
            "jsLiteral",
            "drawerText",
            "_drawerIdFor",
            "drawerRelationLabel",
            "drawerRelationRow",
            "renderDrawerRelations",
            "loadDependencyLinks",
            "drawerContextHtml",
            "drawerReturnToContext",
            "drawerNavigate",
            "updateUrlFromControls",
        ]
        functions = "\n".join(
            _extract_function(
                source,
                (
                    "async function "
                    if name
                    in {
                        "loadDependencyLinks",
                        "drawerReturnToContext",
                        "drawerNavigate",
                    }
                    else "function "
                )
                + name
                + "(",
            )
            for name in names
        )
        run = subprocess.run(
            [
                "node",
                "-e",
                functions
                + r"""
let lang='ja'; const currentLanguage=()=>lang,t=x=>x;
const appConfig={ids:{key:'id'}},STATUS_LABEL={'[x]':'Done'};
let drawerItem={id:'root',title:'Original'},drawerEditing=false,_drawerNavigationToken=0;
let container={innerHTML:'',dataset:{}},pending=[],opens=[],toasts=[];
const location={href:'http://fixture/?id=root',pathname:'/'};
const query=()=>new URLSearchParams(new URL(location.href).search);
const history={state:null,replaceState(state){this.state=state;}};
const document={getElementById:()=>container,querySelector:()=>({focus(){}})};
const switchDrawerTab=()=>{};
const api=path=>new Promise((resolve,reject)=>pending.push({path,resolve,reject}));
const showToast=text=>toasts.push(text);
const openDrawer=(item,mode,context)=>{drawerItem=item;opens.push({item,mode,context});++_drawerNavigationToken;};
const links={records:[
 {source_id:'root',target_id:'child',relation:'parent',target_title:'<img onerror=x>',target_type:'T',target_status:'[x]',status:'ok'},
 {source_id:'incoming',target_id:'root',relation:'depends_on',source_title:'Incoming',source_type:'N',status:'ok'},
 {source_id:'root',target_id:'missing',relation:'constructor',status:'missing'},
 {source_id:'root',target_id:'ambig',relation:'related',status:'ambiguous'},
]};
const thread={relations:{successors:[{id:'successor',title:'Successor',kind:'N'}]},explicit:{truncated:true},consistency:{warnings:[{relation:'<img>',evidence:{successor_id:'s',predecessor_id:'p'}}],truncated:true},derived:{related:[{relation:'same_day',target_id:'nearby',target:{title:'Nearby',kind:'J',status:'[x]'},source_field:'due',target_field:'on',days:0}]}};
const before=JSON.stringify({links,thread});
const result={ja:renderDrawerRelations('root',links,thread),parent:drawerRelationLabel('parent'),child:drawerRelationLabel('parent',true),blocked:drawerRelationLabel('blocks',true),unknown:drawerRelationLabel('constructor')};
lang='en';result.en=renderDrawerRelations('root',links,thread);lang='ja';
result.unchanged=before===JSON.stringify({links,thread});
result.noIdRow=drawerRelationRow("候補",null,{title:"No ID"});
result.empty=renderDrawerRelations('root',{records:[]},{relations:{},derived:{related:[]}});
result.errors=renderDrawerRelations('root',null,null,'<bad links>','<bad thread>');
history.state={drawerContext:{id:'root',title:'<img>',target:'other'}};
result.context=drawerContextHtml({id:'other'});result.noContext=drawerContextHtml({id:'root'});
const state=history.state;updateUrlFromControls();result.normalizationPreserved=history.state===state;history.state=null;
(async()=>{
 let load=loadDependencyLinks(drawerItem);pending[0].resolve(links);pending[1].reject(Error('thread failed'));await load;
 result.partial=container.innerHTML;result.requests=pending.map(x=>x.path);pending=[];
 load=loadDependencyLinks(drawerItem);const old=container;container={innerHTML:'new mounted panel',dataset:{}};
 pending[0].resolve(links);pending[1].resolve(thread);await load;result.remount=container.innerHTML;pending=[];
 load=loadDependencyLinks(drawerItem);drawerItem={id:'other'};
 pending[0].resolve(links);pending[1].resolve(thread);await load;result.otherItem=container.innerHTML;pending=[];
 drawerItem={id:'root',title:'Original'};
 const first=drawerNavigate('one'),second=drawerNavigate('two');pending[1].resolve({item:{id:'two',title:'Two'}});await second;
 pending[0].resolve({item:{id:'one'}});await first;result.opens=opens.slice();pending=[];
 const fail=drawerNavigate('missing');pending[0].reject(Error('not found'));await fail;result.failurePreserved=drawerItem.id==='two';result.toasts=toasts;pending=[];
 const stale=drawerNavigate('late');location.href='http://fixture/?id=back';pending[0].resolve({item:{id:'late'}});await stale;result.urlGuard=opens.length===1;pending=[];
 const closed=drawerNavigate('closed');drawerItem=null;++_drawerNavigationToken;pending[0].resolve({item:{id:'closed'}});await closed;result.closedGuard=opens.length===1;
 pending=[];drawerItem={id:'two',title:'Two'};
 history.state={drawerContext:{id:'root',title:'Original',target:'two'}};
 const returning=drawerReturnToContext();pending[0].resolve({item:{id:'root',title:'Fresh original'}});await returning;
 result.returned=opens.at(-1);pending=[];
 const idless=loadDependencyLinks({title:'No ID'});await idless;result.idless=container.textContent;result.idlessRequests=pending.length;
 console.log(JSON.stringify(result));
})();
""",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(run.stdout)
        self.assertEqual("親", result["parent"])
        self.assertEqual("子", result["child"])
        self.assertEqual("妨げている項目", result["blocked"])
        self.assertEqual("constructor", result["unknown"])
        for value in [
            "明示された関係",
            "日付が近い候補",
            "Nearby",
            "Incoming",
            "constructor",
            "取得上限",
            "整合性",
            "ambiguous",
        ]:
            self.assertIn(value, result["ja"])
        self.assertIn("Explicit links", result["en"])
        self.assertIn("&lt;img onerror=x&gt;", result["ja"])
        self.assertNotIn("<img", result["ja"])
        self.assertNotIn('data-relation-id="missing"', result["ja"])
        self.assertNotIn('data-relation-id="ambig"', result["ja"])
        self.assertIn("ありません", result["empty"])
        self.assertIn("IDがない", result["noIdRow"])
        self.assertIn("&lt;bad links&gt;", result["errors"])
        self.assertIn("&lt;bad thread&gt;", result["errors"])
        self.assertIn("&lt;img&gt;", result["context"])
        self.assertEqual("", result["noContext"])
        self.assertTrue(result["normalizationPreserved"])
        self.assertTrue(result["unchanged"])
        self.assertIn("Incoming", result["partial"])
        self.assertIn("thread failed", result["partial"])
        self.assertEqual(2, len(result["requests"]))  # Graph is loaded on demand.
        self.assertEqual("new mounted panel", result["remount"])
        self.assertEqual("new mounted panel", result["otherItem"])
        self.assertEqual(["two"], [x["item"]["id"] for x in result["opens"]])
        self.assertEqual("root", result["opens"][0]["context"]["id"])
        self.assertTrue(result["failurePreserved"])
        self.assertTrue(result["toasts"])
        self.assertTrue(result["urlGuard"])
        self.assertTrue(result["closedGuard"])
        self.assertEqual("Fresh original", result["returned"]["item"]["title"])
        self.assertIsNone(result["returned"]["context"])
        self.assertEqual(0, result["idlessRequests"])
        self.assertIn("IDがない", result["idless"])
