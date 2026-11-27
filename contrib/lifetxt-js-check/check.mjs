import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { MAX_BYTES, MAX_FILES, parse, parseDocuments } from './parser.mjs';

function escapeConsole(text) {
    return text.replace(/[^\x20-\x7e]/g, char =>
        '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
}

function quoteId(value) {
    return escapeConsole(JSON.stringify(value));
}
const usage = 'Usage: node check.mjs FILE [FILE ...]';

async function readInput(path) {
    const file = await open(path, constants.O_RDONLY | (constants.O_NONBLOCK ?? 0));
    try {
        if (!(await file.stat()).isFile()) throw new Error('Expected a regular file');
        const bytes = Buffer.alloc(MAX_BYTES + 1);
        let length = 0;
        while (length < bytes.length) {
            const { bytesRead } = await file.read(bytes, length, bytes.length - length);
            if (bytesRead === 0) break;
            length += bytesRead;
        }
        if (length > MAX_BYTES) throw new Error(`Input exceeds ${MAX_BYTES} UTF-8 bytes`);
        return new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(0, length));
    } finally {
        await file.close();
    }
}

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
    console.log(`${usage}\nChecks supported life.txt syntax and values.`);
} else if (args.length === 0 || args.length > MAX_FILES) {
    console.error(usage);
    if (args.length > MAX_FILES) console.error(`Pass at most ${MAX_FILES} files.`);
    process.exitCode = 2;
} else {
    try {
        const documents = [];
        for (const source of args) {
            try {
                documents.push({ source, text: await readInput(source) });
            } catch (error) {
                if (args.length === 1) throw error;
                throw new Error(`${quoteId(source)}: ${escapeConsole(error.message)}`);
            }
        }
        const result = documents.length === 1 ? parse(documents[0].text) : parseDocuments(documents);
        for (const { severity, code, line, key, part, firstLine, source, firstSource, value, path, childCount } of result.diagnostics) {
            const field = key ? ` (${escapeConsole(key)}:${part ? ` ${escapeConsole(part)}` : ''})` : '';
            let target = '';
            if (value !== undefined) {
                target = ` ${quoteId(value)}`;
                if (firstLine !== undefined) {
                    const firstFile = firstSource === undefined ? '' : `${quoteId(firstSource)}: `;
                    target += `, first seen at ${firstFile}line ${firstLine}`;
                }
            }
            if (path) target = ` ${path.map(quoteId).join(' -> ')}`;
            if (childCount !== undefined) target += `, ${childCount} open child item(s)`;
            const location = source === undefined ? `Line ${line}` : `${quoteId(source)}: line ${line}`;
            console.log(`${location}: ${severity} ${code}${field}${target}`);
        }
        if (result.diagnosticCount > result.diagnostics.length) {
            console.log(`${result.diagnosticCount - result.diagnostics.length} additional diagnostics omitted.`);
        }
        if (result.incomplete) console.log('Some input was not checked. Use lifetxt check for full validation.');
        if (result.hasErrors) process.exitCode = 1;
        else if (result.incomplete) process.exitCode = 3;
        else console.log('No errors in the checked input. Use lifetxt check for full validation.');
    } catch (error) {
        console.error(error.message);
        process.exitCode = 2;
    }
}
