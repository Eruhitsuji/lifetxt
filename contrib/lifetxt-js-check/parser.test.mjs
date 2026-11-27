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

test('checks simple recurrence and identifies each problematic RRULE part', () => {
    const result = parse([
        '[ ] T Daily repeat:daily repeat:weekdays interval:2 count:3',
        '[ ] E Rules repeat:RRULE:FREQ=YEARLY;BYDAY=-1FR;BYMONTHDAY=-1;BYMONTH=2,12;UNTIL=20281231',
        '[ ] E Incorrect repeat:RRULE:FREQ=DAILY;COUNT=0;BYDAY=2MO;JUNK',
        '[ ] T Simple repeat:hourly interval:-1 count:0',
        '[ ] T Typed repeat:json<< [12,"daily"] >>',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'invalid-rrule', line: 3, key: 'repeat', part: 'COUNT' },
        { severity: 'warning', code: 'invalid-rrule', line: 3, key: 'repeat', part: 'BYDAY' },
        { severity: 'warning', code: 'invalid-repeat', line: 4, key: 'repeat' },
        { severity: 'warning', code: 'expected-positive-integer', line: 4, key: 'interval' },
        { severity: 'warning', code: 'expected-positive-integer', line: 4, key: 'count' },
        { severity: 'error', code: 'detail-expects-text', line: 5, key: 'repeat' },
    ]);
    assert.equal(result.hasErrors, true);
});

test('accepts all requirement states in short and JSON conditions', () => {
    const states = ['not_started', 'in_progress', 'done', 'canceled', 'moved', 'maybe', 'note',
        '[ ]', '[/]', '[x]', '[-]', '[>]', '[?]', '[N]'];
    const condition = JSON.stringify({ all: [
        { id: 'review', state: states },
        { any: ['materials=not_started,done', 'review=alias=done'] },
    ] });
    assert.deepEqual(parse('[ ] T Review id:review id:review=alias\n' +
        '[ ] T Materials id:materials\n[ ] T Submit requires:"review=' + states.join(',') + '" ' +
        'requires:json<< ' + condition + ' >>').diagnostics.map(d => d.code), ['invalid-id']);
});

test('reports the first problem in each requires value on its item line', () => {
    const result = parse('# comment\n[ ] T Submit requires:"a b=done" requires:review=done, ' +
        'requires:json<< [{"all":["ok=done",{"id":"other","state":[]}]}, ' +
        '{"all":[]}, {"id":"review","state":true}] >>\n[ ] T Next');
    assert.deepEqual(result.diagnostics, ['id', 'state', 'state', 'shape', 'state'].map(part =>
        ({ severity: 'error', code: 'invalid-requires', line: 2, key: 'requires', part })));
    assert.equal(result.hasErrors, true);
    assert.equal(result.items.length, 2);
});

test('checks ID syntax, preserves case, and keeps the first occurrence', () => {
    const result = parse([
        '[ ] T First id:Case id:case id:Case id:A.1@cal/team:class_1-test',
        '[ ] T Invalid id:"has space" id:"" id:""',
        '[ ] T Next id:Case id:case',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, [
        ...Array.from({ length: 3 }, () =>
            ({ severity: 'warning', code: 'invalid-id', line: 2, key: 'id' })),
        { severity: 'warning', code: 'duplicate-id', line: 1, key: 'id', firstLine: 1, value: 'Case' },
        { severity: 'warning', code: 'duplicate-id', line: 3, key: 'id', firstLine: 1, value: 'Case' },
        { severity: 'warning', code: 'duplicate-id', line: 3, key: 'id', firstLine: 1, value: 'case' },
    ]);
    assert.equal(result.hasErrors, false);
});

test('reports a type error without indexing a non-text ID', () => {
    const result = parse('[ ] T Typed id:json<< [true,12,null] >>\n[ ] T Text id:True id:12');
    assert.deepEqual(result.diagnostics, [
        { severity: 'error', code: 'detail-expects-text', line: 1, key: 'id' },
    ]);
    assert.equal(result.hasErrors, true);
});

test('checks explicit and inferred references against the same input', () => {
    const result = parse([
        '[ ] T Parent id:parent',
        '  [ ] T Child id:child ref:child related:later',
        '[ ] T Later id:later id:alias',
        '[ ] T SameAlias id:alias',
        '[ ] T Other depends_on:alias requires:json<< {"all":["missing=done","missing=maybe"]} >>',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'duplicate-id', line: 4, key: 'id', firstLine: 3, value: 'alias' },
        { severity: 'warning', code: 'self-reference', line: 2, key: 'ref', value: 'child' },
        { severity: 'warning', code: 'ambiguous-reference', line: 5, key: 'depends_on', value: 'alias' },
        { severity: 'warning', code: 'missing-reference', line: 5, key: 'requires', value: 'missing' },
    ]);
    assert.equal(result.hasErrors, false);
});

test('finds separate cycles and ignores a dependency edge duplicated by blocks', () => {
    const result = parse([
        '[ ] T A id:a depends_on:b',
        '[ ] T B id:b depends_on:a blocks:a',
        '[ ] T C id:c parent:d',
        '[ ] T D id:d parent:c',
        '[ ] T E id:e ref:f',
        '[ ] T F id:f ref:e',
    ].join('\n'));
    assert.deepEqual(result.diagnostics, [
        { severity: 'warning', code: 'reference-cycle', line: 3, key: 'parent', path: ['c', 'd', 'c'] },
        { severity: 'warning', code: 'reference-cycle', line: 1, key: 'depends_on', path: ['a', 'b', 'a'] },
    ]);
});

test('walks a deep parent cycle iteratively and reports its starting line', () => {
    const ids = Array.from({ length: 500 }, (_, i) => 'a' + i);
    const text = ids.map((id, i) =>
        '[ ] T T id:' + id + ' parent:' + ids[(i + 1) % ids.length]).join('\n');
    assert.deepEqual(parse(text).diagnostics, [
        { severity: 'warning', code: 'reference-cycle', line: 1, key: 'parent', path: [...ids, ids[0]] },
    ]);
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
