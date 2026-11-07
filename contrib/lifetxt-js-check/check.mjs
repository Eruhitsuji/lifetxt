import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { MAX_BYTES, parse } from './parser.mjs';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
    console.log('Usage: node check.mjs FILE\nChecks supported life.txt syntax only.');
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
        for (const { severity, code, line } of result.diagnostics) {
            console.log(`Line ${line}: ${severity} ${code}`);
        }
        if (result.diagnosticCount > result.diagnostics.length) {
            console.log(`${result.diagnosticCount - result.diagnostics.length} additional diagnostics omitted.`);
        }
        if (result.incomplete) console.log('Some syntax was not checked. Use lifetxt check for full validation.');
        if (result.hasErrors) process.exitCode = 1;
        else if (result.incomplete) process.exitCode = 3;
        else console.log('No errors in the checked syntax. Semantic checks require lifetxt check.');
    } catch (error) {
        console.error(error.message);
        process.exitCode = 2;
    }
}
