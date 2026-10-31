import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath,base]=process.argv.slice(2);
const browser=await launch(browserPath),cases=[];
try {
  for(const width of [1280,390,320])for(const lang of ['en','ja'])for(const dark of [false,true]){
    await browser.command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<500});
    await browser.command('Page.navigate',{url:`${base}/?view=items&lang=${lang}&theme=${dark?'dark':'light'}`});
    await browser.wait('typeof currentItems!=="undefined"&&currentItems.length>0&&appConfig?.web?.top_clock','loaded');
    await browser.evaluate(`(async()=>{
      window.historyQueries=[];window.historyWrites=[];window.realHistoryApi=api;
      window.historyFixture={complete:false,bounds:{returned_events:1,total_valid_events:4,truncated:true},limitations:['item_history_incomplete','event_limit_truncated'],invalid_events:[{code:'invalid_fixture'}],diagnostics:[{code:'fixture_warning',message:'<img onerror=bad>'}],events:[{record_kind:'item_event',record_id:'fixture-event',at:'2026-10-30T20:10:17Z',event:'completed',transaction:'fixture-transaction',source_revision:'fixture-revision',sequence:2,payload:{before_status:'[ ]',after_status:'[x]',item_title:'Done'},valid:true}]};
      api=async(path,opts)=>{
        if(opts?.method&&!['GET','HEAD'].includes(opts.method))historyWrites.push(path);
        if(path.startsWith('/api/native-timeline/')){historyQueries.push(path);if(window.failHistory)throw Error('<img> fixture failure');return JSON.parse(JSON.stringify(historyFixture));}
        return realHistoryApi(path,opts);
      };
      const item=(await api('/api/items/id/history')).item;openDrawer(item);switchDrawerTab('timeline');
    })()`);
    await browser.wait('!!document.querySelector(".nt-event")&&document.activeElement?.classList.contains("drawer-close-btn")','history');
    let info=await browser.evaluate(`(()=>{
      const panel=document.getElementById('drawer-native-timeline');
      return {text:panel.textContent,day:panel.querySelector('.nt-day-heading').textContent,closed:!document.getElementById('nt-advanced').open,contained:document.getElementById('drawer-body').scrollWidth<=document.getElementById('drawer-body').clientWidth+1,noInjection:!panel.querySelector('img,script')};
    })()`);
    assert(info.closed);assert(info.contained);assert(info.noInjection);assert.equal(info.day,'2026-10-31');
    assert(info.text.includes('2026-10-31 05:10:17 JST'));assert(info.text.includes('fixture-transaction'));
    assert(info.text.includes(lang==='ja'?'確認可能な履歴は一部':'Partial / limited history'));
    await browser.evaluate("document.querySelector('#nt-advanced summary').focus()");
    await browser.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});
    await browser.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    await browser.wait('document.getElementById("nt-advanced").open','native keyboard expansion');
    const layout=await browser.evaluate(`(()=>{
      const fields=document.querySelector('.nt-advanced-fields');
      const summary=document.querySelector('#nt-advanced > summary');
      const filters=document.querySelector('#drawer-native-timeline .nt-filters');
      return {display:getComputedStyle(fields).display, columns:getComputedStyle(fields).gridTemplateColumns.split(' ').length,
        filters:getComputedStyle(filters).display, height:summary.getBoundingClientRect().height};
    })()`);
    assert.equal(layout.display,'grid');assert.equal(layout.filters,'grid');
    assert.equal(layout.columns,width<=600?1:2);assert(layout.height>=44);
    await browser.evaluate("document.getElementById('nt-filter-since').value='2026-10-30T00:00:00+09:00';document.getElementById('nt-filter-event').value='completed';document.getElementById('nt-filter-limit').value='2';applyNativeTimelineFilters()");
    await browser.wait('!!document.querySelector(".nt-event")','filtered response');
    const q=await browser.evaluate('historyQueries.at(-1)');
    const params=new URL('http://fixture'+q).searchParams;
    assert.equal(params.get('event'),'completed');assert.equal(params.get('limit'),'2');assert.equal(params.get('since'),'2026-10-30T00:00:00+09:00');
    assert(await browser.evaluate("document.getElementById('nt-advanced').open"));
    await browser.evaluate("setNativeTimelineRange('custom')");
    assert.equal(await browser.evaluate('document.activeElement.id'),'nt-filter-since');
    await browser.evaluate('clearNativeTimelineFilters()');
    await browser.wait('!!document.querySelector(".nt-event")','clear');
    assert.equal(await browser.evaluate('historyQueries.at(-1)'),'/api/native-timeline/history');
    await browser.evaluate('failHistory=true;applyNativeTimelineFilters()');
    await browser.wait('!!document.querySelector("#drawer-native-timeline [role=alert]")','failed read');
    assert(await browser.evaluate("!document.querySelector('#drawer-native-timeline img')&&!!document.getElementById('nt-filter-event')"));
    await browser.evaluate('failHistory=false;historyFixture={...historyFixture,complete:true,events:[],invalid_events:[],diagnostics:[],limitations:[],bounds:{returned_events:0,total_valid_events:0,truncated:false}};applyNativeTimelineFilters()');
    await browser.wait('!!document.querySelector(".nt-coverage-complete")','empty complete');
    assert(await browser.evaluate('historyWrites.length===0'));
    cases.push({width,lang,dark,...info});
  }
  console.log(JSON.stringify({cases,noWrites:true}));
}finally{await browser.close();}
