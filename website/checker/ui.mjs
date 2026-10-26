import { MAX_BYTES, COLD_MS, WARM_MS } from './limits.mjs';
const copy = document.documentElement.lang === 'ja' ? {
  idle:'チェックを押すとランタイムを読み込みます。',
  ready:'ランタイムは読み込み済みです。チェックを押すと再検査します。',
  busy:'読み込み・チェック中… 初回は約14MBを取得するため、接続速度によって時間がかかります。',
  checking:'チェック中…',
  cancelled:'入力・結果・ランタイムを消去しました。',
  timeout:'時間切れです。入力は保持しています。接続を確認し、チェックを押して再試行してください。',
  failed:'実行に失敗しました。入力は保持しています。接続を確認し、チェックを押して再試行してください。',
  oversized:'上限候補16,384 UTF-8 bytesを超えています。入力を短くしてください。',
  finished:'文法・項目チェックが完了しました。CLI全検査とは異なります。',
  valid:'エラーなし', invalid:'エラーまたは未対応のFormat版',
  count:'診断総数', shown:'表示数', items:'項目数', unsupported:'未対応のFormat版です。',
  line:'行', column:'列', hint:'ヒント', error:'エラー', warning:'警告', info:'情報',
  bytes:'UTF-8 bytes',
} : {
  idle:'Choose Check to load the runtime.',
  ready:'Runtime loaded. Choose Check to check again.',
  busy:'Loading / checking… The first run downloads about 14 MB and may take time depending on your connection.',
  checking:'Checking…',
  cancelled:'Input, results and runtime cleared.',
  timeout:'Timed out; input kept. Check your connection and choose Check to retry.',
  failed:'Check failed; input kept. Check your connection and choose Check to retry.',
  oversized:'Input exceeds the candidate limit of 16,384 UTF-8 bytes. Shorten it and retry.',
  finished:'Grammar and item check finished. This differs from the full CLI check.',
  valid:'No errors', invalid:'Errors or unsupported Format version',
  count:'Total diagnostics', shown:'Shown', items:'Items', unsupported:'Unsupported Format version.',
  line:'Line', column:'Column', hint:'Hint', error:'Error', warning:'Warning', info:'Info',
  bytes:'UTF-8 bytes',
};
const input = document.querySelector('#input');
const button = document.querySelector('#check');
const cancel = document.querySelector('#cancel');
const status = document.querySelector('#status');
const output = document.querySelector('#output');
const bytes = document.querySelector('#bytes');
let worker, timer, ready = false, id = 0;
const size = () => new TextEncoder().encode(input.value).length;
function updateBytes() { bytes.textContent = `${size()} / ${MAX_BYTES} ${copy.bytes}`; }
function stop(message, clearInput = false) {
  clearTimeout(timer); worker?.terminate(); worker = undefined; ready = false; ++id;
  if (clearInput) input.value = '';
  output.textContent = ''; status.textContent = message;
  input.readOnly = false; button.disabled = false; cancel.disabled = input.value.length === 0; updateBytes();
}
function render(result) {
  const lines = [result.valid ? copy.valid : copy.invalid];
  if (!result.supported_format) lines.push(copy.unsupported);
  lines.push(`${copy.items}: ${result.items}; ${copy.count}: ${result.diagnostic_count}; ${copy.shown}: ${result.diagnostics.length}`);
  for (const diagnostic of result.diagnostics) {
    const position = [];
    if (diagnostic.line != null) position.push(`${copy.line} ${diagnostic.line}`);
    if (diagnostic.column != null) position.push(`${copy.column} ${diagnostic.column}`);
    const severity = {error:copy.error, warning:copy.warning, info:copy.info}[diagnostic.severity] ?? diagnostic.severity ?? '';
    let summary = `${position.join(' · ')} ${severity} ${diagnostic.code ?? ''}: ${diagnostic.message}`.trim();
    if (diagnostic.hint) summary += `\n${copy.hint}: ${diagnostic.hint}`;
    lines.push(summary);
  }
  output.textContent = lines.join('\n\n');
}
input.addEventListener('input', () => {
  updateBytes(); cancel.disabled = !worker && input.value.length === 0;
  output.textContent = ''; status.textContent = ready ? copy.ready : copy.idle;
});
cancel.addEventListener('click', () => stop(copy.cancelled, true));
window.addEventListener('pagehide', () => stop(copy.cancelled, true));
button.addEventListener('click', () => {
  output.textContent = '';
  if (size() > MAX_BYTES) { status.textContent = copy.oversized; return; }
  input.readOnly = true; button.disabled = true; cancel.disabled = false;
  status.textContent = ready ? copy.checking : copy.busy;
  const request = ++id;
  const arm = ms => { clearTimeout(timer); timer = setTimeout(() => stop(copy.timeout), ms); };
  try {
    worker ??= new Worker('../../checker/worker.mjs', {type:'module'});
    worker.onmessage = ({data}) => {
      if (data.id !== id) return;
      if (data.stage === 'ready') { ready = true; status.textContent = copy.checking; arm(WARM_MS); return; }
      if (data.stage !== 'result') { stop(copy.failed); return; }
      clearTimeout(timer); input.readOnly = false; button.disabled = false;
      status.textContent = copy.finished; render(data.result);
    };
    worker.onerror = () => stop(copy.failed);
    worker.onmessageerror = () => stop(copy.failed);
    arm(ready ? WARM_MS : COLD_MS);
    worker.postMessage({id:request, text:input.value});
  } catch (_) { stop(copy.failed); }
});
updateBytes(); status.textContent = copy.idle;
