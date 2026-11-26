import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parse } from './parser.mjs';

test('recognizes every Format 1 status and type', () => {
    for (const status of ['[ ]', '[/]', '[x]', '[-]', '[>]', '[?]', '[N]']) {
        for (const type of 'TEDRHNSMJ') {
            const result = parse(`${status} ${type} title`);
            assert.equal(result.items[0].status, status);
            assert.equal(result.items[0].type, type);
            assert.deepEqual(result.diagnostics, []);
        }
    }
});

test('preserves Unicode, repeated and special keys, and body text', () => {
    const text = '\uFEFF#! format_version: 1\r\n# note\r  [N] N "日本語😀 \\"引用\\"" ' +
        'custom:"A B" custom:C __proto__:safe body:Start\n  | 続き\n|Last';
    const result = parse(text);
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'indent-no-parent', line: 3 },
    ]);
    assert.deepEqual(result.items, [{
        line: 3, indent: 2, status: '[N]', type: 'N', title: '日本語😀 "引用"',
        details: [['custom', ['A B', 'C']], ['__proto__', ['safe']], ['body', ['Start\n続き\nLast']]],
    }]);
});

test('reports bounded syntax errors with physical line numbers', () => {
    const cases = [
        ['[z] T title', 'invalid-item-start'],
        ['[ ] Q title', 'invalid-item-start'],
        ['[ ] T title tag=value', 'invalid-detail'],
        ['[ ] T title tag:', 'invalid-bare-value'],
        ['[ ] T title tag:"bad', 'unclosed-quote'],
        ['[ ] T "title"tag:value', 'quoted-value-separator'],
        ['[ ] T\ttitle', 'tab-in-item'],
        ['| orphan', 'orphan-body'],
        ['[N] N title body:a body:b\n| ambiguous', 'ambiguous-body'],
    ];
    for (const [input, code] of cases) {
        const result = parse('# comment\n' + input);
        assert.equal(result.hasErrors, true, input);
        assert.equal(result.diagnostics[0].code, code, input);
        assert.equal(result.diagnostics[0].line, input.includes('\n') ? 3 : 2, input);
    }
});

test('joins physical lines before parsing and attaches subsequent body lines', () => {
    const result = parse([
        '[ ] T "long\\  ',
        '  title" \\ ',
        ' tag:a',
        ' | body',
        '[ ] T next',
    ].join('\r\n'));
    assert.deepEqual(result.diagnostics, []);
    assert.equal(result.incomplete, false);
    assert.deepEqual(result.items, [
        {
            line: 1, indent: 0, status: '[ ]', type: 'T', title: 'longtitle',
            details: [['tag', ['a']], ['body', ['body']]],
        },
        { line: 5, indent: 0, status: '[ ]', type: 'T', title: 'next', details: [] },
    ]);
});

test('reports malformed joins at the affected physical line', () => {
    const nextLineIsBody = parse('[ ] T title\\\n  |body\n[ ] T next');
    assert.deepEqual(nextLineIsBody.diagnostics, [
        { severity: 'error', code: 'line-join-into-body', line: 2 },
    ]);
    assert.equal(nextLineIsBody.items[1].line, 3);

    for (const ending of ['', '\n', '\r\n', '\r', '\u2028']) {
        const text = '[ ] T title \\\n tag:a\\ ';
        const result = parse(text + ending);
        assert.deepEqual(result.diagnostics, [
            { severity: 'error', code: 'dangling-line-join', line: 2 },
        ]);
        assert.equal(result.hasErrors, true);
        assert.equal(result.incomplete, false);
        assert.deepEqual(parse(text + ending + '\n\n').diagnostics, []);
    }
});

test('reads multiline JSON details and keeps JSON string delimiters literal', () => {
    const result = parse([
        '[ ] T title tag:first options:json<<',
        '\t{"text":"embedded >> marker","list":[null,{"same":true}]}',
        '>> tag:json<< ["second","third"] >> empty:json<< [] >>',
        '[ ] T next',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, []);
    assert.deepEqual(result.items[0].details, [
        ['tag', ['first', 'second', 'third']],
        ['options', [{ text: 'embedded >> marker', list: [null, { same: true }] }]],
        ['empty', []],
    ]);
    assert.equal(result.items[1].line, 4);
});

test('reports JSON errors and preserves the following details and items', () => {
    const result = parse('[ ] T title tag:json<<\n ["ok"]\n' +
        '>> options:json<< ["bad",] >> tag:after\n[ ] T next');
    assert.deepEqual(result.diagnostics, [
        { severity: 'error', code: 'invalid-json-detail', line: 3 },
    ]);
    assert.deepEqual(result.items[0].details, [['tag', ['ok', 'after']], ['options', []]]);
    assert.equal(result.items[1].line, 4);

    const unclosed = parse('[ ] T title tag:json<<\n ["not closed >>"]\n[ ] T next');
    assert.equal(unclosed.diagnostics[0].code, 'invalid-json-detail');
    assert.equal(unclosed.items[1].line, 3);
});

test('flags JSON integers that would lose precision', () => {
    const result = parse('[ ] T title options:json<< {"large":9007199254740993} >> tag:after');
    assert.deepEqual(result.diagnostics, [
        { severity: 'unsupported', code: 'json-integer-precision', line: 1 },
    ]);
    assert.equal(result.incomplete, true);
    assert.equal(result.hasErrors, false);
    assert.deepEqual(result.items[0].details, [['options', []], ['tag', ['after']]]);
});

test('uses the nearest less-indented item and keeps explicit parent values', () => {
    const result = parse([
        '[ ] T Root id:root id:second',
        '  [ ] T Child id:child',
        '    | Child body',
        '# separator',
        '',
        '    [ ] T Grandchild tag:before parent:json<< [] >> tag:after',
        '  [ ] T Sibling parent:second',
        '[ ] T Other id:other',
        '  [ ] T UnderOther',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, []);
    const parents = result.items.map(item => item.details.find(([key]) => key === 'parent')?.[1]);
    assert.deepEqual(parents, [undefined, ['root'], ['child'], ['second'], undefined, ['other']]);
    assert.deepEqual(result.items[2].details, [
        ['tag', ['before', 'after']], ['parent', ['child']],
    ]);
});

test('warns if no parent can be inferred without falling back to a distant ancestor', () => {
    const result = parse('  [ ] T Orphan\n[ ] T Root id:root\n' +
        '  [ ] T WithoutId\n    [ ] T Grandchild\n  [ ] T Sibling');
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'indent-no-parent', line: 1 },
        { severity: 'warning', code: 'indent-parent-no-id', line: 4 },
    ]);
    assert.equal(result.hasErrors, false);
    assert.deepEqual(result.items[3].details, []);
    assert.deepEqual(result.items[4].details, [['parent', ['root']]]);
});

test('checks calendar boundaries, clock values, fractions and offsets', () => {
    for (const detail of [
        'on:2000-02-29', 'on:0001-01-01', 'due:9999-12-31',
        'from:2024-02-29T23:59:59.000001+2359', 'at:08:30:05.1-03:30', 'at:08:30Z',
    ]) {
        assert.deepEqual(parse('[ ] T title ' + detail).diagnostics, [], detail);
    }
    for (const [key, value, code] of [
        ['on', '0000-01-01', 'invalid-date'],
        ['on', '1900-02-29', 'invalid-date'],
        ['on', '2024-13-01', 'invalid-date'],
        ['due', '2024-04-31', 'invalid-date-or-datetime'],
        ['at', '24:00', 'invalid-time-or-datetime'],
        ['at', '12:60', 'invalid-time-or-datetime'],
        ['at', '12:00:60', 'invalid-time-or-datetime'],
        ['at', '12:00:00.1234567', 'invalid-time-or-datetime'],
        ['at', '12:00+24:00', 'invalid-time-or-datetime'],
        ['at', '12:00+0060', 'invalid-time-or-datetime'],
        ['from', '2024-01-01', 'invalid-datetime'],
        ['to', '"2024-02-29 12:00"', 'invalid-datetime'],
        ['due', 'json<< "2024-02-29\\n" >>', 'invalid-date-or-datetime'],
    ]) {
        const detail = key + ':' + value;
        const result = parse('# comment\n[ ] T title ' + detail);
        assert.deepEqual(result.diagnostics, [
            { severity: 'warning', code, line: 2, key },
        ], detail);
        assert.equal(result.hasErrors, false, detail);
    }
});

test('reports one type error per affected temporal field and keeps the record', () => {
    const result = parse('[ ] T title due:invalid due:json<< [null, 1] >> at:json<< [] >>');
    assert.deepEqual(result.diagnostics, [
        { severity: 'error', code: 'detail-expects-text', line: 1, key: 'due' },
    ]);
    assert.equal(result.hasErrors, true);
    assert.equal(result.items.length, 1);
});

test('warns about reversed event ranges at fractional-second precision', () => {
    const result = parse([
        '[ ] E EarlierEnd from:2026-12-01T09:00:00.000002 to:2026-12-01T09:00:00.000001',
        '[ ] E Equal from:2026-12-01T09:00 to:2026-12-01T09:00:00.000000',
        '[ ] E FirstValues from:2026-12-01T09:00 to:2026-12-01T09:01 to:2026-12-01T08:00',
        '[ ] T Task from:2026-12-01T09:00 to:2026-12-01T08:00',
        '[ ] E Missing from:2026-12-01T09:00',
        '[ ] E Empty from:2026-12-01T09:00 to:json<< [] >>',
        '[ ] E Invalid from:2026-12-01T09:00 to:2026-12-01T24:00',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'event-end-before-start', line: 1, key: 'to' },
        { severity: 'warning', code: 'invalid-datetime', line: 7, key: 'to' },
    ]);
    assert.equal(result.hasErrors, false);
});

test('excludes unknown format versions', () => {
    const future = parse('#! format_version: 2\nanything');
    assert.equal(future.incomplete, true);
    assert.equal(future.items.length, 0);
    assert.equal(future.diagnostics[0].code, 'unsupported-format');
});

test('enforces UTF-8 size and tracks errors beyond the display cap', () => {
    assert.equal(parse('#' + 'あ'.repeat(5461)).hasErrors, false);
    assert.equal(parse('#' + 'あ'.repeat(5461) + 'x').diagnostics[0].code, 'input-too-large');
    const result = parse(('[ ] T "\\q"\n').repeat(101) + 'bad');
    assert.equal(result.diagnostics.length, 100);
    assert.equal(result.diagnosticCount, 102);
    assert.equal(result.hasErrors, true);
});
