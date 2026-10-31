import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base]=process.argv.slice(2);
const browser=await launch(browserPath),cases=[];
async function enter(){
  await browser.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});
  await browser.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
}
try {
  for(const width of [1280,390,320])for(const lang of ['en','ja'])for(const dark of [false,true]){
    await browser.command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<500});
    await browser.command('Page.navigate',{url:`${base}/?view=items&lang=${lang}&theme=${dark?'dark':'light'}`});
    await browser.wait('typeof currentItems!=="undefined"&&currentItems.length>0','loaded');
    await browser.evaluate(`(async()=>{
      window.relationWrites=[];window.graphRequests=[];window.realRelationsApi=api;
      api=async(path,opts)=>{
        if(opts?.method&&!['GET','HEAD'].includes(opts.method))relationWrites.push(path);
        if(path.startsWith('/api/graph?'))graphRequests.push(path);
        return realRelationsApi(path,opts);
      };
      openDrawer((await api('/api/items/id/origin')).item);switchDrawerTab('relations');
    })()`);
    await browser.wait('!!document.querySelector("#drawer-deps [data-relation-id=record]")','links');
    const info=await browser.evaluate(`(()=>{
      const panel=document.getElementById('drawer-deps'),d=panel.querySelector('details[ontoggle]');
      return {text:panel.textContent,closed:!d.open,contained:document.getElementById('drawer-body').scrollWidth<=document.getElementById('drawer-body').clientWidth+1,noInjection:!panel.querySelector('img,script'),height:panel.querySelector('[data-relation-id=record]').getBoundingClientRect().height};
    })()`);
    assert(info.closed);assert(info.contained);assert(info.noInjection);assert(info.height>=44);
    assert(info.text.includes('Nearby'));assert(info.text.includes('Event <img onerror=bad>'));
    assert(info.text.includes(lang==='ja'?'明示された関係':'Explicit links'));
    // Other graph users may load the dashboard graph; compare only after drawer readiness.
    const beforeGraph=await browser.evaluate('graphRequests.length');
    await browser.evaluate("document.querySelector('#drawer-deps details[ontoggle] summary').focus()");await enter();
    await browser.wait('!!document.querySelector(".drawer-relation-graph svg")','graph expansion');
    assert.equal(await browser.evaluate('graphRequests.length'),beforeGraph+1);
    await browser.evaluate("setGraphLayout('tb')");
    assert(await browser.evaluate("document.querySelector('#drawer-deps details[ontoggle]').open&&!!document.querySelector('.drawer-relation-graph svg')"));
    assert.equal(await browser.evaluate('graphRequests.length'),beforeGraph+1);
    await browser.evaluate("document.querySelector('#drawer-deps [data-relation-id=record]').focus()");await enter();
    await browser.wait('drawerItem?.id==="record"&&!!document.getElementById("drawer-context-back")','related record');
    assert.equal(await browser.evaluate('new URL(location.href).searchParams.get("id")'),'record');
    assert(await browser.evaluate('document.querySelector(".drawer-context").textContent.includes("Original")'));
    assert(await browser.evaluate('document.getElementById("drawer-title").textContent.includes("Event <img onerror=bad>")'));
    await browser.evaluate('history.back()');
    await browser.wait('drawerItem?.id==="origin"','browser Back');
    await browser.evaluate('history.forward()');
    await browser.wait('drawerItem?.id==="record"&&!!document.getElementById("drawer-context-back")','browser Forward');
    await browser.evaluate("document.getElementById('drawer-context-back').focus()");await enter();
    await browser.wait('drawerItem?.id==="origin"&&!document.getElementById("drawer-tab-relations").hidden','return');
    assert.equal(await browser.evaluate('document.activeElement.getAttribute("aria-controls")'),'drawer-tab-relations');
    assert.equal(await browser.evaluate('new URL(location.href).searchParams.get("id")'),'origin');
    await browser.evaluate("drawerNavigate('missing-record')");
    await browser.wait('document.getElementById("toast-container").textContent.includes("missing-record")','missing error');
    assert.equal(await browser.evaluate('drawerItem.id'),'origin');
    assert.equal(await browser.evaluate('relationWrites.length'),0);
    cases.push({width,lang,dark,...info});
  }
  console.log(JSON.stringify({cases,noWrites:true}));
} finally {await browser.close();}
