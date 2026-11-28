/** @typedef {{severity: 'error'|'warning'|'unsupported', code: string, line: number, key?: string, part?: string, firstLine?: number, source?: string, firstSource?: string, value?: string, path?: string[], childCount?: number}} Diagnostic */
/** @typedef {null|boolean|number|string|JsonValue[]|{[key: string]: JsonValue}} JsonValue */
/** @typedef {{line: number, indent: number, status: string, type: string, title: string, details: [string, JsonValue[]][]}} Item */
/** @typedef {{items: Item[], diagnostics: Diagnostic[], diagnosticCount: number, hasErrors: boolean, incomplete: boolean}} ParseResult */

export const MAX_BYTES = 16_384;
export const MAX_FILES = 64;
export const MAX_DIAGNOSTICS = 100;
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
const KNOWN_KEYS = new Set([
    'id', 'source', 'uid', 'parent', 'ref', 'depends_on', 'requires', 'blocks', 'related',
    'created', 'updated', 'done', 'due', 'do', 'from', 'to', 'state', 'user', 'person',
    'owner', 'assignee', 'attendee', 'sender', 'recipient', 'team', 'group', 'service',
    'channel', 'visibility', 'notify_at', 'notify_from', 'notify_to', 'ack', 'snooze_until',
    'on', 'at', 'repeat', 'repeat_base', 'interval', 'until', 'count', 'elapsed', 'project',
    'context', 'loc', 'priority', 'importance', 'progress', 'est', 'tag', 'note', 'body',
    'mood', 'weather', 'url', 'reason', 'moved_to', 'file', 'dir',
]);
const KEY_STYLE = /^[a-z][a-z0-9_]*\n?$/;
// Core exempts record-owned fields from custom-key warnings (safety_compat_v2.py).
const RECORD_OWNED_KEYS = new Map([
    ['project', ['area', 'record']],
    ['milestone', ['record']],
    ['risk', ['record', 'severity']],
    ['issue', ['record', 'severity']],
    ['decision', ['record']],
    ['meeting', ['record']],
    ['ticket', [
        'branch', 'build', 'category', 'closed_by', 'commit', 'component', 'duplicate_of',
        'follows', 'milestone', 'pr', 'realizes', 'record', 'replaced_by', 'reporter',
        'resolution', 'severity', 'sprint', 'story_points', 'ticket_status', 'tracker',
        'version', 'watcher',
    ]],
    ['ticket_event', [
        'activity', 'author', 'change', 'event', 'from_status', 'provider', 'record', 'role',
        'sequence', 'sprint', 'ticket_revision', 'to_status', 'tracker', 'transaction',
        'version', 'watcher',
    ]],
    ['time_entry', [
        'activity', 'corrects', 'created_at', 'event_id', 'record', 'sequence', 'timer_ref',
    ]],
    ['progress_event', [
        'after_progress', 'before_missing', 'before_progress', 'operation', 'record',
        'sequence', 'source_revision', 'transaction',
    ]],
    ['item_event', [
        'actor', 'after', 'after_missing', 'after_status', 'before', 'before_missing',
        'before_status', 'completed_at', 'event', 'field', 'item_kind', 'item_title', 'record',
        'relation', 'sequence', 'source_revision', 'target', 'transaction',
    ]],
]);
const DATE_OR_DATETIME_KEYS = new Set([
    'created', 'updated', 'done', 'due', 'do', 'moved_to', 'notify_at',
    'notify_from', 'notify_to', 'ack', 'snooze_until', 'until',
]);
const DATE_VALUE = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_VALUE = /^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d)(?:\.(\d{1,6}))?)?(Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)?$/;
const MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
// Python's ID regex also matches before a single trailing LF in a JSON string.
const ID_VALUE = /^[A-Za-z0-9][A-Za-z0-9_.:@\/-]*\n?$/;
const REFERENCE_KEYS = [
    'parent', 'ref', 'depends_on', 'blocks', 'related',
    'duplicate_of', 'replaced_by', 'follows', 'realizes',
];
const OPEN_STATUSES = new Set(['[ ]', '[/]', '[>]', '[?]']);
const STATUS_STATES = new Set([
    'available', 'busy', 'away', 'offline', 'dnd', 'focus', 'sleeping',
    'commuting', 'working', 'studying', 'meeting', 'custom',
]);
const SIMPLE_REPEATS = new Set(['daily', 'weekly', 'monthly', 'yearly', 'weekdays']);
const RRULE_FREQUENCIES = new Set(['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']);
const RRULE_PARTS = new Set(['FREQ', 'INTERVAL', 'COUNT', 'UNTIL', 'BYDAY', 'BYMONTHDAY', 'BYMONTH', 'WKST']);
const WEEKDAYS = new Set(['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']);
const REQUIREMENT_STATES = new Set([
    'not_started', 'in_progress', 'done', 'canceled', 'moved', 'maybe', 'note',
    '[ ]', '[/]', '[x]', '[-]', '[>]', '[?]', '[N]',
]);

function requirementLeafProblem(id, states, targets) {
    if (typeof id !== 'string' || !id || /[\p{White_Space}\x1c-\x1f]/u.test(id)) return 'id';
    if (!states.length || states.some(state => !REQUIREMENT_STATES.has(state))) return 'state';
    targets?.add(id);
    return null;
}

function requirementProblem(value, depth = 0, targets) {
    if (depth > 32) return 'depth';
    if (typeof value === 'string') {
        const separator = value.lastIndexOf('=');
        return separator < 0 ? 'shape' :
            requirementLeafProblem(value.slice(0, separator), value.slice(separator + 1).split(','), targets);
    }
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return 'shape';

    const keys = Object.keys(value);
    if (keys.length === 2 && Object.hasOwn(value, 'id') && Object.hasOwn(value, 'state')) {
        const states = Array.isArray(value.state) ? value.state : [value.state];
        return requirementLeafProblem(value.id, states, targets);
    }
    if (keys.length !== 1) return 'shape';
    const [operator] = keys;
    const children = value[operator];
    if ((operator !== 'all' && operator !== 'any') || !Array.isArray(children) || !children.length) {
        return 'shape';
    }
    for (const child of children) {
        const problem = requirementProblem(child, depth + 1, targets);
        if (problem) return problem;
    }
    return null;
}

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

function recurrenceInteger(value) {
    const text = value.trim();
    if (!/^[+-]?\d(?:_?\d)*$/.test(text)) return NaN;
    return Number(text.replaceAll('_', ''));
}

function isPositiveInteger(value) {
    return recurrenceInteger(value) > 0;
}

function isProgress(value) {
    if (typeof value !== 'string') return false;
    const text = value.trim();
    const percent = /^(-?\d+(?:\.\d+)?)%$/.exec(text);
    if (percent) return Number(percent[1]) >= 0 && Number(percent[1]) <= 100;
    const fraction = /^(-?\d+)\/(-?\d+)$/.exec(text);
    if (!fraction) return false;
    const current = BigInt(fraction[1]);
    const total = BigInt(fraction[2]);
    return total > 0n && current >= 0n && current <= total;
}

function validateDuration(value, key, line, report) {
    const match = /^(?:(\d+)h(?:(\d+)m)?|(\d+)m?)$/.exec(value.trim().toLowerCase());
    if (!match) {
        report('warning', 'invalid-duration', line, key);
        return;
    }
    const total = BigInt(match[1] ?? '0') * 60n + BigInt(match[2] ?? match[3] ?? '0');
    const hours = total / 60n;
    const minutes = total % 60n;
    let compact = minutes + 'm';
    if (hours > 0n) {
        compact = hours + 'h';
        if (minutes > 0n) compact += String(minutes).padStart(2, '0') + 'm';
    }
    if (compact !== value) report('warning', 'noncompact-duration', line, key, { part: compact });
}

function isRruleUntil(value) {
    if (isDate(value) || isDateTime(value)) return true;
    const match = /^(\d{4})(\d{2})(\d{2})(?:[Tt](\d{2})(\d{2})(\d{2})(Z|[+-]\d{4})?)?$/.exec(value);
    if (!match) return false;
    const [, year, month, day, hour, minute, second, offset = ''] = match;
    return isDate(year + '-' + month + '-' + day) &&
        (hour === undefined || isTime(hour + ':' + minute + ':' + second + offset));
}

function isRruleNumberList(value, minimum, maximum) {
    return value.split(',').every(token => {
        const number = recurrenceInteger(token);
        return number >= minimum && number <= maximum && number !== 0;
    });
}

function rruleProblems(value) {
    const parts = new Map();
    let malformed = false;
    for (const chunk of value.slice('RRULE:'.length).split(';')) {
        const entry = chunk.trim();
        if (!entry) continue;
        const separator = entry.indexOf('=');
        if (separator < 0) {
            malformed = true;
            continue;
        }
        const key = entry.slice(0, separator).trim().toUpperCase();
        if (key) parts.set(key, entry.slice(separator + 1).trim());
    }

    // Match Core's initial warnings before running the stricter fallback
    // checks. The fallback contributes at most one warning.
    const problems = [];
    const freq = parts.get('FREQ')?.toUpperCase();
    if (!RRULE_FREQUENCIES.has(freq)) problems.push('FREQ');
    if ([...parts.keys()].some(key => !RRULE_PARTS.has(key))) problems.push('KEY');
    for (const key of ['INTERVAL', 'COUNT']) {
        if (parts.has(key) && !isPositiveInteger(parts.get(key))) problems.push(key);
    }
    const until = parts.get('UNTIL');
    if (until !== undefined && !isRruleUntil(until.toUpperCase())) problems.push('UNTIL');
    const byday = parts.get('BYDAY')?.split(',').map(token => token.trim().toUpperCase());
    if (byday?.some(token => !WEEKDAYS.has(token.slice(-2)) ||
        (token.length > 2 && freq && freq !== 'MONTHLY' && freq !== 'YEARLY'))) {
        problems.push('BYDAY');
    }
    if (problems.length) return problems;

    if (malformed) return ['KEY=VALUE'];
    for (const key of RRULE_PARTS) {
        if (parts.get(key) === '') return [key];
    }
    if (until !== undefined && !isRruleUntil(until)) return ['UNTIL'];
    if (byday?.some(token => {
        if (token.length <= 2) return false;
        const position = recurrenceInteger(token.slice(0, -2));
        return Number.isNaN(position) || position === 0;
    })) return ['BYDAY'];
    if (parts.has('BYMONTHDAY') && !isRruleNumberList(parts.get('BYMONTHDAY'), -31, 31)) return ['BYMONTHDAY'];
    if (parts.has('BYMONTH') && !isRruleNumberList(parts.get('BYMONTH'), 1, 12)) return ['BYMONTH'];
    if (parts.has('WKST') && !WEEKDAYS.has(parts.get('WKST').toUpperCase())) return ['WKST'];
    if (freq === 'WEEKLY' && parts.has('BYMONTHDAY')) return ['BYMONTHDAY'];
    return [];
}

function validateRepeat(value, line, report) {
    if (SIMPLE_REPEATS.has(value)) return;
    if (!value.startsWith('RRULE:')) {
        report('warning', 'invalid-repeat', line, 'repeat');
        return;
    }
    for (const part of rruleProblems(value)) {
        report('warning', 'invalid-rrule', line, 'repeat', { part });
    }
}

function wallClock(value) {
    const [date, time] = value.split('T');
    const [, hour, minute, second = '00', fraction = '', offset] = TIME_VALUE.exec(time);
    const zone = !offset || offset === 'Z' ? 'Z' : offset.replace(/:?([0-5]\d)$/, ':$1');
    const clock = new Date(`${date}T${hour}:${minute}:${second}${zone}`);
    if (!offset) return [clock.getTime(), fraction.padEnd(6, '0')];

    // Core compares offset-aware values as local wall-clock fields. Encode
    // those fields as UTC solely to order them alongside offsetless values.
    const localYear = clock.getFullYear();
    if (localYear < 1 || localYear > 9999) return null;
    const wall = new Date(0);
    wall.setUTCFullYear(localYear, clock.getMonth(), clock.getDate());
    wall.setUTCHours(clock.getHours(), clock.getMinutes(), clock.getSeconds());
    return [wall.getTime(), fraction.padEnd(6, '0')];
}

function isReversedRange(from, to) {
    if (typeof from !== 'string' || typeof to !== 'string' ||
        !isDateTime(from) || !isDateTime(to)) return false;
    const start = wallClock(from);
    const end = wallClock(to);
    return start !== null && end !== null &&
        (end[0] < start[0] || (end[0] === start[0] && end[1] < start[1]));
}

function validateEventRange(item, report) {
    const from = item.details.find(([key]) => key === 'from')?.[1][0];
    const to = item.details.find(([key]) => key === 'to')?.[1][0];
    if (isReversedRange(from, to)) {
        report('warning', 'event-end-before-start', item.line, 'to');
    }
}

function validateStatusItem(item, report) {
    const details = new Map(item.details);
    const start = details.get('from');
    const end = details.get('to');
    if (!start) report('error', 'status-missing-from', item.line, 'from');
    for (const value of start ?? []) {
        if (!isDateTime(value)) report('error', 'status-invalid-from', item.line, 'from');
    }
    if (!details.has('state')) report('error', 'status-missing-state', item.line, 'state');
    for (const value of end ?? []) {
        if (!isDateTime(value)) report('error', 'status-invalid-to', item.line, 'to');
    }
    if (end && item.status !== '[x]') {
        report('warning', 'status-closed-marker', item.line, 'to');
    } else if (!end && item.status !== '[/]') {
        report('warning', 'status-open-marker', item.line, 'to');
    }
}

function validateMessageItem(item, report) {
    const details = new Map(item.details);
    if (!details.has('sender')) report('error', 'message-missing-sender', item.line, 'sender');
    if (!details.has('recipient')) report('error', 'message-missing-recipient', item.line, 'recipient');

    const start = details.get('notify_from');
    const end = details.get('notify_to');
    if (start && end) {
        const from = isDate(start[0]) ? start[0] + 'T00:00' : start[0];
        const to = isDate(end[0]) ? end[0] + 'T23:59:59' : end[0];
        if (isReversedRange(from, to)) {
            report('warning', 'notification-end-before-start', item.line, 'notify_to');
        }
    } else if (start || end) {
        report('warning', 'notification-missing-boundary', item.line, start ? 'notify_to' : 'notify_from');
    }

    if (item.status === '[N]') report('warning', 'message-workflow-marker', item.line);
}

function validateItemMarker(item, report) {
    const isNote = item.type === 'N' || item.type === 'J';
    if (item.status === '[N]' && !isNote) {
        report('warning', 'note-marker-with-actionable-type', item.line);
    } else if (item.status !== '[N]' && isNote) {
        report('warning', 'note-item-with-workflow-marker', item.line);
    }
    const hasDone = item.details.some(([key]) => key === 'done');
    if (item.status === '[x]' && !hasDone && item.type !== 'S') {
        report('warning', 'completed-item-missing-done', item.line, 'done');
    } else if (item.status !== '[x]' && hasDone) {
        report('warning', 'done-without-completed-marker', item.line, 'done');
    }
}

function validateItemDetails(item, report) {
    validateItemMarker(item, report);
    const record = item.details.find(([key]) => key === 'record')?.[1][0];
    const recordKeys = RECORD_OWNED_KEYS.get(typeof record === 'string' ? record.toLowerCase() : record);
    let hasTypeError = false;
    for (const [key, values] of item.details) {
        if (key === 'requires') {
            for (const value of values) {
                const problem = requirementProblem(value);
                if (problem) report('error', 'invalid-requires', item.line, key, { part: problem });
            }
            continue;
        }
        const known = KNOWN_KEYS.has(key);
        if ((known || REFERENCE_KEYS.includes(key)) && values.some(value => typeof value !== 'string')) {
            report('error', 'detail-expects-text', item.line, key);
            hasTypeError = true;
            continue;
        }
        if (key === 'importance' &&
            (values.length !== 1 || !['high', 'normal', 'low'].includes(values[0]))) {
            report('warning', 'invalid-importance', item.line, key);
        }
        if (!KEY_STYLE.test(key)) report('warning', 'detail-key-style', item.line, key);
        if (!known && !recordKeys?.includes(key)) report('warning', 'custom-detail-key', item.line, key);

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
        } else if (key === 'interval' || key === 'count') {
            code = 'expected-positive-integer';
            accepts = isPositiveInteger;
        } else if (key === 'id') {
            code = 'invalid-id';
            accepts = value => ID_VALUE.test(value);
        } else if (key === 'state') {
            code = 'unknown-state';
            accepts = value => STATUS_STATES.has(value);
        } else if (key === 'progress') {
            code = 'invalid-progress';
            accepts = isProgress;
        } else if (REFERENCE_KEYS.includes(key)) {
            code = 'invalid-reference-id';
            accepts = value => ID_VALUE.test(value);
        }
        for (const value of values) {
            if (key === 'repeat') validateRepeat(value, item.line, report);
            else if (key === 'est' || key === 'elapsed') validateDuration(value, key, item.line, report);
            else if (accepts && !accepts(value)) report('warning', code, item.line, key);
        }
    }
    if (item.type === 'E' && !hasTypeError) validateEventRange(item, report);
    if (item.type === 'S' && !hasTypeError) validateStatusItem(item, report);
    if (item.type === 'M' && !hasTypeError) validateMessageItem(item, report);
}

function indexIds(items, report, idKey) {
    const index = new Map();
    for (const item of items) {
        const values = item.details.find(([key]) => key === idKey)?.[1] ?? [];
        for (const value of values) {
            if (typeof value !== 'string' || !value) continue;
            const entry = index.get(value);
            if (!entry) {
                index.set(value, { item, count: 1 });
            } else {
                entry.count++;
                report('warning', 'duplicate-id', item.line, idKey, { firstLine: entry.item.line, value });
            }
        }
    }
    return index;
}

const PROGRESS_EVENT_FIELDS = [
    'id', 'parent', 'at', 'sequence', 'transaction',
    'source_revision', 'operation', 'after_progress',
];

function normalizedEventTimestamp(value) {
    if (typeof value !== 'string') return null;
    const text = value.trim().replace(' ', 'T');
    if (!isDateTime(text) || !/(?:Z|[+-]\d{2}:?\d{2})$/.test(text)) return null;
    const epoch = Date.parse(text.replace(/\.(\d+)(?=Z|[+-]\d)/, ''));
    if (!Number.isFinite(epoch)) return null;
    const utc = new Date(epoch).toISOString();
    return utc.length === 24 && !utc.startsWith('0000') ? utc.replace('.000Z', 'Z') : null;
}

function eventSequence(value) {
    const text = String(value).trim();
    return /^[+-]?\d(?:_?\d)*$/.test(text) ? BigInt(text.replaceAll('_', '')) : 0n;
}

function historyEventId(prefix, parent, sequence) {
    const safeParent = String(parent).replace(/[^A-Za-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '') || 'item';
    return prefix + '-' + safeParent + '-' + String(sequence).padStart(6, '0');
}

function reportProgressHistory(items, report, idKey) {
    const events = [];
    const parents = new Map();
    for (const item of items) {
        const details = new Map(item.details);
        if (item.type === 'N' && details.get('record')?.includes('progress_event')) {
            events.push({ item, details });
            continue;
        }
        for (const id of details.get(idKey) ?? []) {
            if (typeof id !== 'string') continue;
            const matches = parents.get(id) ?? [];
            matches.push(details);
            parents.set(id, matches);
        }
    }

    const ids = new Set();
    const transactions = new Set();
    const histories = new Map();
    for (const { item, details } of events) {
        const values = key => details.get(key) ?? [];
        const first = key => values(key)[0];
        const warn = (code, key, part) => report('warning', code, item.line, key, part ? { part } : undefined);
        const missing = PROGRESS_EVENT_FIELDS.filter(key => !values(key).length);
        const repeated = PROGRESS_EVENT_FIELDS.filter(key => values(key).length > 1);
        if (missing.length) warn('progress-event-missing', 'record', missing.join(', '));
        if (repeated.length) warn('progress-event-repeated', 'record', repeated.join(', '));

        const parent = first('parent');
        if (parent && parents.get(parent)?.length !== 1) warn('progress-event-parent', 'parent');
        const timestamp = normalizedEventTimestamp(first('at'));
        if (timestamp === null || timestamp !== first('at')) warn('progress-event-timestamp', 'at');
        const sequence = eventSequence(first('sequence'));
        if (sequence <= 0n) warn('progress-event-sequence', 'sequence');
        const revision = first('source_revision');
        if (revision && !/^[0-9a-f]{64}\n?$/.test(revision)) warn('progress-event-revision', 'source_revision');
        const operation = first('operation');
        if (operation && operation !== 'set' && operation !== 'delta') warn('progress-event-operation', 'operation');

        const before = values('before_progress');
        const after = values('after_progress');
        const missingValues = values('before_missing');
        const beforeMissing = missingValues.length === 1 && missingValues[0] === 'true';
        if (beforeMissing === Boolean(before.length)) warn('progress-event-before-choice', 'before_progress');
        if (missingValues.length && !beforeMissing) warn('progress-event-before-flag', 'before_missing');
        if (beforeMissing && operation === 'delta') warn('progress-event-delta-missing', 'before_missing');
        if (beforeMissing && sequence > 1n) warn('progress-event-late-missing', 'before_missing');
        for (const [key, list] of [['before_progress', before], ['after_progress', after]]) {
            if (list.length > 1) warn('progress-event-progress-repeated', key);
            for (const value of list) {
                if (!isProgress(value)) warn('progress-event-invalid-progress', key);
            }
        }

        const id = first('id');
        const transaction = first('transaction');
        for (const [value, seen, key] of [[id, ids, 'id'], [transaction, transactions, 'transaction']]) {
            if (!value) continue;
            if (seen.has(value)) warn('progress-event-duplicate', key);
            seen.add(value);
        }
        if (!parent || sequence <= 0n) continue;
        let history = histories.get(parent);
        if (!history) {
            history = { sequences: new Set(), rows: [] };
            histories.set(parent, history);
        }
        if (history.sequences.has(sequence)) warn('progress-event-duplicate', 'sequence');
        history.sequences.add(sequence);
        history.rows.push({ line: item.line, timestamp, sequence, before, after });
        const expectedId = historyEventId('PE', parent, sequence);
        if (id && id !== expectedId) warn('progress-event-id-mismatch', 'id');
    }

    for (const [parent, { sequences, rows }] of histories) {
        rows.sort((a, b) => a.sequence < b.sequence ? -1 : Number(a.sequence > b.sequence));
        const latest = rows.at(-1);
        if (latest.sequence !== BigInt(sequences.size)) {
            report('warning', 'progress-history-gap', latest.line, 'sequence');
        }
        for (let i = 1; i < rows.length; i++) {
            const previous = rows[i - 1];
            const current = rows[i];
            if (previous.after.length && current.before.length && previous.after[0] !== current.before[0]) {
                report('warning', 'progress-history-discontinuous', current.line, 'before_progress');
            }
            if (previous.timestamp && current.timestamp && previous.timestamp > current.timestamp) {
                report('warning', 'progress-history-time-order', current.line, 'at');
            }
        }
        const matches = parents.get(parent);
        if (latest.after.length && matches?.length === 1 &&
            matches[0].get('progress')?.[0] !== latest.after[0]) {
            report('warning', 'progress-history-current-mismatch', latest.line, 'progress');
        }
    }
}

const ITEM_EVENT_FIELDS = ['record', 'id', 'parent', 'event', 'at', 'sequence', 'transaction', 'source_revision'];
const ITEM_EVENT_OPTIONAL = ['actor', 'source', 'remote_operation', 'remote_request_hash'];
const STATUS_CHANGE_EVENTS = new Set(['status_changed', 'completed', 'reopened', 'canceled']);
const ITEM_EVENT_PAYLOAD = new Map([
    ['created', ['item_kind', 'item_title', 'after_status']],
    ['edited', ['item_kind', 'item_title', 'after_status']],
    ['deleted', ['item_kind', 'item_title', 'before_status']],
    ...Array.from(STATUS_CHANGE_EVENTS, type => [type, ['before_status', 'after_status']]),
    ['relation_added', ['relation', 'target']],
    ['relation_removed', ['relation', 'target']],
    ['schedule_changed', ['field']],
]);

function validateItemEvent(details, type, sequence, warn) {
    const values = key => details.get(key) ?? [];
    const first = key => values(key)[0];
    const warnFields = (code, fields) => {
        if (fields.length) warn(code, 'record', fields.join(', '));
    };
    warnFields('item-event-missing', ITEM_EVENT_FIELDS.filter(key => !values(key).length));
    warnFields('item-event-cardinality', ITEM_EVENT_FIELDS.filter(key => values(key).length !== 1));

    const payload = ITEM_EVENT_PAYLOAD.get(type);
    if (type && !payload) warn('item-event-type', 'event');
    const allowed = new Set([...ITEM_EVENT_FIELDS, ...ITEM_EVENT_OPTIONAL, ...(payload ?? [])]);
    if (type === 'completed') allowed.add('completed_at');
    if (type === 'schedule_changed') {
        for (const key of ['before', 'after', 'before_missing', 'after_missing']) allowed.add(key);
    }
    if (payload) warnFields('item-event-payload', payload.filter(key => values(key).length !== 1));
    warnFields('item-event-unknown-field', [...details.keys()].filter(key => !allowed.has(key)).sort());
    warnFields('item-event-repeated', [...allowed].filter(key => values(key).length > 1).sort());

    const timestamp = normalizedEventTimestamp(first('at'));
    if (!timestamp || timestamp !== first('at')) warn('item-event-timestamp', 'at');
    if (sequence <= 0n) warn('item-event-sequence', 'sequence');
    if (first('source_revision') && !/^[0-9a-f]{64}\n?$/.test(first('source_revision'))) {
        warn('item-event-revision', 'source_revision');
    }
    if (type === 'relation_added' || type === 'relation_removed') {
        const relation = first('relation');
        if (relation && !['follows', 'realizes', 'replaced_by'].includes(relation)) {
            warn('item-event-field', 'relation');
        }
    }
    if (type === 'schedule_changed') {
        const field = first('field');
        if (field && !['on', 'due', 'from', 'to', 'at'].includes(field)) warn('item-event-field', 'field');
        for (const side of ['before', 'after']) {
            const flags = values(side + '_missing');
            const validMissing = flags.length === 1 && flags[0] === 'true';
            if ((values(side).length === 1) === validMissing || (flags.length && !validMissing)) {
                warn('item-event-schedule-value', side);
            }
        }
    }
    if (STATUS_CHANGE_EVENTS.has(type) && first('before_status') &&
        first('before_status') === first('after_status')) warn('item-event-unchanged-status', 'after_status');
}

function itemEventDateTime(value) {
    if (typeof value !== 'string') return null;
    const text = value.trim().replace(' ', 'T');
    if (isDate(text)) return text + 'T00:00';
    return isDateTime(text) ? text : null;
}

function reportItemEventHistory(items, report, idKey) {
    const parents = new Map();
    const events = [];
    for (const item of items) {
        const details = new Map(item.details);
        if (item.type === 'N' && details.get('record')?.includes('item_event')) {
            events.push({ item, details });
            continue;
        }
        for (const value of details.get(idKey) ?? []) {
            if (typeof value !== 'string') continue;
            const matches = parents.get(value) ?? [];
            matches.push(item);
            parents.set(value, matches);
        }
    }

    const ids = new Set();
    const transactions = new Set();
    const histories = new Map();
    for (const { item, details } of events) {
        const first = key => details.get(key)?.[0];
        const warn = (code, key, part) => report('warning', code, item.line, key, part ? { part } : undefined);
        const sequence = eventSequence(first('sequence'));
        const type = first('event');
        validateItemEvent(details, type, sequence, warn);
        const parent = first('parent');
        if (parent && parents.get(parent)?.length !== 1) warn('item-event-parent', 'parent');
        const id = first('id');
        for (const [key, value, seen] of [['id', id, ids], ['transaction', first('transaction'), transactions]]) {
            if (!value) continue;
            if (seen.has(value)) warn('item-event-duplicate', key);
            seen.add(value);
        }
        if (!parent || sequence <= 0n) continue;
        let history = histories.get(parent);
        if (!history) {
            history = { sequences: new Set(), rows: [] };
            histories.set(parent, history);
        }
        if (history.sequences.has(sequence)) warn('item-event-duplicate', 'sequence');
        history.sequences.add(sequence);
        if (id && id !== historyEventId('IE', parent, sequence)) warn('item-event-id-mismatch', 'id');
        history.rows.push({
            line: item.line, sequence, type, at: itemEventDateTime(first('at')),
            before: first('before_status') ?? '', after: first('after_status') ?? '',
        });
    }

    for (const [parent, { sequences, rows }] of histories) {
        rows.sort((a, b) => a.sequence < b.sequence ? -1 : Number(a.sequence > b.sequence));
        const earliest = rows[0];
        const latest = rows.at(-1);
        const start = earliest.type === 'created' ? 1n : earliest.sequence;
        if (latest.sequence - start + 1n !== BigInt(sequences.size)) {
            report('warning', 'item-history-gap', latest.line, 'sequence');
        }
        let previousStatus;
        let previousAt;
        for (const event of rows) {
            if (isReversedRange(previousAt, event.at)) report('warning', 'item-history-time-order', event.line, 'at');
            if (event.at) previousAt = event.at;
            if (event.type === 'created') {
                if (event !== earliest || event.sequence !== 1n) {
                    report('warning', 'item-history-creation-order', event.line, 'sequence');
                }
                previousStatus = event.after;
            } else if (STATUS_CHANGE_EVENTS.has(event.type)) {
                if (previousStatus !== undefined && previousStatus !== event.before) {
                    report('warning', 'item-history-discontinuous', event.line, 'before_status');
                }
                previousStatus = event.after;
            }
        }
        const matches = parents.get(parent);
        if (matches?.length === 1 && previousStatus !== undefined && matches[0].status !== previousStatus) {
            report('warning', 'item-history-current-mismatch', latest.line, 'after_status');
        }
    }
}

function reportReferences(items, index, report, idKey) {
    function check(item, sourceIds, key, value) {
        if (typeof value !== 'string') return;
        let code;
        if (sourceIds.has(value)) code = 'self-reference';
        else if (!index.has(value)) code = 'missing-reference';
        else if (index.get(value).count > 1) code = 'ambiguous-reference';
        else return;
        report('warning', code, item.line, key, { value });
    }

    for (const item of items) {
        const details = new Map(item.details);
        const sourceIds = new Set((details.get(idKey) ?? []).filter(id => typeof id === 'string' && id));
        for (const key of REFERENCE_KEYS) {
            for (const value of details.get(key) ?? []) check(item, sourceIds, key, value);
        }
    }
    reportCycles(index, report);
    reportTemporalOrder(items, index, report, idKey);
    reportCompletedDependencies(items, index, report);
    // Core reports requires references after the regular link and cycle diagnostics.
    for (const item of items) {
        const details = new Map(item.details);
        const conditions = details.get('requires');
        if (!conditions?.length) continue;
        const sourceIds = new Set((details.get(idKey) ?? []).filter(id => typeof id === 'string' && id));
        for (const condition of conditions) {
            const targets = new Set();
            if (requirementProblem(condition, 0, targets)) continue;
            for (const value of targets) check(item, sourceIds, 'requires', value);
        }
    }
}

function reportCompletedDependencies(items, index, report) {
    for (const item of items) {
        if (item.status !== '[x]') continue;
        for (const value of item.details.find(([key]) => key === 'depends_on')?.[1] ?? []) {
            const target = index.get(value);
            if (target?.count === 1 && target.item !== item && OPEN_STATUSES.has(target.item.status)) {
                report('warning', 'completed-with-open-dependency', item.line, 'depends_on', { value });
            }
        }
    }
}

function reportClosedParents(items, report, idKey) {
    const parents = new Map();
    const openChildren = new Map();
    for (const item of items) {
        const details = new Map(item.details);
        // Core's parent check uses the last item with the ID, even when
        // duplicate IDs are diagnosed elsewhere.
        for (const id of details.get(idKey) ?? []) {
            if (typeof id === 'string') parents.set(id, item);
        }
        for (const id of details.get('parent') ?? []) {
            if (typeof id !== 'string') continue;
            const count = openChildren.get(id) ?? 0;
            openChildren.set(id, count + Number(OPEN_STATUSES.has(item.status)));
        }
    }
    for (const [value, childCount] of openChildren) {
        const parent = parents.get(value);
        if (childCount && (parent?.status === '[x]' || parent?.status === '[-]')) {
            report('warning', 'closed-parent-with-open-children', parent.line, idKey, { value, childCount });
        }
    }
}

function comparableDate(details) {
    for (const key of ['due', 'do', 'on', 'from']) {
        const value = details.get(key)?.[0];
        if (typeof value !== 'string') continue;
        // Core uses the calendar date as written, including for offset datetimes.
        if (isDate(value) || isDateTime(value)) return value.slice(0, 10);
    }
    return null;
}

function reportTemporalOrder(items, index, report, idKey) {
    for (const item of items) {
        const details = new Map(item.details);
        const follows = details.get('follows') ?? [];
        const replacements = details.get('replaced_by') ?? [];
        if (!follows.length && !replacements.length) continue;
        const ids = (details.get(idKey) ?? []).filter(id => typeof id === 'string' && id);
        if (index.get(ids[0])?.count !== 1) continue;
        const date = comparableDate(details);
        if (!date) continue;

        // Core emits replaced_by before follows for each item.
        for (const [key, references] of [['replaced_by', replacements], ['follows', follows]]) {
            for (const value of references) {
                const target = index.get(value);
                if (target?.count !== 1 || target.item === item) continue;
                const targetDate = comparableDate(new Map(target.item.details));
                if (!targetDate) continue;
                if (key === 'follows' ? date < targetDate : targetDate < date) {
                    report('warning', 'temporal-reference-order', item.line, key, { value });
                }
            }
        }
    }
}

function* cyclePaths(edges) {
    const visited = new Set();
    const active = new Map();
    const reported = new Set();
    const stack = [];
    function enter(id) {
        active.set(id, stack.length);
        stack.push({ id, targets: edges.get(id).values() });
    }

    for (const root of edges.keys()) {
        if (visited.has(root)) continue;
        enter(root);
        while (stack.length) {
            const frame = stack.at(-1);
            const { value: target, done } = frame.targets.next();
            if (done) {
                stack.pop();
                active.delete(frame.id);
                visited.add(frame.id);
            } else if (active.has(target)) {
                const path = stack.slice(active.get(target)).map(entry => entry.id);
                const signature = JSON.stringify([...path].sort());
                if (!reported.has(signature)) {
                    reported.add(signature);
                    yield [...path, target];
                }
            } else if (!visited.has(target)) {
                enter(target);
            }
        }
    }
}

function reportCycles(index, report) {
    const owners = new Map();
    for (const [id, entry] of index) {
        if (entry.count === 1) owners.set(id, entry.item);
    }
    for (const key of ['parent', 'depends_on', 'duplicate_of', 'replaced_by', 'follows', 'realizes']) {
        const edges = new Map();
        for (const [id, item] of owners) {
            const values = item.details.find(([name]) => name === key)?.[1] ?? [];
            edges.set(id, new Set(values.filter(target => owners.has(target))));
        }
        if (key === 'depends_on') {
            for (const [id, item] of owners) {
                const blocks = item.details.find(([name]) => name === 'blocks')?.[1] ?? [];
                for (const target of blocks) edges.get(target)?.add(id);
            }
        }
        for (const path of cyclePaths(edges)) {
            report('warning', 'reference-cycle', owners.get(path[0]).line, key, { path });
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

function inferParent(item, ancestor, report, idKey) {
    const parent = item.details.find(([name]) => name === 'parent');
    if (item.indent === 0 || parent?.[1].length) return;

    if (!ancestor) {
        report('warning', 'indent-no-parent', item.line);
        return;
    }
    const ids = ancestor.details.find(([name]) => name === idKey)?.[1];
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

function collectDiagnostics() {
    /** @type {ParseResult} */
    const result = {
        items: [], diagnostics: [], diagnosticCount: 0, hasErrors: false, incomplete: false,
    };
    function report(severity, code, line, key, fields) {
        result.diagnosticCount++;
        result.hasErrors ||= severity === 'error';
        result.incomplete ||= severity === 'unsupported';
        if (result.diagnostics.length < MAX_DIAGNOSTICS) {
            const diagnostic = { severity, code, line, ...fields };
            if (key !== undefined) diagnostic.key = key;
            result.diagnostics.push(diagnostic);
        }
    }
    return { result, report };
}

function parseDocument(text, report, idKey) {
    if (typeof text !== 'string') throw new TypeError('Expected text');
    /** @type {Item[]} */
    const items = [];
    if (text.length > MAX_BYTES || encoder.encode(text).length > MAX_BYTES) {
        report('error', 'input-too-large', 1);
        return items;
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
        return items;
    }

    /** @type {Item | null} */
    let previous = null;
    let previousHasError = false;
    function finishItem() {
        if (previous && !previousHasError) validateItemDetails(previous, report);
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
                inferParent(previous, ancestors.at(-1), report, idKey);
                ancestors.push(previous);
                items.push(previous);
            }
        }
    }
    finishItem();
    return items;
}

function checkItemSet(items, report, idKey) {
    const idIndex = indexIds(items, report, idKey);
    reportReferences(items, idIndex, report, idKey);
    reportClosedParents(items, report, idKey);
    reportProgressHistory(items, report, idKey);
    reportItemEventHistory(items, report, idKey);
}

/** Check supported Format 1 syntax, hierarchy and selected field values.
 * @param {string} text
 * @param {{idKey?: string}} [options]
 * @returns {ParseResult}
 */
export function parse(text, { idKey = 'id' } = {}) {
    const { result, report } = collectDiagnostics();
    result.items = parseDocument(text, report, idKey);
    checkItemSet(result.items, report, idKey);
    return result;
}

/** Check independent documents with a shared ID and reference index.
 * @param {{source: string, text: string}[]} documents
 * @param {{idKey?: string}} [options]
 */
export function parseDocuments(documents, { idKey = 'id' } = {}) {
    const { result, report } = collectDiagnostics();
    const locations = [];
    const sharedItems = [];
    for (const { source, text } of documents) {
        const items = parseDocument(text, (severity, code, line, key, fields) => {
            report(severity, code, line, key, { ...fields, source });
        }, idKey);
        for (const item of items) {
            const locationIndex = locations.length;
            locations.push({ source, line: item.line });
            result.items.push({ ...item, source });
            // The shared passes use a unique location index. Preserve the
            // original file and physical line for every reported location.
            sharedItems.push({ ...item, line: locationIndex });
        }
    }
    checkItemSet(sharedItems, (severity, code, locationIndex, key, fields) => {
        const { source, line } = locations[locationIndex];
        const first = locations[fields?.firstLine];
        const original = first ? { firstLine: first.line, firstSource: first.source } : {};
        report(severity, code, line, key, { ...fields, source, ...original });
    }, idKey);
    return result;
}

/** Read supported checker settings. The browser only uses the ID key. */
export function parseCheckerConfig(text) {
    const config = JSON.parse(text);
    if (!config || typeof config !== 'object' || Array.isArray(config)) {
        throw new Error('Expected a JSON object');
    }
    const options = {};
    if (config.attachments && typeof config.attachments === 'object' && !Array.isArray(config.attachments)) {
        options.attachments = config.attachments;
    }
    for (const value of [config.ids?.key, config.api?.id_key]) {
        if (value === undefined || value === null || value === '') continue;
        if (typeof value !== 'string' || /[\s:"]/.test(value)) {
            throw new Error('Expected ids.key or api.id_key to be a detail key');
        }
        options.idKey = value;
        break;
    }
    return options;
}

const HASH_MARKER = '#sha256=';

/** Split an attachment value and validate any hash fragment. */
export function splitAttachmentValue(value) {
    const text = value.trim();
    const separator = text.lastIndexOf(HASH_MARKER);
    const rawPath = separator < 0 ? text : text.slice(0, separator);
    const path = rawPath.trim().replaceAll('\\', '/');
    const digest = separator < 0 ? '' : text.slice(separator + HASH_MARKER.length).trim();
    if (!path || path.includes('\0') || !/^[0-9a-f]*$/i.test(digest)) {
        return null;
    }
    return { path, rawPath, digest: digest.toLowerCase() };
}

export function attachmentPath(value) {
    return splitAttachmentValue(value)?.path ?? null;
}

// Match the Python checker's default attachment settings.
export const DIRECTORY_IGNORES = Object.freeze([
    '.git', '.hg', '.svn', '.venv', 'venv', '__pycache__', 'node_modules',
    '.mypy_cache', '.pytest_cache', '.DS_Store', 'Thumbs.db',
]);
export const MAX_DIRECTORY_FILES = 2000;
export const MAX_DIRECTORY_BYTES = 200 * 1024 * 1024;
