// Execute actual client handlers with a small DOM/HTTP boundary, not a second parser.
import fs from 'node:fs';
import vm from 'node:vm';
const inputs=JSON.parse(process.argv[2]);
const read=name=>fs.readFileSync(new URL('../lifetxt/'+name,import.meta.url),'utf8');
const web=read('web_assets_js_08.js');
const quick=web.slice(web.indexOf('async function quickAddLine()'),web.indexOf('let captureSubmitPending'));
const capture=web.slice(web.indexOf('let captureSubmitPending'),web.indexOf('function initializeCaptureMode'));
const focusSource=read('web_assets_js_17.js');
const focus=focusSource.slice(focusSource.indexOf('async function focusQuickAdd()'),focusSource.indexOf('async function ',focusSource.indexOf('async function focusQuickAdd()')+20));
const plannerSource=read('web_planner.js');
const plannerStart=plannerSource.indexOf("$('capture-form').onsubmit=")+"$('capture-form').onsubmit=".length;
const planner=plannerSource.slice(plannerStart,plannerSource.indexOf('finally{pending=false;b.disabled=false}}',plannerStart)+'finally{pending=false;b.disabled=false}}'.length);
const commandsSource=read('web_assets_js_09.js');
const addStart=commandsSource.indexOf('add: async (arg) => {')+'add: '.length;
const commandAdd=commandsSource.slice(addStart,commandsSource.indexOf('},\n      delete:',addStart)+1);
const actions=[['quick',quick,'quickAddLine()','quick-line'],['capture',capture,'submitCapture()','capture-text'],['planner',`const submit=${planner};`,'submit({preventDefault(){}})','capture-text'],['focus',focus,'focusQuickAdd()','focus-quick-title'],['command',`const submit=${commandAdd};`,'submit(input.value)','command']];
const output=[];
for(const [surface,source,invoke,id] of actions){
 const elements=new Map();
 const element=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',className:'',disabled:false,focused:0,classList:{add(){},remove(){},toggle(){}},setAttribute(){},removeAttribute(){},focus(){this.focused++},querySelector(){return element('submit')},close(){}});return elements.get(id)};
 const input=element(id);let calls=[];let fail=false;
 const t=surface==='planner'?{captured:'Captured',captureError:'Failed: '}:x=>x;
 const context=vm.createContext({document:{getElementById:element},$:element,input,t,appConfig:{ids:{key:'uid'}},pending:false,writable:true,_fmtDate:()=> '2026-10-02',Date,JSON,console,load:async()=>{},loadFocus:async()=>{},toggleQuickAdd(){},showToast(){},refreshAll:async()=>{},actionableErrorText:e=>e.message,api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(fail)throw new Error('Invalid record');return {item:{title:'Saved',details:{uid:['test-id']}}}}});
 vm.runInContext(source,context);
 for(const text of inputs){input.value=text;calls=[];await vm.runInContext(invoke,context);output.push({surface,text,calls,value:input.value});}
 fail=true;input.value='[ ] T "unterminated';calls=[];try{await vm.runInContext(invoke,context)}catch(e){if(surface!=='command')throw e}output.push({surface,text:input.value,calls,failure:true,value:input.value});
}
process.stdout.write(JSON.stringify(output));
