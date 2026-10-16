(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  let locale = params.get('lang') === 'ja' || (!params.has('lang') && navigator.language.startsWith('ja')) ? 'ja' : 'en';
  const strings = {
    en: {title:'Procedures',notice:'Definition browsing only. Reading a step does not perform or complete work.',reload:'Reload definitions',list:'Definitions',flow:'Flowchart',flowNote:'Select a node to read its instruction. The numbered text below includes every transition.',steps:'Steps and transitions',exports:'Text / Mermaid / DOT',format:'Format',empty:'No procedure definitions in the configured sources.',invalid:'Invalid definition',unavailable:'Some configured sources could not be read.',loading:'Loading…',failed:'Could not load the procedure. Reload to try again.',unsupported:'This server does not support procedure browsing. Items and Planner remain available from life.txt.',start:'Start',status:'Definition status',previous:'Previous',next:'Next',record:'Open record',end:'End of definition; no work has been completed.',revision:'Template revision',large:'Large flowchart: use the complete step and transition list below.',choose:'Select a definition.'},
    ja: {title:'手順書',notice:'手順の定義を閲覧しています。読むだけでは作業の実施・完了になりません。',reload:'定義を再読み込み',list:'手順一覧',flow:'フローチャート',flowNote:'ノードを選ぶと説明に移動します。下の一覧にもすべての遷移を表示します。',steps:'ステップと遷移',exports:'テキスト / Mermaid / DOT',format:'形式',empty:'設定済みファイルに手順の定義がありません。',invalid:'定義が不正です',unavailable:'読み込めないファイルがあります。',loading:'読み込み中…',failed:'手順を読み込めませんでした。再読み込みしてください。',unsupported:'このサーバーは手順表示に未対応です。life.txtからItemsやPlannerを利用できます。',start:'開始',status:'定義の状態',previous:'前のステップ',next:'次のステップ',record:'レコードを開く',end:'定義の終端です。作業が完了したことは意味しません。',revision:'定義の改訂',large:'大きな図です。下のステップ・遷移一覧ですべてを確認できます。',choose:'手順を選択してください。'}
  };
  const t = key => strings[locale][key];
  let current = null, catalogData = null, generation = 0, credential = "";
  const feedback = text => { $('feedback').textContent = text; };
  function el(tag, text, parent, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    if (parent) parent.append(node);
    return node;
  }
  function applyLanguage() {
    document.documentElement.lang = locale;
    $('language').value = locale;
    document.querySelectorAll('[data-text]').forEach(node => node.textContent = t(node.dataset.text));
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {...options,headers:{Accept:'application/json',...(credential ? {Authorization:'Bearer '+credential} : {}),...(options.headers || {})},cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.message || (response.status === 404 && path === '/api/procedures' ? t('unsupported') : t('failed')));
      error.diagnostics = data.diagnostics;
      throw error;
    }
    return data;
  }
  function showDiagnostics(rows, parent) {
    rows.forEach(row => el('li', row.code + ': ' + row.message, parent));
  }
  function stepTarget(index) { return 'procedure-step-' + index; }
  function stepLink(parent, text, target, indices) {
    const index = indices.get(target);
    const link = el('a', text + ' → ' + target, parent);
    link.href = '#' + stepTarget(index);
    link.onclick = () => { const node = $(stepTarget(index)); if (node) node.focus(); };
  }
  function svgNode(tag, attrs, parent, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([name,value]) => node.setAttribute(name, value));
    if (text !== undefined) node.textContent = text;
    parent.append(node);
    return node;
  }
  function renderFlow(data, indices) {
    const host = $('flow'); host.replaceChildren();
    // The complete text alternative always includes all 500 supported steps.
    // Bound SVG DOM/layout work separately from the domain's graph bounds.
    if (data.steps.length > 80 || data.edges.length > 160) { el('p', t('large'), host); return; }
    const width = 520, row = 130, height = data.steps.length * row + 50;
    const svg = svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-labelledby':'diagram-title'},host);
    svgNode('title',{id:'diagram-title'},svg,t('flow'));
    data.edges.forEach((edge, edgeIndex) => {
      const from = indices.get(edge.source), to = indices.get(edge.target);
      const y1 = from * row + 75, y2 = to * row + 75;
      const lane = 365 + (edgeIndex % 8) * 16;
      const path = from === to ? `M 350 ${y1-15} H ${lane} V ${y2+15} H 350` : `M 350 ${y1} H ${lane} V ${y2} H 350`;
      svgNode('path',{d:path},svg);
      svgNode('path',{d:`M 358 ${y2-5} L 350 ${y2} L 358 ${y2+5}`},svg);
      svgNode('text',{x:lane+3,y:y1+(to > from ? 22 : -22),class:'edge-label'},svg,edge.label);
    });
    data.steps.forEach((step, index) => {
      const y = index * row + 30;
      const link = svgNode('a',{href:'#'+stepTarget(index),'aria-label':step.id+': '+step.title},svg);
      link.addEventListener('click', () => $(stepTarget(index)).focus());
      if (step.kind === 'decision') svgNode('polygon',{points:`175,${y} 350,${y+45} 175,${y+90} 0,${y+45}`},link);
      else if (step.kind === 'end') svgNode('ellipse',{cx:175,cy:y+45,rx:174,ry:44},link);
      else svgNode('rect',{x:1,y,width:348,height:90,rx:8},link);
      svgNode('text',{x:175,y:y+37,'text-anchor':'middle'},link,step.id.length > 32 ? step.id.slice(0,31)+'…' : step.id);
      const title = step.title.length > 32 ? step.title.slice(0,31)+'…' : step.title;
      svgNode('text',{x:175,y:y+60,'text-anchor':'middle'},link,title);
    });
  }
  function render(data) {
    current = data;
    $('definition').hidden = false;
    $('root-title').textContent = data.root.title;
    $('meta').textContent = `${t('status')}: ${data.root.status} · ${t('start')}: ${data.start} · ${t('revision')}: ${data.template_revision}`;
    $('root-body').textContent = data.root.body.join('\n');
    $('warnings').replaceChildren(); showDiagnostics(data.diagnostics, $('warnings'));
    const indices = new Map(data.steps.map((step,index) => [step.id,index]));
    $('steps').replaceChildren();
    data.steps.forEach((step,index) => {
      const li = el('li',undefined,$('steps')); li.id = stepTarget(index); li.tabIndex = -1;
      el('h4',step.id + ': ' + step.title,li);
      el('p',`${step.kind} · ${t('status')}: ${step.status} · parent: ${step.parent} · depth: ${step.depth} · line: ${step.line}`,li,'step-meta');
      el('div',step.body.join('\n'),li,'body');
      const previous = data.edges.filter(edge => edge.target === step.id), next = data.edges.filter(edge => edge.source === step.id);
      const prevLinks = el('div',t('previous')+': ',li,'step-links');
      previous.forEach(edge => stepLink(prevLinks,edge.label,edge.source,indices));
      const nextLinks = el('div',t('next')+': ',li,'step-links');
      next.forEach(edge => stepLink(nextLinks,edge.label,edge.target,indices));
      if (!next.length) el('p',t('end'),li);
      const record = el('a',t('record'),li); record.href = step.item_href;
    });
    renderFlow(data,indices); $('export').textContent = data.formats[$('format').value];
  }
  function renderCatalog(data) {
    catalogData = data; $('catalog').replaceChildren();
    data.procedures.forEach(row => {
      const li = el('li',undefined,$('catalog'));
      const link = el('a',row.title + ' ['+row.id+'] · '+row.source.slice(0,8) + (row.valid ? '' : ' · '+t('invalid')),li);
      link.href = row.href + '&lang='+locale;
      if (params.get('source') === row.source && params.get('id') === row.id) link.setAttribute('aria-current','page');
      link.onclick = event => {
        event.preventDefault(); if(runBusy)return; params.delete('run'); params.set('source',row.source); params.set('id',row.id);
        history.pushState(null,'','/procedures?'+params.toString()); loadDefinition(row.source,row.id);
      };
    });
  }
  async function loadDefinition(source, id) {
    invalidateRun();
    const turn = ++generation;
    current = null; $('definition').hidden = true; feedback(t('loading'));
    try {
      const data = await api('/api/procedures/'+encodeURIComponent(source)+'/'+encodeURIComponent(id));
      if (turn !== generation) return;
      if (data.schema !== 'procedure-v1' || data.mode !== 'definition') throw new Error(t('unsupported'));
      render(data); if(catalogData) renderCatalog(catalogData); feedback(''); $('root-title').focus(); if(credential)await refreshRun();
    } catch (error) {
      if (turn !== generation) return;
      feedback(error.message);
      if (error.diagnostics) feedback(error.message+' '+error.diagnostics.map(row => row.code+': '+row.message).join(' · '));
      if(credential && params.get('run'))await refreshRun();
    }
  }
  async function load() {
    invalidateRun();
    const turn = ++generation;
    current = null; $('definition').hidden = true; $('catalog').replaceChildren(); feedback(t('loading'));
    $('reload').disabled = true;
    try {
      const data = await api('/api/procedures');
      if (turn !== generation) return;
      if (data.schema !== 'procedure-catalog-v1') throw new Error(t('unsupported'));
      renderCatalog(data);
      feedback(data.failures.length ? t('unavailable') : data.procedures.length ? t('choose') : t('empty'));
      if (params.get('source') && params.has('id')) await loadDefinition(params.get('source'),params.get('id'));
    } catch (error) { if (turn === generation) feedback(error.message); }
    finally { $('reload').disabled = false; }
  }
  $('format').onchange = () => { if (current) $('export').textContent = current.formats[$('format').value]; };
  $('language').onchange = () => { locale = $('language').value; params.set('lang',locale); history.replaceState(null,'','/procedures?'+params.toString()); applyLanguage(); if(catalogData)renderCatalog(catalogData); if(current)render(current); runLabels(); if(runSnapshot)displayRun(runSnapshot); };
  $('reload').onclick = load;
  window.addEventListener('popstate', () => { const query = new URLSearchParams(location.search); if (query.toString() === params.toString()) return; Array.from(params.keys()).forEach(key=>params.delete(key)); query.forEach((value,key)=>params.set(key,value)); load(); });
  __PROCEDURE_RUN_JS__
  applyLanguage(); load();
})();
