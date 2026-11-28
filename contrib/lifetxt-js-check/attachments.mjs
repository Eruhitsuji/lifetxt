import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { open, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { MAX_DIAGNOSTICS, splitAttachmentValue } from './parser.mjs';

async function hashFile(path) {
    const file = await open(path, constants.O_RDONLY | (constants.O_NONBLOCK ?? 0));
    try {
        if (!(await file.stat()).isFile()) throw new Error('Expected a regular file');
        const hash = createHash('sha256');
        const chunk = Buffer.alloc(65536);
        while (true) {
            const { bytesRead } = await file.read(chunk, 0, chunk.length);
            if (!bytesRead) return hash.digest('hex');
            hash.update(chunk.subarray(0, bytesRead));
        }
    } finally {
        await file.close();
    }
}

async function attachmentProblem(value, key, source, verify) {
    const parsed = splitAttachmentValue(value);
    if (parsed === null) return { code: 'attachment-invalid-value' };
    const { path, digest } = parsed;

    let resolved;
    if (path === '~' || path.startsWith('~/')) {
        resolved = resolve(homedir(), path === '~' ? '.' : `.${path.slice(1)}`);
    } else {
        if (process.platform !== 'win32' && /^[A-Za-z]:\//.test(path)) return { code: 'attachment-missing' };
        resolved = resolve(dirname(source), path);
    }
    try {
        const info = await stat(resolved);
        if (info.isDirectory() !== (key === 'dir')) return { code: 'attachment-wrong-type' };
        if (!verify || !digest) return;
        if (key === 'dir') return { code: 'attachment-directory-hash-unsupported', severity: 'unsupported' };
        if (!info.isFile()) return { code: 'attachment-unreadable' };
        const actual = (await hashFile(resolved)).slice(0, digest.length);
        if (actual !== digest) return { code: 'attachment-hash-changed', part: `SHA-256 ${actual}` };
    } catch (error) {
        const code = error.code === 'ENOENT' || error.code === 'ENOTDIR'
            ? 'attachment-missing'
            : 'attachment-unreadable';
        return { code };
    }
}

export async function checkAttachments(result, defaultSource, verify) {
    for (const { details, line, source } of result.items) {
        for (const key of ['file', 'dir']) {
            const values = details.find(([name]) => name === key)?.[1] ?? [];
            for (const value of values) {
                if (typeof value !== 'string') continue;
                const problem = await attachmentProblem(value, key, source ?? defaultSource, verify);
                if (!problem) continue;
                result.incomplete ||= problem.severity === 'unsupported';
                result.diagnosticCount++;
                if (result.diagnostics.length < MAX_DIAGNOSTICS) {
                    result.diagnostics.push({ severity: 'warning', ...problem, line, source, key, value });
                }
            }
        }
    }
}
