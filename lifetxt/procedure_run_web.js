  const runStrings = {
    en: {runTitle:'Procedure run (explicit operations)',token:'Web API token',signIn:'Sign in',signOut:'Sign out',shared:'This token represents one shared operator. People sharing it share run ownership.',runReload:'Reload run snapshot',newRun:'Prepare a new run',savedRuns:'Existing runs',runNotice:'Run state is separate from this definition. No external work is executed.',not_started:'Not started',active:'Active',paused:'Paused',completed:'Completed',abandoned:'Abandoned',next:'Next',choose:'Choose',pause:'Pause',resume:'Resume',finish:'Finish',abandon:'Abandon',startRun:'Start run',blocked:'Template changed/unavailable. Only pause or abandon may remain available.',confirmLoop:'This definition contains a loop. Start with the fixed traversal and visit limits?',confirmAbandon:'Abandon this run? This retains its evidence and does not undo external work.',reloadRequired:'Operation refused or outcome uncertain. Check the original request receipt, then explicitly reload. No operation was retried.',receipt:'Check original request',committed:'Original request committed',notFound:'No committed receipt found. This does not authorize replay. Reload and review before any new action.',readOnly:'Run controls are read-only',sequence:'Sequence',currentStep:'Current step',loadingRun:'Loading run snapshot…',signedOut:'Signed out. Token cleared.'},
    ja: {runTitle:'手順の実施（明示操作）',token:'Web APIトークン',signIn:'サインイン',signOut:'サインアウト',shared:'このトークンは共有の実施者を表します。同じトークンの利用者は同じrunを操作できます。',runReload:'runの状態を再読み込み',newRun:'新しいrunを準備',savedRuns:'既存のrun',runNotice:'実施状況は定義と別に記録します。外部作業を自動実行しません。',not_started:'未開始',active:'実施中',paused:'中断中',completed:'完了',abandoned:'打切り',next:'次へ',choose:'選択',pause:'中断',resume:'再開',finish:'完了を記録',abandon:'打ち切る',startRun:'runを開始',blocked:'定義が変更されたか読めません。中断・打切りのみ可能な場合があります。',confirmLoop:'この定義にはループがあります。遷移数・訪問数の上限を確認して開始しますか？',confirmAbandon:'このrunを打ち切りますか？ 証跡を残し、外部作業は巻き戻しません。',reloadRequired:'操作が拒否されたか結果が不確定です。元の要求の記録を確認し、明示的に再読み込みしてください。操作の自動再送はしていません。',receipt:'元の要求を確認',committed:'元の要求は記録されています',notFound:'確定済みの記録が見つかりません。再送の許可ではありません。状態を再読み込みして判断してください。',readOnly:'runは閲覧のみです',sequence:'記録番号',currentStep:'現在のステップ',loadingRun:'runの状態を読み込み中…',signedOut:'サインアウトしました。トークンを消去しました。'}
  };
  const rt = key => runStrings[locale][key] || key;
  let runSnapshot = null, runGeneration = 0, runBusy = false, pendingRequest = null;
  function runLabels() {
    document.querySelectorAll('[data-run-text]').forEach(node => node.textContent = rt(node.dataset.runText));
  }
  function runQuery(runId, requestId, selection) {
    const query = new URLSearchParams({source:selection?.source || params.get('source') || '',root_id:selection?.root_id || params.get('id') || ''});
    if (runId) query.set('run_id', runId);
    if (requestId) query.set('request_id', requestId);
    return '/api/procedure-runs?'+query.toString();
  }
  function runUrl(id) {
    if (id) params.set('run',id); else params.delete('run');
    history.replaceState(null,'','/procedures?'+params.toString());
  }
  function invalidateRun() {
    ++runGeneration; runSnapshot = null; $('run-actions').replaceChildren(); $('run-state').textContent = '';
    $('run-body').textContent = ''; $('run-picker').replaceChildren();
  }
  function setRunBusy(value) {
    runBusy = value;
    ['run-panel','operator-login'].forEach(id => $(id).querySelectorAll('button,input,select').forEach(node => node.disabled = value));
    $('reload').disabled = value; $('language').disabled = value;
  }
  function displayRun(data) {
    runSnapshot = data; $('run-panel').hidden = false;
    $('run-feedback').textContent = data.blocked ? rt('blocked') : data.read_only_reason ? rt('readOnly')+' · '+data.read_only_reason : '';
    $('run-state').textContent = [rt(data.status), 'run: '+(data.run_id || '—'),rt('currentStep')+': '+data.step,rt('sequence')+': '+data.sequence].join(' · ');
    $('run-body').textContent = data.instruction ? [data.instruction.title,...data.instruction.body].join('\n') : '';
    $('run-picker').replaceChildren();
    const empty = el('option',rt('newRun'),$('run-picker')); empty.value = '';
    data.runs.forEach(row => { const option = el('option',row.run_id+' · '+rt(row.status)+' · '+row.step,$('run-picker')); option.value = row.run_id; });
    $('run-picker').value = data.run_id || '';
    $('run-actions').replaceChildren();
    if (!pendingRequest) data.actions.forEach(action => {
      const button = el('button',action.operation === 'start' ? rt('startRun') : rt(action.operation)+(action.choice ? ': '+action.choice : ''),$('run-actions'));
      button.type = 'button'; button.dataset.operation = action.operation;
      if (action.choice) button.dataset.choice = action.choice;
      button.onclick = () => submitRun(data,action);
    });
  }
  async function refreshRun(runId = params.get('run')) {
    if (!credential || !params.get('source') || !params.get('id') || runBusy) return;
    invalidateRun(); const activeTurn = runGeneration;
    $('run-panel').hidden = false; $('run-feedback').textContent = rt('loadingRun');
    try {
      const data = await api(runQuery(runId));
      if (activeTurn !== runGeneration) return;
      if (data.schema !== 'procedure-run-web-v1') throw new Error(t('unsupported'));
      displayRun(data); runUrl(data.run_id); $("run-state").focus();
    } catch (error) {
      if (activeTurn !== runGeneration) return;
      invalidateRun(); $('run-feedback').textContent = error.message;
    }
  }
  async function submitRun(snapshot, action) {
    if (runBusy || pendingRequest || runSnapshot !== snapshot) return;
    if (action.operation === 'start' && action.requires_loop_confirmation && !confirm(rt('confirmLoop'))) return;
    if (action.operation === 'abandon' && !confirm(rt('confirmAbandon'))) return;
    // Freeze what was displayed before yielding; no asynchronous auto-refresh here.
    const requestId = crypto.randomUUID ? crypto.randomUUID() : 'req-'+Date.now()+'-'+Math.random().toString(16).slice(2);
    const body = {source:snapshot.source,root_id:snapshot.root_id,operation:action.operation,request_id:requestId,template_revision:snapshot.template_revision,log_revision:snapshot.log_revision,step:snapshot.step,sequence:snapshot.sequence};
    if (action.operation === 'start') body.allow_loops = Boolean(action.requires_loop_confirmation);
    else body.run_id = snapshot.run_id;
    if (action.choice) body.choice = action.choice;
    pendingRequest = {requestId,runId:snapshot.run_id,source:snapshot.source,root_id:snapshot.root_id};
    setRunBusy(true); ++runGeneration;
    try {
      const data = await api('/api/procedure-runs',{method:'POST',headers:{'Content-Type':'application/json','If-Match':'"'+snapshot.source_revision+'"',[snapshot.client_time_header]:new Date().toISOString()},body:JSON.stringify(body)});
      if(data.schema !== 'procedure-run-web-v1' || data.source !== snapshot.source || data.root_id !== snapshot.root_id || data.receipt?.request_id !== requestId || !Array.isArray(data.runs) || !Array.isArray(data.actions))throw new Error(t('failed'));
      pendingRequest = null;
      if(params.get('source') === snapshot.source && params.get('id') === snapshot.root_id && credential){displayRun(data);runUrl(data.run_id);$('run-state').focus();}
    } catch (error) {
      invalidateRun(); $('run-feedback').textContent = rt('reloadRequired')+' '+error.message;
      $('run-receipt').hidden = false;
    } finally { setRunBusy(false); }
  }
  $('operator-login').onsubmit = async event => {
    event.preventDefault(); if(runBusy)return;
    credential = $('operator-token').value; $('operator-token').value = '';
    invalidateRun();
    try { await load(); if(credential) await refreshRun(); }
    catch (error) { $('run-feedback').textContent = error.message; }
  };
  $('operator-signout').onclick = () => {
    if(runBusy)return;
    credential = ''; $('operator-token').value = ''; pendingRequest = null;
    invalidateRun(); $('run-panel').hidden = true; $('run-receipt').hidden = true;
    feedback(rt('signedOut'));
  };
  $('run-reload').onclick = () => { if(!runBusy)refreshRun(); };
  $('run-new').onclick = () => { if(!runBusy && !pendingRequest){runUrl(null);refreshRun(null);} };
  $('run-picker').onchange = () => { if(!runBusy && !pendingRequest){runUrl($('run-picker').value);refreshRun();} };
  $('run-receipt').onclick = async () => {
    if(runBusy || !pendingRequest || !credential)return;
    const original = pendingRequest; setRunBusy(true);
    try {
      const data = await api(runQuery(original.runId,original.requestId,original));
      const found = data.schema === 'procedure-run-web-v1' && data.receipt?.request_id === original.requestId && data.source === original.source && data.root_id === original.root_id && Array.isArray(data.runs) && Array.isArray(data.actions);
      const absent = data.schema === 'procedure-run-web-v1' && data.outcome === 'not_found' && data.receipt === null;
      if(!found && !absent)throw new Error(t('failed'));
      pendingRequest = null; $('run-receipt').hidden = true;
      if(data.receipt){ if(params.get('source') === original.source && params.get('id') === original.root_id){displayRun(data);runUrl(data.run_id);} $('run-feedback').textContent = rt('committed')+': '+data.receipt.event+' · '+data.receipt.sequence; }
      else { invalidateRun(); $('run-feedback').textContent = rt('notFound'); }
    } catch(error){ $('run-feedback').textContent = error.message+' '+rt('reloadRequired'); }
    finally {setRunBusy(false);}
  };
  window.addEventListener('pagehide', () => {credential='';$('operator-token').value='';invalidateRun();$('run-panel').hidden=true;});
  runLabels();
