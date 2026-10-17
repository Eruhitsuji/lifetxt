const input = document.querySelector('#input');
const button = document.querySelector('#check');
const cancel = document.querySelector('#cancel');
const status = document.querySelector('#status');
const output = document.querySelector('#output');
let worker, timer, ready = false, id = 0;
function stop(message) {
  clearTimeout(timer); worker?.terminate(); worker = undefined; ready = false; ++id;
  input.value = ''; output.textContent = ''; status.textContent = message;
  button.disabled = false; cancel.disabled = true;
}
cancel.addEventListener('click', () => stop('Cancelled; input, output and runtime cleared.'));
button.addEventListener('click', () => {
  if (new TextEncoder().encode(input.value).length > 65536) {
    status.textContent = 'Input exceeds 65536 UTF-8 bytes.'; return;
  }
  button.disabled = true; cancel.disabled = false; output.textContent = '';
  status.textContent = 'Loading / checking…';
  worker ??= new Worker('./worker.mjs', {type:'module'});
  const request = ++id;
  const arm = ms => { clearTimeout(timer); timer = setTimeout(() => stop('Timed out; runtime and input cleared.'), ms); };
  arm(120000);
  worker.onmessage = ({data}) => {
    if (data.id !== id) return;
    if (data.stage === 'ready') {
      ready = true;
      output.textContent = JSON.stringify(data, null, 2) + '\n'; arm(5000); return;
    }
    clearTimeout(timer); button.disabled = false;
    status.textContent = data.stage === 'result' ? 'Finished (parser-only scope).' : data.message;
    output.textContent += JSON.stringify(data, null, 2);
  };
  worker.onerror = () => stop('Runtime failed to load; input cleared. Retry with local dependencies available.');
  // Warm checks also have a bounded wall-clock budget; startup gets a longer budget.
  if (ready) arm(5000);
  worker.postMessage({id:request, text:input.value});
});
