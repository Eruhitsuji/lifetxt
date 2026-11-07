import { parse } from './parser.mjs';

const messages = {
    ja: {
        errors: '書式エラーがあります。',
        incomplete: '検査対象外の構文があります。完全な検査には lifetxt check を使用してください。',
        ok: '検査した範囲では書式エラーは見つかりませんでした。',
        line: '行',
        omitted: '件の診断を省略しました。',
        labels: { error: 'エラー', warning: '警告', unsupported: '対象外' },
        'invalid-bare-value': '値が空か、引用符の使い方が正しくありません。',
        'quoted-value-separator': '閉じ引用符の後にスペースが必要です。',
        'unknown-escape': 'このエスケープは仕様で定義されていません。',
        'unclosed-quote': '引用符が閉じていません。',
        'tab-in-item': '項目行でタブは使えません。',
        'invalid-item-start': '行頭の状態・種類・タイトルを確認してください。',
        'invalid-detail': '詳細は key:value の形式で入力してください。',
        'input-too-large': 'UTF-8で16 KiBを超えています。',
        'unsupported-format': 'この形式バージョンは検査対象外です。',
        'line-join': 'バックスラッシュによる行継続は検査対象外です。',
        'orphan-body': '本文行の直前に項目が必要です。',
        'ambiguous-body': 'body: が複数ある項目には本文行を結び付けられません。',
    },
    en: {
        errors: 'Syntax errors found.',
        incomplete: 'Some syntax was not checked. Use lifetxt check for full validation.',
        ok: 'No errors found in the checked syntax.',
        line: 'Line',
        omitted: 'additional diagnostics omitted.',
        labels: { error: 'Error', warning: 'Warning', unsupported: 'Unchecked' },
        'invalid-bare-value': 'A value is empty or uses quotes incorrectly.',
        'quoted-value-separator': 'A space is required after a closing quote.',
        'unknown-escape': 'This escape is not defined in the format.',
        'unclosed-quote': 'A quote is not closed.',
        'tab-in-item': 'Tabs are not allowed in item lines.',
        'invalid-item-start': 'Check the leading status, type, and title.',
        'invalid-detail': 'Write details as key:value.',
        'input-too-large': 'Input exceeds 16 KiB in UTF-8.',
        'unsupported-format': 'This format version is outside the checked scope.',
        'line-join': 'Backslash line joins are outside the checked scope.',
        'orphan-body': 'A body line needs a preceding item.',
        'ambiguous-body': 'A body line cannot attach to an item with repeated body: values.',
    },
};

const lang = document.documentElement.lang;
const copy = messages[lang];
const input = document.getElementById('input');
const button = document.getElementById('check');
const status = document.getElementById('status');
const output = document.getElementById('output');

function clearResult() {
    status.textContent = '';
    output.textContent = '';
}

input.addEventListener('input', clearResult);
window.addEventListener('pagehide', () => {
    input.value = '';
    clearResult();
});

button.addEventListener('click', () => {
    const result = parse(input.value);
    const summaries = [];
    if (result.hasErrors) summaries.push(copy.errors);
    if (result.incomplete) summaries.push(copy.incomplete);
    status.textContent = summaries.length ? summaries.join(' ') : copy.ok;

    const lines = result.diagnostics.map(({ severity, code, line }) => {
        const location = lang === 'ja' ? `${line}${copy.line}` : `${copy.line} ${line}`;
        return `${location} · ${copy.labels[severity]} · ${code} · ${copy[code] ?? code}`;
    });
    const hidden = result.diagnosticCount - result.diagnostics.length;
    if (hidden) lines.push(lang === 'ja' ? `${hidden}${copy.omitted}` : `${hidden} ${copy.omitted}`);
    output.textContent = lines.join('\n');
});
button.disabled = false;
