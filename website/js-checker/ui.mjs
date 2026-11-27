import { parse } from './parser.mjs';

const messages = {
    ja: {
        errors: 'エラーがあります。',
        incomplete: '検査対象外の入力があります。完全な検査には lifetxt check を使用してください。',
        ok: '検査した範囲ではエラーは見つかりませんでした。完全な検査には lifetxt check を使用してください。',
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
        'invalid-json-detail': 'json<< と >> の間に有効なJSON値を1つ置き、値の前後に空白または改行を入れてください。',
        'json-detail-separator': '閉じ区切りの >> の後にスペースが必要です。',
        'json-integer-precision': 'JavaScriptで正確に扱える整数の範囲を超えています。lifetxt check で確認してください。',
        'input-too-large': 'UTF-8で16 KiBを超えています。',
        'unsupported-format': 'この形式バージョンは検査対象外です。',
        'dangling-line-join': '行末のバックスラッシュの後には続きの行が必要です。',
        'line-join-into-body': '縦棒で始まる本文行へはバックスラッシュで連結できません。',
        'orphan-body': '本文行の直前に項目が必要です。',
        'ambiguous-body': '本文行の前に指定できる body: は、文字列1つまでです。',
        'indent-no-parent': 'インデントの浅い親項目が見つかりません。parent: を指定するか、行頭の空白を削除してください。',
        'indent-parent-no-id': '直近の親候補に id: がありません。親候補に id: を付けるか、子項目に parent: を指定してください。',
        'invalid-date': '実在する日付を YYYY-MM-DD で指定してください。',
        'invalid-datetime': '日時を YYYY-MM-DDTHH:MM で指定してください。秒・小数秒・UTCオフセットを追加できます。',
        'invalid-date-or-datetime': '日付 YYYY-MM-DD または日時 YYYY-MM-DDTHH:MM を指定してください。',
        'invalid-time-or-datetime': '時刻 HH:MM または日時 YYYY-MM-DDTHH:MM を指定してください。',
        'detail-expects-text': '文字列の値を指定してください。',
        'event-end-before-start': 'イベントの終了日時が開始日時より前です。',
        'unknown-state': '既知の状態名（available、busy、away、offline、dnd、focus、sleeping、commuting、working、studying、meeting、custom）を指定してください。',
        'status-missing-from': '状態項目には開始日時が必要です。',
        'status-invalid-from': '状態項目の開始には有効な日時を指定してください。',
        'status-missing-state': '状態項目には状態名が必要です。',
        'status-invalid-to': '状態項目の終了には有効な日時を指定してください。',
        'status-closed-marker': '終了日時を指定した状態項目には [x] を推奨します。',
        'status-open-marker': '終了日時のない状態項目には [/] を推奨します。',
        'invalid-repeat': 'daily、weekly、monthly、yearly、weekdays、または RRULE: を指定してください。',
        'expected-positive-integer': '1以上の整数を指定してください。',
        'invalid-rrule': 'RRULE の該当箇所の値または組み合わせを確認してください。',
        'invalid-id': '英数字で始まる半角のIDを指定してください。記号は _ . : @ / - を使用できます。',
        'invalid-reference-id': '参照先のIDは、英数字で始まる半角の値を指定してください。',
        'missing-reference': value => `ID ${JSON.stringify(value)} が入力内に見つかりません。`,
        'self-reference': value => `ID ${JSON.stringify(value)} はこの項目自身を指しています。`,
        'ambiguous-reference': value => `ID ${JSON.stringify(value)} が複数回使われており、参照先を特定できません。`,
        'reference-cycle': '参照が循環しています。',
        'completed-with-open-dependency': value => `完了済みですが、前提項目 ${JSON.stringify(value)} が未完了です。`,
        'closed-parent-with-open-children': (value, { childCount }) => `完了・取消済みの親 ${JSON.stringify(value)} に未完了の子が ${childCount} 件あります。`,
        'temporal-reference-order': value => `ID ${JSON.stringify(value)} との参照関係が、項目に記載された日付順と矛盾しています。`,
        'duplicate-id': (value, { firstLine }) => `${JSON.stringify(value)} は ${firstLine}行目で既に使われています。`,
        requires: {
            shape: 'ID=state、または id/state の組、all、any でJSON条件を指定してください。all と any には条件が1つ以上必要です。',
            id: '空白を含まないIDを指定してください。',
            state: '有効な状態名か状態マーカーを1つ以上指定してください。',
            depth: '条件の入れ子は32段階までです。',
        },
    },
    en: {
        errors: 'Errors found.',
        incomplete: 'Some input was not checked. Use lifetxt check for full validation.',
        ok: 'No errors found in the checked input. Use lifetxt check for full validation.',
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
        'invalid-json-detail': 'Write one valid JSON value with whitespace around it between json<< and >>.',
        'json-detail-separator': 'Add a space after the closing >> before the next detail.',
        'json-integer-precision': 'This integer exceeds the JavaScript safe integer range. Use lifetxt check.',
        'input-too-large': 'Input exceeds 16 KiB in UTF-8.',
        'unsupported-format': 'This format version is outside the checked scope.',
        'dangling-line-join': 'A trailing backslash must be followed by another line.',
        'line-join-into-body': 'A backslash cannot join into a pipe-prefixed body line.',
        'orphan-body': 'A body line needs a preceding item.',
        'ambiguous-body': 'A body line can follow at most one text body: value.',
        'indent-no-parent': 'No less-indented parent item was found. Add parent: or move the item to column 1.',
        'indent-parent-no-id': 'The nearest less-indented item has no id:. Give it an id: or specify parent: on the child.',
        'invalid-date': 'Enter a valid calendar date in YYYY-MM-DD format.',
        'invalid-datetime': 'Enter a datetime in YYYY-MM-DDTHH:MM format, optionally with seconds, fractional seconds, and a UTC offset.',
        'invalid-date-or-datetime': 'Enter a date in YYYY-MM-DD format or a datetime in YYYY-MM-DDTHH:MM format.',
        'invalid-time-or-datetime': 'Enter a time in HH:MM format or a datetime in YYYY-MM-DDTHH:MM format.',
        'detail-expects-text': 'Enter a text value.',
        'event-end-before-start': 'The event ends before it starts.',
        'unknown-state': 'Use a known state: available, busy, away, offline, dnd, focus, sleeping, commuting, working, studying, meeting, or custom.',
        'status-missing-from': 'A status item needs a start datetime.',
        'status-invalid-from': 'Use a valid start datetime for the status item.',
        'status-missing-state': 'A status item needs a state name.',
        'status-invalid-to': 'Use a valid end datetime for the status item.',
        'status-closed-marker': 'Use [x] when a status item has an end datetime.',
        'status-open-marker': 'Use [/] when a status item has no end datetime.',
        'invalid-repeat': 'Use daily, weekly, monthly, yearly, weekdays, or RRULE:.',
        'expected-positive-integer': 'Enter an integer of 1 or greater.',
        'invalid-rrule': 'Check the value or combination for the indicated RRULE part.',
        'invalid-id': 'Enter an ASCII ID starting with a letter or digit. Allowed punctuation is _ . : @ / -.',
        'invalid-reference-id': 'Enter an ASCII reference ID starting with a letter or digit.',
        'missing-reference': value => `ID ${JSON.stringify(value)} was not found in the input.`,
        'self-reference': value => `ID ${JSON.stringify(value)} refers to this item.`,
        'ambiguous-reference': value => `ID ${JSON.stringify(value)} occurs more than once, so the target is ambiguous.`,
        'reference-cycle': 'The references form a cycle.',
        'completed-with-open-dependency': value => `This item is completed, but prerequisite ${JSON.stringify(value)} is still open.`,
        'closed-parent-with-open-children': (value, { childCount }) => `Completed or canceled parent ${JSON.stringify(value)} has ${childCount} open child items.`,
        'temporal-reference-order': value => `The relation to ID ${JSON.stringify(value)} conflicts with the items’ calendar date order.`,
        'duplicate-id': (value, { firstLine }) => `${JSON.stringify(value)} first appears on line ${firstLine}.`,
        requires: {
            shape: 'Use ID=state or a JSON condition with id and state, all, or any. An all or any group needs at least one condition.',
            id: 'Enter a nonempty ID without whitespace.',
            state: 'Enter one or more valid state names or status markers.',
            depth: 'Conditions can be nested up to 32 levels.',
        },
    },
};

const lang = document.documentElement.lang;
const copy = messages[lang];
const input = document.getElementById('input');
const button = document.getElementById('check');
const loadSample = document.getElementById('load-sample');
const status = document.getElementById('status');
const output = document.getElementById('output');

function clearResult() {
    status.textContent = '';
    output.textContent = '';
}

function syncSampleButton() {
    loadSample.disabled = input.value !== '';
}

input.addEventListener('input', () => {
    clearResult();
    syncSampleButton();
});
loadSample.addEventListener('click', () => {
    if (input.value !== '') return;
    input.value = loadSample.dataset.sample;
    clearResult();
    input.focus();
    syncSampleButton();
});
window.addEventListener('pagehide', () => {
    input.value = '';
    clearResult();
    syncSampleButton();
});

button.addEventListener('click', () => {
    const result = parse(input.value);
    const summaries = [];
    if (result.hasErrors) summaries.push(copy.errors);
    if (result.incomplete) summaries.push(copy.incomplete);
    status.textContent = summaries.length ? summaries.join(' ') : copy.ok;

    const lines = result.diagnostics.map(diagnostic => {
        const { severity, code, line, key, part, value, path } = diagnostic;
        const location = lang === 'ja' ? `${line}${copy.line}` : `${copy.line} ${line}`;
        const isRequirement = code === 'invalid-requires';
        const field = key ? `${key}: ${part && !isRequirement ? `[${part}] ` : ''}` : '';
        let message = isRequirement ? copy.requires[part] : copy[code];
        if (typeof message === 'function') message = message(value, diagnostic);
        if (path) message += ` ${path.map(id => JSON.stringify(id)).join(' → ')}`;
        return `${location} · ${copy.labels[severity]} · ${code} · ${field}${message ?? code}`;
    });
    const hidden = result.diagnosticCount - result.diagnostics.length;
    if (hidden) lines.push(lang === 'ja' ? `${hidden}${copy.omitted}` : `${hidden} ${copy.omitted}`);
    output.textContent = lines.join('\n');
});
button.disabled = false;
syncSampleButton();
