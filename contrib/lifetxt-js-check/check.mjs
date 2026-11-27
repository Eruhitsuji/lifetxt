import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { MAX_BYTES, parse } from './parser.mjs';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
    console.log('Usage: node check.mjs FILE\nChecks supported life.txt syntax and values.');
} else if (args.length !== 1) {
    console.error('Usage: node check.mjs FILE');
    process.exitCode = 2;
} else {
    try {
        const file = await open(args[0], constants.O_RDONLY | (constants.O_NONBLOCK ?? 0));
        let result;
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
            result = parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(0, length)));
        } finally {
            await file.close();
        }
        for (const { severity, code, line, key, part, firstLine, value } of result.diagnostics) {
            const field = key ? ` (${key}:${part ? ` ${part}` : ''})` : '';
            let target = '';
            if (value !== undefined) {
                const escaped = JSON.stringify(value).replace(/[^\x20-\x7e]/g, char =>
                    '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
                target = ` ${escaped}`;
                if (firstLine !== undefined) target += `, first seen at line ${firstLine}`;
            }
            console.log(`Line ${line}: ${severity} ${code}${field}${target}`);
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
