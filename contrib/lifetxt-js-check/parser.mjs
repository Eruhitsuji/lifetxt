/** @typedef {{severity: 'error'|'warning'|'unsupported', code: string, line: number}} Diagnostic */
/** @typedef {{line: number, indent: number, status: string, type: string, title: string, details: [string, string[]][]}} Item */
/** @typedef {{items: Item[], diagnostics: Diagnostic[], diagnosticCount: number, hasErrors: boolean, incomplete: boolean}} ParseResult */

export const MAX_BYTES = 16_384;
const MAX_DIAGNOSTICS = 100;
const ITEM_START = /^( *)\[([ /x>N?-])\] +([TEDRHNSMJ]) +/;
const DIRECTIVE = /^#!\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$/;
const JOIN = /\\ *$/;
const encoder = new TextEncoder();

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

function readItem(line, lineNumber, report) {
    if (line.includes('\t')) {
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

    const details = new Map();
    let pos = title.end;
    while (pos < line.length) {
        while (line[pos] === ' ') pos++;
        if (pos === line.length) break;
        const key = /^[^ :"\t]+:/.exec(line.slice(pos));
        if (!key) {
            report('error', 'invalid-detail');
            return null;
        }
        const name = key[0].slice(0, -1);
        const value = readValue(line, pos + key[0].length, report);
        if (!value) return null;
        if (!details.has(name)) details.set(name, []);
        details.get(name).push(value.value);
        pos = value.end;
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

/** Check the supported Format 1 syntax without applying Core semantic rules.
 * @param {string} text
 * @returns {ParseResult}
 */
export function parse(text) {
    if (typeof text !== 'string') throw new TypeError('Expected text');
    /** @type {ParseResult} */
    const result = {
        items: [], diagnostics: [], diagnosticCount: 0, hasErrors: false, incomplete: false,
    };
    function report(severity, code, line) {
        result.diagnosticCount++;
        result.hasErrors ||= severity === 'error';
        result.incomplete ||= severity === 'unsupported';
        if (result.diagnostics.length < MAX_DIAGNOSTICS) {
            result.diagnostics.push({ severity, code, line });
        }
    }

    if (text.length > MAX_BYTES || encoder.encode(text).length > MAX_BYTES) {
        report('error', 'input-too-large', 1);
        return result;
    }

    const lines = text.replace(/^\uFEFF/, '').split(/\r\n|[\r\n]/);
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

    /** @type {Item | 'skipped' | null} */
    let previous = null;
    for (let index = 0; index < lines.length; index++) {
        const line = lines[index];
        const lineNumber = index + 1;
        const visible = line.replace(/^ */, '');
        if (JOIN.test(line)) {
            report('unsupported', 'line-join', lineNumber);
            while (index + 1 < lines.length && JOIN.test(lines[index])) index++;
            previous = 'skipped';
        } else if (visible.startsWith('|')) {
            if (previous === 'skipped') continue;
            if (!previous) {
                report('error', 'orphan-body', lineNumber);
                continue;
            }
            const body = previous.details.find(([name]) => name === 'body');
            const content = visible.replace(/^\| ?/, '');
            if (!body) {
                previous.details.push(['body', [content]]);
            } else if (body[1].length === 1) {
                body[1][0] += '\n' + content;
            } else {
                report('error', 'ambiguous-body', lineNumber);
            }
        } else if (/^[ \t]*$/.test(line) || visible.startsWith('#')) {
            previous = null;
        } else {
            previous = readItem(line, lineNumber, (severity, code) => report(severity, code, lineNumber));
            if (previous) result.items.push(previous);
        }
    }
    return result;
}
