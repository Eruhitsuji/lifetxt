import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { checkAttachments } from './attachments.mjs';
import { MAX_BYTES, MAX_FILES, parse, parseCheckerConfig, parseDocuments } from './parser.mjs';

function escapeConsole(text) {
    return text.replace(/[^\x20-\x7e]/g, char =>
        '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
}

function quoteId(value) {
    return escapeConsole(JSON.stringify(value));
}
const usage = 'Usage: node check.mjs [--config PATH] [--check-files | --verify-files] FILE [FILE ...]';

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

async function readConfig(path) {
    try {
        return parseCheckerConfig(await readInput(path));
    } catch (error) {
        throw new Error(`Config ${quoteId(path)}: ${escapeConsole(error.message)}`);
    }
}

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
    console.log(`${usage}\nChecks supported life.txt syntax and values.`);
} else {
    let configPath;
    let checkFilesOption = false;
    let verifyFiles = false;
    while (['--config', '--check-files', '--verify-files'].includes(args[0])) {
        const option = args.shift();
        if (option === '--config') {
            configPath = args.shift();
        } else {
            checkFilesOption = true;
            verifyFiles ||= option === '--verify-files';
        }
    }
    if (args[0] === '--') args.shift();
    if (args.length === 0 || args.length > MAX_FILES) {
        console.error(usage);
        if (args.length > MAX_FILES) console.error(`Pass at most ${MAX_FILES} files.`);
        process.exitCode = 2;
    } else {
        await checkFiles(args, configPath, { checkFilesOption, verifyFiles });
    }
}

async function checkFiles(paths, configPath, { checkFilesOption, verifyFiles }) {
    try {
        const options = configPath === undefined ? {} : await readConfig(configPath);
        const documents = [];
        for (const source of paths) {
            try {
                documents.push({ source, text: await readInput(source) });
            } catch (error) {
                if (paths.length === 1) throw error;
                throw new Error(`${quoteId(source)}: ${escapeConsole(error.message)}`);
            }
        }
        const result = documents.length === 1
            ? parse(documents[0].text, options)
            : parseDocuments(documents, options);
        if (checkFilesOption) await checkAttachments(result, paths[0], verifyFiles);
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
