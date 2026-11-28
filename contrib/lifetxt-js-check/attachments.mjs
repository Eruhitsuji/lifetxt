import { stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { MAX_DIAGNOSTICS, attachmentPath } from './parser.mjs';

async function attachmentProblem(value, key, source) {
    const path = attachmentPath(value);
    if (path === null) return 'attachment-invalid-value';

    let resolved;
    if (path === '~' || path.startsWith('~/')) {
        resolved = resolve(homedir(), path === '~' ? '.' : `.${path.slice(1)}`);
    } else {
        if (process.platform !== 'win32' && /^[A-Za-z]:\//.test(path)) return 'attachment-missing';
        resolved = resolve(dirname(source), path);
    }
    try {
        const info = await stat(resolved);
        if (info.isDirectory() !== (key === 'dir')) return 'attachment-wrong-type';
    } catch (error) {
        return error.code === 'ENOENT' || error.code === 'ENOTDIR'
            ? 'attachment-missing'
            : 'attachment-unreadable';
    }
}

export async function checkAttachments(result, defaultSource) {
    for (const { details, line, source } of result.items) {
        for (const key of ['file', 'dir']) {
            const values = details.find(([name]) => name === key)?.[1] ?? [];
            for (const value of values) {
                if (typeof value !== 'string') continue;
                const code = await attachmentProblem(value, key, source ?? defaultSource);
                if (code === undefined) continue;
                result.diagnosticCount++;
                if (result.diagnostics.length < MAX_DIAGNOSTICS) {
                    result.diagnostics.push({ severity: 'warning', code, line, source, key, value });
                }
            }
        }
    }
}
