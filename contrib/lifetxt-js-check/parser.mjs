/** @typedef {{severity: 'error'|'warning'|'unsupported', code: string, line: number, key?: string}} Diagnostic */
/** @typedef {null|boolean|number|string|JsonValue[]|{[key: string]: JsonValue}} JsonValue */
/** @typedef {{line: number, indent: number, status: string, type: string, title: string, details: [string, JsonValue[]][]}} Item */
/** @typedef {{items: Item[], diagnostics: Diagnostic[], diagnosticCount: number, hasErrors: boolean, incomplete: boolean}} ParseResult */

export const MAX_BYTES = 16_384;
const MAX_DIAGNOSTICS = 100;
const ITEM_START = /^( *)\[([ /x>N?-])\] +([TEDRHNSMJ]) +/;
const NEXT_RECORD = /^ *(?:\[[ /x>N?-]\] |[#|])/;
const DIRECTIVE = /^#!\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$/;
const LINE_BREAK = /\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/;
const JOIN = /\\ *$/;
const DETAIL = /^[^ :"\t]+:/;
const JSON_START = /^json<<(?:[ \t\r\n]|$)/;
const JSON_SPACE = /[ \t\r\n]/;
const UNCLOSED_JSON = Symbol('unclosed JSON detail');
const encoder = new TextEncoder();

// Match Core's field groups in lifetxt/model.py.
const DATE_OR_DATETIME_KEYS = new Set([
    'created', 'updated', 'done', 'due', 'do', 'moved_to', 'notify_at',
    'notify_from', 'notify_to', 'ack', 'snooze_until', 'until',
]);
const DATE_VALUE = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_VALUE = /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)?$/;
const MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function isDate(value) {
    const match = DATE_VALUE.exec(value);
    if (!match) return false;
    const [year, month, day] = match.slice(1).map(Number);
    if (year === 0 || month < 1 || month > 12 || day < 1) return false;
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    return day <= (month === 2 && leap ? 29 : MONTH_DAYS[month - 1]);
}

function isTime(value) {
    return TIME_VALUE.test(value);
}

function isDateTime(value) {
    const [date, time, extra] = value.split('T');
    return time !== undefined && extra === undefined && isDate(date) && isTime(time);
}

function validateTemporalDetails(item, report) {
    for (const [key, values] of item.details) {
        let code;
        let accepts;
        if (key === 'on') {
            code = 'invalid-date';
            accepts = isDate;
        } else if (key === 'from' || key === 'to') {
            code = 'invalid-datetime';
            accepts = isDateTime;
        } else if (DATE_OR_DATETIME_KEYS.has(key)) {
            code = 'invalid-date-or-datetime';
            accepts = value => isDate(value) || isDateTime(value);
        } else if (key === 'at') {
            code = 'invalid-time-or-datetime';
            accepts = value => isTime(value) || isDateTime(value);
        } else {
            continue;
        }
        if (values.some(value => typeof value !== 'string')) {
            report('error', 'detail-expects-text', item.line, key);
            continue;
        }
        for (const value of values) {
            if (!accepts(value)) report('warning', code, item.line, key);
        }
    }
}

function jsonClose(text) {
    // The same string-token rule applies when recovering from malformed JSON.
    for (const token of text.matchAll(/"(?:[^"\\\n]|\\[^\n])*"|(>>)/g)) {
        if (token[1]) return token.index;
    }
    return -1;
}

function extendJson(lines, index, candidate, lineNumber) {
    const parts = [candidate];
    let end = index;
    for (let next = index + 1; next < lines.length; next++) {
        const following = lines[next];
        if (NEXT_RECORD.test(following)) break;
        parts.push(following);
        if (!following.trim()) continue;
        end = next;
        if (jsonClose(following) !== -1) {
            const combined = parts.join('\n');
            if (readItem(combined, lineNumber, () => {}, true) !== UNCLOSED_JSON) {
                return { line: combined, end };
            }
        }
    }
    return { line: parts.slice(0, end - index + 1).join('\n'), end };
}

function* logicalLines(lines, report) {
    for (let index = 0; index < lines.length; index++) {
        const lineNumber = index + 1;
        let parts = [];
        let current = lines[index];
        while (true) {
            const candidate = parts.join('') + current;
            if (candidate.includes('json<<') &&
                readItem(candidate, lineNumber, () => {}, true) === UNCLOSED_JSON) {
                const extended = extendJson(lines, index, candidate, lineNumber);
                current = extended.line;
                index = extended.end;
                parts = [];
            }
            if (!JOIN.test(current)) break;
            parts.push(current.replace(JOIN, ''));
            index++;
            if (index === lines.length) {
                report('error', 'dangling-line-join', index);
                current = '';
                break;
            }
            current = lines[index].replace(/^ */, '');
            if (current.startsWith('|')) {
                report('error', 'line-join-into-body', index + 1);
            }
        }
        parts.push(current);
        yield { line: parts.join(''), lineNumber };
    }
}

function validateJsonValues(payload) {
    // JSON.parse checks syntax, but silently accepts duplicate keys and rounds integers.
    const containers = [];
    let unsafeInteger = false;
    for (const [token, keySuffix] of payload.matchAll(
        /"(?:[^"\\]|\\.)*"([ \t\r\n]*:)?|[{}\[\]]|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/g,
    )) {
        if (token === '{' || token === '[') {
            containers.push(token === '{' ? new Set() : null);
        } else if (token === '}' || token === ']') {
            containers.pop();
        } else if (keySuffix) {
            const keys = containers.at(-1);
            const key = JSON.parse(token.slice(0, -keySuffix.length));
            if (keys.has(key)) throw new SyntaxError('Duplicate JSON object key');
            keys.add(key);
        } else if (token[0] !== '"') {
            const number = Number(token);
            if (/[.eE]/.test(token)) {
                if (!Number.isFinite(number)) throw new SyntaxError('Non-finite JSON number');
            } else {
                unsafeInteger ||= !Number.isSafeInteger(number);
            }
        }
    }
    return !unsafeInteger;
}

function readJson(line, pos, probe, report) {
    const start = pos + 'json<<'.length;
    const tail = line.slice(start);
    const sameLine = tail.split('\n', 1)[0].replace(/^[ \t]*/, '');
    if ((!sameLine.includes('>>') && DETAIL.test(sameLine)) || (!tail && !probe)) {
        return { values: ['json<<'], end: start };
    }
    const close = jsonClose(tail);
    if (close === -1 && probe) return UNCLOSED_JSON;
    const end = close === -1 ? line.length : start + close + 2;
    if (probe) return { values: [], end };
    const offset = line.slice(0, pos).split('\n').length - 1;
    try {
        const payload = tail.slice(0, close);
        if (close === -1 || !JSON_SPACE.test(payload.at(-1) ?? '')) {
            throw new SyntaxError('Missing JSON closing delimiter or whitespace');
        }
        const value = JSON.parse(payload);
        if (!validateJsonValues(payload)) {
            report('unsupported', 'json-integer-precision', offset);
            return { values: [], end };
        }
        return { values: Array.isArray(value) ? value : [value], end };
    } catch (error) {
        if (!(error instanceof SyntaxError)) throw error;
        report('error', 'invalid-json-detail', offset);
        return { values: [], end };
    }
}

function readValue(line, start, report) {
    if (line[start] !== '"') {
        const space = line.indexOf(' ', start);
        const end = space < 0 ? line.length : space;
        const value = line.slice(start, end);
        if (!value || value.includes('"')) {
            report('error', 'invalid-bare-value');
            return null;
        }
        return { value, end };
    }

    let value = '';
    for (let pos = start + 1; pos < line.length; pos++) {
        const char = line[pos];
        if (char === '"') {
            const end = pos + 1;
            if (end < line.length && line[end] !== ' ') {
                report('error', 'quoted-value-separator');
                return null;
            }
            return { value, end };
        }
        if (char === '\\') {
            const escaped = line[++pos];
            if (escaped === undefined) break;
            if (escaped !== '"' && escaped !== '\\') {
                report('warning', 'unknown-escape');
            }
            value += escaped;
        } else {
            value += char;
        }
    }
    report('error', 'unclosed-quote');
    return null;
}

function readItem(line, lineNumber, report, probe = false) {
    if (!line.includes('json<<') && line.includes('\t')) {
        report('error', 'tab-in-item');
        return null;
    }
    const start = ITEM_START.exec(line);
    if (!start) {
        report('error', 'invalid-item-start');
        return null;
    }
    const title = readValue(line, start[0].length, report);
    if (!title) return null;
    if (line.slice(0, title.end).includes('\t')) {
        report('error', 'tab-in-item');
        return null;
    }

    const details = new Map();
    let pos = title.end;
    while (pos < line.length) {
        while (line[pos] === ' ') pos++;
        if (pos === line.length) break;
        const key = DETAIL.exec(line.slice(pos));
        if (!key) {
            report('error', line[pos] === '\t' ? 'tab-in-item' : 'invalid-detail');
            return null;
        }
        const name = key[0].slice(0, -1);
        const valueStart = pos + key[0].length;
        let detail;
        if (JSON_START.test(line.slice(valueStart))) {
            detail = readJson(line, valueStart, probe, report);
            if (detail === UNCLOSED_JSON) return detail;
        } else {
            const value = readValue(line, valueStart, report);
            if (!value) return null;
            if (value.value.includes('\t')) {
                report('error', 'tab-in-item');
                return null;
            }
            detail = { values: [value.value], end: value.end };
        }
        if (!details.has(name)) details.set(name, []);
        for (const value of detail.values) details.get(name).push(value);
        pos = detail.end;
        if (pos < line.length && line[pos] !== ' ') {
            report('error', line[pos] === '\t' ? 'tab-in-item' : 'json-detail-separator');
            break;
        }
    }
    return {
        line: lineNumber,
        indent: start[1].length,
        status: `[${start[2]}]`,
        type: start[3],
        title: title.value,
        details: [...details],
    };
}

function inferParent(item, ancestor, report) {
    const parent = item.details.find(([name]) => name === 'parent');
    if (item.indent === 0 || parent?.[1].length) return;

    if (!ancestor) {
        report('warning', 'indent-no-parent', item.line);
        return;
    }
    const ids = ancestor.details.find(([name]) => name === 'id')?.[1];
    if (!ids?.length) {
        report('warning', 'indent-parent-no-id', item.line);
        return;
    }
    if (parent) {
        parent[1].push(ids[0]);
    } else {
        item.details.push(['parent', [ids[0]]]);
    }
}

/** Check supported Format 1 syntax, hierarchy and temporal values.
 * @param {string} text
 * @returns {ParseResult}
 */
export function parse(text) {
    if (typeof text !== 'string') throw new TypeError('Expected text');
    /** @type {ParseResult} */
    const result = {
        items: [], diagnostics: [], diagnosticCount: 0, hasErrors: false, incomplete: false,
    };
    function report(severity, code, line, key) {
        result.diagnosticCount++;
        result.hasErrors ||= severity === 'error';
        result.incomplete ||= severity === 'unsupported';
        if (result.diagnostics.length < MAX_DIAGNOSTICS) {
            result.diagnostics.push(key === undefined ? { severity, code, line } : { severity, code, line, key });
        }
    }

    if (text.length > MAX_BYTES || encoder.encode(text).length > MAX_BYTES) {
        report('error', 'input-too-large', 1);
        return result;
    }

    const lines = text.replace(/^\uFEFF/, '').split(LINE_BREAK);
    // A final newline terminates the preceding line without adding a blank line.
    if (lines.at(-1) === '') lines.pop();
    let version;
    let versionLine = 1;
    for (const [index, line] of lines.entries()) {
        const directive = DIRECTIVE.exec(line);
        if (!directive) break;
        if (directive[1] === 'format_version') {
            version = directive[2];
            versionLine = index + 1;
        }
    }
    if (version !== undefined && version !== '1') {
        report('unsupported', 'unsupported-format', versionLine);
        return result;
    }

    /** @type {Item | null} */
    let previous = null;
    let previousHasError = false;
    function finishItem() {
        if (previous && !previousHasError) validateTemporalDetails(previous, report);
        previous = null;
        previousHasError = false;
    }
    /** @type {Item[]} */
    const ancestors = [];
    // Collect join diagnostics before parsing the assembled lines, as Core does.
    const joinedLines = Array.from(logicalLines(lines, report));
    for (const { line, lineNumber } of joinedLines) {
        const visible = line.replace(/^ */, '');
        if (visible.startsWith('|')) {
            if (!previous) {
                report('error', 'orphan-body', lineNumber);
                continue;
            }
            const body = previous.details.find(([name]) => name === 'body');
            const content = visible.replace(/^\| ?/, '');
            if (!body) {
                previous.details.push(['body', [content]]);
            } else if (body[1].length === 0) {
                body[1].push(content);
            } else if (body[1].length === 1 && typeof body[1][0] === 'string') {
                body[1][0] += '\n' + content;
            } else {
                report('error', 'ambiguous-body', lineNumber);
                previousHasError = true;
            }
        } else {
            finishItem();
            if (/^[ \t]*$/.test(line) || visible.startsWith('#')) continue;
            const item = readItem(line, lineNumber, (severity, code, offset = 0) => {
                report(severity, code, lineNumber + offset);
                previousHasError ||= severity === 'error';
            });
            previous = item === UNCLOSED_JSON ? null : item;
            if (previous) {
                while (ancestors.length && ancestors.at(-1).indent >= previous.indent) {
                    ancestors.pop();
                }
                inferParent(previous, ancestors.at(-1), report);
                ancestors.push(previous);
                result.items.push(previous);
            }
        }
    }
    finishItem();
    return result;
}
