import { MAX_BYTES, COLD_MS, WARM_MS } from './limits.mjs';
const copy = document.documentElement.lang === 'ja' ? {
  idle:'チェックを押すとランタイムを読み込みます。',
  busy:'読み込み・チェック中…',
  cancelled:'入力・結果・ランタイムを消去しました。',
  timeout:'時間切れです。入力を消去しました。接続を確認し、再入力して実行してください。',
  failed:'実行に失敗しました。入力を消去しました。接続を確認し、再入力して実行してください。',
  oversized:'上限候補16,384 UTF-8 bytesを超えています。入力を短くしてください。',
  finished:'文法・項目チェックが完了しました。CLI全検査とは異なります。',
  valid:'エラーなし', invalid:'エラーまたは未対応のFormat版',
  count:'診断総数', shown:'表示数', items:'項目数', unsupported:'未対応のFormat版です。',
  bytes:'UTF-8 bytes',
} : {
  idle:'Choose Check to load the runtime.', busy:'Loading / checking…',
  cancelled:'Input, results and runtime cleared.',
  timeout:'Timed out; input cleared. Check your connection, paste again and retry.',
  failed:'Check failed; input cleared. Check your connection, paste again and retry.',
  oversized:'Input exceeds the candidate limit of 16,384 UTF-8 bytes. Shorten it and retry.',
  finished:'Grammar and item check finished. This differs from the full CLI check.',
  valid:'No errors', invalid:'Errors or unsupported Format version',
  count:'Total diagnostics', shown:'Shown', items:'Items', unsupported:'Unsupported Format version.',
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
function stop(message) {
  clearTimeout(timer); worker?.terminate(); worker = undefined; ready = false; ++id;
  input.value = ''; output.textContent = ''; status.textContent = message;
  input.readOnly = false; button.disabled = false; cancel.disabled = true; updateBytes();
}
function render(result) {
  const lines = [result.valid ? copy.valid : copy.invalid];
  if (!result.supported_format) lines.push(copy.unsupported);
  lines.push(`${copy.items}: ${result.items}; ${copy.count}: ${result.diagnostic_count}; ${copy.shown}: ${result.diagnostics.length}`);
  for (const diagnostic of result.diagnostics) lines.push(JSON.stringify(diagnostic, null, 2));
  output.textContent = lines.join('\n\n');
}
input.addEventListener('input', () => {
  updateBytes(); output.textContent = ''; status.textContent = copy.idle;
});
cancel.addEventListener('click', () => stop(copy.cancelled));
window.addEventListener('pagehide', () => stop(copy.cancelled));
button.addEventListener('click', () => {
  output.textContent = '';
  if (size() > MAX_BYTES) { status.textContent = copy.oversized; return; }
  input.readOnly = true; button.disabled = true; cancel.disabled = false;
  status.textContent = copy.busy;
  const request = ++id;
  const arm = ms => { clearTimeout(timer); timer = setTimeout(() => stop(copy.timeout), ms); };
  try {
    worker ??= new Worker('../../checker/worker.mjs', {type:'module'});
    worker.onmessage = ({data}) => {
      if (data.id !== id) return;
      if (data.stage === 'ready') { ready = true; arm(WARM_MS); return; }
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
