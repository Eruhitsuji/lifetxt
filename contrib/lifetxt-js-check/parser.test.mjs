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
    assert.deepEqual(result.diagnostics, []);
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
