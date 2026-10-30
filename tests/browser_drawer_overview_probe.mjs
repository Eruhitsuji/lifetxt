import assert from 'node:assert/strict';
import {launch} from './browser_revision_support.mjs';
const [browserPath, base] = process.argv.slice(2);
const browser = await launch(browserPath);
const results = [];
try {
  for (const width of [1280, 390, 320]) for (const lang of ['en', 'ja']) for (const dark of [false, true]) {
    await browser.command('Emulation.setDeviceMetricsOverride', {width, height:900, deviceScaleFactor:1, mobile:width<500});
    await browser.command('Page.navigate', {url:`${base}/?view=items&lang=${lang}&theme=${dark?'dark':'light'}`});
    await browser.wait('typeof currentItems !== "undefined" && currentItems.length > 0 && appConfig?.web?.top_clock && document.querySelector("#items button.item")', 'loaded');
    await browser.evaluate(`(async()=>{
      const item=(await api('/api/items/id/overview')).item;
      const opener=document.querySelector('#items button.item');opener.id='overview-opener';opener.focus();
      openDrawer(item);
    })()`);
    await browser.wait('workSessionView?.ready || workSessionView?.needsRefresh', 'work snapshot');
    await browser.wait("document.activeElement?.classList.contains('drawer-close-btn')", 'drawer focused');
    const info = await browser.evaluate(`(() => {
      const panel=document.getElementById('drawer-tab-overview');
      const summaries=[...panel.querySelectorAll('summary')].map(x=>x.textContent);
      const fields=panel.querySelector('.drawer-fields').textContent;
      const raw=panel.querySelector('.drawer-technical').textContent;
      return {summaries, fields, raw, text:panel.textContent, bodyFirst:panel.querySelector('.markdown, .drawer-plain-body').compareDocumentPosition(panel.querySelector('.drawer-fields')) & Node.DOCUMENT_POSITION_FOLLOWING,
        uploadClosed:!document.getElementById('attachment-upload-file').closest('details').open,
        workClosed:!workSessionView.disclosure.open,
        deleteSeparated:!!document.querySelector('#drawer-overflow .drawer-danger-actions #drawer-delete-btn'),
        pageContained:document.documentElement.scrollWidth<=innerWidth,
        title:document.getElementById('drawer-title').textContent};
    })()`);
    await browser.evaluate("switchDrawerTab('timeline')");
    assert(await browser.evaluate("getComputedStyle(document.getElementById('drawer-tab-overview')).display==='none'"));
    await browser.evaluate("switchDrawerTab('overview')");
    assert(info.bodyFirst);assert(info.uploadClosed);assert(info.workClosed);assert(info.deleteSeparated);assert(info.pageContained);
    assert(info.title.includes('Done'));assert(info.raw.includes('custom:Done'));assert(info.raw.includes('2026-10-30T20:10:17Z'));
    assert(info.fields.includes(lang==='ja'?'期限':'Due'));assert(info.fields.includes(lang==='ja'?'実施予定':'Scheduled'));
    assert(info.fields.includes('2026-10-31 05:10:17 JST'));
    assert(info.text.includes(lang==='ja'?'作業セッションは停止中':'No work session is running'));
    assert(info.text.includes(lang==='ja'?'見積時間を超過':'Over estimate'));
    // Native keyboard disclosure, not a synthetic click or arbitrary state change.
    await browser.evaluate("document.querySelector('.drawer-technical summary').focus()");
    await browser.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});
    await browser.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    await browser.wait("document.querySelector('.drawer-technical').open", "keyboard disclosure open");
    const contained=await browser.evaluate(`(() => {
      document.querySelectorAll('#drawer-tab-overview details').forEach(x=>x.open=true);
      const body=document.getElementById('drawer-body');
      body.scrollTop=body.scrollHeight;
      return body.scrollWidth <= body.clientWidth + 1 && body.scrollTop > 0;
    })()`);assert(contained);
    // Reopening disposes the old controllers; disabled/finished states are explicit.
    await browser.evaluate("openDrawer({...drawerItem,status:'[x]'},'none')");
    assert(await browser.evaluate("!document.getElementById('drawer-done-btn') && !document.getElementById('drawer-done-date-btn')"));
    await browser.evaluate("openDrawer({...drawerItem,editable:false},'none')");
    assert(await browser.evaluate("!!document.querySelector('.drawer-readonly-note') && document.getElementById('drawer-edit-btn').disabled"));
    await browser.evaluate('closeDrawer()');
    await browser.wait("!document.getElementById('detail-drawer').classList.contains('open') && document.activeElement.id === 'overview-opener'", "focus restored");
    results.push({width,lang,dark,...info});
  }
  // A running session is test-only API evidence; no source/timer writes occur.
  await browser.evaluate(`(async()=>{
    window.overviewApi=api;
    const rev=await api('/api/revision'), health=await api('/api/health');
    const item=(await api('/api/items/id/overview')).item;
    api=async(path,opts)=>path==='/api/work-session'?{running:true,id:'overview',item_revision:rev.revision,timer_revision:'a'.repeat(64),file:health.writable_path}:overviewApi(path,opts);
    openDrawer(item,'none');
  })()`);
  await browser.wait('workSessionView?.ready', 'running snapshot');
  assert(await browser.evaluate('workSessionView.ownSession && workSessionView.disclosure.open && !workSessionView.stop.disabled'));
  await browser.evaluate(`(async()=>{
    const rev=await overviewApi('/api/revision'), health=await overviewApi('/api/health');
    api=async(path,opts)=>path==='/api/work-session'?{running:true,id:'other',item_revision:rev.revision,timer_revision:'a'.repeat(64),file:health.writable_path}:overviewApi(path,opts);
    openDrawer(drawerItem,'none');
  })()`);
  await browser.wait('workSessionView?.ready', 'other running snapshot');
  assert(await browser.evaluate('workSessionView.running && !workSessionView.ownSession && !workSessionView.disclosure.open && workSessionView.start.disabled'));
  await browser.evaluate("api=async(path,opts)=>path==='/api/work-session'?Promise.reject(Error('fixture unavailable')):overviewApi(path,opts);openDrawer(drawerItem,'none')");
  await browser.wait('workSessionView?.needsRefresh', 'unavailable');
  assert(await browser.evaluate("workSessionView.feedback.textContent.length>0 && !workSessionView.disclosure.contains(workSessionView.feedback)"));
  console.log(JSON.stringify({cases:results, running:true, unavailable:true}));
} finally {await browser.close();}
